"""S2 offline engineering tests; synthetic calls are not experiment/quality evidence."""
from copy import deepcopy
import json
from pathlib import Path
from threading import Event
import time

import pytest

from evaluation.s2_fixtures import SyntheticProvider, synthetic_report, request_payload
from schemas.review import ComponentCritiqueReport, METRICS
from workflow.contract_context import ContractContext
from workflow.grounding import claims_in
from workflow.review_config import ReviewRunConfig
from workflow.review_events import EventJournal, replay_events
from workflow.review_graph import build_review_workflow
from workflow.review_runtime import PhysicalResponse, ProviderFailure, LocalRequestLease

ROOT = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"


def setup_run(tmp_path, *, condition="C", fail_roles=(), severity="high", score=3, before=None,
              overrides=None, provider_kind=None, **kwargs):
    ctx = ContractContext.from_case(ROOT, "ai_education", condition=condition)
    provider = SyntheticProvider(ctx, fail_roles=fail_roles, severity=severity, score=score, before=before)
    if provider_kind:
        provider.provider = provider_kind
    data = dict(condition=condition, run_kind="debug", provider=provider.provider,
        model_exact_id=provider.model_exact_id, model_config_version="synthetic-only-v1",
        max_requests=64, max_total_tokens=20_000_000, max_output_tokens=1024,
        max_prompt_chars=1_000_000, request_seconds=10)
    data.update(overrides or {})
    config = ReviewRunConfig(**data)
    workflow = build_review_workflow(ctx, config=config, provider=provider, output_dir=tmp_path / "run", **kwargs)
    return workflow, provider


def calls(workflow):
    return replay_events(workflow.journal.path)["attempts"]


@pytest.mark.parametrize("role", METRICS)
@pytest.mark.parametrize("score,expected", [(0, 0), (1, 2.5), (2, 5), (3, 7.5), (4, 10)])
def test_score_is_computed_on_fixed_scale(role, score, expected):
    report = ComponentCritiqueReport.model_validate(synthetic_report(role, score=score))
    assert report.overall_score == expected
    assert report.revision_required == (expected < 7)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unknown", "negative", "too_high", "float", "bool", "string", "overall", "issue_duplicate", "issue_version"])
def test_review_rejects_bad_or_legacy_scores(mutation):
    data = synthetic_report("research", severity="high")
    if mutation == "missing": data["metrics"].pop()
    if mutation == "duplicate": data["metrics"][0] = deepcopy(data["metrics"][1])
    if mutation == "unknown": data["metrics"][0]["criterion"] = "invented"
    if mutation == "overall": data["overall_score"] = 10
    if mutation == "issue_duplicate": data["issues"] *= 2
    if mutation == "issue_version": data["issues"][0]["artifact_version"] = 2
    bad = {"negative": -1, "too_high": 5, "float": 3.5, "bool": True, "string": "3"}
    if mutation in bad: data["metrics"][0]["score"] = bad[mutation]
    with pytest.raises(ValueError): ComponentCritiqueReport.model_validate(data)


@pytest.mark.parametrize("condition,expected_calls,reviewed", [("A", 8, ()), ("B", 15, ("final",)),
    ("C", 18, ("research", "strategy", "finance", "final")), ("D", 18, ("research", "strategy", "finance", "final"))])
def test_pass_routes_skip_every_revision(tmp_path, condition, expected_calls, reviewed):
    workflow, provider = setup_run(tmp_path, condition=condition)
    result = workflow.run()
    assert result["status"] == "completed", result["error"]
    assert len(provider.calls) == expected_calls == len(calls(workflow))
    assert result["branches"] == {r: "skip_revision" for r in reviewed}
    assert all(h["status"] == "succeeded" for h in result["handoffs"])
    assert all(ref["artifact_version"] == 1 for ref in result["effective_artifacts"].values())
    assert result["terminal_contract_passed"] and not result["external_ready"]
    assert not any(c["task_purpose"] == "revision" for c in calls(workflow))
    assert all(workflow.artifacts[f"{r}.initial"].sha256 == workflow.artifacts[f"{r}.effective"].sha256 for r in workflow.roles)
    assert len({c["node_scope_id"] for c in calls(workflow)}) == (1 if condition == "A" else 4)
    assert len((workflow.journal.directory / "internal_export/proposal.md").read_text(encoding="utf-8").split("\n\n## ")) == 14


@pytest.mark.parametrize("condition", ["C", "D"])
@pytest.mark.parametrize("role", METRICS)
@pytest.mark.parametrize("severity,score", [(None, 2), ("high", 4), ("critical", 4)])
def test_fail_routes_revise_once_and_keep_semantic_state(tmp_path, condition, role, severity, score):
    workflow, provider = setup_run(tmp_path, condition=condition, fail_roles=[role], severity=severity, score=score)
    result = workflow.run()
    assert result["status"] == "completed", result["error"]
    gen_role = "writer" if role == "final" else role
    assert result["effective_artifacts"][gen_role]["artifact_version"] == 2
    gate = result["gates"][gen_role]
    assert gate["revision_count"] == 1 and gate["semantic_verification_status"] == "unverified_after_revision"
    assert sum(c["task_purpose"] == "critic" for c in calls(workflow)) == 4
    revisions = [c for c in calls(workflow) if c["task_purpose"] == "revision"]
    assert len(revisions) == (8 if role == "final" else 2)
    assert all(c["role"] == "Revision" and c["purpose"] == "revision" for c in revisions)
    assert result["blocking"] == (severity == "critical")
    assert all(i["status"] == "unverified_after_revision" for i in result["issues"])
    assert all(h["status"] == "succeeded" for h in result["handoffs"])
    if severity:
        final = workflow.artifacts["writer.effective"]
        assert final.unresolved_major and result["needs_human_review"]
        assert all(c.critic_status == "unverified_after_revision" and c.confidence == "low" for c in claims_in(final.payload()))
    if role != "final":
        for req in provider.calls:
            payload = request_payload(req.prompt)
            for upstream in payload.get("upstream_artifacts", []):
                if upstream["role"] == gen_role and not issubclass(req.schema, ComponentCritiqueReport):
                    assert upstream["artifact_version"] == 2


def test_b_final_failure_and_all_c_failures(tmp_path):
    for condition in ("B", "C"):
        workflow, provider = setup_run(tmp_path / condition, condition=condition,
            fail_roles=METRICS, severity="critical")
        result = workflow.run()
        assert result["status"] == "completed", result["error"]
        assert len(provider.calls) == (23 if condition == "B" else 32)
        assert all(g["revision_count"] == 1 for g in result["gates"].values())
        assert result["blocking"] and not result["external_ready"]


@pytest.mark.parametrize("role", METRICS)
def test_gate_does_not_accept_second_review(role):
    report = ComponentCritiqueReport.model_validate(synthetic_report(role, score=1))
    with pytest.raises(ValueError, match="second"): report.gate(revision_count=1)


@pytest.mark.parametrize("condition", ["B", "C", "D"])
def test_budget_exhaustion_retains_expected_missing_handoffs(tmp_path, condition):
    workflow, provider = setup_run(tmp_path, condition=condition, overrides={"max_requests": 1})
    base_ids = set(workflow.handoffs.rows)
    result = workflow.run()
    assert result["status"] == "budget_exhausted"
    assert len(provider.calls) == len(calls(workflow)) == result["budget"]["request_count"] == 1
    assert base_ids <= {h["handoff_id"] for h in result["handoffs"]}
    assert any(h["status"] == "missing" for h in result["handoffs"])
    assert "unknown" in result["branches"].values()


@pytest.mark.parametrize("role,limit", [("research", 3), ("strategy", 6), ("finance", 9), ("final", 18)])
def test_revision_cannot_reset_request_budget(tmp_path, role, limit):
    workflow, provider = setup_run(tmp_path, fail_roles=[role], overrides={"max_requests": limit})
    result = workflow.run()
    assert result["status"] == "budget_exhausted"
    gen_role = "writer" if role == "final" else role
    assert result["gates"][gen_role]["revision_count"] == 1
    assert result["gates"][gen_role]["decision"] == "stop_budget"
    assert len(provider.calls) == limit
    assert f"{gen_role}.effective" not in workflow.artifacts


def test_one_structure_repair_keeps_logical_task_and_first_failure(tmp_path):
    def bad_first(req, index):
        if index == 1: return PhysicalResponse("{broken", None)
    workflow, provider = setup_run(tmp_path, before=bad_first)
    result = workflow.run()
    assert result["status"] == "completed", result["error"]
    first, repair = calls(workflow)[:2]
    assert first["logical_task_id"] == repair["logical_task_id"]
    assert first["attempt_id"] != repair["attempt_id"]
    assert first["status"] == "invalid_output" and repair["purpose"] == "structure_repair"
    assert first["total_tokens"] is None and first["usage_missing_reason"]
    assert first["budget_token_charge"] == first["reservation_tokens"]
    assert workflow.generator.tasks[0].first_output_passed is False
    assert result["budget"]["usage_missing_calls"] == 1


def test_second_bad_structure_stops_without_third_attempt(tmp_path):
    workflow, provider = setup_run(tmp_path, before=lambda req, index: PhysicalResponse("{}"))
    result = workflow.run()
    assert result["status"] == "failed" and len(provider.calls) == 2
    assert len({c["logical_task_id"] for c in calls(workflow)}) == 1


def test_transport_retry_is_a_physical_attempt_not_structure_repair(tmp_path):
    def fail(req, index):
        if index == 1: raise ProviderFailure("Synthetic503", retryable=True, request_finished=True)
    workflow, provider = setup_run(tmp_path, before=fail, overrides={"transport_retries": 1})
    assert workflow.run()["status"] == "completed"
    first, retry = calls(workflow)[:2]
    assert retry["transport_retry_of"] == first["attempt_id"]
    assert retry["purpose"] == first["purpose"] == "generate"
    assert retry["logical_task_id"] == first["logical_task_id"]
    assert len(workflow.generator.tasks[0].attempts) == 2
    assert workflow.generator.tasks[0].first_physical_attempt_passed is False
    assert workflow.generator.tasks[0].first_output_passed is False


@pytest.mark.parametrize("source_field", ["source_ids", "affected_claim_ids"])
def test_bad_critic_reference_never_reaches_revision(tmp_path, source_field):
    def fail(req, index):
        if issubclass(req.schema, ComponentCritiqueReport):
            data = synthetic_report("research", severity="critical")
            data["issues"][0][source_field] = ["invented"]
            return PhysicalResponse(json.dumps(data), {}, 10, 5, 15)
    workflow, provider = setup_run(tmp_path, before=fail)
    result = workflow.run()
    assert result["status"] == "failed"
    assert not any(c["task_purpose"] == "revision" for c in calls(workflow))
    assert len(provider.calls) == (3 if source_field == "source_ids" else 4)


@pytest.mark.parametrize("limit", ["max_total_tokens", "max_prompt_chars"])
def test_zero_calls_if_reservation_or_prompt_cannot_fit(tmp_path, limit):
    workflow, provider = setup_run(tmp_path, overrides={limit: 1})
    result = workflow.run()
    assert result["status"] == "budget_exhausted"
    assert not provider.calls and not calls(workflow)
    assert result["budget"]["request_count"] == 0


def test_api_failure_is_durable_and_never_counted_as_zero_usage(tmp_path):
    def fail(req, index): raise ProviderFailure("SyntheticAPIError")
    workflow, provider = setup_run(tmp_path, before=fail)
    result = workflow.run()
    assert result["status"] == "failed" and len(provider.calls) == 1
    event = calls(workflow)[0]
    assert event["status"] == "failed" and event["total_tokens"] is None
    assert event["usage_raw"] is None and event["usage_missing_reason"]
    assert result["budget"]["request_count"] == 1


def test_cancel_before_dispatch_records_stop(tmp_path):
    cancel = Event()
    workflow, provider = setup_run(tmp_path, cancel=cancel)
    cancel.set()
    assert workflow.run()["status"] == "cancelled"
    assert not provider.calls


@pytest.mark.parametrize("condition,limits", [("A", dict(node_seconds=.8, run_seconds=10)),
    ("C", dict(node_seconds=.8, run_seconds=10)), ("C", dict(node_seconds=10, run_seconds=.8))])
def test_clock_is_shared_across_batches_and_review(tmp_path, condition, limits):
    elapsed = [0.0]
    def tick(req, index): elapsed[0] += .5
    workflow, provider = setup_run(tmp_path, condition=condition, before=tick,
        overrides=limits, clock=lambda: elapsed[0])
    result = workflow.run()
    assert result["status"] == "timeout"
    assert len(provider.calls) == 2
    assert len({c["node_scope_id"] for c in calls(workflow)}) == 1


def test_local_abandoned_request_blocks_new_instances_and_runs(tmp_path):
    done = Event()
    def slow(req, index):
        done.wait(2)
    lease_dir = tmp_path / "leases"
    lease = LocalRequestLease(lease_dir, "synthetic-local-endpoint")
    workflow, provider = setup_run(tmp_path / "first", condition="D", provider_kind="local", before=slow,
        overrides={"request_seconds": .05}, local_lease=lease)
    try:
        result = workflow.run()
        assert result["status"] == "timeout" and lease.path.exists()
        other, other_provider = setup_run(tmp_path / "second", condition="D", provider_kind="local",
            local_lease=LocalRequestLease(lease_dir, "synthetic-local-endpoint"))
        assert other.run()["status"] == "failed"
        assert not other_provider.calls and not calls(other)
    finally:
        done.set()
    assert lease.path.exists()  # A late client completion alone is not a server-idle confirmation.


def test_replay_deduplicates_and_keeps_unknown_dispatch(tmp_path):
    workflow, _ = setup_run(tmp_path / "sample")
    workflow.run()
    data = calls(workflow)[0]
    data.update(status="dispatching", ended_at_utc=None)
    journal = EventJournal(tmp_path / "journal", workflow.run_id)
    event = journal.emit("call", data)
    journal.emit("call", data, event_id=event["event_id"])
    assert len(journal.events) == 1
    with journal.path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\n{interrupted")
    result = replay_events(journal.path)
    assert result["truncated_tail"] and len(result["attempts"]) == 1
    assert result["attempts"][0]["status"] == "interrupted_unknown"
    assert result["automatic_resume_allowed"] is False


def test_no_reinvoke_or_existing_output_overwrite(tmp_path):
    workflow, provider = setup_run(tmp_path)
    workflow.run()
    count = len(provider.calls)
    with pytest.raises(ValueError, match="already started"): workflow.run()
    assert len(provider.calls) == count
    with pytest.raises(FileExistsError): setup_run(tmp_path)


def test_provider_schema_prepares_without_network():
    from google.genai.types import Schema
    from workflow.gemini_schema import relaxed_response_schema
    Schema.model_validate(relaxed_response_schema(ComponentCritiqueReport))


def test_mixed_score_is_not_rounded_before_gate():
    data = synthetic_report("research", score=3)
    data["metrics"][0]["score"] = 2
    report = ComponentCritiqueReport.model_validate(data)
    assert report.overall_score == 6.875 and report.revision_required


def test_dispatch_start_is_durable_before_provider_and_usage_can_exceed_cap(tmp_path):
    holder = {}
    def observe(req, index):
        live = replay_events(holder["workflow"].journal.path)["attempts"]
        assert len(live) == index and live[-1]["status"] == "interrupted_unknown"
        data = synthetic_report("research")
        return PhysicalResponse(json.dumps(data), dict(total=30_000_000), 10, 5, 30_000_000)
    workflow, provider = setup_run(tmp_path, before=observe)
    holder["workflow"] = workflow
    result = workflow.run()
    # Schema is also wrong, but the token cap still blocks any repair request.
    assert result["status"] == "budget_exhausted" and len(provider.calls) == 1
    assert result["budget"]["actual_total_tokens_known"] == 30_000_000
    assert calls(workflow)[0]["total_tokens"] == 30_000_000


def test_cancellation_during_physical_wait_is_counted_once(tmp_path):
    cancel = Event()
    def stop(req, index):
        cancel.set()
    workflow, provider = setup_run(tmp_path, before=stop, cancel=cancel)
    result = workflow.run()
    assert result["status"] == "cancelled" and len(provider.calls) == 1
    assert len(calls(workflow)) == 1


def test_revision_structure_repair_keeps_revision_attribution(tmp_path):
    seen = []
    def corrupt(req, index):
        data = request_payload(req.prompt)
        if data.get("previous_artifact") and not seen:
            seen.append(True)
            return PhysicalResponse("{bad", None)
    workflow, _ = setup_run(tmp_path, fail_roles=["research"], before=corrupt)
    result = workflow.run()
    assert result["status"] == "completed", result["error"]
    revisions = [c for c in calls(workflow) if c["task_purpose"] == "revision"]
    assert [c["purpose"] for c in revisions] == ["revision", "structure_repair", "revision"]
    assert all(c["role"] == "Revision" for c in revisions)
    assert revisions[0]["logical_task_id"] == revisions[1]["logical_task_id"]
    assert result["budget"]["revision_request_count"] == 3
    assert result["budget"]["structure_repair_request_count"] == 1
    assert result["gates"]["research"]["revision_count"] == 1


def test_sqlite_existing_json_columns_persist_events_and_versions(tmp_path):
    from contextlib import contextmanager
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from storage.db import Base
    from storage.repositories import get_run
    engine = create_engine(f"sqlite:///{(tmp_path / 's2.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    @contextmanager
    def sessions():
        with factory() as session:
            yield session
    workflow, _ = setup_run(tmp_path, condition="B", fail_roles=["final"], session_factory=sessions)
    result = workflow.run()
    assert result["status"] == "completed", result["error"]
    with sessions() as session:
        run = get_run(session, workflow.run_id)
        assert run.workflow_version == "multi-agent-review-gates-v3-two-stage" and run.status == "completed"
        events = [node.output_snapshot for node in run.node_outputs]
        assert len([e for e in events if e["kind"] == "call"]) == 46
        stages = {a.output_payload.get("stage") for a in run.agent_outputs if a.output_type == "s2.artifact"}
        assert stages == {"initial", "revision", "effective"}
        assert any(a.output_type == "s2.critique" for a in run.agent_outputs)
        assert run.token_usage["request_count"] == 23
    def fail(req, index): raise ProviderFailure("SyntheticFailure")
    failed, _ = setup_run(tmp_path / "failed", before=fail, session_factory=sessions)
    assert failed.run()["status"] == "failed"
    with sessions() as session:
        run = get_run(session, failed.run_id)
        assert run.token_usage["request_count"] == 1
        assert run.token_usage["total_tokens"] is None and run.token_usage["usage_missing_reason"]
        assert len(run.errors) == 1
    engine.dispose()


def test_gemini_adapter_makes_one_sdk_call_with_remaining_timeout_and_raw_usage():
    from types import SimpleNamespace
    from google.genai import types
    from workflow.review_providers import GeminiPhysicalProvider
    from workflow.review_runtime import PhysicalRequest
    received = []
    usage = types.GenerateContentResponseUsageMetadata(prompt_token_count=10, candidates_token_count=5,
        thoughts_token_count=7, total_token_count=22)
    def generate(**kwargs):
        received.append(kwargs)
        return SimpleNamespace(text="{}", usage_metadata=usage, candidates=[])
    adapter = GeminiPhysicalProvider(api_key="synthetic-unused", sdk_client=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    response = adapter.invoke(PhysicalRequest("fixture", ComponentCritiqueReport, "system", 0, 100, .75))
    assert len(received) == 1 and received[0]["config"].http_options.timeout == 750
    assert received[0]["config"].http_options.retry_options.attempts == 1
    assert response.total_tokens == 22 and response.output_tokens == 5
    assert response.usage_raw["thoughts_token_count"] == 7


def test_formal_execution_cannot_bypass_future_freeze_gates(tmp_path):
    with pytest.raises(ValueError, match="formal experiment runner"):
        setup_run(tmp_path, overrides={"run_kind": "formal"})


def test_transport_retry_blocked_by_budget_is_not_an_actual_retry(tmp_path):
    def fail(req, index): raise ProviderFailure("Synthetic503", retryable=True, request_finished=True)
    workflow, provider = setup_run(tmp_path, before=fail, overrides={"max_requests": 1, "transport_retries": 1})
    result = workflow.run()
    assert result["status"] == "budget_exhausted"
    assert len(provider.calls) == result["budget"]["request_count"] == 1
    assert result["budget"]["transport_retry_count"] == 0


def test_physical_worker_keeps_frozen_evidence_context(tmp_path):
    from tools.web_search import search_web
    def unexpected_search(req, index): search_web("must be blocked before provider search")
    workflow, provider = setup_run(tmp_path, before=unexpected_search)
    result = workflow.run()
    assert result["status"] == "failed" and len(provider.calls) == 1
    assert result["error"]["error_type"] == "FrozenEvidenceAccessError"
