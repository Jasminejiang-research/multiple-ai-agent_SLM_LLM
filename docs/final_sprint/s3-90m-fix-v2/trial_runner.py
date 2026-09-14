"""One non-formal complete D; fresh per-plan allowance requires explicit approval."""
from __future__ import annotations

import argparse
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
from pydantic import Field
from support.capability_base import CapabilityConfig, ContextCheckedProvider
from schemas.contract_outputs import CONTRACT_VERSION
from slm.granite_provider import inspect_ollama
from slm.granite_preflight import load_context_tokenizer
from slm.owned_ollama import OwnedOllama
from slm.resource_monitor import ResourceMonitor, WindowsResourceProbe
from slm.windows_awake import WindowsAwake
from slm.factories import build_slm_review_workflow
from workflow.contract_context import ContractContext
from workflow.contract_generation import PROMPT_VERSION
from workflow.review_events import EventJournal
from workflow.review_runtime import LocalRequestLease


class RecoveryConfig(CapabilityConfig):
    model_config_version: Literal['granite-h-micro-cpu-90m-v2'] = 'granite-h-micro-cpu-90m-v2'
    node_seconds: float = Field(default=5400, gt=0, le=5400)
    run_seconds: float = Field(default=5400, gt=0, le=5400)
    request_seconds: float = Field(default=5400, gt=0, le=5400)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate_authorization(config, record):
    if record.get('approved') is not True or record.get('scope') != 'ai_education_slm_independent_90m_validation':
        raise ValueError('Fresh independent 90-minute validation allowance is pending explicit approval')
    expected = {key: getattr(config, key) for key in ('run_seconds', 'node_seconds', 'request_seconds',
        'max_output_tokens', 'max_requests', 'max_total_tokens', 'max_prompt_chars')}
    if record.get('approved_limits') != expected:
        raise ValueError('Configuration differs from the approved allowance')


def verified_history(record):
    raw = Path(record['result_path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['sha256']:
        raise ValueError('Historical result hash mismatch')
    result = json.loads(raw)
    if result.get('case_id') != 'ai_education' or result.get('formal_eligible') is not False:
        raise ValueError('Expected non-formal AI education history')
    budget = result['budget']
    usage = dict(request_count=budget['cumulative_request_count'],
        charged_total_tokens=budget['cumulative_charged_total_tokens'],
        elapsed_seconds=budget['cumulative_elapsed_seconds'])
    if (any(type(usage[key]) is not int or usage[key] < 0 for key in ('request_count', 'charged_total_tokens')) or
            type(usage['elapsed_seconds']) not in (int, float) or not math.isfinite(usage['elapsed_seconds']) or usage['elapsed_seconds'] < 0):
        raise ValueError('Invalid historical consumption')
    return usage


def execute(config, authorization, history, *, shared_repo, output, owner_path,
            tokenizer_path, tokenizer_provenance):
    # Approval is validated before owning a server, acquiring power requests or calling a model.
    validate_authorization(config, authorization)
    started = monotonic()
    journal = EventJournal(output, str(uuid4()))
    cancel, deadline_fired = Event(), Event()
    owner = OwnedOllama(owner_path, journal=journal, endpoint=config.endpoint)
    monitor = timer = provider = workflow = awake = None
    awake_entered = False
    inference_finished = None
    result = dict(case_id='ai_education', formal_eligible=False, formal_runs_started=0, gemini_calls=0,
        public_config_changed=False, complete_proposal_produced=False, phases={},
        per_plan_deadline_seconds=config.run_seconds, historical_consumption=history,
        deadline_scope='one complete SLM D including all stages, criticism and conditional revisions; independent of LLM')

    def deadline():
        deadline_fired.set()
        cancel.set()
        journal.emit('per_plan_deadline', dict(limit_seconds=config.run_seconds))
        owner.stop()

    try:
        owner.validate()
        timer = Timer(max(0, config.run_seconds - (monotonic() - started)), deadline)
        timer.daemon = True
        timer.start()
        awake = WindowsAwake(journal=journal, reason='Bounded 90-minute AI education plan validation')
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
        remaining = config.run_seconds - (monotonic() - started)
        if remaining <= 0 or cancel.is_set():
            raise TimeoutError('Deadline or resource guard stopped initialization')
        provider = ContextCheckedProvider(config, model_digest=metadata['model_digest'], tokenizer=tokenizer)
        journal.emit('recovery_manifest', dict(config=config.model_dump(mode='json'), authorization=authorization,
            historical_consumption=history, model_metadata=metadata, contract_version=CONTRACT_VERSION,
            prompt_version=PROMPT_VERSION, packet_sha256=context.packet_sha256, brief_sha256=context.brief_sha256,
            standalone_research_duplicate=False, research_gate='the unchanged complete D graph', formal_eligible=False))
        run_config = config.review_config('smoke', model_digest=metadata['model_digest']).model_copy(update={
            'run_seconds': remaining, 'node_seconds': min(config.node_seconds, remaining),
            'request_seconds': min(config.request_seconds, remaining)})
        workflow = build_slm_review_workflow(context, config=run_config, provider=provider, cancel=cancel,
            local_lease=LocalRequestLease(Path(shared_repo)/'data/granite_endpoint_leases', config.endpoint),
            output_dir=journal.directory/'full_d')
        full = workflow.run()
        inference_finished = monotonic() - started
        result['phases']['full_d'] = full
        result['status'] = full['status']
        artifact = next((workflow.artifacts[key] for key in ('writer.effective', 'writer.revision', 'writer.initial')
            if key in workflow.artifacts), None)
        if artifact is not None:
            context.verify_artifact(artifact)
            export = workflow.journal.directory/'internal_export'
            if not export.exists():
                export = journal.directory/'complete_artifact_before_workflow_failure'
                context.export(artifact, export)
            result.update(complete_proposal_produced=True, proposal_directory=str(export), external_ready=False)
    except (Exception, KeyboardInterrupt) as exc:
        result.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:1200])
        journal.emit('recovery_error', dict(error_type=type(exc).__name__, error=str(exc)[:1200]))
    finally:
        inference_finished = inference_finished if inference_finished is not None else monotonic() - started
        if timer:
            timer.cancel()
        try:
            resources = monitor.close() if monitor else None
        except (Exception, KeyboardInterrupt) as exc:
            resources = dict(status='failed', reason='resource_monitor_cleanup_failed', error_type=type(exc).__name__)
        try:
            proof = owner.stop()
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
        budget = workflow.client.snapshot() if workflow else dict(request_count=0, charged_total_tokens=0)
        elapsed = monotonic() - started
        result.update(elapsed_seconds=elapsed, inference_elapsed_seconds=inference_finished,
            cleanup_elapsed_seconds=elapsed-inference_finished, resources=resources, server_stop=proof,
            power_cleanup=power_cleanup, deadline_fired=deadline_fired.is_set(),
            http_requests=provider.http_requests if provider else 0,
            budget=dict(this_run_request_count=budget['request_count'],
                this_run_charged_total_tokens=budget['charged_total_tokens'], this_run_elapsed_seconds=elapsed,
                cumulative_request_count=history['request_count']+budget['request_count'],
                cumulative_charged_total_tokens=history['charged_total_tokens']+budget['charged_total_tokens'],
                cumulative_elapsed_seconds=history['elapsed_seconds']+elapsed,
                this_run_time_limit_seconds=config.run_seconds, per_plan_budget=budget))
        if resources and resources['status'] != 'passed':
            result['status'] = 'resource_stopped'
        if not isinstance(proof, dict) or proof.get('status') != 'owned_process_tree_terminated':
            result['status'] = 'cleanup_failed'
        if deadline_fired.is_set() or inference_finished >= config.run_seconds:
            result['status'] = 'timeout'
        result['within_deadline'] = inference_finished < config.run_seconds
        result['complete_d_passed'] = (result.get('status') == 'completed' and result['complete_proposal_produced']
            and result['within_deadline'] and bool(resources and resources['status'] == 'passed')
            and power_cleanup == 'released')
        journal.emit('recovery_result', result)
        (journal.directory/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    for name in ('shared-repo', 'output', 'server-owner'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    config = RecoveryConfig.model_validate(read_json(ROOT/'trial_config.json'))
    authorization = read_json(ROOT/'authorization.json')
    validate_authorization(config, authorization)
    history = verified_history(read_json(ROOT/'budget_carryover.json'))
    if args.check_only:
        print(json.dumps(dict(status='ready', historical_consumption=history, model_calls=0,
            per_plan_seconds=config.run_seconds, max_requests=config.max_requests, max_total_tokens=config.max_total_tokens)))
        return 0
    setup = args.shared_repo/'docs/final_sprint/s3-v1/setup'
    result = execute(config, authorization, history, shared_repo=args.shared_repo, output=args.output,
        owner_path=args.server_owner, tokenizer_path=setup/'tokenizer.json', tokenizer_provenance=setup/'tokenizer_provenance.json')
    print(json.dumps({key: result.get(key) for key in ('status', 'complete_d_passed', 'complete_proposal_produced',
        'elapsed_seconds', 'http_requests', 'budget')}, indent=2))
    return 0 if result['complete_d_passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
