"""Offline boundaries for the cumulative physical Gemini smoke reservation."""
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from evaluation.s5_llm_only import run_config, SMOKE_LIMITS
from evaluation.s5_smoke_budget import CumulativeSmokeBudget
from workflow.review_events import EventJournal
from workflow.review_runtime import BoundedClient, PhysicalResponse, SharedBudgetStop


class MemoryJournal:
    def __init__(self):
        self.events = []

    def emit(self, kind, payload):
        self.events.append((kind, payload))


def gate(prior=None, limits=None):
    return CumulativeSmokeBudget(prior or dict(requests=0, total_tokens=0, cost_usd=0),
        limits or SMOKE_LIMITS)


@pytest.mark.parametrize("metric,prior", [
    ("requests", dict(requests=54, total_tokens=0, cost_usd=0)),
    ("total_tokens", dict(requests=0, total_tokens=479001, cost_usd=0)),
    ("cost_usd", dict(requests=0, total_tokens=0, cost_usd=1.1975001)),
])
def test_each_cumulative_limit_blocks_before_reservation(metric, prior):
    budget, journal = gate(prior), MemoryJournal()
    with pytest.raises(SharedBudgetStop, match="hard-limit"):
        budget.reserve_request(attempt_id="blocked", estimated_tokens=1000, journal=journal)
    assert budget.snapshot()["charged"]["requests"] == 0
    assert not journal.events


def test_exact_boundary_allows_one_call_and_settles_actual_thinking_cost():
    budget = gate(dict(requests=53, total_tokens=479000, cost_usd=1.1975))
    journal = MemoryJournal()
    budget.reserve_request(attempt_id="last", estimated_tokens=1000, journal=journal)
    budget.record_usage(attempt_id="last", event=dict(prompt_tokens=100, output_tokens=200,
        total_tokens=400), journal=journal)
    snapshot = budget.snapshot()
    assert snapshot["charged"] == dict(requests=1, prompt_tokens=100, output_tokens=200,
        total_tokens=400, cost_usd=.00078)
    assert snapshot["charged"] == snapshot["actual_complete_usage"]
    assert [e[1]["status"] for e in journal.events] == ["reserved_before_dispatch", "actual_usage"]
    with pytest.raises(SharedBudgetStop):
        budget.check_request(estimated_tokens=1)


@pytest.mark.parametrize("usage", [dict(prompt_tokens=None, output_tokens=None, total_tokens=None),
    dict(prompt_tokens=None, output_tokens=100, total_tokens=200),
    dict(prompt_tokens=100, output_tokens=None, total_tokens=1200)])
def test_unknown_or_partial_usage_retains_full_reservation_and_stops(usage):
    budget, journal = gate(), MemoryJournal()
    budget.reserve_request(attempt_id="unknown", estimated_tokens=1000, journal=journal)
    budget.record_usage(attempt_id="unknown", event=usage, journal=journal)
    snapshot = budget.snapshot()
    charge = max(1000, usage["total_tokens"] or 0)
    assert snapshot["charged"]["total_tokens"] == charge
    assert snapshot["charged"]["cost_usd"] == charge * 2.5 / 1_000_000
    assert snapshot["charged"]["requests"] == 1
    assert snapshot["actual_complete_usage"]["requests"] == 0
    assert snapshot["usage_incomplete"]
    assert snapshot["actual_field_basis"] == "conservative_charged_usage_not_actual_expense"
    with pytest.raises(SharedBudgetStop, match="unresolved"):
        budget.check_request(estimated_tokens=1)


class TinyOutput(BaseModel):
    value: int


class OfflineProvider:
    provider = "gemini"
    model_exact_id = "gemini-2.5-flash"

    def __init__(self, usage=True):
        self.calls = 0
        self.usage = usage

    def invoke(self, request):
        self.calls += 1
        return PhysicalResponse('{"value":1}', prompt_tokens=10 if self.usage else None,
            output_tokens=10 if self.usage else None, total_tokens=25 if self.usage else None)


def invoke(client, task):
    with client.attempt_scope(logical_task_id=task, role="single", task_purpose="generate",
            purpose="generate", batch_number=None, schema_sha256="0" * 64,
            packet_sha256="1" * 64):
        return client.generate_structured_once("tiny", TinyOutput)


def test_shared_gate_tracks_two_clients_across_arms_without_whole_arm_reserve(tmp_path):
    budget = gate(dict(requests=52, total_tokens=450000, cost_usd=1.0))
    providers = []
    for arm in "AB":
        provider = OfflineProvider()
        client = BoundedClient(provider, run_config(arm, "smoke"),
            EventJournal(tmp_path / arm, arm), cumulative_budget=budget)
        client.begin_node("single")
        assert invoke(client, arm).value == 1
        providers.append(provider)
    assert [p.calls for p in providers] == [1, 1]
    assert budget.snapshot()["charged"]["requests"] == 2
    assert budget.snapshot()["charged"]["total_tokens"] == 50
    with pytest.raises(SharedBudgetStop):
        invoke(client, "third")
    assert providers[-1].calls == 1


def test_client_unknown_usage_preserves_raw_call_then_prevents_next_dispatch(tmp_path):
    budget, provider = gate(), OfflineProvider(usage=False)
    journal = EventJournal(tmp_path / "unknown", "unknown")
    client = BoundedClient(provider, run_config("A", "smoke"), journal,
        cumulative_budget=budget)
    client.begin_node("single")
    assert invoke(client, "one").value == 1
    with pytest.raises(SharedBudgetStop, match="unresolved"):
        invoke(client, "two")
    assert provider.calls == 1
    call = [e["payload"] for e in journal.events if e["kind"] == "call"][-1]
    assert call["raw_output"] == '{"value":1}' and call["total_tokens"] is None
    assert budget.snapshot()["charged"]["total_tokens"] == call["reservation_tokens"]


def test_prior_unknown_smoke_cannot_be_omitted_on_new_prepare(tmp_path, monkeypatch):
    import evaluation.s5_llm_only as runner
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    folder = tmp_path / "docs/final_sprint/s5-llm-only-v1"
    folder.mkdir(parents=True)
    (folder / "smoke_summary.json").write_text(json.dumps(dict(
        actual=dict(requests=1, total_tokens=1000, cost_usd=.0025),
        usage_accounting=dict(usage_incomplete=True))), encoding="utf-8")
    with pytest.raises(ValueError, match="usage unresolved"):
        runner._prior_nonformal_spend(tmp_path / "docs/final_sprint/s5-llm-only-v2")


@pytest.mark.parametrize("settled", [True, False])
def test_smoke_outer_exception_keeps_active_arm_usage_or_pending_reservation(tmp_path, monkeypatch, settled):
    from contextlib import nullcontext
    import dotenv
    import evaluation.s5_llm_only as runner
    import evaluation.s4_resources as resources
    import workflow.review_graph as graph
    import workflow.review_providers as providers

    experiment = tmp_path / "experiment"
    experiment.mkdir()
    freeze = dict(status="pending_smoke", execution_branch=runner.LLM_ONLY_BRANCH,
        pre_smoke_code_inventory={},
        model_metadata={"A-C": {"credential_source_variable": "GOOGLE_API_KEY"}},
        prior_nonformal_spend=dict(requests=20, total_tokens=126460, cost_usd=.1857164),
        configs={arm: run_config(arm, "formal").model_dump(mode="json") for arm in "ABC"})
    (experiment / "freeze.json").write_text(json.dumps(freeze), encoding="utf-8")
    monkeypatch.setattr(runner, "code_inventory", lambda root: {})
    # This isolated exception-path fixture owns its synthetic historical spend.
    monkeypatch.setattr(runner, "_prior_nonformal_spend", lambda path: freeze["prior_nonformal_spend"])
    monkeypatch.setattr(runner, "load_plan", lambda path: {"case_root": str(tmp_path)})
    monkeypatch.setattr(runner.ContractContext, "from_case", lambda *args, **kwargs: None)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(providers, "resolve_gemini_credential",
        lambda **kwargs: ("offline-test-placeholder", "GOOGLE_API_KEY"))
    monkeypatch.setattr(providers, "GeminiPhysicalProvider", lambda **kwargs: object())
    monkeypatch.setattr(resources, "RunTelemetry", lambda *args, **kwargs: nullcontext())

    class ExplodingWorkflow:
        def __init__(self, **kwargs):
            self.journal = EventJournal(kwargs["output_dir"], kwargs["run_id"])
            self.budget = kwargs["cumulative_budget"]

        def run(self):
            self.budget.reserve_request(attempt_id="active", estimated_tokens=1000,
                journal=self.journal)
            if settled:
                self.budget.record_usage(attempt_id="active", event=dict(prompt_tokens=100,
                    output_tokens=200, total_tokens=400), journal=self.journal)
            raise RuntimeError("offline post-reservation failure")

    monkeypatch.setattr(graph, "build_review_workflow", lambda context, **kwargs: ExplodingWorkflow(**kwargs))
    summary = runner.run_smokes(experiment)
    assert summary["status"] == "failed" and summary["failed_condition"] == "A"
    assert summary["actual"]["requests"] == summary["active_arm_charged"]["requests"] == 1
    assert summary["actual"]["total_tokens"] == (400 if settled else 1000)
    assert summary["actual"]["cost_usd"] == (.00078 if settled else .0025)
    assert summary["usage_accounting"]["usage_incomplete"] is (not settled)
    assert summary["cumulative_live_smoke"]["requests"] == 21
    assert (experiment / "smoke_summary.json").is_file()
