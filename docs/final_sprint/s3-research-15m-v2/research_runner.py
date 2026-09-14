"""One Research-only probe charged to the remaining approved 90-minute pool.

No Critic, Strategy, Finance, Writer or full-D execution. The production
Research parent node still includes Critic/revision inside its own 1200 seconds.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
from threading import Event, Timer
from time import monotonic
from typing import Literal
from uuid import uuid4

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime'))
from pydantic import Field, model_validator
from support.capability_base import CapabilityConfig, ContextCheckedProvider
from schemas.contract_outputs import CONTRACT_VERSION
from slm.granite_preflight import load_context_tokenizer
from slm.granite_provider import inspect_ollama
from slm.owned_ollama import OwnedOllama
from slm.resource_monitor import ResourceMonitor, WindowsResourceProbe
from slm.windows_awake import WindowsAwake
from workflow.contract_context import ContractContext
from workflow.contract_generation import ContractGenerator, PROMPT_VERSION
from workflow.review_events import EventJournal
from workflow.review_runtime import BoundedClient, LocalRequestLease, RunCancelled, SharedBudgetStop
from workflow.run_budget import RunBudgetExceededError


class ResearchConfig(CapabilityConfig):
    model_config_version: Literal['granite-h-micro-cpu-research-20m-v1',
        'granite-h-micro-cpu-research-15m-v2'] = 'granite-h-micro-cpu-research-20m-v1'
    node_seconds: float = Field(default=1200, gt=0, le=1200)
    run_seconds: float = Field(default=1200, gt=0, le=1200)
    request_seconds: float = Field(default=1200, gt=0, le=1200)

    @model_validator(mode='after')
    def continuation_time_limit(self):
        if self.model_config_version == 'granite-h-micro-cpu-research-15m-v2' and any(
                getattr(self, key) > 900 for key in ('run_seconds', 'node_seconds', 'request_seconds')):
            raise ValueError('The v2 Research continuation has a 900-second maximum for run, node and request')
        return self


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate_authorization(config, record):
    if record.get('scope') != 'ai_education_research_20m' or record.get('approved') is not True:
        raise ValueError('Research-only 20-minute authorization is missing')
    expected = {key: getattr(config, key) for key in ('run_seconds', 'node_seconds', 'request_seconds',
        'max_output_tokens', 'max_requests', 'max_total_tokens', 'max_prompt_chars')}
    if record.get('approved_limits') != expected:
        raise ValueError('Configuration differs from the approved Research allowance')
    parent_raw = Path(record['parent_authorization_path']).read_bytes()
    if hashlib.sha256(parent_raw).hexdigest() != record['parent_authorization_sha256']:
        raise ValueError('Parent pool authorization hash mismatch')
    parent = json.loads(parent_raw.decode('utf-8-sig'))
    if (parent.get('approved') is not True or parent.get('scope') != 'ai_education_slm_independent_90m_validation'
            or any(parent.get('approved_limits', {}).get(key) != value for key, value in
                   dict(run_seconds=5400, max_requests=36, max_total_tokens=500000, max_output_tokens=8192).items())
            or any(parent.get(key) != record.get(key) for key in ('expected_model_digest', 'expected_ollama_version'))):
        raise ValueError('Parent pool authorization does not match this continuation')


def valid_consumption(value):
    if (any(type(value[key]) is not int or value[key] < 0 for key in ('request_count', 'charged_total_tokens'))
            or type(value['elapsed_seconds']) not in (int, float)
            or not math.isfinite(value['elapsed_seconds']) or value['elapsed_seconds'] < 0):
        raise ValueError('Invalid historical consumption')
    return value


def known_usage(snapshot):
    result = {key: snapshot[key] for key in ('actual_prompt_tokens_known', 'actual_output_tokens_known',
        'actual_total_tokens_known', 'usage_missing_calls')}
    if any(type(value) is not int or value < 0 for value in result.values()):
        raise ValueError('Invalid known-usage subtotal')
    return result


def verified_carryover(record, *, _seen=()):
    """Verify a hashed chain back to the separately approved 90-minute pool.

    A finished Research component contributes this_probe to its inherited pool.
    Neither its all-history total nor its own smaller component can reset that
    pool. Every ancestor is read and verified; no unknown reservation is refunded.
    """
    path = Path(record['result_path']).resolve()
    if path in _seen or len(_seen) >= 16:
        raise ValueError('Carryover source chain is cyclic or exceeds the audit bound')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['sha256']:
        raise ValueError('Carryover result hash mismatch')
    source = json.loads(raw)
    if source.get('case_id') != 'ai_education' or source.get('formal_eligible') is not False:
        raise ValueError('Expected non-formal AI education source result')
    if 'this_probe' in source:
        return _verified_research_carryover(source, record, path, _seen=(*_seen, path))
    budget, snapshot = source['budget'], source['budget']['per_plan_budget']
    pool = valid_consumption(dict(request_count=budget['this_run_request_count'],
        charged_total_tokens=budget['this_run_charged_total_tokens'], elapsed_seconds=budget['this_run_elapsed_seconds']))
    history = valid_consumption(dict(request_count=budget['cumulative_request_count'],
        charged_total_tokens=budget['cumulative_charged_total_tokens'], elapsed_seconds=budget['cumulative_elapsed_seconds']))
    if (pool['request_count'] != snapshot['request_count'] or pool['charged_total_tokens'] != snapshot['charged_total_tokens']
            or abs(pool['elapsed_seconds'] - source['elapsed_seconds']) > .001):
        raise ValueError('Source pool budget does not match its own request/time ledger')
    if any(history[key] < pool[key] for key in pool):
        raise ValueError('All-history accounting cannot be less than current-pool use')
    if (snapshot['max_requests'], snapshot['max_total_tokens'], budget['this_run_time_limit_seconds']) != (36, 500000, 5400):
        raise ValueError('Source is not the separately approved 36-request/500000-token/90-minute pool')
    usage = known_usage(snapshot)
    if usage['actual_total_tokens_known'] > pool['charged_total_tokens']:
        raise ValueError('Known usage exceeds retained pool charges')
    return dict(source_result=dict(result_path=str(path.resolve()), sha256=record['sha256'],
                source_status=source.get('status')),
        pool_limits=dict(request_count=36, charged_total_tokens=500000, elapsed_seconds=5400.0),
        pool_used=pool, pool_known_usage=usage, all_history_used=history,
        source_per_plan_budget=deepcopy(snapshot),
        unknown_usage_policy='Retain every unknown-call reservation; known subtotals are not total actual usage. '
            'All-history known usage before this pool was not supplied and is not fabricated.')


def _same_consumption(actual, expected, label):
    actual = valid_consumption(actual)
    if (any(actual[key] != expected[key] for key in ('request_count', 'charged_total_tokens'))
            or abs(actual['elapsed_seconds'] - expected['elapsed_seconds']) > .000001):
        raise ValueError('Research carryover conservation failed: ' + label)


def _checked_known(snapshot, consumption, label):
    usage = known_usage(snapshot)
    if (usage['usage_missing_calls'] > consumption['request_count']
            or usage['actual_total_tokens_known'] > consumption['charged_total_tokens']
            or usage['actual_prompt_tokens_known'] + usage['actual_output_tokens_known'] > consumption['charged_total_tokens']
            or usage['usage_missing_calls'] == 0 and
                (usage['actual_total_tokens_known'] != consumption['charged_total_tokens'] or
                 usage['actual_prompt_tokens_known'] + usage['actual_output_tokens_known'] != usage['actual_total_tokens_known'])):
        raise ValueError('Research carryover known/unknown usage inconsistent: ' + label)
    return usage


def _verified_research_carryover(source, record, path, *, _seen):
    if (source.get('status') not in ('completed', 'failed', 'cancelled', 'timeout', 'resource_stopped',
                                   'budget_exhausted', 'cleanup_failed')
            or source.get('formal_runs_started') != 0 or source.get('gemini_calls') != 0
            or source.get('complete_proposal_produced') is not False or source.get('complete_d_passed') is not False
            or not source.get('scope', '').startswith('Research generation only:')):
        raise ValueError('Expected a finished Research-only component result')
    inherited = source['inherited_allowance']
    parent = verified_carryover(inherited['source_result'], _seen=_seen)
    # These fields existed in the first Research runner. Verify them directly
    # against the original hashed parent, rather than trusting nested copies.
    if inherited['pool_limits'] != parent['pool_limits']:
        raise ValueError('Research carryover parent pool limits changed')
    for key in ('pool_used', 'all_history_used'):
        _same_consumption(inherited[key], parent[key], 'inherited ' + key)
    if (inherited['pool_known_usage'] != parent['pool_known_usage']
            or inherited['source_per_plan_budget'] != parent['source_per_plan_budget']
            or inherited['unknown_usage_policy'] != parent['unknown_usage_policy']):
        raise ValueError('Research carryover parent snapshot or unknown usage changed')
    probe = valid_consumption(source['this_probe'])
    snapshot = probe['budget_snapshot']
    if (snapshot['request_count'] != probe['request_count']
            or snapshot['charged_total_tokens'] != probe['charged_total_tokens']
            or type(source['elapsed_seconds']) not in (int, float)
            or not math.isfinite(source['elapsed_seconds'])
            or abs(source['elapsed_seconds'] - probe['elapsed_seconds']) > .000001):
        raise ValueError('Research carryover this_probe differs from its request/time ledger')
    usage = _checked_known(snapshot, probe, 'this_probe')
    if probe['known_usage'] != usage:
        raise ValueError('Research carryover this_probe known usage differs from snapshot')
    remaining = {key: parent['pool_limits'][key] - parent['pool_used'][key] for key in parent['pool_limits']}
    if (snapshot.get('revision_request_count', 0) != 0
            or type(source.get('http_requests')) is not int or not 0 <= source['http_requests'] <= probe['request_count']
            or probe['request_count'] and (snapshot['max_requests'] != remaining['request_count']
                or snapshot['max_total_tokens'] != remaining['charged_total_tokens'])):
        raise ValueError('Research carryover component scope or remaining budget differs')
    before = source['remaining_before_probe']
    if (before['max_requests'] != remaining['request_count'] or before['max_total_tokens'] != remaining['charged_total_tokens']
            or abs(before['pool_remaining_seconds'] - remaining['elapsed_seconds']) > .000001
            or type(source['probe_deadline_seconds']) not in (float, int)
            or not 0 < source['probe_deadline_seconds'] <= min(1200, remaining['elapsed_seconds'])
            or before['probe_seconds'] != source['probe_deadline_seconds']):
        raise ValueError('Research carryover component received a reset time/token allowance')
    pool = {key: parent['pool_used'][key] + probe[key] for key in parent['pool_used']}
    history = {key: parent['all_history_used'][key] + probe[key] for key in parent['all_history_used']}
    _same_consumption(source['pool_cumulative'], pool, 'pool_cumulative')
    _same_consumption(source['all_history_cumulative'], history, 'all_history_cumulative')
    pool_usage = {key: parent['pool_known_usage'][key] + usage[key] for key in usage}
    if source['pool_cumulative']['known_usage'] != pool_usage:
        raise ValueError('Research carryover lost inherited known/unknown usage counters')
    _checked_known(pool_usage, pool, 'pool cumulative')
    if (source['all_history_cumulative']['known_usage_before_current_pool'] is not None
            or source['unknown_usage_policy'] != parent['unknown_usage_policy']):
        raise ValueError('Research carryover fabricated older known usage or changed retention policy')
    _same_consumption(source['pool_remaining'],
        {key: max(0, parent['pool_limits'][key] - pool[key]) for key in pool}, 'pool_remaining')
    source_ref = dict(result_path=str(path), sha256=record['sha256'], source_status=source['status'])
    return dict(source_result=source_ref, pool_limits=deepcopy(parent['pool_limits']), pool_used=pool,
        pool_known_usage=pool_usage, all_history_used=history, source_per_plan_budget=deepcopy(snapshot),
        source_budget_scope='finished_research_component_not_whole_pool',
        source_this_probe=deepcopy(probe), source_inherited_allowance=deepcopy(inherited),
        source_chain=[source_ref, *deepcopy(parent.get('source_chain', [parent['source_result']]))],
        unknown_usage_policy=parent['unknown_usage_policy'])


def remaining_allowance(config, carryover):
    if (config.max_requests, config.max_total_tokens) != (36, 500000):
        raise ValueError('Global pool ceilings must remain 36 requests and 500000 tokens')
    limits, used = carryover['pool_limits'], valid_consumption(carryover['pool_used'])
    remaining = {key: limits[key] - used[key] for key in limits}
    if any(value <= 0 for value in remaining.values()):
        raise ValueError('Approved pool exhausted; no new request is authorized')
    return dict(max_requests=remaining['request_count'], max_total_tokens=remaining['charged_total_tokens'],
                pool_remaining_seconds=remaining['elapsed_seconds'],
                probe_seconds=min(1200.0, config.run_seconds, remaining['elapsed_seconds']))


def empty_snapshot():
    return dict(request_count=0, charged_total_tokens=0, actual_prompt_tokens_known=0,
        actual_output_tokens_known=0, actual_total_tokens_known=0, usage_missing_calls=0,
        structure_repair_request_count=0, transport_retry_count=0, revision_request_count=0,
        token_counter_basis='budget_charge_actual_or_retained_estimate')


def execute(config, authorization, carryover, *, shared_repo, output, owner_path,
            tokenizer_path, tokenizer_provenance):
    validate_authorization(config, authorization)
    allowance = remaining_allowance(config, carryover)
    # All validation above precedes journal creation, server ownership and model access.
    started = monotonic()
    journal = EventJournal(output, str(uuid4()))
    cancel, deadline_fired = Event(), Event()
    owner = timer = awake = monitor = provider = client = generator = None
    awake_entered = False
    inference_finished = None
    result = dict(case_id='ai_education', formal_eligible=False, formal_runs_started=0, gemini_calls=0,
        complete_proposal_produced=False, complete_d_passed=False, public_config_changed=False,
        research_artifact_produced=False, research_probe_passed=False,
        scope='Research generation only: body + grounding + the existing one shared structure repair; '
              'no Critic, semantic revision, Strategy, Finance, Writer or full D.',
        production_scope_note='Production Research parent deadline also covers its existing Critic and conditional revision.',
        probe_deadline_seconds=allowance['probe_seconds'], inherited_allowance=deepcopy(carryover),
        remaining_before_probe=allowance)

    def deadline():
        deadline_fired.set()
        cancel.set()
        try:
            journal.emit('research_probe_deadline', dict(limit_seconds=allowance['probe_seconds']))
        finally:
            if owner is not None:
                owner.stop()

    try:
        owner = OwnedOllama(owner_path, journal=journal, endpoint=config.endpoint)
        owner.validate()
        timer = Timer(max(0, allowance['probe_seconds'] - (monotonic() - started)), deadline)
        timer.daemon = True
        timer.start()
        awake = WindowsAwake(journal=journal,
            reason=f"Bounded Research-only validation, at most {allowance['probe_seconds']:g} seconds")
        awake.__enter__()
        awake_entered = True
        metadata = inspect_ollama(config)
        if (metadata['model_digest'] != authorization['expected_model_digest'] or
                metadata['ollama_version'] != authorization['expected_ollama_version']):
            raise ValueError('Model digest or Ollama runtime differs from authorization')
        tokenizer = load_context_tokenizer(tokenizer_path, tokenizer_provenance)
        context = ContractContext.from_case(ROOT/'runtime/docs/final_sprint/s0-v1', 'ai_education', condition='D')
        probe = WindowsResourceProbe(endpoint=config.endpoint)

        def cpu_probe():
            observation = probe()
            for loaded in observation.get('loaded_models') or []:
                if (loaded.get('name', '').removesuffix(':latest') != config.model_alias or
                        loaded.get('context_length') != 32768 or loaded.get('size_vram') != 0):
                    raise ValueError('Unexpected model placement or context')
            return observation

        monitor = ResourceMonitor(cpu_probe, journal, cancel, interval=config.sample_seconds, abort=owner.stop)
        monitor.start()
        remaining = allowance['probe_seconds'] - (monotonic() - started)
        if remaining <= 0 or cancel.is_set():
            raise TimeoutError('Research deadline or resource guard stopped initialization')
        provider = ContextCheckedProvider(config, model_digest=metadata['model_digest'], tokenizer=tokenizer)
        run_config = config.review_config('smoke', model_digest=metadata['model_digest']).model_copy(update={
            'max_requests': allowance['max_requests'], 'max_total_tokens': allowance['max_total_tokens'],
            'run_seconds': remaining, 'node_seconds': min(config.node_seconds, remaining),
            'request_seconds': min(config.request_seconds, remaining)})
        journal.emit('research_probe_manifest', dict(config=config.model_dump(mode='json'),
            effective_run_config=run_config.model_dump(mode='json'), authorization=authorization,
            carryover=carryover, model_metadata=metadata, contract_version=CONTRACT_VERSION,
            prompt_version=PROMPT_VERSION, packet_sha256=context.packet_sha256, brief_sha256=context.brief_sha256,
            scope=result['scope'], formal_eligible=False))
        client = BoundedClient(provider, run_config, journal, cancel=cancel,
            local_lease=LocalRequestLease(Path(shared_repo)/'data/granite_endpoint_leases', config.endpoint))
        client.input_refs = [dict(artifact_id='packet', artifact_version=1, sha256=context.packet_sha256),
                             dict(artifact_id='brief', artifact_version=1, sha256=context.brief_sha256)]
        generator = ContractGenerator(client, task_sink=lambda task: journal.emit('logical_task', task),
                                       attempt_scope=client.attempt_scope)
        client.begin_node('research')
        artifact = generator.generate(context, 'research')
        context.verify_artifact(artifact)
        client.check()
        path = journal.directory / 'artifact.json'
        with path.open('x', encoding='utf-8') as stream:
            json.dump(artifact.as_dict(), stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        journal.emit('research_artifact', dict(artifact=artifact.as_dict(), sha256=artifact.sha256,
            elapsed_seconds=monotonic()-started, canonical_verified=True, human_support='not_assessed'))
        result.update(status='completed', research_artifact_produced=True, artifact_path=str(path), artifact_sha256=artifact.sha256)
        client.end_node('completed')
        inference_finished = monotonic() - started
    except (Exception, KeyboardInterrupt) as exc:
        cancel.set()
        status = ('cancelled' if isinstance(exc, (KeyboardInterrupt, RunCancelled)) else
                  'timeout' if isinstance(exc, TimeoutError) else
                  'budget_exhausted' if isinstance(exc, (SharedBudgetStop, RunBudgetExceededError)) else 'failed')
        result.update(status=status, error_type=type(exc).__name__, error=str(exc)[:1200])
        journal.emit('research_probe_error', dict(status=status, error_type=type(exc).__name__, error=str(exc)[:1200]))
    finally:
        inference_finished = inference_finished if inference_finished is not None else monotonic() - started
        if timer is not None:
            timer.cancel()
        if client is not None and client.node_started is not None:
            try:
                client.end_node(result.get('status', 'failed'))
            except Exception as exc:
                journal.emit('research_node_cleanup_error', dict(error_type=type(exc).__name__))
        try:
            resources = monitor.close() if monitor is not None else None
        except (Exception, KeyboardInterrupt) as exc:
            resources = dict(status='failed', reason='resource_monitor_cleanup_failed', error_type=type(exc).__name__)
        try:
            proof = owner.stop() if owner is not None else dict(status='not_owned')
        except (Exception, KeyboardInterrupt) as exc:
            proof = dict(status='termination_unconfirmed', error_type=type(exc).__name__)
        power_cleanup = 'not_acquired'
        if awake is not None:
            try:
                awake.__exit__(None, None, None)
                power_cleanup = 'released' if awake_entered else 'not_acquired'
            except (Exception, KeyboardInterrupt) as exc:
                power_cleanup = 'failed'
                result.update(status='cleanup_failed', power_cleanup_error=type(exc).__name__)
        snapshot = client.snapshot() if client is not None else empty_snapshot()
        elapsed = monotonic() - started
        used = dict(request_count=snapshot['request_count'], charged_total_tokens=snapshot['charged_total_tokens'], elapsed_seconds=elapsed)
        pool = {key: carryover['pool_used'][key] + used[key] for key in used}
        history = {key: carryover['all_history_used'][key] + used[key] for key in used}
        current_known = known_usage(snapshot)
        pool_known = {key: carryover['pool_known_usage'][key] + current_known[key] for key in current_known}
        result.update(elapsed_seconds=elapsed, inference_elapsed_seconds=inference_finished,
            cleanup_elapsed_seconds=elapsed-inference_finished, resources=resources, server_stop=proof,
            power_cleanup=power_cleanup, deadline_fired=deadline_fired.is_set(),
            http_requests=provider.http_requests if provider is not None else 0,
            this_probe=dict(**used, known_usage=current_known, budget_snapshot=snapshot),
            pool_cumulative=dict(**pool, known_usage=pool_known),
            all_history_cumulative=dict(**history, known_usage_before_current_pool=None,
                known_usage_note='Only current-pool known subtotals are available; older unknown usage is retained in charges.'),
            pool_remaining={key: max(0, carryover['pool_limits'][key] - pool[key]) for key in pool},
            unknown_usage_policy=carryover['unknown_usage_policy'])
        if resources and resources['status'] != 'passed':
            result['status'] = 'resource_stopped'
        if proof.get('status') != 'owned_process_tree_terminated':
            result['status'] = 'cleanup_failed'
        within_probe = inference_finished < allowance['probe_seconds']
        within_pool = carryover['pool_used']['elapsed_seconds'] + inference_finished < carryover['pool_limits']['elapsed_seconds']
        if deadline_fired.is_set() or not within_probe or not within_pool:
            result['status'] = 'timeout'
        result.update(within_probe_deadline=within_probe, within_pool_generation_deadline=within_pool)
        result['research_probe_passed'] = (result.get('status') == 'completed' and result['research_artifact_produced']
            and within_probe and within_pool and bool(resources and resources['status'] == 'passed') and power_cleanup == 'released')
        journal.emit('research_probe_result', result)
        with (journal.directory/'result.json').open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    for name in ('shared-repo', 'output', 'server-owner'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    config = ResearchConfig.model_validate(read_json(ROOT/'trial_config.json'))
    authorization = read_json(ROOT/'authorization.json')
    validate_authorization(config, authorization)
    carryover = verified_carryover(read_json(ROOT/'budget_carryover.json'))
    allowance = remaining_allowance(config, carryover)
    if args.check_only:
        print(json.dumps(dict(status='ready', model_calls=0, scope='Research only', allowance=allowance,
            pool_used=carryover['pool_used'], all_history_used=carryover['all_history_used']), indent=2))
        return 0
    setup = args.shared_repo/'docs/final_sprint/s3-v1/setup'
    result = execute(config, authorization, carryover, shared_repo=args.shared_repo, output=args.output,
        owner_path=args.server_owner, tokenizer_path=setup/'tokenizer.json', tokenizer_provenance=setup/'tokenizer_provenance.json')
    print(json.dumps({key: result.get(key) for key in ('status', 'research_probe_passed', 'research_artifact_produced',
        'elapsed_seconds', 'http_requests', 'this_probe', 'pool_cumulative', 'all_history_cumulative')}, indent=2))
    return 0 if result['research_probe_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
