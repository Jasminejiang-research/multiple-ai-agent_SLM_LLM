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
    # Keep the original 20-minute regression matrix while separately testing
    # the installed v2 15-minute continuation profile below.
    data = runner.read_json(runner.ROOT/'trial_config.json')
    data.update(model_config_version='granite-h-micro-cpu-research-20m-v1',
                node_seconds=1200, run_seconds=1200, request_seconds=1200)
    return runner.ResearchConfig.model_validate(data)


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
    def execute(config_override=None):
        active_config = config_override or config
        active_authorization = deepcopy(authorization)
        if config_override is not None:
            active_authorization['approved_limits'] = {key: getattr(active_config, key)
                for key in authorization['approved_limits']}
        return runner.execute(active_config, active_authorization, carryover, shared_repo=tmp_path, output=tmp_path/'run',
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


def research_source_record(tmp_path, *, parent_record=None, change=None):
    """Durable synthetic component result; no provider or runtime execution."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    parent_record = parent_record or source_record(tmp_path)
    parent = runner.verified_carryover(parent_record)
    used = dict(request_count=3, charged_total_tokens=24572, elapsed_seconds=816.734)
    usage = dict(actual_prompt_tokens_known=21485, actual_output_tokens_known=3087,
                 actual_total_tokens_known=24572, usage_missing_calls=0)
    remaining = {key: parent['pool_limits'][key] - parent['pool_used'][key] for key in used}
    snapshot = dict(**used, **usage, max_requests=remaining['request_count'],
        max_total_tokens=remaining['charged_total_tokens'], revision_request_count=0)
    pool = {key: parent['pool_used'][key] + used[key] for key in used}
    history = {key: parent['all_history_used'][key] + used[key] for key in used}
    source = dict(case_id='ai_education', formal_eligible=False, formal_runs_started=0, gemini_calls=0,
        complete_proposal_produced=False, complete_d_passed=False,
        scope='Research generation only: synthetic component fixture', status='failed', http_requests=3,
        elapsed_seconds=used['elapsed_seconds'], inherited_allowance=parent,
        probe_deadline_seconds=min(1200, remaining['elapsed_seconds']),
        remaining_before_probe=dict(max_requests=remaining['request_count'],
            max_total_tokens=remaining['charged_total_tokens'], pool_remaining_seconds=remaining['elapsed_seconds'],
            probe_seconds=min(1200, remaining['elapsed_seconds'])),
        this_probe=dict(**used, known_usage=usage, budget_snapshot=snapshot),
        pool_cumulative=dict(**pool, known_usage={key: parent['pool_known_usage'][key] + usage[key] for key in usage}),
        all_history_cumulative=dict(**history, known_usage_before_current_pool=None),
        pool_remaining={key: max(0, parent['pool_limits'][key] - pool[key]) for key in pool},
        unknown_usage_policy=parent['unknown_usage_policy'])
    if change:
        change(source)
    path = tmp_path/'completed_research_result.json'
    path.write_text(json.dumps(source), encoding='utf-8')
    return dict(result_path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def v2_config():
    data = runner.read_json(runner.ROOT/'trial_config.json')
    data.update(model_config_version='granite-h-micro-cpu-research-15m-v2',
                node_seconds=900, run_seconds=900, request_seconds=900)
    return runner.ResearchConfig.model_validate(data)


@pytest.mark.parametrize('field', ['run_seconds', 'node_seconds', 'request_seconds'])
def test_v2_profile_rejects_more_than_900_seconds(field):
    data = v2_config().model_dump()
    data[field] = 900.001
    with pytest.raises(ValidationError, match='900-second'):
        runner.ResearchConfig.model_validate(data)


def test_v1_profile_still_accepts_the_original_1200_seconds(config):
    assert config.model_config_version == 'granite-h-micro-cpu-research-20m-v1'
    assert config.run_seconds == config.node_seconds == config.request_seconds == 1200


def test_research_continuation_uses_pool_cumulative_and_preserves_unknown_ancestor(tmp_path):
    record = research_source_record(tmp_path)
    before = Path(record['result_path']).read_bytes()
    carry = runner.verified_carryover(record)
    assert carry['pool_used']['request_count'] == 5
    assert carry['pool_used']['charged_total_tokens'] == 115489
    assert carry['pool_used']['elapsed_seconds'] == pytest.approx(4401.422)
    assert carry['all_history_used']['request_count'] == 21
    assert carry['all_history_used']['charged_total_tokens'] == 412058
    assert carry['pool_known_usage']['actual_total_tokens_known'] == 29566
    assert carry['pool_known_usage']['usage_missing_calls'] == 1
    assert carry['source_inherited_allowance']['source_per_plan_budget']['charged_total_tokens'] == 90917
    assert carry['source_budget_scope'] == 'finished_research_component_not_whole_pool'
    assert len(carry['source_chain']) == 2
    allowance = runner.remaining_allowance(v2_config(), carry)
    assert allowance['max_requests'] == 31 and allowance['max_total_tokens'] == 384511
    assert allowance['pool_remaining_seconds'] == pytest.approx(998.578)
    assert allowance['probe_seconds'] == 900
    assert Path(record['result_path']).read_bytes() == before


def test_recursive_research_chain_does_not_drop_earlier_components(tmp_path):
    first = research_source_record(tmp_path/'first')
    second = research_source_record(tmp_path/'second', parent_record=first)
    carry = runner.verified_carryover(second)
    assert carry['pool_used']['request_count'] == 8
    assert carry['pool_used']['charged_total_tokens'] == 140061
    assert carry['pool_known_usage']['usage_missing_calls'] == 1
    assert carry['all_history_used']['request_count'] == 24
    assert len(carry['source_chain']) == 3
    assert runner.remaining_allowance(v2_config(), carry)['probe_seconds'] == pytest.approx(181.844)


@pytest.mark.parametrize('mutation', [
    'inherited_pool_count', 'inherited_unknown_count', 'inherited_reservation',
    'probe_charge', 'probe_time', 'probe_known', 'pool_total', 'history_total',
    'pool_known', 'remaining_time', 'older_known', 'source_ceiling', 'probe_ceiling',
    'reset_time', 'running', 'revision', 'http_count'])
def test_rehashed_inconsistent_component_cannot_reset_or_refund_budget(tmp_path, mutation):
    def change(source):
        if mutation == 'inherited_pool_count': source['inherited_allowance']['pool_used']['request_count'] = 0
        if mutation == 'inherited_unknown_count': source['inherited_allowance']['pool_known_usage']['usage_missing_calls'] = 0
        if mutation == 'inherited_reservation': source['inherited_allowance']['source_per_plan_budget']['charged_total_tokens'] = 4994
        if mutation == 'probe_charge': source['this_probe']['charged_total_tokens'] -= 1
        if mutation == 'probe_time': source['this_probe']['elapsed_seconds'] = -1
        if mutation == 'probe_known': source['this_probe']['known_usage']['usage_missing_calls'] = 0.5
        if mutation == 'pool_total': source['pool_cumulative']['charged_total_tokens'] -= 1
        if mutation == 'history_total': source['all_history_cumulative']['request_count'] -= 18
        if mutation == 'pool_known': source['pool_cumulative']['known_usage']['usage_missing_calls'] = 0
        if mutation == 'remaining_time': source['pool_remaining']['elapsed_seconds'] = 5400
        if mutation == 'older_known': source['all_history_cumulative']['known_usage_before_current_pool'] = 0
        if mutation == 'source_ceiling': source['remaining_before_probe']['max_requests'] = 36
        if mutation == 'probe_ceiling': source['this_probe']['budget_snapshot']['max_total_tokens'] = 500000
        if mutation == 'reset_time': source['probe_deadline_seconds'] = 5400
        if mutation == 'running': source['status'] = 'running'
        if mutation == 'revision': source['this_probe']['budget_snapshot']['revision_request_count'] = 1
        if mutation == 'http_count': source['http_requests'] = 4
    record = research_source_record(tmp_path, change=change)
    with pytest.raises(ValueError):
        runner.verified_carryover(record)


def test_ancestor_hash_mutation_is_detected_even_when_latest_hash_is_valid(tmp_path):
    record = research_source_record(tmp_path)
    source = runner.read_json(record['result_path'])
    ancestor = Path(source['inherited_allowance']['source_result']['result_path'])
    ancestor.write_bytes(ancestor.read_bytes() + b' ')
    with pytest.raises(ValueError, match='hash mismatch'):
        runner.verified_carryover(record)


def test_cyclic_research_chain_fails_without_recursive_loop(tmp_path):
    record = research_source_record(tmp_path)
    source = runner.read_json(record['result_path'])
    source['inherited_allowance']['source_result'] = record
    path = Path(record['result_path'])
    path.write_text(json.dumps(source), encoding='utf-8')
    record['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='cyclic'):
        runner.verified_carryover(record)


def test_v2_mock_probe_runs_once_with_900_seconds_and_31_remaining_requests(harness, tmp_path):
    carry = runner.verified_carryover(research_source_record(tmp_path/'source'))
    harness.carryover.clear()
    harness.carryover.update(carry)
    result = harness.execute(v2_config())
    assert result['research_probe_passed']
    assert harness.state['generation_calls'] == harness.state['timer_count'] == 1
    assert harness.state['timer'].seconds == 900
    assert harness.state['run_config'].max_requests == 31
    assert harness.state['run_config'].max_total_tokens == 384511
    assert harness.state['run_config'].run_seconds == 900
    assert result['pool_cumulative']['request_count'] == 8
    assert result['pool_cumulative']['charged_total_tokens'] == 123689
    assert result['pool_cumulative']['known_usage']['usage_missing_calls'] == 2
    assert result['all_history_cumulative']['request_count'] == 24
    assert result['complete_proposal_produced'] is result['complete_d_passed'] is False
    assert harness.events[-4:] == ['timer_cancel', 'monitor_close', 'owner_stop', 'power_exit']


def test_invalid_carryover_check_only_has_zero_execute_calls(tmp_path, monkeypatch):
    record = research_source_record(tmp_path, change=lambda source: source['pool_cumulative'].update(request_count=0))
    original = runner.read_json
    monkeypatch.setattr(runner, 'read_json', lambda path: record if Path(path).name == 'budget_carryover.json' else original(path))
    touched = []
    def forbidden(*args, **kwargs):
        touched.append(True)
        pytest.fail('Invalid carryover reached runtime execution')
    monkeypatch.setattr(runner, 'execute', forbidden)
    monkeypatch.setattr('sys.argv', ['research_runner.py', '--check-only', '--shared-repo', str(tmp_path),
        '--output', str(tmp_path/'not_created'), '--server-owner', 'unused'])
    with pytest.raises(ValueError, match='conservation'):
        runner.main()
    assert not touched and not (tmp_path/'not_created').exists()
