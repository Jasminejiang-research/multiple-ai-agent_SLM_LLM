"""S2 Granite injection seam only; no local model is loaded or called."""
from pathlib import Path
from evaluation.s2_fixtures import SyntheticProvider
from schemas.review import METRICS
from slm.factories import build_slm_review_workflow
from workflow.contract_context import ContractContext
from workflow.review_config import ReviewRunConfig
from workflow.review_runtime import LocalRequestLease


def test_local_injection_uses_all_common_critics_and_revisions(tmp_path):
    root = Path(__file__).resolve().parents[2] / "docs/final_sprint/s0-v1"
    ctx = ContractContext.from_case(root, "ai_education", condition="D")
    provider = SyntheticProvider(ctx, fail_roles=METRICS, severity="critical")
    provider.provider = "local"
    config = ReviewRunConfig(condition="D", run_kind="debug", provider="local",
        model_exact_id=provider.model_exact_id, model_config_version="synthetic-local-only",
        max_requests=64, max_total_tokens=20_000_000, max_output_tokens=1024,
        max_prompt_chars=1_000_000, request_seconds=10)
    lease = LocalRequestLease(tmp_path / "leases", "synthetic-local-server")
    workflow = build_slm_review_workflow(ctx, config=config, provider=provider, local_lease=lease,
        output_dir=tmp_path / "result")
    result = workflow.run()
    assert result["status"] == "completed", result["error"]
    assert len(provider.calls) == 32 and len(result["reports"]) == 4
    assert all(g["revision_count"] == 1 for g in result["gates"].values())
    assert result["blocking"] and not lease.path.exists()
