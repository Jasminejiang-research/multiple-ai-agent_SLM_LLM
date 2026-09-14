"""Audited S5 LLM-only admission, Gemini smoke, and joint-freeze utilities."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
from threading import Event
from uuid import uuid4

from schemas.evidence import canonical_hash
from schemas.compact_wire import WIRE_VERSION
from workflow.compact_protocol import (
    GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION,
    MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION, MVP30_SECONDS, PROMPT_VERSION,
    VALID_PLAN_SECONDS,
)
from workflow.contract_context import ContractContext
from workflow.review_config import ReviewRunConfig
from evaluation.s4_io import append_event, file_hash, read_json, write_csv, write_json
from evaluation.s5_smoke_budget import resolve_smoke_budget_baseline
from evaluation.s4_runner import (
    AUTHORITY_NAMES, AUTHORITY_ROOT, D_POLICY_STATUS, LLM_ONLY_BRANCH,
    ROOT, check_freeze, code_inventory, load_plan, runtime_inventory, status,
    verify_smoke_budget_epoch_authorization,
)

MODEL = "gemini-2.5-flash"
MODEL_CONFIG_VERSION = "gemini-2.5-flash-standard-32k-s6-compact-dual-lineage-v23"
SMOKE_ARMS = ("A", "B", "C")
SMOKE_CASE = "ai_education"
INPUT_PRICE = .30
OUTPUT_PRICE = 2.50
SMOKE_LIMITS = {"requests": 54, "total_tokens": 480000, "cost_usd": 1.20}
FORMAL_LIMITS = {"requests": 108, "total_tokens": 960000, "cost_usd": 2.40}
COMBINED_COST_LIMIT = 3.60


def run_config(condition: str, run_kind: str) -> ReviewRunConfig:
    return ReviewRunConfig(condition=condition, run_kind=run_kind, provider="gemini",
        model_exact_id=MODEL, model_config_version=MODEL_CONFIG_VERSION,
        max_requests=18, max_total_tokens=160000, max_output_tokens=8192,
        max_prompt_chars=26000, node_seconds=1200, run_seconds=VALID_PLAN_SECONDS,
        request_seconds=420, transport_retries=0, context_tokens=32768,
        thinking_budget=1024,
        protocol_version=WIRE_VERSION, mvp_seconds=MVP30_SECONDS,
        config_version=GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION)


def conservative_cost(prompt_tokens: int, output_tokens: int, total_tokens: int) -> float:
    if any(type(value) is not int or value < 0 for value in (prompt_tokens, output_tokens, total_tokens)):
        raise ValueError("complete non-negative provider usage is required for cost accounting")
    if total_tokens < prompt_tokens + output_tokens:
        raise ValueError("provider total token count is inconsistent")
    billable_output = total_tokens - prompt_tokens
    return round((prompt_tokens * INPUT_PRICE + billable_output * OUTPUT_PRICE) / 1_000_000, 9)


def _record(path: Path) -> dict:
    return {"path": str(path), "sha256": file_hash(path)}


def _evidence_inventory(case_root: Path) -> dict:
    return {p.relative_to(case_root).as_posix(): file_hash(p)
        for p in sorted((case_root / "cases").rglob("*")) if p.is_file()}


def _prior_nonformal_spend(output: Path) -> dict:
    """Recompute every immutable S5 smoke summary rather than hard-code v1-v6."""
    candidates = []
    for directory in (ROOT / "docs/final_sprint").glob("s5-llm-only-v*"):
        match = re.fullmatch(r"s5-llm-only-v([0-9]+)", directory.name)
        if match and directory.resolve() != output.resolve():
            summary_path = directory / "smoke_summary.json"
            if summary_path.is_file():
                candidates.append((int(match.group(1)), summary_path))
    records = []
    totals = {"requests": 0, "total_tokens": 0, "cost_usd": 0.0}
    for _, summary_path in sorted(candidates):
        summary = read_json(summary_path)
        if summary.get("usage_accounting", {}).get("usage_incomplete"):
            raise ValueError(f"prior smoke usage unresolved; conservative reservation retained: {summary_path}")
        actual = summary.get("actual", {})
        requests, total_tokens, cost = (
            actual.get("requests"), actual.get("total_tokens"), actual.get("cost_usd"))
        if (type(requests) is not int or requests < 0 or type(total_tokens) is not int or
                total_tokens < 0 or not isinstance(cost, (int, float)) or cost < 0):
            raise ValueError(f"invalid prior smoke accounting: {summary_path}")
        record = _record(summary_path)
        record.update(requests=requests, total_tokens=total_tokens, cost_usd=cost)
        records.append(record)
        totals["requests"] += requests
        totals["total_tokens"] += total_tokens
        totals["cost_usd"] = round(totals["cost_usd"] + cost, 9)
    return {"records": records, **totals,
        "scope": "all preserved s5-llm-only-vN smoke summaries; immutable lifetime accounting; an explicitly authorized epoch may define a separate active ceiling"}


def _approve_frozen_input_copy(case_root: Path, approval_path: Path) -> dict:
    approval = {"path": str(approval_path.resolve()),
        "scope": "complete_case_brief_evidence_and_case_specific_finance"}
    counts = {"ai_education": 21, "intelligent_ring": 27}
    result = {}
    for case_id, expected_count in counts.items():
        folder = case_root / "cases" / case_id
        brief = read_json(folder / "brief.json")
        policy = brief["additional_context"]["financial_policy"]
        brief["additional_context"]["financial_policy"] = policy.replace(
            "awaiting user approval, not user-confirmed values",
            "approved by the user for the frozen experiment, not external facts")
        def approve_statuses(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "review_status" and item == "pending":
                        value[key] = "approved"
                    else:
                        approve_statuses(item)
            elif isinstance(value, list):
                for item in value:
                    approve_statuses(item)
        approve_statuses(brief["financial_inputs"])
        write_json(folder / "brief.json", brief, replace=True)

        packet = read_json(folder / "packet.json")
        packet.update(review_status="approved", approval_record=approval)
        packet["packet_sha256"] = canonical_hash({key: value for key, value in packet.items()
            if key != "packet_sha256"})
        write_json(folder / "packet.json", packet, replace=True)

        case = read_json(folder / "case.json")
        case.update(review_status="approved", approval_record={**approval,
            "case_specific_finance_count": expected_count},
            brief_sha256=file_hash(folder / "brief.json"), packet_sha256=packet["packet_sha256"],
            proposed_by="Codex; explicitly confirmed by the user for this frozen LLM-only experiment",
            formal_execution_allowed=True)
        write_json(folder / "case.json", case, replace=True)
        context = ContractContext.from_case(case_root, case_id, condition="A",
            execution_mode="formal_frozen")
        actual_count = len(context.finance.expected_values())
        if actual_count != expected_count:
            raise ValueError("approved case-specific finance count changed")
        result[case_id] = {"brief_sha256": context.brief_sha256,
            "packet_sha256": context.packet_sha256,
            "case_specific_finance_count": actual_count}
    return result


def prepare(source_experiment: Path, output: Path, authorization: Path) -> dict:
    source_experiment, output, authorization = map(Path, (source_experiment, output, authorization))
    if output.exists():
        raise FileExistsError("LLM-only S5 experiment must use a fresh directory")
    source_plan = load_plan(source_experiment)
    if source_plan["kind"] != "formal_plan":
        raise ValueError("LLM-only branch requires the preserved formal eight-row plan")
    decision = read_json(authorization)
    if (decision.get("approved") is not True or decision.get("execution_branch") != LLM_ONLY_BRANCH or
            decision.get("formal_conditions") != list(SMOKE_ARMS) or
            decision.get("D_row_state") != D_POLICY_STATUS or
            decision.get("output_change", {}).get("max_output_tokens_per_physical_response") != 8192 or
            decision.get("prompt_change", {}).get("prompt_version") != PROMPT_VERSION or
            decision.get("prompt_change", {}).get("approved") is not True or
            decision.get("prompt_change", {}).get("claim_id_min_chars") != 3 or
            decision.get("prompt_change", {}).get("text_equals_claim_required") is not True or
            decision.get("schema_change", {}).get("claim_reason_max_chars") != 200 or
            decision.get("schema_change", {}).get("approved") is not True or
            decision.get("schema_change", {}).get("finance_note_claim_max_items") != 8 or
            decision.get("mechanical_repair_change", {}).get("approved") is not True or
            decision.get("mechanical_repair_change", {}).get("pad_short_claim_ids") is not True or
            decision.get("mechanical_repair_change", {}).get("downgrade_unsubstantiated_sourced_fact") is not True or
            decision.get("mechanical_repair_change", {}).get("delete_terminal_punctuation_on_exact_parent_match") is not True or
            decision.get("mechanical_repair_change", {}).get("max_terminal_characters_deleted") != 1 or
            decision.get("mechanical_repair_change", {}).get("version") != MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION or
            decision.get("mechanical_repair_change", {}).get("normalize_invalid_sourced_fact_disposition") is not True or
            decision.get("mechanical_repair_change", {}).get("split_compact_citation_bracket_lists") is not True or
            decision.get("mechanical_repair_change", {}).get("may_mechanically_insert_inline_citations") is not True or
            decision.get("mechanical_repair_change", {}).get("mirror_only_selected_frozen_evidence_ids") is not True or
            decision.get("mechanical_repair_change", {}).get("remove_only_selected_frozen_financial_markers_from_prose") is not True or
            decision.get("mechanical_repair_change", {}).get("preserve_structured_financial_value_ids") is not True or
            decision.get("mechanical_repair_change", {}).get("normalize_integer_source_quality_scale_5_to_unit") is not True or
            decision.get("mechanical_repair_change", {}).get("q_equals_1_unchanged") is not True or
            decision.get("mechanical_repair_change", {}).get("other_invalid_q_rejected") is not True or
            decision.get("mechanical_repair_change", {}).get("append_existing_same_parent_claim_text_only") is not True or
            decision.get("mechanical_repair_change", {}).get("preserve_original_body_verbatim") is not True or
            decision.get("mechanical_repair_change", {}).get("invalid_numeric_source_recency_to_unknown") is not True or
            decision.get("mechanical_repair_change", {}).get("partition_finance_note_claims_without_deletion") is not True or
            decision.get("mechanical_repair_change", {}).get("append_code_owned_financial_assumption_notice") is not True or
            decision.get("repair_instruction_change", {}).get("approved") is not True or
            decision.get("repair_instruction_change", {}).get("version") != "compact-structure-repair-instruction-v1-s5" or
            decision.get("runner_logic_repairs", {}).get("exact_same_text_lineage_identity_continuity", {}).get("approved") is not True or
            decision.get("runner_logic_repairs", {}).get("exact_same_text_lineage_identity_continuity", {}).get("version") != "explicit-same-text-lineage-identity-v1-s5" or
            decision.get("runner_logic_repairs", {}).get("exact_same_text_lineage_identity_continuity", {}).get("applies_only_to_config_version") != GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION or
            decision.get("runner_logic_repairs", {}).get("claim_id_collision_normalization", {}).get("approved") is not True or
            decision.get("runner_logic_repairs", {}).get("claim_id_collision_normalization", {}).get("version") != "declared-upstream-claim-id-split-v1-s5" or
            decision.get("runner_logic_repairs", {}).get("claim_id_collision_normalization", {}).get("applies_only_to_config_version") != GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION or
            decision.get("runner_logic_repairs", {}).get("dual_declared_lineage", {}).get("approved") is not True or
            decision.get("runner_logic_repairs", {}).get("dual_declared_lineage", {}).get("version") != "dual-declared-exact-text-lineage-v1-s5" or
            decision.get("runner_logic_repairs", {}).get("dual_declared_lineage", {}).get("applies_only_to_config_version") != GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION or
            decision.get("mechanical_repair_change", {}).get("applies_only_to_config_version") != GEMINI_8192_DUAL_LINEAGE_CONFIG_VERSION or
            decision.get("mechanical_repair_change", {}).get("may_add_evidence_ids") is not False or
            decision.get("mechanical_repair_change", {}).get("may_change_words") is not False or
            decision.get("prompt_change", {}).get("recommendation_premise_required") is not True or
            decision.get("prompt_change", {}).get("mirror_selected_evidence_ids_inline") is not True or
            decision.get("prompt_change", {}).get("finance_gap_max_items") != 3 or
            decision.get("prompt_change", {}).get("exactly_one_object_per_named_main_array") is not True or
            decision.get("prompt_change", {}).get("financial_ids_only_in_structured_f") is not True or
            decision.get("external_data_authorization", {}).get("credential_source_variable") != "GOOGLE_API_KEY" or
            decision.get("generation_strategy_change", {}).get("thinking_budget") != 1024 or
            decision.get("generation_strategy_change", {}).get("approved") is not True or
            decision.get("preserve_previous_failed_smoke") is not True or
            decision.get("combined_smoke_and_formal_max_cost_usd") != COMBINED_COST_LIMIT):
        raise ValueError("explicit LLM-only authorization record is incomplete")
    for record in decision.get("previous_failed_smokes", []):
        path = ROOT / record["path"]
        if (not path.is_file() or file_hash(path) != record["sha256"] or
                read_json(path).get("actual", {}).get("requests") != record["requests"] or
                read_json(path).get("actual", {}).get("total_tokens") != record["total_tokens"] or
                read_json(path).get("actual", {}).get("cost_usd") != record["cost_usd"]):
            raise ValueError("authorized prior smoke evidence changed")
    for record in decision.get("previous_pre_dispatch_no_go", []):
        path = ROOT / record["path"]
        if (not path.is_file() or file_hash(path) != record["sha256"] or
                any(record.get(key) != 0 for key in ("requests", "total_tokens", "cost_usd")) or
                (path.parent / "smokes").exists() or (path.parent / "smoke_schedule.jsonl").exists()):
            raise ValueError("prior zero-dispatch evidence is changed or has smoke activity")
        zero = read_json(path)
        if any(zero.get(key) != 0 for key in ("smoke_requests", "smoke_total_tokens",
                "smoke_cost_usd", "formal_runs_started")):
            raise ValueError("prior pre-dispatch record does not establish zero activity")
    prior_spend = _prior_nonformal_spend(output)
    verify_smoke_budget_epoch_authorization(decision.get("smoke_budget_epoch_authorization"))
    budget_baseline = resolve_smoke_budget_baseline(prior_spend,
        decision.get("smoke_budget_epoch_authorization"))
    output.mkdir(parents=True)
    write_json(output / "scope_decision.json", decision)
    frozen_root = output / "frozen_inputs"
    shutil.copytree(Path(source_plan["case_root"]), frozen_root)
    approved_inputs = _approve_frozen_input_copy(frozen_root, output / "scope_decision.json")
    # Preserve every planned ID and the exact randomized row order. Only the
    # approved input-copy hashes and experiment identity are versioned here.
    plan = json.loads(json.dumps(source_plan))
    version_match = re.fullmatch(r"s5-llm-only-v([0-9]+)", output.name)
    version_label = f"v{version_match.group(1)}" if version_match else "test-candidate"
    plan.update(version=f"eight-slot-s6-compact-llm-only-{version_label}", experiment_id=uuid4().hex,
        source_plan_sha256=file_hash(source_experiment / "plan.json"),
        execution_branch=LLM_ONLY_BRANCH, case_root=str(frozen_root.resolve()),
        protocol_sha256=file_hash(frozen_root / "protocol.json"))
    case_root = Path(plan["case_root"])
    for row in plan["rows"]:
        context = ContractContext.from_case(case_root, row["case_id"], condition=row["condition"],
            execution_mode="formal_frozen")
        row.update(packet_sha256=context.packet_sha256, brief_sha256=context.brief_sha256)
    write_json(output / "plan.json", plan)
    append_event(output / "freeze_history.jsonl", {"kind": "prepared_pending_smoke",
        "execution_branch": LLM_ONLY_BRANCH, "source_plan_sha256": file_hash(source_experiment / "plan.json")})
    for row in plan["rows"]:
        if row["condition"] == "D":
            append_event(output / "schedule.jsonl", {"kind": "policy_not_run",
                "planned_id": row["planned_id"], "state": D_POLICY_STATUS,
                "reason": "user-approved LLM-only branch after preserved D no_go"})

    d_record = ROOT / "docs/final_sprint/s6-fast-generation-v1/D_PREFLIGHT_ATTEMPT_03.json"
    demo_record = ROOT / "docs/final_sprint/s6-fast-generation-v1/BEST_EFFORT_DEMO_RESULT.json"
    smoke_approval = authorization
    scope_path = output / "scope_decision.json"
    scope_ref = _record(scope_path)
    configs = {arm: run_config(arm, "formal").model_dump(mode="json") for arm in SMOKE_ARMS}
    freeze = {
        "status": "pending_smoke",
        "execution_branch": LLM_ONLY_BRANCH,
        "plan_sha256": canonical_hash(plan),
        "approvals": {"cases": "approved", "common_budget": "approved",
            "D_preflight": "approved_no_go_omit_D", "gemini_quota_and_spend": "approved",
            "S1": "passed", "S2": "passed", "S4": "passed", "S6": "passed",
            "formal_execution": "approved"},
        "approval_records": {key: dict(scope_ref) for key in
            ("cases", "common_budget", "D_preflight", "formal_execution")},
        "configs": configs,
        "code_inventory": {},
        "pre_smoke_code_inventory": code_inventory(ROOT),
        "evidence_files": _evidence_inventory(case_root),
        "preflight_reports": {"D": _record(d_record)},
        "authority_files": {str(AUTHORITY_ROOT / name): file_hash(AUTHORITY_ROOT / name)
            for name in AUTHORITY_NAMES},
        "total_request_limit": FORMAL_LIMITS["requests"],
        "total_token_limit": FORMAL_LIMITS["total_tokens"],
        "cost_limits_usd": {"smoke": SMOKE_LIMITS["cost_usd"],
            "formal": FORMAL_LIMITS["cost_usd"], "combined": COMBINED_COST_LIMIT,
            "conservative_rate_per_million_tokens": OUTPUT_PRICE},
        "comparison_policy": {"reported": ["B-A", "C-B"],
            "unavailable": {"C-D": "D_preflight_no_go"},
            "success_subset_substitution": False},
        "excluded_nonformal_artifacts": {"best_effort_demo": {
            **_record(demo_record), "formal_eligible": False,
            "c_minus_d_comparison_eligible": False}},
        "smoke_actual": {"status": "not_started"},
        "prior_nonformal_spend": prior_spend,
        "smoke_budget_epoch_authorization": decision.get("smoke_budget_epoch_authorization"),
        "smoke_budget_baseline": budget_baseline,
        "runtime_versions": {},
        "model_metadata": {"A-C": {"provider": "gemini", "model_exact_id": MODEL,
            "service_tier": "standard", "thinking_budget": 1024,
            "mechanical_claim_repair": MECHANICAL_FINANCE_NOTICE_REPAIR_VERSION,
            "terminal_punctuation_exact_parent_match": True,
            "text_equals_claim_required": True,
            "selected_evidence_id_inline_mirroring": True,
            "inline_mirroring_owner": "deterministic_adapter",
            "credential_source_variable": decision["external_data_authorization"]["credential_source_variable"],
            "paid_tools": False},
            "D": {"formal_execution": D_POLICY_STATUS}},
        "source_records": {"authorization": _record(authorization),
            "gemini_smoke_approval": _record(smoke_approval), "D_no_go": _record(d_record)},
    }
    freeze["approval_records"].update({
        "gemini_quota_and_spend": _record(smoke_approval),
        "S1": _record(ROOT / "docs/final_sprint/s6-fast-generation-v1/PROTOCOL_MANIFEST.json"),
        "S2": _record(ROOT / "docs/final_sprint/s6-fast-generation-v1/PROTOCOL_MANIFEST.json"),
        "S4": _record(ROOT / "docs/final_sprint/s6-fast-generation-v1/VERSION_MANIFEST.json"),
        "S6": _record(ROOT / "docs/final_sprint/s6-fast-generation-v1/VERSION_MANIFEST.json"),
    })
    write_json(output / "freeze.json", freeze)
    write_csv(output / "manifest.csv", status(output)["rows"])
    return {"status": "prepared_pending_smoke", "experiment": str(output),
        "planned_rows": 8, "D_rows_sealed": 2, "formal_runs_started": 0,
        "pre_smoke_code_files": len(freeze["pre_smoke_code_inventory"]),
        "approved_inputs": approved_inputs}


def run_smokes(experiment: Path) -> dict:
    experiment = Path(experiment)
    freeze = read_json(experiment / "freeze.json")
    if freeze.get("status") != "pending_smoke" or freeze.get("execution_branch") != LLM_ONLY_BRANCH:
        raise ValueError("smoke requires the fresh pending LLM-only freeze candidate")
    if (experiment / "smoke_summary.json").exists() or (experiment / "smoke_schedule.jsonl").exists():
        raise ValueError("smoke evidence already exists; never rerun or overwrite it")
    if code_inventory(ROOT) != freeze["pre_smoke_code_inventory"]:
        raise ValueError("code/prompt/config inventory changed before smoke")
    from dotenv import load_dotenv
    from evaluation.s4_metrics import reduce_run
    from evaluation.s4_resources import RunTelemetry
    from workflow.review_graph import build_review_workflow
    from workflow.review_providers import GeminiPhysicalProvider, resolve_gemini_credential
    from evaluation.s5_smoke_budget import CumulativeSmokeBudget

    load_dotenv(ROOT / ".env")
    expected_credential_source = freeze["model_metadata"]["A-C"]["credential_source_variable"]
    key, credential_source = resolve_gemini_credential(
        expected_source=expected_credential_source)
    results = []
    totals = {"requests": 0, "prompt_tokens": 0, "output_tokens": 0,
        "total_tokens": 0, "cost_usd": 0.0}
    cumulative_budget = CumulativeSmokeBudget(freeze["prior_nonformal_spend"], SMOKE_LIMITS,
        input_price=INPUT_PRICE, output_price=OUTPUT_PRICE,
        authorization=freeze.get("smoke_budget_epoch_authorization"))
    verify_smoke_budget_epoch_authorization(freeze.get("smoke_budget_epoch_authorization"))
    if (freeze.get("smoke_budget_epoch_authorization") is not None and
            "smoke_budget_baseline" not in freeze):
        raise ValueError("authorized smoke epoch requires its frozen baseline")
    if freeze.get("smoke_budget_baseline", cumulative_budget.baseline) != cumulative_budget.baseline:
        raise ValueError("smoke budget baseline changed since preparation")
    if _prior_nonformal_spend(experiment) != freeze["prior_nonformal_spend"]:
        raise ValueError("historical smoke evidence or cumulative accounting changed before dispatch")
    smoke_root = experiment / "smokes"
    smoke_root.mkdir()
    append_event(experiment / "smoke_schedule.jsonl", {"kind": "credential_selection",
        "variable_name": credential_source, "credential_value_recorded": False})
    for arm in SMOKE_ARMS:
        formal = ReviewRunConfig.model_validate(freeze["configs"][arm])
        config = formal.model_copy(update={"run_kind": "smoke"})
        prior = cumulative_budget.prior
        arm_before = cumulative_budget.snapshot()["charged"]
        run_id = uuid4().hex
        run_dir = smoke_root / f"{SMOKE_CASE}-{arm}"
        append_event(experiment / "smoke_schedule.jsonl", {"kind": "claim", "condition": arm,
            "run_id": run_id, "run_path": str(run_dir.relative_to(experiment))})
        try:
            context = ContractContext.from_case(Path(load_plan(experiment)["case_root"]),
                SMOKE_CASE, condition=arm)
            provider = GeminiPhysicalProvider(api_key=key)
            cancel = Event()
            workflow = build_review_workflow(context, config=config, provider=provider,
                output_dir=run_dir, run_id=run_id, planned_id=None, cancel=cancel,
                cumulative_budget=cumulative_budget)
            with RunTelemetry(workflow.journal, cancel, enforce_gate=False):
                result = workflow.run()
            reduced = reduce_run(run_dir, condition=arm)
            observed_usage = {"requests": reduced["request_count"],
                "prompt_tokens": reduced["prompt_tokens"], "output_tokens": reduced["output_tokens"],
                "total_tokens": reduced["total_tokens"]}
            accounting = cumulative_budget.snapshot()
            totals = accounting["charged"]
            usage = {name: totals[name] - arm_before[name]
                     for name in ("requests", "prompt_tokens", "output_tokens", "total_tokens")}
            cost = round(totals["cost_usd"] - arm_before["cost_usd"], 9)
            row = {"condition": arm, "status": result["status"],
                "terminal_contract_passed": result["terminal_contract_passed"],
                "mock_only": result["mock_only"], "run_id": run_id,
                "run_path": str(run_dir), "result_path": str(run_dir / "result.json"),
                "result_sha256": file_hash(run_dir / "result.json"), **usage, "cost_usd": cost,
                "observed_provider_usage": observed_usage,
                "usage_incomplete": reduced["usage_incomplete"] or accounting["usage_incomplete"],
                "accounting_basis": accounting["accounting_basis"],
                "config": config.model_dump(mode="json"), "config_sha256": config.sha256}
            results.append(row)
            passed = (result["status"] == "completed" and result["terminal_contract_passed"] is True and
                result["mock_only"] is False and reduced["completed"] and
                not row["usage_incomplete"] and
                usage["requests"] <= 18 and usage["total_tokens"] <= 160000 and
                prior["requests"] + totals["requests"] <= SMOKE_LIMITS["requests"] and
                prior["total_tokens"] + totals["total_tokens"] <= SMOKE_LIMITS["total_tokens"] and
                prior["cost_usd"] + totals["cost_usd"] <= SMOKE_LIMITS["cost_usd"])
            append_event(experiment / "smoke_schedule.jsonl", {"kind": "result", **row,
                "passed": passed, "cumulative": dict(totals)})
            if not passed:
                summary = {"status": "failed", "failed_condition": arm, "results": results,
                    "actual": totals, "prior_nonformal_spend": freeze["prior_nonformal_spend"],
                    "usage_accounting": accounting,
                    "active_cumulative_smoke": accounting["active_cumulative"],
                    "budget_baseline": cumulative_budget.baseline,
                    "cumulative_live_smoke": {key: round(freeze["prior_nonformal_spend"][key] + totals[key], 9)
                        if key == "cost_usd" else freeze["prior_nonformal_spend"][key] + totals[key]
                        for key in ("requests", "total_tokens", "cost_usd")},
                    "code_inventory_unchanged": code_inventory(ROOT) == freeze["pre_smoke_code_inventory"]}
                write_json(experiment / "smoke_summary.json", summary)
                return summary
        except BaseException as exc:
            accounting = cumulative_budget.snapshot()
            totals = accounting["charged"]
            active_charge = {name: round(totals[name] - arm_before[name], 9)
                             if name == "cost_usd" else totals[name] - arm_before[name]
                             for name in totals}
            append_event(experiment / "smoke_schedule.jsonl", {"kind": "failure", "condition": arm,
                "error_type": type(exc).__name__, "message": str(exc)[:500],
                "active_arm_charged": active_charge, "usage_accounting": accounting})
            summary = {"status": "failed", "failed_condition": arm,
                "error_type": type(exc).__name__, "results": results, "actual": totals,
                "active_arm_charged": active_charge, "usage_accounting": accounting,
                "active_cumulative_smoke": accounting["active_cumulative"],
                "budget_baseline": cumulative_budget.baseline,
                "prior_nonformal_spend": freeze["prior_nonformal_spend"],
                "cumulative_live_smoke": {key: round(freeze["prior_nonformal_spend"][key] + totals[key], 9)
                    if key == "cost_usd" else freeze["prior_nonformal_spend"][key] + totals[key]
                    for key in ("requests", "total_tokens", "cost_usd")},
                "code_inventory_unchanged": code_inventory(ROOT) == freeze["pre_smoke_code_inventory"]}
            write_json(experiment / "smoke_summary.json", summary)
            return summary
    after = code_inventory(ROOT)
    unchanged = after == freeze["pre_smoke_code_inventory"]
    summary = {"status": "passed" if unchanged else "blocked_code_changed_after_smoke",
        "results": results, "actual": totals, "hard_limits": SMOKE_LIMITS,
        "usage_accounting": cumulative_budget.snapshot(),
        "active_cumulative_smoke": cumulative_budget.snapshot()["active_cumulative"],
        "budget_baseline": cumulative_budget.baseline,
        "prior_nonformal_spend": freeze["prior_nonformal_spend"],
        "cumulative_live_smoke": {key: round(freeze["prior_nonformal_spend"][key] + totals[key], 9)
            if key == "cost_usd" else freeze["prior_nonformal_spend"][key] + totals[key]
            for key in ("requests", "total_tokens", "cost_usd")},
        "code_inventory_unchanged": unchanged, "post_smoke_code_inventory": after,
        "paid_tools_used": False, "formal_runs_started": 0}
    write_json(experiment / "smoke_summary.json", summary)
    return summary


def joint_freeze(experiment: Path) -> dict:
    experiment = Path(experiment)
    freeze_path = experiment / "freeze.json"
    freeze = read_json(freeze_path)
    summary_path = experiment / "smoke_summary.json"
    summary = read_json(summary_path)
    current = code_inventory(ROOT)
    if (freeze.get("status") != "pending_smoke" or summary.get("status") != "passed" or
            not summary.get("code_inventory_unchanged") or
            current != freeze.get("pre_smoke_code_inventory") or
            current != summary.get("post_smoke_code_inventory")):
        raise ValueError("joint freeze prohibited: smoke failed or code/prompt/wire/schema/evaluation inventory changed")
    pending = experiment / "freeze.pending.before_joint_freeze.json"
    shutil.copyfile(freeze_path, pending)
    freeze.update(status="frozen", code_inventory=current,
        runtime_versions=runtime_inventory(), smoke_actual={"status": "passed", **summary["actual"]},
        jointly_frozen_conditions=list(SMOKE_ARMS),
        smoke_summary={"path": str(summary_path), "sha256": file_hash(summary_path)})
    for row in summary["results"]:
        path = Path(row["result_path"])
        freeze["preflight_reports"][row["condition"]] = _record(path)
    write_json(freeze_path, freeze, replace=True)
    append_event(experiment / "freeze_history.jsonl", {"kind": "joint_freeze",
        "execution_branch": LLM_ONLY_BRANCH, "conditions": list(SMOKE_ARMS),
        "pending_sha256": file_hash(pending), "frozen_sha256": file_hash(freeze_path),
        "smoke_summary_sha256": file_hash(summary_path)})
    gate = check_freeze(experiment)
    return {"status": "frozen" if gate["ready"] else "frozen_but_blocked",
        "freeze_sha256": file_hash(freeze_path), "formal_gate": gate,
        "formal_runs_started": status(experiment)["formal_runs_started"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--source-experiment", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--authorization", required=True, type=Path)
    p = commands.add_parser("smoke")
    p.add_argument("--experiment", required=True, type=Path)
    p = commands.add_parser("joint-freeze")
    p.add_argument("--experiment", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare(args.source_experiment, args.output_dir, args.authorization)
        elif args.command == "smoke":
            result = run_smokes(args.experiment)
        else:
            result = joint_freeze(args.experiment)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in ("prepared_pending_smoke", "passed", "frozen") else 2
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
