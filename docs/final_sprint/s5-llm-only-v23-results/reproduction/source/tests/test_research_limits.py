"""Offline controller tests: no model/network calls or real-time waits."""
import json

import pytest
from pydantic import BaseModel

from workflow.llm_client import StructuredOutputValidationError
from workflow.research_limits import (RESEARCH_PROFILE_VERSION, RESEARCH_TOTAL_SECONDS,
                                      RESEARCH_OUTPUT_CAPS)
from workflow.review_config import ReviewRunConfig
from workflow.review_events import EventJournal, replay_events
from workflow.review_runtime import BoundedClient, PhysicalResponse, ProviderFailure, WallClockExceeded
from workflow.run_budget import RunBudgetExceededError


class Ack(BaseModel):
    ok: bool


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class FakeProvider:
    provider = "mock"
    model_exact_id = "synthetic-only"

    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.duration = 0
        self.response = PhysicalResponse('{"ok":true}', {}, 10, 5, 15, "stop")
        self.fail_once = None

    def invoke(self, request):
        self.calls.append(request)
        self.clock.now += self.duration
        if self.fail_once:
            error, self.fail_once = self.fail_once, None
            raise error
        return self.response


def make_client(tmp_path, **overrides):
    clock = FakeClock()
    provider = FakeProvider(clock)
    settings = dict(condition="D", run_kind="debug", provider="mock",
        model_exact_id=provider.model_exact_id, model_config_version="synthetic-only",
        max_requests=36, max_total_tokens=1_000_000, max_output_tokens=8192,
        max_prompt_chars=10000, node_seconds=1200, request_seconds=1200, run_seconds=5400)
    settings.update(overrides)
    config = ReviewRunConfig(**settings)
    journal = EventJournal(tmp_path / "events", "synthetic-research")
    return BoundedClient(provider, config, journal, clock=clock), provider, clock


def generate(client, *, role="research", stage="body", purpose="generate", task_purpose=None):
    metadata = dict(logical_task_id="research.synthetic", role=role, artifact_version=1,
        schema_sha256="synthetic", packet_sha256="synthetic", batch_number=None,
        generation_stage=stage, purpose=purpose,
        task_purpose=task_purpose or ("generate" if purpose == "structure_repair" else purpose))
    with client.attempt_scope(**metadata):
        return client.generate_structured_once("hello", Ack, system_instruction="system")


def attempts(client):
    return replay_events(client.journal.path)["attempts"]


@pytest.mark.parametrize("global_cap", [8192, 512])
@pytest.mark.parametrize("stage,stage_cap", [("body", 640), ("grounding", 2304), ("single", 2304)])
@pytest.mark.parametrize("purpose", ["generate", "revision", "structure_repair"])
def test_each_research_physical_request_uses_lower_stage_and_global_cap(tmp_path, global_cap, stage, stage_cap, purpose):
    client, provider, clock = make_client(tmp_path, max_output_tokens=global_cap)
    client.begin_node("research")
    generate(client, stage=stage, purpose=purpose)
    effective = min(global_cap, stage_cap)
    assert provider.calls[0].max_output_tokens == effective
    event = attempts(client)[0]
    expected_estimate = len(("hellosystem" + json.dumps(Ack.model_json_schema(), ensure_ascii=False)).encode("utf-8")) + effective
    assert event["reservation_tokens"] == expected_estimate
    for snapshot in (event["budget_before"], event["budget_after"]):
        assert snapshot["effective_max_output_tokens"] == effective
        assert snapshot["configured_max_output_tokens"] == global_cap
        assert snapshot["research_profile_version"] == RESEARCH_PROFILE_VERSION
        assert snapshot["effective_deadline_run_elapsed_seconds"] == 1200


@pytest.mark.parametrize("role,purpose,task_purpose", [
    ("research_critic", "critic", "critic"),
    ("research_critic", "structure_repair", "critic"),
    ("research", "critic", "critic"),
    ("strategy", "generate", "generate"),
    ("finance", "revision", "revision"),
    ("writer", "structure_repair", "generate"),
    ("single", "generate", "generate"),
])
def test_critic_and_other_roles_keep_the_global_output_cap(tmp_path, role, purpose, task_purpose):
    client, provider, clock = make_client(tmp_path)
    client.begin_node("research" if "critic" in role else role)
    generate(client, role=role, purpose=purpose, task_purpose=task_purpose)
    assert provider.calls[0].max_output_tokens == 8192


def test_repair_critic_and_revision_share_one_research_deadline(tmp_path):
    client, provider, clock = make_client(tmp_path)
    client.begin_node("research")
    provider.duration = 200
    provider.response = PhysicalResponse("invalid", {}, 10, 5, 15)
    with pytest.raises(StructuredOutputValidationError):
        generate(client)
    provider.response = PhysicalResponse('{"ok":true}', {}, 10, 5, 15)
    for duration, metadata in [
        (100, dict(purpose="structure_repair")),
        (300, dict(stage="grounding")),
        (300, dict(role="research_critic", purpose="critic", stage="single")),
        (200, dict(purpose="revision")),
    ]:
        provider.duration = duration
        generate(client, **metadata)
    assert client.snapshot()["node_elapsed_seconds"] == 1100
    assert [request.timeout_seconds for request in provider.calls] == [1200, 1000, 900, 600, 300]
    assert [request.max_output_tokens for request in provider.calls] == [640, 640, 2304, 8192, 640]
    assert {event["budget_before"]["node_deadline_run_elapsed_seconds"] for event in attempts(client)} == {1200}
    with pytest.raises(RuntimeError, match="cannot reset"):
        client.begin_node("research")
    provider.duration = 150
    with pytest.raises(WallClockExceeded):
        generate(client, stage="grounding", purpose="structure_repair", task_purpose="revision")
    assert provider.calls[-1].timeout_seconds == 100
    assert provider.calls[-1].max_output_tokens == 2304
    with pytest.raises(WallClockExceeded):
        generate(client, purpose="revision")
    assert len(provider.calls) == 6
    client.end_node("timeout")
    assert client.journal.events[-1]["payload"]["budget"]["node_elapsed_seconds"] == 1250


@pytest.mark.parametrize("limits,expected", [
    (dict(node_seconds=80), 80), (dict(run_seconds=30), 30), (dict(request_seconds=20), 20),
])
def test_research_never_raises_existing_lower_time_limits(tmp_path, limits, expected):
    client, provider, clock = make_client(tmp_path, **limits)
    client.begin_node("research")
    generate(client)
    assert provider.calls[0].timeout_seconds == expected


def test_research_cap_is_independent_of_larger_trial_node_override(tmp_path):
    client, provider, clock = make_client(tmp_path)
    # Trial helpers can already hold independently validated, larger node limits.
    client.config = client.config.model_copy(update={"node_seconds": 3600})
    clock.now += 100
    client.begin_node("research")
    assert client.check() == RESEARCH_TOTAL_SECONDS
    assert client.snapshot()["node_deadline_run_elapsed_seconds"] == 1300
    clock.now += 1200
    with pytest.raises(WallClockExceeded):
        generate(client)
    assert not provider.calls
    client.end_node("timeout")
    client.begin_node("strategy")
    assert client.check() == 3600
    assert client.snapshot()["node_deadline_run_elapsed_seconds"] == 4900


def test_transport_retry_keeps_cap_and_elapsed_time(tmp_path):
    client, provider, clock = make_client(tmp_path, transport_retries=1)
    client.begin_node("research")
    provider.duration = 200
    provider.fail_once = ProviderFailure("Synthetic503", retryable=True, request_finished=True)
    generate(client, stage="grounding", purpose="revision")
    assert [request.max_output_tokens for request in provider.calls] == [2304, 2304]
    assert [request.timeout_seconds for request in provider.calls] == [1200, 1000]
    first, retry = attempts(client)
    assert retry["transport_retry_of"] == first["attempt_id"]
    assert first["budget_token_charge"] == first["reservation_tokens"]
    assert client.snapshot()["node_elapsed_seconds"] == 400


def test_unknown_usage_retains_effective_reservation_without_resetting_shared_budget(tmp_path):
    schema_bytes = len(("hellosystem" + json.dumps(Ack.model_json_schema(), ensure_ascii=False)).encode("utf-8"))
    reservation = schema_bytes + RESEARCH_OUTPUT_CAPS["body"]
    client, provider, clock = make_client(tmp_path, max_total_tokens=reservation)
    client.begin_node("research")
    provider.response = PhysicalResponse('{"ok":true}')
    generate(client)
    with pytest.raises(RunBudgetExceededError):
        generate(client, stage="grounding", purpose="revision")
    assert len(provider.calls) == 1
    snapshot = client.snapshot()
    assert snapshot["charged_total_tokens"] == reservation
    assert snapshot["actual_total_tokens_known"] == 0
    assert snapshot["usage_missing_calls"] == 1
