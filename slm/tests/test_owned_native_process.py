"""Bound identity survives independent cleanup; ambiguous PIDs are never killed."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from slm import owned_ollama
from slm.windows_process import NativeProcessHandle


class Journal:
    def __init__(self):
        self.events = []

    def emit(self, kind, payload):
        self.events.append((kind, payload))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    path = tmp_path / "owner.json"
    path.write_text(json.dumps(dict(endpoint="http://127.0.0.1:11434", num_parallel=1,
        max_loaded_models=1, context_length=32768, pid=4242, started_at_utc="2026-09-07T09:00:00Z")))
    process = dict(Name="ollama.exe", CommandLine="ollama serve", CreatedUtc="2026-09-07T09:00:00Z", ListenerPids=[4242])
    delta = datetime(2026, 9, 7, 9, tzinfo=timezone.utc) - datetime(1601, 1, 1, tzinfo=timezone.utc)
    identity = dict(pid=4242, creation_filetime=(delta.days * 86400 + delta.seconds) * 10000000,
        image_path="C:\\Apps\\Ollama\\ollama.exe")
    state = dict(exited=False, identity=identity.copy(), taskkill_error=None, exits_after_kill=True)
    calls, handles = [], []

    class Handle:
        def __init__(self, pid):
            assert pid == 4242
            self.closed, self.waits = False, []
            handles.append(self)

        def identity(self):
            return state["identity"].copy()

        def wait_exited(self, timeout_ms):
            self.waits.append(timeout_ms)
            return state["exited"]

        def close(self):
            self.closed = True

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == "taskkill":
            if state["taskkill_error"]:
                raise state["taskkill_error"]
            state["exited"] = state["exits_after_kill"]
            return SimpleNamespace(stdout="terminated")
        return SimpleNamespace(stdout=json.dumps(process))

    monkeypatch.setattr(owned_ollama, "NativeProcessHandle", Handle)
    monkeypatch.setattr(owned_ollama, "hidden_run", run)
    return SimpleNamespace(path=path, process=process, state=state, calls=calls, handles=handles,
        create=lambda: owned_ollama.OwnedOllama(path, journal=Journal(), endpoint="http://127.0.0.1:11434"))


def test_verified_native_stop_has_no_cim_under_load_and_is_idempotent(setup):
    owner = setup.create()
    original = setup.path.read_bytes()
    owner.validate()
    assert owner.identity_path.exists()
    result = owner.stop()
    assert result["status"] == "owned_process_tree_terminated"
    assert result["identity_method"] == "native_handle_and_persisted_identity"
    assert result["lease_released"] is False
    assert setup.handles[0].closed
    assert setup.handles[0].waits[-1] == 2000
    assert len(setup.calls) == 2
    assert setup.calls[1] == (["taskkill", "/PID", "4242", "/T", "/F"], {"timeout": 10})
    assert owner.stop() == result and len(setup.calls) == 2
    assert setup.path.read_bytes() == original


def test_independent_cleanup_restores_exact_persisted_identity(setup):
    initial = setup.create()
    initial.validate()
    initial.native_process.close()
    restored = setup.create()
    assert restored.native_process is None
    assert restored.stop()["status"] == "owned_process_tree_terminated"
    assert len(setup.calls) == 2  # initial startup CIM + recovery taskkill only
    assert len(setup.handles) == 2


@pytest.mark.parametrize("change", ["pid", "creation_filetime", "image_path"])
def test_recovery_refuses_identity_changes_without_taskkill(setup, change):
    setup.create().validate()
    setup.state["identity"][change] = "C:\\Other\\ollama.exe" if change == "image_path" else setup.state["identity"][change] + 1
    result = setup.create().stop()
    assert result["status"] == "termination_unconfirmed"
    assert result["lease_released"] is False
    assert len(setup.calls) == 1
    assert setup.handles[-1].closed


def test_recovery_refuses_modified_owner_or_malformed_evidence(setup):
    owner = setup.create()
    owner.validate()
    setup.path.write_text(setup.path.read_text() + "\n")
    assert setup.create().stop()["status"] == "termination_unconfirmed"
    owner.identity_path.write_text("{broken")
    assert setup.create().stop()["status"] == "termination_unconfirmed"
    assert len(setup.calls) == 1


def test_startup_requires_original_listener_and_commandline_checks(setup):
    setup.process["ListenerPids"] = [1234]
    with pytest.raises(ValueError, match="listener"):
        setup.create().validate()
    assert not setup.handles
    setup.process["ListenerPids"] = [4242]
    setup.process["CommandLine"] = "ollama run"
    with pytest.raises(ValueError, match="serve"):
        setup.create().validate()
    assert not setup.handles


def test_startup_native_identity_must_match_cim_creation_exactly(setup):
    setup.state["identity"]["creation_filetime"] += 10000000
    owner = setup.create()
    with pytest.raises(ValueError, match="creation time"):
        owner.validate()
    assert setup.handles[0].closed
    assert owner.stop()["status"] == "termination_unconfirmed"
    assert len(setup.calls) == 1


@pytest.mark.parametrize("failure", ["taskkill", "wait"])
def test_native_stop_failure_never_claims_termination_or_releases_lease(setup, failure):
    owner = setup.create()
    owner.validate()
    if failure == "taskkill":
        setup.state["taskkill_error"] = TimeoutError("taskkill timeout")
    else:
        setup.state["exits_after_kill"] = False
    result = owner.stop()
    assert result["status"] == "termination_unconfirmed" and not result["lease_released"]
    assert not owner.stopped
    assert not setup.handles[0].closed  # keep PID binding while termination is unresolved


def test_recovery_absent_process_is_not_inferred_as_clean_tree(setup):
    setup.create().validate()
    setup.state["exited"] = True
    assert setup.create().stop()["status"] == "termination_unconfirmed"
    assert len(setup.calls) == 1


@pytest.mark.skipif(os.name != "nt", reason="requires native Windows process API")
def test_native_current_process_read_only_smoke():
    handle = NativeProcessHandle(os.getpid())
    try:
        identity = handle.identity()
        assert identity["pid"] == os.getpid()
        assert identity["creation_filetime"] > 0
        assert Path(identity["image_path"]).name.lower().startswith("python")
        assert Path(identity["image_path"]).suffix.lower() == ".exe"
        assert handle.wait_exited(0) is False
        with pytest.raises(ValueError, match="bounded"):
            handle.wait_exited(10001)
    finally:
        handle.close()
    handle.close()
