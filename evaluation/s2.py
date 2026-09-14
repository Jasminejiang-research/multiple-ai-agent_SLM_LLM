"""Run explicitly synthetic S2 route audits, with no API keys, network or model calls."""
import argparse
import json
from pathlib import Path
from workflow.contract_context import ContractContext
from workflow.review_config import ReviewRunConfig
from workflow.review_graph import build_review_workflow
from evaluation.s2_fixtures import SyntheticProvider
from schemas.review import ComponentCritiqueReport
from schemas.review_events import CallEventPayload, ExpectedHandoff


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    schemas = {schema.__name__: schema.model_json_schema() for schema in
        (ReviewRunConfig, ComponentCritiqueReport, CallEventPayload, ExpectedHandoff)}
    (args.output_dir / "schemas.json").write_text(json.dumps(schemas, indent=2), encoding="utf-8")
    root = Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1"
    rows = []
    for condition in "ABCD":
        ctx = ContractContext.from_case(root, "ai_education", condition=condition)
        for path in ("pass", "revision") if condition != "A" else ("pass",):
            config = ReviewRunConfig(condition=condition, run_kind="debug", provider="mock",
                model_exact_id=SyntheticProvider.model_exact_id, model_config_version="synthetic-only-v1",
                max_requests=64, max_total_tokens=20_000_000, max_output_tokens=1024,
                max_prompt_chars=1_000_000, request_seconds=10)
            provider = SyntheticProvider(ctx, fail_roles=config.reviewed_roles if path == "revision" else (), severity="critical")
            workflow = build_review_workflow(ctx, config=config, provider=provider, output_dir=args.output_dir / f"{condition}-{path}")
            result = workflow.run()
            rows.append(dict(condition=condition, route=path, status=result["status"], requests=len(provider.calls),
                blocking=result["blocking"], branches=result["branches"], all_handoffs_passed=all(h["status"] == "succeeded" for h in result["handoffs"])))
    summary = dict(synthetic_only=True, actual_model_calls=0, formal_runs_started=0, routes=rows)
    (args.output_dir / "audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if all(row["status"] == "completed" and row["all_handoffs_passed"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
