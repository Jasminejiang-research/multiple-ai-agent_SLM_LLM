"""Power-scope failures prevent inference and cannot bypass owned cleanup."""
from types import SimpleNamespace

import pytest

from slm import granite_preflight


@pytest.fixture
def harness(tmp_path, monkeypatch):
    events = []
    state = dict(enter_error=False, exit_error=False, model_error=False, monitor_start_error=False,
        monitor_close_error=False, owner_error=False, owner_unconfirmed=False, model_calls=0)

    class Owner:
        def __init__(self, *args, **kwargs):
            self.proof = None

        def validate(self):
            events.append("owner_validate")

        def stop(self):
            events.append("owner_stop")
            if state["owner_error"]:
                raise OSError("owner cleanup failed")
            self.proof = dict(status="termination_unconfirmed" if state["owner_unconfirmed"] else "owned_process_tree_terminated",
                lease_released=False)
            return self.proof

    class Monitor:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            events.append("monitor_start")
            if state["monitor_start_error"]:
                raise OSError("monitor start failed")

        def close(self):
            events.append("monitor_close")
            if state["monitor_close_error"]:
                raise OSError("monitor cleanup failed")
            return dict(status="passed")

    class Awake:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            events.append("awake_enter")
            if state["enter_error"]:
                raise OSError("power request failed")
            return self

        def __exit__(self, *args):
            events.append("awake_exit")
            assert "monitor_close" in events and "owner_stop" in events
            if state["exit_error"]:
                raise OSError("power cleanup failed")
            return False

    provenance = tmp_path / "provenance.json"
    provenance.write_text("{}")
    monkeypatch.setattr(granite_preflight, "load_context_tokenizer", lambda *args: object())
    monkeypatch.setattr(granite_preflight, "ResourceMonitor", Monitor)
    config = SimpleNamespace(endpoint="http://127.0.0.1:11434", sample_seconds=5, model_dump=lambda **kwargs: {})
    context = SimpleNamespace(case_id="ai_education", packet_sha256="packet", brief_sha256="brief",
        packet=SimpleNamespace(review_status="pending"))
    runner = granite_preflight.GranitePreflight(config=config, context=context, output_dir=tmp_path / "run",
        owner_path="unused", tokenizer_path="unused", tokenizer_provenance=provenance,
        probe=lambda: {}, metadata={}, owner_factory=Owner, awake_factory=Awake)

    def warmup():
        events.append("model_call")
        state["model_calls"] += 1
        assert events.index("awake_enter") < events.index("model_call")
        if state["model_error"]:
            raise ValueError("model failed")
        runner.phases["warmup"] = dict(status="passed")
        return True

    runner.warmup = warmup
    return SimpleNamespace(runner=runner, state=state, events=events)


def test_normal_run_releases_only_after_owned_cleanup(harness):
    result = harness.runner.run("warmup")
    assert result["status"] == "phase_passed"
    assert harness.events[-3:] == ["monitor_close", "owner_stop", "awake_exit"]
    assert harness.events.count("monitor_close") == harness.events.count("owner_stop") == 1


def test_enter_failure_prevents_all_model_calls_and_still_cleans_up(harness):
    harness.state["enter_error"] = True
    result = harness.runner.run("warmup")
    assert result["status"] == "no_go" and result["model_calls"] == 0
    assert harness.state["model_calls"] == 0
    assert "monitor_start" not in harness.events and "awake_exit" not in harness.events
    assert harness.events[-2:] == ["monitor_close", "owner_stop"]
    assert result["phases"]["warmup"]["status"] == "not_run"
    assert result["phases"]["power_scope"]["status"] == "failed"


def test_existing_cancellation_cannot_report_success_with_unrun_phases(harness):
    harness.runner.cancel.set()
    result = harness.runner.run("warmup")
    assert result["status"] == "no_go"
    assert result["phases"]["warmup"]["status"] == "not_run"
    assert harness.state["model_calls"] == 0
    assert harness.events[-3:] == ["monitor_close", "owner_stop", "awake_exit"]


@pytest.mark.parametrize("failure,phase", [
    ("exit_error", "power_scope"), ("model_error", "unexpected_stop"),
    ("monitor_start_error", "unexpected_stop"), ("monitor_close_error", "resource_cleanup"),
    ("owner_error", "server_cleanup"), ("owner_unconfirmed", "server_cleanup"),
])
def test_failures_never_pass_and_all_cleanup_paths_are_attempted(harness, failure, phase):
    harness.state[failure] = True
    result = harness.runner.run("warmup")
    assert result["status"] == "no_go"
    assert result["phases"][phase]["status"] == "failed"
    assert harness.events[-3:] == ["monitor_close", "owner_stop", "awake_exit"]
    assert harness.events.count("monitor_close") == harness.events.count("owner_stop") == 1
    assert harness.runner.cancel.is_set()
