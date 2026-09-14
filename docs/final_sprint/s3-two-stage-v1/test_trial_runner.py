"""Budget carryover regressions; no real providers or process start."""
import json
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pytest
from trial_runner import RecoveryConfig, TrialBudget, verified_carryover


def test_prior_run_and_all_phases_share_time_and_request_tokens():
    now = [100.0]
    config = RecoveryConfig()
    prior = dict(elapsed_seconds=2121.203,request_count=2,charged_total_tokens=23903)
    ledger = TrialBudget(config,prior,clock=lambda:now[0])
    assert ledger.remaining()['max_requests'] == 34
    assert ledger.remaining()['max_total_tokens'] == 476097
    now[0] += 60
    ledger.consume('schema_probe',dict(request_count=1,charged_total_tokens=200))
    now[0] += 180
    ledger.consume('research',dict(request_count=2,charged_total_tokens=16000))
    remaining = ledger.remaining()
    assert remaining['run_seconds'] == pytest.approx(14400-2121.203-240)
    assert remaining['max_requests'] == 31
    assert remaining['max_total_tokens'] == 459897
    with pytest.raises(ValueError,match='already accounted'):
        ledger.consume('research',dict(request_count=1,charged_total_tokens=5))
    now[0] += 14400
    with pytest.raises(ValueError,match='exhausted'): ledger.remaining()


@pytest.mark.parametrize('prior',[
    dict(elapsed_seconds=-1,request_count=2,charged_total_tokens=2),
    dict(elapsed_seconds=1,request_count=-1,charged_total_tokens=2),
    dict(elapsed_seconds=float('nan'),request_count=2,charged_total_tokens=2),
    dict(elapsed_seconds=1,request_count=2,charged_total_tokens=True),
])
def test_malformed_prior_cannot_expand_budget(prior):
    with pytest.raises(ValueError): TrialBudget(RecoveryConfig(),prior)


def test_carryover_requires_exact_previous_result_hash(tmp_path):
    path = tmp_path/'prior.json'
    path.write_text(json.dumps(dict(case_id='ai_education',formal_eligible=False,elapsed_seconds=5,
        workflow={'budget':dict(request_count=1,charged_total_tokens=2)})))
    with pytest.raises(ValueError,match='hash mismatch'):
        verified_carryover(dict(result_path=str(path),sha256='0'*64))


def test_recovery_carryover_uses_cumulative_not_latest_usage(tmp_path):
    path=tmp_path/'prior.json'
    path.write_text(json.dumps(dict(case_id='ai_education',formal_eligible=False,elapsed_seconds=710,
        budget=dict(this_run_request_count=3,cumulative_request_count=5,
            cumulative_charged_total_tokens=37864,cumulative_elapsed_seconds=2831.124))))
    prior=verified_carryover(dict(result_path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    remaining=TrialBudget(RecoveryConfig(),prior).remaining()
    assert remaining['max_requests']==31
    assert remaining['max_total_tokens']==462136
    assert 11568<remaining['run_seconds']<11569
