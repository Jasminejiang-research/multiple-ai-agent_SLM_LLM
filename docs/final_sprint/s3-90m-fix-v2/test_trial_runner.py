"""Helper-only offline approval, accounting, cleanup and completion guards."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import trial_runner as runner


@pytest.fixture
def config():
    return runner.RecoveryConfig.model_validate(runner.read_json(runner.ROOT / "trial_config.json"))


@pytest.fixture
def authorization(config):
    record = deepcopy(runner.read_json(runner.ROOT / "authorization.json"))
    record["approved"] = True  # Test-only object; never changes authorization.json.
    record["approved_limits"] = {key: getattr(config, key) for key in (
        "run_seconds", "node_seconds", "request_seconds", "max_output_tokens", "max_requests",
        "max_total_tokens", "max_prompt_chars")}
    return record


def history_file(tmp_path, **changes):
    budget = dict(cumulative_request_count=19, cumulative_charged_total_tokens=327001,
        cumulative_elapsed_seconds=10193.483)
    budget.update(changes)
    path = tmp_path / "old_result.json"
    path.write_text(json.dumps(dict(case_id="ai_education", formal_eligible=False, budget=budget,
        unknown_response=dict(actual_usage=None, retained_budget_reservation=114777))), encoding="utf-8")
    return dict(result_path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_pending_authorization_rejects_before_owner_power_provider_or_model(tmp_path, monkeypatch, config, authorization):
    authorization["approved"] = False
    touched = []
    def forbidden(*args, **kwargs):
        touched.append(True)
        pytest.fail("A runtime dependency was touched before approval")
    for name in ("OwnedOllama", "WindowsAwake", "ContextCheckedProvider", "inspect_ollama", "Timer", "EventJournal"):
        monkeypatch.setattr(runner, name, forbidden)
    with pytest.raises(ValueError, match="pending explicit approval"):
        runner.execute(config, authorization, {}, shared_repo=tmp_path, output=tmp_path / "run",
            owner_path="unused", tokenizer_path="unused", tokenizer_provenance="unused")
    assert not touched and not (tmp_path / "run").exists()


@pytest.mark.parametrize("field", ["run_seconds", "node_seconds", "request_seconds"])
def test_each_time_budget_rejects_more_than_5400(config, field):
    with pytest.raises(ValidationError):
        runner.RecoveryConfig.model_validate({**config.model_dump(), field: 5400.001})


def test_approved_limits_must_exactly_match_config(config, authorization):
    authorization["approved_limits"]["max_requests"] += 1
    with pytest.raises(ValueError, match="differs"):
        runner.validate_authorization(config, authorization)


def test_historical_hash_and_unknown_usage_reservation_are_preserved(tmp_path):
    record = history_file(tmp_path)
    original = Path(record["result_path"]).read_bytes()
    history = runner.verified_history(record)
    assert history == dict(request_count=19, charged_total_tokens=327001, elapsed_seconds=10193.483)
    assert Path(record["result_path"]).read_bytes() == original
    with pytest.raises(ValueError, match="hash mismatch"):
        runner.verified_history({**record, "sha256": "0" * 64})


@pytest.mark.parametrize("changes", [
    {"cumulative_request_count": -1}, {"cumulative_request_count": True},
    {"cumulative_charged_total_tokens": -1}, {"cumulative_charged_total_tokens": 1.5},
    {"cumulative_elapsed_seconds": -1}, {"cumulative_elapsed_seconds": float("nan")},
    {"cumulative_elapsed_seconds": float("inf")}, {"cumulative_elapsed_seconds": True},
])
def test_historical_consumption_is_finite_nonnegative_and_correctly_typed(tmp_path, changes):
    with pytest.raises(ValueError, match="Invalid historical consumption"):
        runner.verified_history(history_file(tmp_path, **changes))


@pytest.fixture
def harness(tmp_path, monkeypatch, config, authorization):
    events, clock = [], [0.0]
    history_record = history_file(tmp_path)
    history = runner.verified_history(history_record)
    old_bytes = Path(history_record["result_path"]).read_bytes()
    state = dict(power_enter_error=False, power_exit_error=False, monitor_close_error=False,
        owner_stop_error=False, owner_unconfirmed=False, resource_gap=False, fire_deadline=False,
        late_without_timer=False, bad_model=False, bad_placement=False, artifact=True,
        model_calls=0, timer=None, workflow_config=None, provider=None)
    monkeypatch.setattr(runner, "monotonic", lambda: clock[0])

    class Owner:
        def __init__(self, *args, **kwargs):
            events.append("owner_created")

        def validate(self):
            events.append("owner_validated")

        def stop(self):
            events.append("owner_stop")
            if state["owner_stop_error"]:
                raise OSError("owner stop failed")
            return dict(status="termination_unconfirmed" if state["owner_unconfirmed"] else "owned_process_tree_terminated",
                lease_released=False)

    class Timer:
        def __init__(self, seconds, callback):
            assert 0 <= seconds <= 5400
            self.callback = callback
            state["timer"] = self

        def start(self):
            events.append("timer_start")

        def cancel(self):
            events.append("timer_cancel")

    class Awake:
        def __init__(self, **kwargs):
            events.append("power_created")

        def __enter__(self):
            events.append("power_enter")
            if state["power_enter_error"]:
                raise OSError("power enter failed")
            return self

        def __exit__(self, *args):
            events.append("power_exit")
            if state["power_exit_error"]:
                raise OSError("power exit failed")
            return False

    class Monitor:
        def __init__(self, probe, *args, **kwargs):
            events.append("monitor_created")
            probe()

        def start(self):
            events.append("monitor_start")

        def close(self):
            events.append("monitor_close")
            if state["monitor_close_error"]:
                raise OSError("monitor close failed")
            return dict(status="failed" if state["resource_gap"] else "passed",
                reason="resource_observation_gap" if state["resource_gap"] else None)

    class Provider:
        def __init__(self, *args, **kwargs):
            events.append("provider_created")
            self.http_requests = 0
            state["provider"] = self

    class Context:
        packet_sha256, brief_sha256 = "packet", "brief"

        @classmethod
        def from_case(cls, *args, **kwargs):
            assert args[1] == "ai_education" and kwargs["condition"] == "D"
            events.append("context_verified")
            return cls()

        def verify_artifact(self, artifact):
            events.append("artifact_verified")

        def export(self, artifact, path):
            events.append("artifact_exported")
            path.mkdir(parents=True)

    def metadata(config):
        events.append("metadata_checked")
        return dict(model_digest="wrong" if state["bad_model"] else authorization["expected_model_digest"],
            ollama_version=authorization["expected_ollama_version"])

    def probe_factory(**kwargs):
        return lambda: dict(loaded_models=[dict(name=config.model_alias, context_length=32768,
            size_vram=1 if state["bad_placement"] else 0)])

    def build(context, **kwargs):
        events.append("workflow_built")
        state["workflow_config"] = kwargs["config"]
        directory = kwargs["output_dir"]
        directory.mkdir(parents=True)
        budget = dict(request_count=2, charged_total_tokens=8200, actual_total_tokens_known=8,
            usage_missing_calls=1, token_counter_basis="budget_charge_actual_or_retained_estimate")
        workflow = SimpleNamespace(journal=SimpleNamespace(directory=directory),
            client=SimpleNamespace(snapshot=lambda: deepcopy(budget)),
            artifacts={"writer.effective": object()} if state["artifact"] else {})
        def run():
            events.append("workflow_run")
            state["model_calls"] += 1
            kwargs["provider"].http_requests += 2
            clock[0] += 10
            if state["fire_deadline"] or state["late_without_timer"]:
                clock[0] = 5400
            if state["fire_deadline"]:
                state["timer"].callback()
            return dict(status="completed")
        workflow.run = run
        return workflow

    for name, value in dict(OwnedOllama=Owner, Timer=Timer, WindowsAwake=Awake, ResourceMonitor=Monitor,
        ContextCheckedProvider=Provider, ContractContext=Context, inspect_ollama=metadata,
        WindowsResourceProbe=probe_factory, build_slm_review_workflow=build,
        LocalRequestLease=lambda *args, **kwargs: object(), load_context_tokenizer=lambda *args: object()).items():
        monkeypatch.setattr(runner, name, value)

    def execute():
        return runner.execute(config, authorization, history, shared_repo=tmp_path, output=tmp_path / "run",
            owner_path="unused", tokenizer_path="unused", tokenizer_provenance="unused")
    return SimpleNamespace(execute=execute, events=events, state=state, history=history, history_record=history_record,
        old_bytes=old_bytes, output=tmp_path / "run", config=config)


def test_mock_complete_d_requires_guards_export_and_all_cleanup(harness):
    result = harness.execute()
    assert result["complete_d_passed"] is True and result["status"] == "completed"
    assert result["complete_proposal_produced"] is True and result["http_requests"] == 2
    assert result["within_deadline"] is True and result["per_plan_deadline_seconds"] == 5400
    assert harness.events.index("power_enter") < harness.events.index("workflow_run")
    assert all(name in harness.events for name in ("owner_validated", "metadata_checked", "context_verified", "artifact_verified", "artifact_exported"))
    assert harness.events[-4:] == ["timer_cancel", "monitor_close", "owner_stop", "power_exit"]
    assert result["power_cleanup"] == "released"
    assert result["server_stop"]["status"] == "owned_process_tree_terminated"
    assert result["formal_runs_started"] == result["gemini_calls"] == 0
    assert result["formal_eligible"] is False and result["public_config_changed"] is False
    assert json.loads((harness.output / "result.json").read_text(encoding="utf-8"))["complete_d_passed"] is True
    budget = result["budget"]
    assert budget["cumulative_charged_total_tokens"] == 327001 + 8200
    assert budget["per_plan_budget"]["actual_total_tokens_known"] == 8
    assert budget["per_plan_budget"]["usage_missing_calls"] == 1
    assert budget["cumulative_request_count"] == 21
    assert budget["cumulative_elapsed_seconds"] == pytest.approx(10203.483)
    assert result["historical_consumption"] == harness.history
    assert Path(harness.history_record["result_path"]).read_bytes() == harness.old_bytes
    assert all(getattr(harness.state["workflow_config"], field) <= 5400 for field in ("run_seconds", "node_seconds", "request_seconds"))


def test_power_entry_failure_has_zero_http_and_still_stops_owner(harness):
    harness.state["power_enter_error"] = True
    result = harness.execute()
    assert result["complete_d_passed"] is False and result["http_requests"] == 0
    assert result["power_cleanup"] == "not_acquired"
    assert "provider_created" not in harness.events and "metadata_checked" not in harness.events
    assert "owner_stop" in harness.events and "timer_cancel" in harness.events
    assert result["budget"]["this_run_charged_total_tokens"] == 0


@pytest.mark.parametrize("failure", ["power_exit_error", "monitor_close_error", "owner_stop_error", "owner_unconfirmed"])
def test_cleanup_failures_never_pass_and_remaining_cleanup_is_attempted(harness, failure):
    harness.state[failure] = True
    result = harness.execute()
    assert result["complete_d_passed"] is False
    assert result["status"] != "completed"
    assert harness.events[-4:] == ["timer_cancel", "monitor_close", "owner_stop", "power_exit"]
    assert (harness.output / "result.json").exists()


@pytest.mark.parametrize("failure,expected", [("resource_gap", "resource_stopped"), ("fire_deadline", "timeout"), ("late_without_timer", "timeout")])
def test_resource_gap_or_either_deadline_signal_overrides_completed_workflow(harness, failure, expected):
    harness.state[failure] = True
    result = harness.execute()
    assert result["phases"]["full_d"]["status"] == "completed"
    assert result["status"] == expected and result["complete_d_passed"] is False
    assert "power_exit" in harness.events and "owner_stop" in harness.events


@pytest.mark.parametrize("failure", ["bad_model", "bad_placement"])
def test_model_or_cpu_placement_mismatch_prevents_http(harness, failure):
    harness.state[failure] = True
    result = harness.execute()
    assert result["http_requests"] == 0 and result["complete_d_passed"] is False
    assert "workflow_run" not in harness.events
    assert harness.events[-1] == "power_exit"


def test_completed_workflow_without_complete_artifact_does_not_pass(harness):
    harness.state["artifact"] = False
    result = harness.execute()
    assert result["status"] == "completed"
    assert result["complete_proposal_produced"] is False and result["complete_d_passed"] is False
