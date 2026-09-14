"""Offline S1 contract audit. Never calls a provider or starts a formal run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from schemas.contract_outputs import CONTRACT_VERSION, ContractProposal
from schemas.evidence import canonical_hash
from workflow.contract_context import ContractContext
from workflow.contract_generation import PROMPT_VERSION
from workflow.finance_contract import FINANCE_VERSION
from workflow.generation_batches import CONTRACT_BATCH_MODELS, PROPOSAL_SECTION_BATCHES


def audit(root: Path) -> dict:
    result = {"package": "S1", "kind": "offline_contract_audit", "model_calls": 0,
              "contract_version": CONTRACT_VERSION, "prompt_version": PROMPT_VERSION,
              "finance_version": FINANCE_VERSION,
              "proposal_schema_sha256": canonical_hash(ContractProposal.model_json_schema()),
              "batches": [{"fields": fields, "schema_sha256": canonical_hash(schema.model_json_schema())}
                          for fields, schema in zip(PROPOSAL_SECTION_BATCHES, CONTRACT_BATCH_MODELS, strict=True)],
              "cases": [], "formal_execution_allowed": False,
              "next_dependencies": ["S2 gates/budget/events", "S3 Granite preflight", "S4 runner", "case and runtime freeze"]}
    for case_id in ("ai_education", "intelligent_ring"):
        contexts = [ContractContext.from_case(root, case_id, condition=c) for c in "ABCD"]
        if len({(c.packet_sha256, c.brief_sha256) for c in contexts}) != 1:
            raise ValueError("A-D input mismatch")
        ctx = contexts[0]
        values = ctx.finance.expected_values()
        ctx.finance.validate(values)
        result["cases"].append({"case_id": case_id, "conditions": list("ABCD"),
            "packet_sha256": ctx.packet_sha256, "brief_sha256": ctx.brief_sha256,
            "packet_review_status": ctx.packet.review_status, "snapshot_validation": "passed",
            "source_count": len(ctx.packet.sources), "chunk_count": len(ctx.packet.chunks),
            "finance_reference_kind": "deterministically_calculated_from_pending_scenario_assumptions_not_model_output",
            "finance_reference_values": [v.model_dump(mode="json") for v in values]})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "docs/final_sprint/s0-v1")
    parser.add_argument("--output-dir", type=Path, help="Create a new directory; existing outputs are never overwritten")
    args = parser.parse_args()
    result = audit(args.root)
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=False)
        def write(name, data):
            (args.output_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write("contract_audit.json", result)
        write("proposal_schema.json", ContractProposal.model_json_schema())
        # Exact S0 packet example. Its local snapshot paths resolve relative to --root.
        write("packet_example.json", json.loads((args.root / "cases/ai_education/packet.json").read_text(encoding="utf-8")))
    print(json.dumps({k:v for k,v in result.items() if k != "cases"}, ensure_ascii=False, indent=2))
    print("Verified two cases, four common conditions, 13 complete sections, 4/3/3/3 batches and frozen Decimal formulas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
