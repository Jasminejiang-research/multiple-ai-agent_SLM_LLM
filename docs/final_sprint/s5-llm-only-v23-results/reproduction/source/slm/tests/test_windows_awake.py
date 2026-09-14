"""Run-scoped requests are acquired and released without changing power plans."""
import pytest

from slm.windows_awake import EXECUTION_REQUIRED, SYSTEM_REQUIRED, WindowsAwake


class API:
    def __init__(self, *, fail=None):
        self.calls, self.fail = [], fail

    def action(self, name, *args):
        self.calls.append((name, *args))
        if self.fail == (name, args[-1] if args else None):
            raise OSError("simulated power API failure")

    def create(self, reason):
        self.action("create", reason)
        return 101

    def set(self, handle, request):
        self.action("set", handle, request)

    def clear(self, handle, request):
        self.action("clear", handle, request)

    def close(self, handle):
        self.action("close", handle)


class Journal:
    def __init__(self):
        self.events = []

    def emit(self, kind, payload):
        self.events.append((kind, payload))


def test_scope_requests_only_system_and_execution_and_releases_in_reverse_order():
    api, journal = API(), Journal()
    with WindowsAwake(api=api, journal=journal):
        assert [call[2] for call in api.calls if call[0] == "set"] == [SYSTEM_REQUIRED, EXECUTION_REQUIRED]
    assert api.calls[-3:] == [("clear", 101, EXECUTION_REQUIRED), ("clear", 101, SYSTEM_REQUIRED), ("close", 101)]
    acquired = next(payload for kind, payload in journal.events if kind == "power_requests_acquired")
    assert acquired["prevents_all_sleep"] is False
    assert any("DC" in item and "five minutes" in item for item in acquired["limitations"])


def test_body_failure_is_preserved_and_requests_still_release():
    api = API()
    with pytest.raises(ValueError, match="generation failure"):
        with WindowsAwake(api=api):
            raise ValueError("generation failure")
    assert api.calls[-1] == ("close", 101)
    assert len([call for call in api.calls if call[0] == "clear"]) == 2


@pytest.mark.parametrize("failed_request,expected_clears", [(SYSTEM_REQUIRED, []), (EXECUTION_REQUIRED, [SYSTEM_REQUIRED])])
def test_partial_acquisition_failure_releases_only_successful_requests(failed_request, expected_clears):
    api = API(fail=("set", failed_request))
    with pytest.raises(OSError, match="simulated"):
        with WindowsAwake(api=api):
            pytest.fail("scope must not run after failed acquisition")
    assert [call[2] for call in api.calls if call[0] == "clear"] == expected_clears
    assert api.calls[-1] == ("close", 101)


def test_create_failure_does_not_clear_an_invalid_handle():
    api = API(fail=("create", "test"))
    with pytest.raises(OSError):
        with WindowsAwake(api=api, reason="test"):
            pass
    assert api.calls == [("create", "test")]


def test_clear_failure_still_clears_other_request_and_closes_handle():
    api = API(fail=("clear", EXECUTION_REQUIRED))
    with pytest.raises(OSError, match="cleanup failed"):
        with WindowsAwake(api=api):
            pass
    assert api.calls[-3:] == [("clear", 101, EXECUTION_REQUIRED), ("clear", 101, SYSTEM_REQUIRED), ("close", 101)]


def test_cleanup_failure_does_not_replace_body_exception():
    api = API(fail=("clear", EXECUTION_REQUIRED))
    with pytest.raises(ValueError, match="original") as raised:
        with WindowsAwake(api=api):
            raise ValueError("original")
    assert any("cleanup" in note for note in raised.value.__notes__)


def test_close_failure_is_not_reported_as_success():
    api, journal = API(fail=("close", 101)), Journal()
    with pytest.raises(OSError, match="cleanup failed"):
        with WindowsAwake(api=api, journal=journal):
            pass
    assert journal.events[-1][1]["status"] == "failed"
