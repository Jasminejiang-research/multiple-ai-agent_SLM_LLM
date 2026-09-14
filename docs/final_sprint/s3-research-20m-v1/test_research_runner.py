"""Offline tests of retained budget, Research-only scope, deadlines and cleanup."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import research_runner as runner


@pytest.fixture
def config():
    return runner.ResearchConfig.model_validate(runner.read_json(runner.ROOT/'trial_config.json'))


@pytest.fixture
def authorization(config, tmp_path):
    parent = dict(approved=True, scope='ai_education_slm_independent_90m_validation',
        approved_limits=dict(run_seconds=5400, max_requests=36, max_total_tokens=500000, max_output_tokens=8192),
        expected_model_digest='test-digest', expected_ollama_version='0.33.2')
    path = tmp_path/'parent_authorization.json'
    path.write_text(json.dumps(parent), encoding='utf-8')
    return dict(approved=True, scope='ai_education_research_20m',
        approved_limits={key: getattr(config, key) for key in ('run_seconds', 'node_seconds', 'request_seconds',
            'max_output_tokens', 'max_requests', 'max_total_tokens', 'max_prompt_chars')},
        expected_model_digest='test-digest', expected_ollama_version='0.33.2',
        parent_authorization_path=str(path), parent_authorization_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def source_record(tmp_path, changes=None):
    source = dict(case_id='ai_education', formal_eligible=False, status='resource_stopped', elapsed_seconds=3584.688,
        budget=dict(this_run_request_count=2, this_run_charged_total_tokens=90917,
            this_run_elapsed_seconds=3584.688, cumulative_request_count=18,
            cumulative_charged_total_tokens=387486, cumulative_elapsed_seconds=13778.171,
            this_run_time_limit_seconds=5400,
            per_plan_budget=dict(max_requests=36, max_total_tokens=500000, request_count=2,
                charged_total_tokens=90917, actual_prompt_tokens_known=4291,
                actual_output_tokens_known=703, actual_total_tokens_known=4994, usage_missing_calls=1)))
    if changes:
        changes(source)
    path = tmp_path/'source_result.json'
    path.write_text(json.dumps(source), encoding='utf-8')
    return dict(result_path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


@pytest.fixture
def carryover(tmp_path):
    return runner.verified_carryover(source_record(tmp_path))


def test_pool_uses_this_run_not_all_history_and_retains_unknown_charge(config, carryover):
    assert carryover['pool_used'] == dict(request_count=2, charged_total_tokens=90917, elapsed_seconds=3584.688)
    assert carryover['all_history_used'] == dict(request_count=18, charged_total_tokens=387486, elapsed_seconds=13778.171)
    assert carryover['pool_known_usage']['actual_total_tokens_known'] == 4994
    assert carryover['pool_known_usage']['usage_missing_calls'] == 1
    remaining = runner.remaining_allowance(config, carryover)
    assert remaining['max_requests'] == 34 and remaining['max_total_tokens'] == 409083
    assert remaining['pool_remaining_seconds'] == pytest.approx(1815.312)
    assert remaining['probe_seconds'] == 1200


@pytest.mark.parametrize('field', ['run_seconds', 'node_seconds', 'request_seconds'])
def test_config_rejects_more_than_1200(config, field):
    with pytest.raises(ValidationError):
        runner.ResearchConfig.model_validate({**config.model_dump(), field: 1200.001})


def test_carryover_hash_is_required_and_source_is_unchanged(tmp_path):
    record = source_record(tmp_path)
    before = Path(record['result_path']).read_bytes()
    runner.verified_carryover(record)
    assert Path(record['result_path']).read_bytes() == before
    with pytest.raises(ValueError, match='hash mismatch'):
        runner.verified_carryover({**record, 'sha256': '0'*64})


@pytest.mark.parametrize('value', [-1, True, 1.5])
def test_invalid_historical_count_is_rejected(tmp_path, value):
    record = source_record(tmp_path, lambda source: source['budget'].update(cumulative_request_count=value))
    with pytest.raises(ValueError, match='Invalid historical'):
        runner.verified_carryover(record)


def test_source_snapshot_mismatch_cannot_refund_unknown_reservation(tmp_path):
    record = source_record(tmp_path, lambda source: source['budget'].update(this_run_charged_total_tokens=4994))
    with pytest.raises(ValueError, match='ledger'):
        runner.verified_carryover(record)


@pytest.mark.parametrize('failure', ['unapproved', 'wrong_limit', 'parent_hash', 'pool_exhausted'])
def test_rejected_authority_or_pool_has_zero_runtime_access(config, authorization, carryover, tmp_path, monkeypatch, failure):
    if failure == 'unapproved': authorization['approved'] = False
    if failure == 'wrong_limit': authorization['approved_limits']['max_requests'] = 99
    if failure == 'parent_hash': authorization['parent_authorization_sha256'] = '0'*64
    if failure == 'pool_exhausted': carryover['pool_used']['elapsed_seconds'] = 5400
    touched = []
    def forbidden(*args, **kwargs):
        touched.append(True)
        pytest.fail('Runtime touched before authorization/budget validation')
    for name in ('EventJournal', 'OwnedOllama', 'WindowsAwake', 'ContextCheckedProvider', 'Timer'):
        monkeypatch.setattr(runner, name, forbidden)
    with pytest.raises(ValueError):
        runner.execute(config, authorization, carryover, shared_repo=tmp_path, output=tmp_path/'run',
            owner_path='unused', tokenizer_path='unused', tokenizer_provenance='unused')
    assert not touched


@pytest.fixture
def harness(tmp_path, monkeypatch, config, authorization, carryover):
    events, clock = [], [0.0]
    state = dict(power_enter_error=False, power_exit_error=False, monitor_close_error=False,
        owner_stop_error=False, owner_unconfirmed=False, resource_gap=False, bad_model=False,
        bad_placement=False, fire_deadline=False, late_without_timer=False, fail_generation=False,
        generation_calls=0, stages=[], timer_count=0, timer=None, run_config=None, artifact_checks=0)
    monkeypatch.setattr(runner, 'monotonic', lambda: clock[0])
    class Owner:
        def __init__(self, *args, **kwargs): events.append('owner_created')
        def validate(self): events.append('owner_validated')
        def stop(self):
            events.append('owner_stop')
            if state['owner_stop_error']: raise OSError('stop failed')
            return dict(status='termination_unconfirmed' if state['owner_unconfirmed'] else 'owned_process_tree_terminated')
    class Timer:
        def __init__(self, seconds, callback):
            assert 0 <= seconds <= 1200
            state['timer_count'] += 1
            state['timer'] = self
            self.seconds, self.callback = seconds, callback
        def start(self): events.append('timer_start')
        def cancel(self): events.append('timer_cancel')
    class Awake:
        def __init__(self, **kwargs): pass
        def __enter__(self):
            events.append('power_enter')
            if state['power_enter_error']: raise OSError('power entry failed')
            return self
        def __exit__(self, *args):
            events.append('power_exit')
            if state['power_exit_error']: raise OSError('power release failed')
    class Monitor:
        def __init__(self, probe, *args, **kwargs): probe()
        def start(self): events.append('monitor_start')
        def close(self):
            events.append('monitor_close')
            if state['monitor_close_error']: raise OSError('monitor cleanup failed')
            return dict(status='failed' if state['resource_gap'] else 'passed')
    class Provider:
        def __init__(self, *args, **kwargs): self.http_requests = 0
    class Client:
        def __init__(self, provider, run_config, *args, **kwargs):
            self.provider, self.node_started = provider, None
            self.snapshot_value = runner.empty_snapshot()
            state['run_config'] = run_config
            self.attempt_scope = object()
        def begin_node(self, name):
            assert name == 'research'
            self.node_started = clock[0]
        def check(self): pass
        def end_node(self, status): self.node_started = None
        def snapshot(self): return deepcopy(self.snapshot_value)
    class Artifact:
        sha256 = 'artifact-hash'
        def as_dict(self): return dict(role='research', artifact_version=1, payload={'synthetic_mock_only': True})
    class Context:
        packet_sha256, brief_sha256 = 'packet', 'brief'
        @classmethod
        def from_case(cls, *args, **kwargs):
            assert args[1] == 'ai_education' and kwargs['condition'] == 'D'
            return cls()
        def verify_artifact(self, artifact): state['artifact_checks'] += 1
    class Generator:
        def __init__(self, client, **kwargs): self.client = client
        def generate(self, context, role):
            assert role == 'research'
            state['generation_calls'] += 1
            # The runner delegates the existing two-stage/one-repair protocol once.
            for stage in ('body', 'grounding', 'structure_repair'):
                state['stages'].append(stage)
                clock[0] += 100
            self.client.provider.http_requests = 3
            self.client.snapshot_value.update(request_count=3, charged_total_tokens=8200,
                actual_prompt_tokens_known=5, actual_output_tokens_known=3,
                actual_total_tokens_known=8, usage_missing_calls=1, structure_repair_request_count=1)
            if state['fire_deadline'] or state['late_without_timer']:
                clock[0] = state['timer'].seconds
            if state['fire_deadline']: state['timer'].callback()
            if state['fail_generation']: raise ValueError('synthetic canonical failure with retained usage')
            return Artifact()
    def metadata(config):
        return dict(model_digest='wrong' if state['bad_model'] else 'test-digest', ollama_version='0.33.2')
    def probe(**kwargs):
        return lambda: dict(loaded_models=[dict(name=config.model_alias, context_length=32768,
            size_vram=1 if state['bad_placement'] else 0)])
    for name, value in dict(OwnedOllama=Owner, Timer=Timer, WindowsAwake=Awake, ResourceMonitor=Monitor,
        ContextCheckedProvider=Provider, BoundedClient=Client, ContractGenerator=Generator,
        ContractContext=Context, inspect_ollama=metadata, WindowsResourceProbe=probe,
        LocalRequestLease=lambda *args: object(), load_context_tokenizer=lambda *args: object()).items():
        monkeypatch.setattr(runner, name, value)
    def execute():
        return runner.execute(config, authorization, carryover, shared_repo=tmp_path, output=tmp_path/'run',
            owner_path='unused', tokenizer_path='unused', tokenizer_provenance='unused')
    return SimpleNamespace(execute=execute, events=events, state=state, carryover=carryover, output=tmp_path/'run')


def test_research_only_uses_one_timer_and_keeps_pool_and_all_history_separate(harness):
    result = harness.execute()
    assert result['research_probe_passed'] and result['research_artifact_produced']
    assert result['complete_proposal_produced'] is result['complete_d_passed'] is False
    assert harness.state['generation_calls'] == harness.state['timer_count'] == harness.state['artifact_checks'] == 1
    assert harness.state['stages'] == ['body', 'grounding', 'structure_repair']
    assert result['inference_elapsed_seconds'] == 300 and result['probe_deadline_seconds'] == 1200
    cfg = harness.state['run_config']
    assert cfg.max_requests == 34 and cfg.max_total_tokens == 409083 and cfg.run_seconds == 1200
    assert result['this_probe']['request_count'] == 3
    assert result['pool_cumulative']['request_count'] == 5
    assert result['pool_cumulative']['charged_total_tokens'] == 99117
    assert result['all_history_cumulative']['request_count'] == 21
    assert result['all_history_cumulative']['charged_total_tokens'] == 395686
    assert result['pool_cumulative']['known_usage']['actual_total_tokens_known'] == 5002
    assert result['pool_cumulative']['known_usage']['usage_missing_calls'] == 2
    assert result['all_history_cumulative']['known_usage_before_current_pool'] is None
    assert result['pool_remaining']['elapsed_seconds'] == pytest.approx(1515.312)
    assert json.loads((harness.output/'artifact.json').read_text())['role'] == 'research'
    assert harness.events[-4:] == ['timer_cancel', 'monitor_close', 'owner_stop', 'power_exit']


def test_less_than_twenty_minutes_remaining_caps_the_one_timer_and_client(harness):
    harness.carryover['pool_used']['elapsed_seconds'] = 5000
    result = harness.execute()
    assert result['probe_deadline_seconds'] == 400
    assert harness.state['timer'].seconds == harness.state['run_config'].run_seconds == 400
    assert result['pool_remaining']['elapsed_seconds'] == 100


@pytest.mark.parametrize('failure', ['power_enter_error', 'bad_model', 'bad_placement'])
def test_preflight_failures_have_zero_model_calls_but_cleanup_runs(harness, failure):
    harness.state[failure] = True
    result = harness.execute()
    assert result['http_requests'] == harness.state['generation_calls'] == 0
    assert result['this_probe']['charged_total_tokens'] == 0
    assert not result['research_probe_passed']
    assert 'owner_stop' in harness.events and 'power_exit' in harness.events


@pytest.mark.parametrize('failure', ['power_exit_error', 'monitor_close_error', 'owner_stop_error', 'owner_unconfirmed'])
def test_all_cleanup_failures_block_success_and_preserve_artifact_and_accounting(harness, failure):
    harness.state[failure] = True
    result = harness.execute()
    assert not result['research_probe_passed'] and result['status'] != 'completed'
    assert result['research_artifact_produced'] and result['pool_cumulative']['charged_total_tokens'] == 99117
    assert harness.events[-4:] == ['timer_cancel', 'monitor_close', 'owner_stop', 'power_exit']
    assert (harness.output/'result.json').exists()


@pytest.mark.parametrize('failure,expected', [('resource_gap', 'resource_stopped'),
    ('fire_deadline', 'timeout'), ('late_without_timer', 'timeout'), ('fail_generation', 'failed')])
def test_timeout_resource_or_generation_failure_never_refunds_unknown_calls(harness, failure, expected):
    harness.state[failure] = True
    result = harness.execute()
    assert result['status'] == expected and not result['research_probe_passed']
    assert result['this_probe']['charged_total_tokens'] == 8200
    assert result['this_probe']['known_usage']['actual_total_tokens_known'] == 8
    assert result['pool_cumulative']['charged_total_tokens'] == 99117
    assert result['pool_cumulative']['known_usage']['usage_missing_calls'] == 2


def test_check_only_performs_no_server_or_model_work(tmp_path, monkeypatch):
    touched = []
    def forbidden(*args, **kwargs):
        touched.append(True)
        pytest.fail('Check-only touched a model/server')
    monkeypatch.setattr(runner, 'execute', forbidden)
    monkeypatch.setattr('sys.argv', ['research_runner.py', '--check-only', '--shared-repo', str(tmp_path),
        '--output', str(tmp_path/'unused'), '--server-owner', 'unused'])
    assert runner.main() == 0
    assert not touched and not (tmp_path/'unused').exists()
