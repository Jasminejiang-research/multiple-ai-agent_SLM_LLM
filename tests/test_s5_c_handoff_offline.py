"""Current S5 C Critic/revision/handoff integration with synthetic responses only."""
from dataclasses import replace
from pathlib import Path

import pytest

from evaluation.s2_fixtures import SyntheticProvider
from evaluation.s5_llm_only import run_config
from schemas.compact_wire import FinanceWire
from schemas.review import METRICS
from workflow.contract_context import ContractContext
from workflow.review_events import replay_events
from workflow.review_graph import build_review_workflow


ROOT = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"


class CurrentFinanceFixtureProvider(SyntheticProvider):
    """Adapt only fixture schema dispatch to the extended finance DTO capacity."""
    provider = "gemini"
    model_exact_id = "gemini-2.5-flash"

    def invoke(self, request):
        if request.schema is not FinanceWire and issubclass(request.schema, FinanceWire):
            request = replace(request, schema=FinanceWire)
        return super().invoke(request)


@pytest.mark.parametrize("case_id", ["ai_education", "intelligent_ring"])
def test_current_c_all_critics_revise_once_and_handoff_every_effective_artifact(tmp_path, case_id):
    context = ContractContext.from_case(ROOT, case_id, condition="C")
    provider = CurrentFinanceFixtureProvider(context, fail_roles=METRICS, severity="high")
    workflow = build_review_workflow(context, config=run_config("C", "smoke"),
        provider=provider, output_dir=tmp_path / case_id)
    result = workflow.run()
    assert result["status"] == "completed", result["error"]
    assert result["terminal_contract_passed"]
    assert len(provider.calls) == 12
    assert result["branches"] == {role: "revise_once" for role in METRICS}
    assert all(issue["status"] == "unverified_after_revision" for issue in result["issues"])
    assert all(ref["artifact_version"] == 2 for ref in result["effective_artifacts"].values())
    assert all(row["status"] == "succeeded" for row in result["handoffs"])
    attempts = replay_events(workflow.journal.path)["attempts"]
    assert all(row["usage_raw"]["synthetic"] for row in attempts)
    assert sum(row["task_purpose"] == "critic" for row in attempts) == 4
    assert sum(row["task_purpose"] == "revision" for row in attempts) == 4
