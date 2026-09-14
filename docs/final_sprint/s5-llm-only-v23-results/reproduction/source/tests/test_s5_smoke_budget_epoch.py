"""Offline accounting for the explicitly authorized v20 smoke budget epoch."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from evaluation.s5_smoke_budget import (
    CumulativeSmokeBudget, resolve_smoke_budget_baseline,
)
from workflow.review_runtime import SharedBudgetStop


LIMITS = dict(requests=54, total_tokens=480000, cost_usd=1.2)


class Journal:
    def __init__(self):
        self.events = []

    def emit(self, kind, payload):
        self.events.append((kind, payload))


def record(version, requests, total_tokens, cost_usd):
    return dict(path=f"docs/final_sprint/s5-llm-only-v{version}/smoke_summary.json",
        sha256=f"{version:064x}", requests=requests, total_tokens=total_tokens,
        cost_usd=cost_usd)


def prior(*records):
    return dict(records=list(records), requests=sum(r["requests"] for r in records),
        total_tokens=sum(r["total_tokens"] for r in records),
        cost_usd=round(sum(r["cost_usd"] for r in records), 9))


def authorization():
    return dict(version="s5-smoke-budget-epoch-v1", approved=True,
        starts_at_experiment_version=20, preserve_lifetime_history=True,
        unchanged_hard_limits=deepcopy(LIMITS),
        authorization_record=dict(path="/scope/LLM_ONLY_S5_V20_BUDGET_EPOCH_AUTHORIZATION.json",
            sha256="a" * 64))


def latest_prior():
    return prior(record(19, 34, 207948, .292885), record(20, 5, 29038, .0335802))


def test_actual_v20_partition_preserves_every_record_and_total_without_mutation():
    historical, decision = latest_prior(), authorization()
    before, approval_before = deepcopy(historical), deepcopy(decision)
    result = resolve_smoke_budget_baseline(historical, decision)
    assert result["mode"] == "authorized_epoch"
    assert result["active_prior"] == dict(requests=5, total_tokens=29038, cost_usd=.0335802)
    assert result["excluded_prior"] == dict(requests=34, total_tokens=207948, cost_usd=.292885)
    assert result["lifetime_prior"] == dict(requests=39, total_tokens=236986, cost_usd=.3264652)
    assert result["active_record_paths"] == [historical["records"][1]["path"]]
    assert result["excluded_record_paths"] == [historical["records"][0]["path"]]
    assert historical == before and decision == approval_before
    result["authorization_record"]["path"] = "cannot-mutate-original.json"
    assert decision == approval_before


def test_without_authorization_all_lifetime_history_still_counts():
    historical = prior(record(19, 54, 479000, 1.0), record(20, 5, 29038, .0335802))
    baseline = resolve_smoke_budget_baseline(historical)
    assert baseline["mode"] == "lifetime"
    assert baseline["active_prior"] == baseline["lifetime_prior"]
    budget = CumulativeSmokeBudget(historical, LIMITS)
    with pytest.raises(SharedBudgetStop, match="hard-limit"):
        budget.check_request(estimated_tokens=1000)


def test_explicit_epoch_admits_same_history_and_keeps_both_audited_totals():
    historical = prior(record(19, 54, 479000, 1.0), record(20, 5, 29038, .0335802))
    budget, journal = CumulativeSmokeBudget(historical, LIMITS, authorization=authorization()), Journal()
    budget.reserve_request(attempt_id="v21-first", estimated_tokens=1000, journal=journal)
    budget.record_usage(attempt_id="v21-first", event=dict(prompt_tokens=100,
        output_tokens=200, total_tokens=400), journal=journal)
    snapshot = budget.snapshot()
    assert snapshot["charged"]["cost_usd"] == .00078
    assert snapshot["active_cumulative"] == dict(requests=6, total_tokens=29438, cost_usd=.0343602)
    assert snapshot["lifetime_cumulative"] == dict(requests=60, total_tokens=508438, cost_usd=1.0343602)
    assert len(journal.events) == 2
    for kind, event in journal.events:
        assert kind == "cumulative_smoke_budget"
        assert event["budget_baseline"]["authorization_record"] == authorization()["authorization_record"]
        assert event["budget_baseline"]["lifetime_prior"]["requests"] == 59


@pytest.mark.parametrize("key,value", [("requests",54), ("total_tokens",479001), ("cost_usd",1.1975001)])
def test_active_epoch_enforces_every_unchanged_next_request_boundary(key, value):
    active = dict(requests=0, total_tokens=0, cost_usd=0)
    active[key] = value
    historical = prior(record(19, 54, 480000, 1.2), record(20, **active))
    budget, journal = CumulativeSmokeBudget(historical, LIMITS, authorization=authorization()), Journal()
    with pytest.raises(SharedBudgetStop, match="hard-limit"):
        budget.reserve_request(attempt_id="blocked", estimated_tokens=1000, journal=journal)
    assert not journal.events and budget.snapshot()["charged"]["requests"] == 0


def test_future_versions_remain_inside_epoch_instead_of_resetting_each_retry():
    historical = prior(*latest_prior()["records"], record(21, 49, 100000, .25))
    baseline = resolve_smoke_budget_baseline(historical, authorization())
    assert baseline["active_prior"]["requests"] == 54
    assert len(baseline["active_record_paths"]) == 2
    with pytest.raises(SharedBudgetStop):
        CumulativeSmokeBudget(historical, LIMITS, authorization=authorization()).check_request(estimated_tokens=1)


@pytest.mark.parametrize("field,value", [("version","wrong"), ("approved",False),
    ("approved",1), ("starts_at_experiment_version",21), ("preserve_lifetime_history",False),
    ("unchanged_hard_limits",dict(requests=55,total_tokens=480000,cost_usd=1.2)),
    ("authorization_record",None)])
def test_unapproved_unversioned_or_expanded_authority_is_rejected(field, value):
    decision = authorization()
    decision[field] = value
    with pytest.raises(ValueError):
        resolve_smoke_budget_baseline(latest_prior(), decision)


@pytest.mark.parametrize("mutation", ["total_mismatch", "duplicate", "missing_v20", "bad_path",
    "bad_hash", "negative", "nonfinite", "unknown", "pending"])
def test_inconsistent_or_uncertain_historical_inventory_cannot_start_epoch(mutation):
    historical = latest_prior()
    if mutation == "total_mismatch":
        historical["requests"] += 1
    elif mutation == "duplicate":
        historical = prior(*historical["records"], historical["records"][1])
    elif mutation == "missing_v20":
        historical = prior(historical["records"][0])
    elif mutation == "bad_path":
        historical["records"][0]["path"] = "../s5-llm-only-v19/smoke_summary.json"
    elif mutation == "bad_hash":
        historical["records"][0]["sha256"] = "not-a-hash"
    elif mutation == "negative":
        historical["records"][0]["requests"] = -1
    elif mutation == "nonfinite":
        historical["records"][0]["cost_usd"] = float("nan")
    elif mutation == "unknown":
        historical["records"][0]["usage_accounting"] = dict(usage_incomplete=True)
    else:
        historical["pending_attempt_ids"] = ["unsettled-historic-call"]
    with pytest.raises(ValueError):
        resolve_smoke_budget_baseline(historical, authorization())


def test_unknown_new_epoch_call_retains_reservation_and_stops_both_accountings():
    budget, journal = CumulativeSmokeBudget(latest_prior(), LIMITS, authorization=authorization()), Journal()
    budget.reserve_request(attempt_id="unknown", estimated_tokens=1000, journal=journal)
    budget.record_usage(attempt_id="unknown", event=dict(prompt_tokens=None,
        output_tokens=None,total_tokens=None), journal=journal)
    snapshot = budget.snapshot()
    assert snapshot["usage_incomplete"]
    assert snapshot["charged"]["total_tokens"] == 1000
    assert snapshot["active_cumulative"] == dict(requests=6, total_tokens=30038, cost_usd=.0360802)
    assert snapshot["lifetime_cumulative"] == dict(requests=40, total_tokens=237986, cost_usd=.3289652)
    with pytest.raises(SharedBudgetStop, match="unresolved"):
        budget.check_request(estimated_tokens=1)


@pytest.mark.parametrize("limits,input_price,output_price", [
    (dict(requests=55,total_tokens=480000,cost_usd=1.2),.30,2.50),
    (LIMITS,.10,2.50), (LIMITS,.30,2.00)])
def test_epoch_does_not_authorize_higher_caps_or_changed_cost_rates(limits,input_price,output_price):
    with pytest.raises(ValueError,match="hard limits or token prices"):
        CumulativeSmokeBudget(latest_prior(),limits,input_price=input_price,
            output_price=output_price,authorization=authorization())


def write_authority(tmp_path):
    from evaluation.s4_io import file_hash
    decision = authorization()
    record_value = {key: value for key, value in decision.items() if key != "authorization_record"}
    record_value["user_message_verbatim"] = "Start the unchanged active allowance at v20; retain previous spend."
    path = tmp_path / "epoch-authority.json"
    path.write_text(json.dumps(record_value), encoding="utf-8")
    decision["authorization_record"] = dict(path=str(path), sha256=file_hash(path))
    return decision, path, record_value


def test_external_authority_file_and_hash_are_verified_offline(tmp_path):
    from evaluation.s4_runner import verify_smoke_budget_epoch_authorization
    decision, _, _ = write_authority(tmp_path)
    verify_smoke_budget_epoch_authorization(decision)
    assert resolve_smoke_budget_baseline(latest_prior(), decision)["mode"] == "authorized_epoch"
    verify_smoke_budget_epoch_authorization(None)  # Legacy configurations retain lifetime accounting.


@pytest.mark.parametrize("mutation", ["missing_file", "bad_hash", "file_tamper", "copy_tamper",
    "empty_user_message", "approval_removed", "version_downgraded"])
def test_external_authority_tamper_or_downgrade_is_rejected(tmp_path, mutation):
    from evaluation.s4_io import file_hash
    from evaluation.s4_runner import verify_smoke_budget_epoch_authorization
    decision, path, value = write_authority(tmp_path)
    if mutation == "missing_file":
        decision["authorization_record"]["path"] = str(tmp_path / "absent.json")
    elif mutation == "bad_hash":
        decision["authorization_record"]["sha256"] = "0" * 64
    elif mutation == "file_tamper":
        path.write_text(json.dumps({**value,"approved":False}), encoding="utf-8")
    elif mutation == "copy_tamper":
        decision["starts_at_experiment_version"] = 21
    else:
        if mutation == "empty_user_message":
            value["user_message_verbatim"] = "  "
        elif mutation == "approval_removed":
            value["approved"] = decision["approved"] = False
        else:
            value["version"] = decision["version"] = "s5-smoke-budget-epoch-v0"
        path.write_text(json.dumps(value), encoding="utf-8")
        decision["authorization_record"]["sha256"] = file_hash(path)
    with pytest.raises(ValueError):
        verify_smoke_budget_epoch_authorization(decision)
        resolve_smoke_budget_baseline(latest_prior(), decision)


@pytest.fixture
def real_prepared_epoch(tmp_path):
    from evaluation.s5_llm_only import prepare
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "s5-llm-only-v21"
    before = {path: path.read_bytes() for path in
        (root / "docs/final_sprint").glob("s5-llm-only-v*/smoke_summary.json")}
    result = prepare(root / "docs/final_sprint/s6-fast-generation-v1/next_s5_entry", output,
        root / "docs/final_sprint/s6-fast-generation-v1/LLM_ONLY_S5_INLINE_CITATION_AUTHORIZATION.json")
    assert result["formal_runs_started"] == 0 and result["D_rows_sealed"] == 2
    assert all(path.read_bytes() == content for path, content in before.items())
    return output


def test_real_offline_prepare_freezes_active_and_lifetime_spend_without_dispatch(real_prepared_epoch):
    from evaluation.s4_runner import status, verify_smoke_budget_epoch_authorization
    freeze = json.loads((real_prepared_epoch / "freeze.json").read_text(encoding="utf-8"))
    decision = freeze["smoke_budget_epoch_authorization"]
    verify_smoke_budget_epoch_authorization(decision)
    baseline = resolve_smoke_budget_baseline(freeze["prior_nonformal_spend"], decision)
    assert freeze["smoke_budget_baseline"] == baseline
    retained_v20 = next(record for record in freeze["prior_nonformal_spend"]["records"]
        if Path(record["path"]).parent.name == "s5-llm-only-v20")
    assert {key:retained_v20[key] for key in LIMITS} == dict(requests=5,total_tokens=29038,cost_usd=.0335802)
    for key in LIMITS:
        historical = freeze["prior_nonformal_spend"]["records"]
        active = [record for record in historical
            if int(Path(record["path"]).parent.name.rsplit("v", 1)[1]) >= 20]
        assert baseline["active_prior"][key] == pytest.approx(sum(row[key] for row in active))
        assert baseline["lifetime_prior"][key] == pytest.approx(sum(row[key] for row in historical))
    assert baseline["excluded_prior"] == dict(requests=34,total_tokens=207948,cost_usd=.292885)
    rows = status(real_prepared_epoch)["rows"]
    assert len(rows) == 8 and all(row["run_id"] is None for row in rows)
    assert not (real_prepared_epoch / "smoke_schedule.jsonl").exists()
    assert not (real_prepared_epoch / "smokes").exists()


@pytest.mark.parametrize("mutation", ["baseline_tamper", "baseline_removed", "authority_hash", "history_changed"])
def test_smoke_gate_rejects_frozen_budget_tamper_before_dispatch(real_prepared_epoch, monkeypatch, mutation):
    import dotenv
    import evaluation.s5_llm_only as runner
    import workflow.review_providers as providers
    freeze_path = real_prepared_epoch / "freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if mutation == "baseline_tamper":
        freeze["smoke_budget_baseline"]["active_prior"]["requests"] -= 1
    elif mutation == "baseline_removed":
        del freeze["smoke_budget_baseline"]
    elif mutation == "authority_hash":
        freeze["smoke_budget_epoch_authorization"]["authorization_record"]["sha256"] = "0" * 64
    else:
        observed_prior = deepcopy(freeze["prior_nonformal_spend"])
        observed_prior["requests"] += 1
        monkeypatch.setattr(runner,"_prior_nonformal_spend",lambda _:observed_prior)
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
    monkeypatch.setattr(dotenv,"load_dotenv",lambda *args,**kwargs:None)
    monkeypatch.setattr(providers,"resolve_gemini_credential",
        lambda **kwargs:("offline-test-no-secret","GOOGLE_API_KEY"))
    dispatches = []
    monkeypatch.setattr(providers,"GeminiPhysicalProvider",lambda **kwargs:dispatches.append(kwargs))
    with pytest.raises(ValueError,match="budget baseline|epoch authorization|frozen baseline|historical smoke"):
        runner.run_smokes(real_prepared_epoch)
    assert not dispatches
    assert not (real_prepared_epoch / "smoke_schedule.jsonl").exists()


@pytest.mark.parametrize("mutation", ["baseline_tamper", "baseline_removed", "authority_hash"])
def test_formal_freeze_gate_reports_budget_tamper(real_prepared_epoch, mutation):
    from evaluation.s4_runner import check_freeze
    freeze_path = real_prepared_epoch / "freeze.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze["smoke_actual"] = dict(requests=0,total_tokens=0,cost_usd=0)
    if mutation == "baseline_tamper":
        freeze["smoke_budget_baseline"]["active_prior"]["total_tokens"] -= 1
    elif mutation == "baseline_removed":
        del freeze["smoke_budget_baseline"]
    else:
        freeze["smoke_budget_epoch_authorization"]["authorization_record"]["sha256"] = "0" * 64
    freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
    result = check_freeze(real_prepared_epoch)
    assert not result["ready"]
    assert "LLM-only aggregate request/token/cost limits are incomplete or exceeded" in result["blockers"]
