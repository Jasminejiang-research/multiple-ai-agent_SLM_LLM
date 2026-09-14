"""S5 evidence directory assembled from S4 exports, with no generation or scoring."""
from pathlib import Path
import shutil

from evaluation.s4_blind import build_blind_pack
from evaluation.s4_export import export_experiment
from evaluation.s4_io import contained, file_hash, read_csv, read_json, write_csv, write_json
from evaluation.s4_runner import load_plan, status
from evaluation.s5_preparation import tree_inventory, validate_inputs, verify_snapshot
from evaluation.s5_review import check_review


def validate_formal_origin(row, reduced):
    """Do not lose setup failures merely because no run-start/config was emitted."""
    config, result = reduced.get("config") or {}, reduced.get("result") or {}
    if config.get("run_kind") not in (None, "formal") or result.get("mock_only") is True:
        raise ValueError("formal run provenance contains synthetic/non-formal output")
    if row["scorable_output"] == "available" or row["execution"] == "succeeded":
        if config.get("run_kind") != "formal" or result.get("mock_only") is not False:
            raise ValueError("scorable formal output lacks explicit formal/non-mock provenance")


def export_bundle(experiment, output, *, human_pack=None, reproduction=None, allow_synthetic=False, figures=True):
    experiment, output = Path(experiment).resolve(), Path(output).resolve()
    plan, state = load_plan(experiment), status(experiment)
    freeze = read_json(experiment / "freeze.json")
    llm_only = freeze.get("execution_branch") == "llm_only_after_D_no_go"
    synthetic = plan["kind"] == "synthetic_rehearsal"
    if synthetic and not allow_synthetic:
        raise ValueError("synthetic export requires --allow-synthetic and stays non-formal")
    if (output.is_relative_to(experiment) or (human_pack and output.is_relative_to(Path(human_pack).resolve())) or
        (reproduction and output.is_relative_to(Path(reproduction).resolve()))):
        raise ValueError("export must use a new directory outside source experiment/pack")
    if state["lock_present"] or state["journal_truncated"] or any(r["execution"] in ("running", "interrupted_unknown") for r in state["rows"]):
        raise ValueError("active/uncertain run; reconcile before evidence export")
    if not any(r["run_id"] for r in state["rows"]):
        raise ValueError("no runs yet; use S4 dry export for preparation, do not create S5 result placeholders")
    inputs = validate_inputs(experiment)
    if not inputs["valid"]:
        raise ValueError("invalid export inputs: " + "; ".join(inputs["errors"]))
    if not synthetic:
        if not reproduction:
            raise ValueError("formal evidence export requires the pre-run reproducibility snapshot")
        capture = read_json(Path(reproduction) / "reproducibility.json")
        if capture["kind"] != "formal_plan" or capture["state"] != "frozen_configuration_captured":
            raise ValueError("formal export cannot use a synthetic or unfrozen preparation snapshot")
        if capture["files"].get("experiment/plan.json") != file_hash(experiment / "plan.json"):
            raise ValueError("reproducibility snapshot belongs to another experiment")
        if capture["files"].get("experiment/freeze.json") != file_hash(experiment / "freeze.json"):
            raise ValueError("frozen configuration changed since reproduction capture")
        # A synthetic workflow may never be relabeled as formal by editing plan metadata.
        from evaluation.s4_metrics import reduce_run
        for row in state["rows"]:
            if row["run_path"]:
                reduced = reduce_run(contained(experiment, row["run_path"]), condition=row["condition"])
                validate_formal_origin(row, reduced)
    if reproduction and not verify_snapshot(reproduction)["valid"]:
        raise ValueError("reproducibility snapshot integrity failed")
    review = check_review(experiment, human_pack) if human_pack else None
    case_root = Path(plan["case_root"])
    # Hash before reading, then recheck after export to reject concurrent mutations.
    before = tree_inventory(experiment)
    review_before = tree_inventory(human_pack) if human_pack else None
    input_before = tree_inventory(case_root)
    output.mkdir(parents=True, exist_ok=False)
    metrics = export_experiment(experiment, output / "derived", human_pack=human_pack, figures=figures)
    if human_pack:
        shutil.copytree(human_pack, output / "human_pack")
    else:
        build_blind_pack(experiment, output / "human_pack")
    shutil.copyfile(case_root / "EVALUATION_RUBRIC.md", output / "01_evaluation_protocol_rubric.md")
    shutil.copyfile(case_root / "protocol.json", output / "01_evaluation_protocol.json")
    comparison_text = ("Approved LLM-only branch: formal execution is A/B/C only; report B−A and C−B. "
        "C−D is unavailable because both D slots are fixed as not_run_preflight_no_go; no successful subset is substituted. "
        if llm_only else "Comparisons B−A, C−B, C−D. ")
    (output / "01_evaluation_protocol.md").write_text(
        "# Evaluation protocol\n\nTwo cases × A–D, eight planned slots; independent n=2. "
        + comparison_text + "See the adjacent exact protocol JSON, approved scope decision and rubric. "
        "All failures and missing values are retained; no replacement runs.\n", encoding="utf-8")
    if llm_only:
        shutil.copyfile(experiment / "scope_decision.json", output / "01_approved_scope_decision.json")
    evidence = []
    for case_id in plan["rows"][0]["case_id"], plan["rows"][4]["case_id"]:
        case = read_json(case_root / "cases" / case_id / "case.json")
        packet = read_json(case_root / "cases" / case_id / "packet.json")
        for source in packet["sources"]:
            evidence.append({**source, "case_id": case_id, "brief_sha256": case["brief_sha256"], "packet_sha256": case["packet_sha256"]})
    write_csv(output / "02_frozen_cases_and_evidence_manifest.csv", evidence)
    write_csv(output / "03_run_manifest.csv", state["rows"])
    run_rows = read_csv(output / "derived/run_metrics.csv")
    role_rows = read_csv(output / "derived/role_metrics.csv")
    write_csv(output / "04_agent_and_system_metrics.csv", [dict(record_type="run", **r) for r in run_rows] +
              [dict(record_type="role", **r) for r in role_rows])
    shutil.copyfile(output / "human_pack/reviewer/ratings.csv", output / "05_blind_evaluation.csv")
    gold = output / "human_pack/reviewer/gold_ledger.csv"
    if gold.exists():
        shutil.copyfile(gold, output / "06_claim_evidence_gold_ledger.csv")
    else:
        candidates = output / "human_pack/private/gold_ledger_candidates.csv"
        if candidates.exists():
            shutil.copyfile(candidates, output / "06_claim_evidence_gold_ledger_UNJUDGED.csv")
    # Gold candidates remain private until hidden-repeat ratings are complete.
    shutil.copyfile(output / "derived/results_tables.md", output / "07_results_tables.md")
    if figures:
        shutil.copytree(output / "derived/figures", output / "08_figures")
    failures = [r for r in state["rows"] if r["execution"] != "succeeded" or r["needs_human_review"]]
    (output / "09_failure_analysis.md").write_text("# Failure and manual-review status\n\n" +
        "\n".join(f"- {r['planned_id']}: {r['execution']}; terminal={r['terminal_contract']}; "
                  f"scorable={r['scorable_output']}; manual={r['needs_human_review']}; reason={r['failure_reason']}" for r in failures) +
        "\n\nOriginal events and failures remain at the paths in 03_run_manifest.csv and archive_manifest.json.\n", encoding="utf-8")
    if reproduction:
        shutil.copytree(reproduction, output / "reproduction")
        shutil.copyfile(Path(reproduction) / "11_reproducibility_manifest.md", output / "11_reproducibility_manifest.md")
    else:
        (output / "11_reproducibility_manifest.md").write_text("# Synthetic engineering export\n\nNo formal frozen reproduction snapshot supplied. See archive_manifest.json for source hashes.\n", encoding="utf-8")
    examples = output / "example_outputs"
    examples.mkdir()
    # Raw internal exports can include identity; never send this directory to a blind reviewer.
    example_index = []
    for row in state["rows"]:
        if not row["run_path"]:
            continue
        directory = contained(experiment, row["run_path"]) / "internal_export"
        if directory.is_dir():
            shutil.copytree(directory, examples / row["planned_id"])
            example_index.append(dict(planned_id=row["planned_id"], run_id=row["run_id"], source=str(directory)))
    write_json(examples / "index.json", example_index)
    stable = before == tree_inventory(experiment) and input_before == tree_inventory(case_root) and (
        not human_pack or review_before == tree_inventory(human_pack))
    report = dict(version="s5-export-v1", valid=stable, kind=plan["kind"], formal_results=not synthetic,
        state="synthetic_engineering_only" if synthetic else "waiting_for_human_review" if not review or review["state"] != "review_complete" else "human_review_imported",
        experiment=str(experiment), inputs=before, case_files=input_before, human_files=review_before,
        review=review, automatic_export=metrics, all_planned_rows=8, model_calls_in_export=0,
        gold_state="released" if gold.exists() else "unjudged_candidate_ledger_generated_private; reviewer release withheld until blind ratings complete",
        comparison_policy=freeze.get("comparison_policy"),
        output_files=tree_inventory(output))
    write_json(output / "archive_manifest.json", report)
    if synthetic:
        (output / "SYNTHETIC_ONLY.txt").write_text("SYNTHETIC ENGINEERING DATA. Never include in formal experiment results.\n", encoding="utf-8")
    if not stable:
        raise ValueError("source changed during export; archive marked invalid, preserve and retry in a new directory")
    return dict(valid=True, kind=plan["kind"], state=report["state"], output=str(output), model_calls=0)
