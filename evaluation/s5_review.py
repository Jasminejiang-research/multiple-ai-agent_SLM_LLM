"""Strict, versioned receipt of human CSVs; S4 remains the sole score calculator."""
from __future__ import annotations

import csv
from datetime import datetime
import math
from pathlib import Path
import shutil

from evaluation.s4_blind import (RATING_FIELDS, LEDGER_FIELDS, COVERAGE_FIELDS, import_human)
from evaluation.s4_io import contained, file_hash, read_csv, read_json, write_json
from evaluation.s4_runner import load_plan, status
from evaluation.s5_preparation import tree_inventory


def strict_csv(path, fields):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != set(fields):
            raise ValueError(f"{Path(path).name}: missing, extra or duplicate columns")
        rows = list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        raise ValueError(f"{Path(path).name}: malformed CSV row width")
    return rows


def _nonblank(value):
    return bool(isinstance(value, str) and value.strip())


def _provenance(row, *, required):
    for field in ("reviewer", "reviewed_at"):
        if required and not _nonblank(row.get(field)):
            raise ValueError("human reviewer/date required")
    if _nonblank(row.get("reviewed_at")):
        try:
            datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("reviewed_at must be an ISO date or datetime") from exc
    for field in ("rating_minutes", "claim_audit_minutes"):
        if row.get(field, "") != "":
            try:
                number = float(row[field])
            except ValueError as exc:
                raise ValueError("review minutes must be finite and nonnegative") from exc
            if not math.isfinite(number) or number < 0:
                raise ValueError("review minutes must be finite and nonnegative")


def check_review(experiment, pack):
    """Empty forms are pending; malformed or mismatched forms fail before any export."""
    experiment, pack = Path(experiment), Path(pack)
    public, private = pack / "reviewer", pack / "private"
    plan, state = load_plan(experiment), status(experiment)
    audit = read_json(private / "pack_audit.json")
    if audit["kind"] != plan["kind"]:
        raise ValueError("synthetic/formal review packs cannot mix")
    mapping = read_csv(private / "identity_mapping.csv")
    known = {r["anonymous_id"] for r in mapping}
    if len(known) != len(mapping) or any(not _nonblank(aid) for aid in known):
        raise ValueError("duplicate/empty private anonymous identity")
    if any(m["hidden_repeat"] not in ("True", "False") for m in mapping):
        raise ValueError("invalid hidden repeat flag")
    canonical = {m["anonymous_id"]: m for m in mapping if m["hidden_repeat"] == "False"}
    slots = {r["planned_id"]: r for r in state["rows"]}
    expected = {r["planned_id"] for r in slots.values() if r["scorable_output"] == "available"}
    if len({m["planned_id"] for m in canonical.values()}) != len(canonical) or {m["planned_id"] for m in canonical.values()} != expected:
        raise ValueError("review must include every scorable canonical output exactly once")
    if len(canonical) != audit["canonical_outputs"] or len(mapping) != audit["rating_copies"]:
        raise ValueError("review inventory differs from generated pack")
    for item in mapping:
        origin = canonical.get(item["canonical_anonymous_id"])
        if not origin or any(item[k] != origin[k] for k in ("planned_id", "run_id", "case_id", "condition")):
            raise ValueError("hidden repeat/canonical identity mismatch")
        slot = slots.get(item["planned_id"])
        if not slot or any(item[k] != slot[k] for k in ("run_id", "case_id", "condition")):
            raise ValueError("review pack belongs to different experiment outputs")
        if file_hash(contained(experiment, slot["run_path"]) / "events.jsonl") != item["source_event_sha256"]:
            raise ValueError("review source events changed")
        if file_hash(contained(public, f"outputs/{item['anonymous_id']}.md")) != item["anonymous_sha256"]:
            raise ValueError("anonymous output changed")
    ratings = strict_csv(public / "ratings.csv", RATING_FIELDS)
    completed = 0
    for row in ratings:
        values = [row[f"AQ{i}"] for i in range(1, 7)]
        filled = [v != "" for v in values]
        if any(filled) and not all(filled):
            raise ValueError("partial six-dimension rating; finish that row or leave all scores blank")
        if all(filled):
            if any(v not in ("1", "2", "3", "4", "5") for v in values):
                raise ValueError("six integer scores in 1..5 required")
            if any(not _nonblank(row[f"AQ{i}_rationale"]) for i in range(1, 7)):
                raise ValueError("six nonblank rating rationales required")
            completed += 1
        _provenance(row, required=all(filled))
    gold_exists = (public / "gold_ledger.csv").exists()
    if gold_exists != (public / "coverage.csv").exists():
        raise ValueError("Gold ledger and coverage must be submitted together")
    if gold_exists:
        if completed != len(mapping) or not mapping:
            raise ValueError("finish all blinded ratings before Gold phase")
        ledger = strict_csv(public / "gold_ledger.csv", LEDGER_FIELDS)
        coverage = strict_csv(public / "coverage.csv", COVERAGE_FIELDS)
        if len(coverage) != len(canonical) or {r["anonymous_id"] for r in coverage} != set(canonical):
            raise ValueError("coverage must contain every canonical output exactly once")
        seen = set()
        enums = dict(decision_critical=("yes", "no"), atomic_reviewed=("yes", "no"),
            human_claim_type=("factual", "assumption", "recommendation", "projection"),
            support_verdict=("sufficient", "partial_support", "none", "contradicted"),
            correct_assumption=("yes", "no"), high_impact=("yes", "no"))
        for row in ledger:
            if row["anonymous_id"] not in canonical:
                raise ValueError("Gold ledger may only contain canonical IDs, never hidden repeats")
            key = (row["anonymous_id"], row["candidate_id"])
            if key in seen or not _nonblank(row["candidate_id"]) or not _nonblank(row["claim_text"]) or not _nonblank(row["occurrences"]):
                raise ValueError("unique claim ID, claim text and output location required")
            seen.add(key)
            for field, allowed in enums.items():
                if row[field] != "" and row[field] not in allowed:
                    raise ValueError(f"invalid human field: {field}")
            _provenance(row, required=bool(row["rationale"] or row["support_verdict"]))
        if {a for a, _ in seen} != set(canonical):
            raise ValueError("candidate ledger inventory missing an output")
        for row in coverage:
            fields = ("all_sections_and_financial_rows_checked", "atomization_and_dedup_complete", "ledger_complete")
            if any(row[k] not in ("", "yes", "no") for k in fields):
                raise ValueError("invalid coverage confirmation")
            _provenance(row, required=all(row[k] == "yes" for k in fields))
    # Existing S4 validates identity sets, numeric formula, support semantics and duplicates.
    human, repeats = import_human(pack)
    ratings_complete = bool(mapping) and completed == len(mapping)
    gold_complete = bool(human) and all(v["state"] != "pending_human_review" for row in human.values() for v in row["claims"].values())
    return dict(valid=True, kind=plan["kind"], state="review_complete" if ratings_complete and gold_complete else "waiting_for_human_review",
        canonical_outputs=len(canonical), rating_copies=len(mapping), completed_rating_copies=completed,
        ratings_complete=ratings_complete, gold_complete=gold_complete, hidden_repeat_count=len(repeats),
        human_fields_generated=0, additional_model_calls=0)


def import_review(experiment, pack, output, *, ratings=None, gold_ledger=None, coverage=None):
    """Copy original packet and returned CSVs to a NEW version, preserving all originals."""
    pack, output = Path(pack).resolve(), Path(output).resolve()
    if output.is_relative_to(pack) or output.is_relative_to(Path(experiment).resolve()):
        raise ValueError("review receipt must be outside source pack and experiment")
    if bool(gold_ledger) != bool(coverage):
        raise ValueError("Gold ledger and coverage must be submitted together")
    sources = tree_inventory(pack)
    submitted = {name: Path(path).resolve() for name, path in
        (("ratings.csv", ratings), ("gold_ledger.csv", gold_ledger), ("coverage.csv", coverage)) if path is not None}
    submitted_hashes = {name: file_hash(path) for name, path in submitted.items()}
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(pack, output / "pack")
    for name, path in submitted.items():
        shutil.copyfile(path, output / "pack" / "reviewer" / name)
    if sources != tree_inventory(pack) or submitted_hashes != {name: file_hash(path) for name, path in submitted.items()}:
        write_json(output / "receipt.json", dict(valid=False, reason="source changed during import"))
        raise ValueError("concurrent source changes during review import")
    try:
        review = check_review(experiment, output / "pack")
    except (ValueError, OSError, KeyError) as exc:
        write_json(output / "receipt.json", dict(valid=False, reason=str(exc), source_files=sources, submitted=submitted_hashes))
        raise ValueError(f"review rejected; original files retained, rejection receipt: {output / 'receipt.json'}; {exc}") from exc
    write_json(output / "receipt.json", dict(**review, source_pack=str(pack), source_files=sources,
        submitted=submitted_hashes, accepted_files=tree_inventory(output / "pack")))
    return dict(**review, accepted_pack=str(output / "pack"))
