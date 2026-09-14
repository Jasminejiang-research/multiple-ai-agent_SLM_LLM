"""Lightweight offline S5 checks using preserved S4 SYNTHETIC data, no providers.

All filled review rows below are test-only arithmetic fixtures, never human verdicts.
"""
from pathlib import Path
import shutil
import socket
from types import SimpleNamespace

import pytest

from evaluation.s4_blind import build_blind_pack, release_gold, import_human
from evaluation.s4_io import read_csv, read_json, write_csv, write_json
from evaluation.s4_runner import ROOT, create_experiment
from evaluation.s5 import main
from evaluation.s5_preparation import capture_reproduction, verify_snapshot, validate_inputs, tree_inventory
from evaluation.s5_review import check_review, import_review, strict_csv
from evaluation.s5_export import export_bundle, validate_formal_origin

SYNTHETIC = ROOT / "docs/final_sprint/s4-v1/synthetic_rehearsal"


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("S5 offline test attempted a network/model connection")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)


@pytest.fixture
def pack(tmp_path):
    path = tmp_path / "pack"
    build_blind_pack(SYNTHETIC, path)
    return path


def fill_test_ratings(pack):
    rows = read_csv(pack / "reviewer/ratings.csv")
    for row in rows:
        row.update(reviewer="SYNTHETIC UNIT TEST ONLY", reviewed_at="2000-01-01")
        for i, score in enumerate([5, 4, 5, 4, 5, 4], 1):
            row[f"AQ{i}"] = str(score)
            row[f"AQ{i}_rationale"] = "TEST FIXTURE; NOT A HUMAN RATING"
    write_csv(pack / "reviewer/ratings.csv", rows)


def fill_test_gold(pack):
    fill_test_ratings(pack)
    release_gold(pack)
    ledger = read_csv(pack / "reviewer/gold_ledger.csv")
    counts = {}
    for row in ledger:
        aid = row["anonymous_id"]
        index = counts.get(aid, 0)
        counts[aid] = index + 1
        row.update(decision_critical="yes" if index < 3 else "no", atomic_reviewed="yes",
            human_claim_type="factual", support_verdict="none", correct_assumption="no", high_impact="yes",
            rationale="SYNTHETIC UNIT TEST; NOT A HUMAN VERDICT", reviewer="TEST ONLY", reviewed_at="2000-01-01")
        if index == 0:
            row.update(support_verdict="sufficient", human_evidence_locations="TEST EVIDENCE LOCATION")
        elif index == 1:
            row.update(human_claim_type="assumption", model_claim_type='["assumption"]', correct_assumption="yes", high_impact="no")
        elif index == 2:
            row.update(support_verdict="partial_support", human_evidence_locations="TEST PARTIAL LOCATION")
    write_csv(pack / "reviewer/gold_ledger.csv", ledger)
    rows = read_csv(pack / "reviewer/coverage.csv")
    for row in rows:
        row.update(all_sections_and_financial_rows_checked="yes", atomization_and_dedup_complete="yes", ledger_complete="yes",
                   reviewer="TEST ONLY", reviewed_at="2000-01-01")
    write_csv(pack / "reviewer/coverage.csv", rows)


def test_s5_has_no_execute_or_freeze_command():
    for command in ("execute", "freeze", "rehearsal"):
        with pytest.raises(SystemExit) as exc:
            main([command])
        assert exc.value.code == 2


def test_legacy_utf16_requirements_and_credential_redaction(tmp_path, monkeypatch):
    from evaluation.s5_preparation import dependency_check
    (tmp_path / "slm").mkdir()
    (tmp_path / "requirements.txt").write_text("pydantic>=2\n", encoding="utf-16")
    (tmp_path / "slm/requirements-slm.txt").write_text("openai>=1\n", encoding="utf-8")
    (tmp_path / ".env").write_text("GEMINI_API_KEY=SYNTHETIC_SECRET_MUST_NOT_APPEAR\n")
    monkeypatch.setattr("evaluation.s5_preparation.subprocess.run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout="No broken requirements found.", stderr=""))
    result = dependency_check(tmp_path)
    assert result["status"] == "passed" and result["gemini_credential_present"]
    assert "SYNTHETIC_SECRET_MUST_NOT_APPEAR" not in str(result)


def test_pending_inputs_no_approval_written(tmp_path):
    dry = tmp_path / "dry"
    create_experiment(dry)
    before = tree_inventory(dry)
    result = validate_inputs(dry)
    assert result["valid"] and not result["formal_gate"]["ready"]
    assert main(["check-inputs", "--experiment", str(dry)]) == 2
    assert tree_inventory(dry) == before and not (dry / "schedule.jsonl").exists()


@pytest.mark.parametrize("damage", ["canonical", "brief", "kind"])
def test_corrupt_plan_rejected(tmp_path, damage):
    dry = tmp_path / "dry"
    create_experiment(dry)
    plan = read_json(dry / "plan.json")
    if damage == "canonical":
        plan["rows"][0]["canonical"] = False
    elif damage == "brief":
        plan["rows"][0]["brief_sha256"] = "0" * 64
    else:
        plan["kind"] = "renamed_synthetic"
    write_json(dry / "plan.json", plan, replace=True)
    assert not validate_inputs(dry)["valid"]


def test_snapshot_records_actual_bytes_and_detects_damage(tmp_path, monkeypatch):
    root, dry, snapshot = tmp_path / "source", tmp_path / "dry", tmp_path / "snapshot"
    (root / "slm").mkdir(parents=True)
    (root / "app.py").write_text("# uncommitted source\n")
    (root / "requirements.txt").write_text("")
    (root / "slm/Modelfile.test").write_text("# synthetic model configuration\n")
    (root / ".env").write_text("GEMINI_API_KEY=DO_NOT_COPY_TEST_SECRET")
    monkeypatch.setattr("evaluation.s5_preparation.dependency_check", lambda root: {"status": "test_only"})
    create_experiment(dry)
    result = capture_reproduction(dry, snapshot, root=root)
    assert result["status"] == "preparation_only_not_frozen"
    assert verify_snapshot(snapshot)["valid"]
    assert (snapshot / "source/slm/Modelfile.test").exists()
    assert not (snapshot / "source/.env").exists()
    assert (snapshot / "source/app.py").read_text() == "# uncommitted source\n"
    with pytest.raises(FileExistsError):
        capture_reproduction(dry, snapshot, root=root)
    (snapshot / "source/app.py").write_text("changed")
    assert not verify_snapshot(snapshot)["valid"]
    assert main(["verify-snapshot", "--snapshot", str(snapshot)]) == 2


def test_empty_review_is_pending_and_immutable(pack):
    before = tree_inventory(pack)
    result = check_review(SYNTHETIC, pack)
    assert result["completed_rating_copies"] == 0 and result["state"] == "waiting_for_human_review"
    assert main(["check-review", "--experiment", str(SYNTHETIC), "--pack", str(pack), "--require-complete", "ratings"]) == 2
    assert tree_inventory(pack) == before


@pytest.mark.parametrize("field,value", [("AQ1", "4"), ("AQ1", "NaN"), ("rating_minutes", "nan"),
    ("rating_minutes", "-1"), ("reviewed_at", "not a date")])
def test_invalid_partial_ratings_rejected(pack, field, value):
    rows = read_csv(pack / "reviewer/ratings.csv")
    rows[0][field] = value
    write_csv(pack / "reviewer/ratings.csv", rows)
    with pytest.raises(ValueError):
        check_review(SYNTHETIC, pack)


@pytest.mark.parametrize("damage", ["extra_column", "duplicate_column", "ragged_row"])
def test_malformed_csv_rejected(tmp_path, damage):
    path = tmp_path / "bad.csv"
    path.write_text({"extra_column": "a,b,c\n1,2,3\n", "duplicate_column": "a,a\n1,2\n", "ragged_row": "a,b\n1,2,3\n"}[damage])
    with pytest.raises(ValueError):
        strict_csv(path, ["a", "b"])


def test_missing_identity_rejected(pack):
    rows = read_csv(pack / "reviewer/ratings.csv")
    write_csv(pack / "reviewer/ratings.csv", rows[:-1])
    with pytest.raises(ValueError, match="missing anonymous"):
        check_review(SYNTHETIC, pack)


def test_versioned_import_keeps_sources_and_rejection_receipt(pack, tmp_path):
    before = tree_inventory(pack)
    accepted = import_review(SYNTHETIC, pack, tmp_path / "receipt")
    assert accepted["state"] == "waiting_for_human_review" and tree_inventory(pack) == before
    with pytest.raises(FileExistsError):
        import_review(SYNTHETIC, pack, tmp_path / "receipt")
    invalid = tmp_path / "returned.csv"
    rows = read_csv(pack / "reviewer/ratings.csv")
    rows[0]["AQ1"] = "2"
    write_csv(invalid, rows)
    with pytest.raises(ValueError, match="review rejected"):
        import_review(SYNTHETIC, pack, tmp_path / "rejected", ratings=invalid)
    assert not read_json(tmp_path / "rejected/receipt.json")["valid"]
    assert tree_inventory(pack) == before


def test_complete_test_fixture_reuses_exact_formulas(pack):
    fill_test_gold(pack)
    result = check_review(SYNTHETIC, pack)
    assert result["ratings_complete"] and result["gold_complete"] and result["hidden_repeat_count"] == 2
    human, repeats = import_human(pack)
    assert len(human) == 8 and len(repeats) == 2
    for row in human.values():
        assert row["academic_quality"] == pytest.approx(88.75)
        assert row["claims"]["claim_grounding"]["value"] == pytest.approx(1 / 3)
        assert row["claims"]["assumption_transparency"]["value"] == .5
        assert row["claims"]["high_impact_unsupported"]["value"] == .5


@pytest.mark.parametrize("damage", ["hidden_repeat", "empty_text", "duplicate", "invalid_verdict", "missing_coverage"])
def test_invalid_gold_rejected(pack, damage):
    fill_test_gold(pack)
    rows = read_csv(pack / "reviewer/gold_ledger.csv")
    if damage == "hidden_repeat":
        mapping = read_csv(pack / "private/identity_mapping.csv")
        rows[0]["anonymous_id"] = next(m["anonymous_id"] for m in mapping if m["hidden_repeat"] == "True")
    elif damage == "empty_text":
        rows[0]["claim_text"] = " "
    elif damage == "duplicate":
        rows.append(rows[0])
    elif damage == "invalid_verdict":
        rows[0]["support_verdict"] = "probably"
    else:
        (pack / "reviewer/coverage.csv").unlink()
    write_csv(pack / "reviewer/gold_ledger.csv", rows)
    with pytest.raises(ValueError):
        check_review(SYNTHETIC, pack)


def test_synthetic_cannot_mix_with_formal_and_unstarted_has_no_results(pack, tmp_path):
    dry = tmp_path / "dry"
    create_experiment(dry)
    with pytest.raises(ValueError, match="cannot mix"):
        check_review(dry, pack)
    with pytest.raises(ValueError, match="no runs yet"):
        export_bundle(dry, tmp_path / "unstarted")
    with pytest.raises(ValueError, match="allow-synthetic"):
        export_bundle(SYNTHETIC, tmp_path / "bad")
    assert not (tmp_path / "unstarted").exists() and not (tmp_path / "bad").exists()


def test_early_failure_missing_metadata_is_retained_without_accepting_mock_outputs():
    failed = dict(execution="failed", scorable_output="not_available")
    validate_formal_origin(failed, {"config": None, "result": None})
    with pytest.raises(ValueError, match="synthetic/non-formal"):
        validate_formal_origin(failed, {"config": {"run_kind": "fixture"}, "result": None})
    with pytest.raises(ValueError, match="provenance"):
        validate_formal_origin(dict(execution="failed", scorable_output="available"), {"config": {}, "result": {}})


def test_synthetic_export_complete_layout_and_pending_gold(pack, tmp_path):
    before = tree_inventory(SYNTHETIC)
    out = tmp_path / "export"
    result = export_bundle(SYNTHETIC, out, human_pack=pack, allow_synthetic=True, figures=False)
    assert result["state"] == "synthetic_engineering_only" and (out / "SYNTHETIC_ONLY.txt").exists()
    assert len(read_csv(out / "03_run_manifest.csv")) == 8
    assert not (out / "06_claim_evidence_gold_ledger.csv").exists()
    assert len(read_json(out / "example_outputs/index.json")) == 8
    assert all(r["academic_quality"] == "" for r in read_csv(out / "derived/run_metrics.csv"))
    assert tree_inventory(SYNTHETIC) == before
    with pytest.raises(FileExistsError):
        export_bundle(SYNTHETIC, out, allow_synthetic=True, figures=False)


def test_test_only_gold_export_pairs_no_reexecution(pack, tmp_path):
    fill_test_gold(pack)
    out = tmp_path / "reviewed_export"
    export_bundle(SYNTHETIC, out, human_pack=pack, allow_synthetic=True, figures=False)
    assert (out / "06_claim_evidence_gold_ledger.csv").exists()
    quality = [r for r in read_csv(out / "derived/paired_summary.csv") if r["metric"] == "academic_quality"]
    assert len(quality) == 3 and all(r["complete_pairs"] == "2" and float(r["mean_difference"]) == 0 for r in quality)
