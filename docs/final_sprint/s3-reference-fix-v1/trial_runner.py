"""Non-formal schema probe -> Research -> complete D, sharing remaining approved budget."""
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
from support.capability_base import CapabilityConfig, ContextCheckedProvider, validate_authorization
from schemas.evidence import StrictModel, canonical_hash
from slm.granite_provider import inspect_ollama
from slm.granite_preflight import load_context_tokenizer
from slm.owned_ollama import OwnedOllama
from slm.resource_monitor import ResourceMonitor, WindowsResourceProbe
from slm.factories import build_slm_review_workflow
from workflow.contract_context import ContractContext
from workflow.contract_generation import ContractGenerator, PROMPT_VERSION
from schemas.contract_outputs import CONTRACT_VERSION
from workflow.review_events import EventJournal
from workflow.review_runtime import BoundedClient, LocalRequestLease


class RecoveryConfig(CapabilityConfig):
    model_config_version: Literal['granite-h-micro-cpu-reference-fix-v1'] = 'granite-h-micro-cpu-reference-fix-v1'


class SchemaLimitProbe(StrictModel):
    # Diagnostic output only, not a proposal or accepted GroundedClaim.
    financial_value_ids: list[Literal['months','starting_cash']] = Field(max_length=2, json_schema_extra={'uniqueItems':True})


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def verified_carryover(record):
    path = Path(record['result_path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['sha256']:
        raise ValueError('Prior run evidence hash mismatch')
    result = json.loads(raw)
    if result.get('case_id') != 'ai_education' or result.get('formal_eligible') is not False:
        raise ValueError('Carryover must be this non-formal AI education trial')
    budget = result['workflow']['budget']
    return dict(elapsed_seconds=result['elapsed_seconds'], request_count=budget['request_count'],
                charged_total_tokens=budget['charged_total_tokens'])


class TrialBudget:
    def __init__(self, config, prior, *, clock=monotonic):
        if (any(type(prior.get(key)) is not int or prior[key] < 0 for key in ('request_count','charged_total_tokens')) or
            type(prior.get('elapsed_seconds')) not in (float,int) or not math.isfinite(prior['elapsed_seconds']) or prior['elapsed_seconds'] < 0):
            raise ValueError('Invalid prior budget usage')
        self.config, self.prior, self.clock = config, dict(prior), clock
        self.started = clock()
        self.requests, self.tokens = prior['request_count'], prior['charged_total_tokens']
        self.phases = set()
        self.remaining()

    def remaining(self):
        values = dict(run_seconds=self.config.run_seconds-self.prior['elapsed_seconds']-(self.clock()-self.started),
            max_requests=self.config.max_requests-self.requests,
            max_total_tokens=self.config.max_total_tokens-self.tokens)
        if any(value <= 0 for value in values.values()):
            raise ValueError('Approved cumulative trial budget exhausted')
        return values

    def consume(self, name, budget):
        if name in self.phases: raise ValueError('Phase budget already accounted')
        self.phases.add(name)
        self.requests += budget['request_count']
        self.tokens += budget['charged_total_tokens']

    def summary(self):
        elapsed = self.clock()-self.started
        return dict(this_run_request_count=self.requests-self.prior['request_count'],
            this_run_charged_total_tokens=self.tokens-self.prior['charged_total_tokens'],
            this_run_elapsed_seconds=elapsed, cumulative_request_count=self.requests,
            cumulative_charged_total_tokens=self.tokens,
            cumulative_elapsed_seconds=self.prior['elapsed_seconds']+elapsed)


def execute(config, authorization, prior, *, shared_repo, output, owner_path, tokenizer_path, tokenizer_provenance):
    validate_authorization(config, authorization)
    ledger = TrialBudget(config, prior)
    journal = EventJournal(output, str(uuid4()))
    cancel = Event()
    deadline_fired = Event()
    owner = OwnedOllama(owner_path, journal=journal, endpoint=config.endpoint)
    monitor = timer = provider = None
    phases = {}
    result = dict(case_id='ai_education', formal_eligible=False, formal_runs_started=0, gemini_calls=0,
        public_config_changed=False, complete_proposal_produced=False, phases=phases)
    def deadline():
        deadline_fired.set()
        cancel.set()
        journal.emit('shared_trial_deadline', ledger.summary())
        owner.stop()
    try:
        owner.validate()
        timer = Timer(ledger.remaining()['run_seconds'], deadline)
        timer.daemon = True
        timer.start()
        metadata = inspect_ollama(config)
        tokenizer = load_context_tokenizer(tokenizer_path, tokenizer_provenance)
        context = ContractContext.from_case(ROOT/'runtime/docs/final_sprint/s0-v1','ai_education',condition='D')
        probe = WindowsResourceProbe(endpoint=config.endpoint)
        def cpu_probe():
            observation = probe()
            for loaded in observation.get('loaded_models') or []:
                if (loaded.get('name','').removesuffix(':latest') != config.model_alias or
                    loaded.get('context_length') != 32768 or loaded.get('size_vram') != 0):
                    raise ValueError('Unexpected model placement or context')
            return observation
        monitor = ResourceMonitor(cpu_probe, journal, cancel, interval=config.sample_seconds, abort=owner.stop)
        monitor.start()
        provider = ContextCheckedProvider(config, model_digest=metadata['model_digest'], tokenizer=tokenizer)
        journal.emit('recovery_manifest',dict(config=config.model_dump(mode='json'),authorization=authorization,
            prior_consumption=prior,remaining=ledger.remaining(),model_metadata=metadata,
            contract_version=CONTRACT_VERSION,prompt_version=PROMPT_VERSION,
            packet_sha256=context.packet_sha256,brief_sha256=context.brief_sha256,
            formal_eligible=False,research_probe_uses_real_inputs=True,full_d_uses_fresh_real_upstream=True))

        def run_config(output_cap=None):
            updates = ledger.remaining()
            if output_cap is not None: updates['max_output_tokens'] = output_cap
            return config.review_config('smoke',model_digest=metadata['model_digest']).model_copy(update=updates)

        def phase(name, action, *, output_cap=None):
            phase_journal = EventJournal(journal.directory/name,str(uuid4()))
            client = BoundedClient(provider,run_config(output_cap),phase_journal,cancel=cancel,
                local_lease=LocalRequestLease(Path(shared_repo)/'data/granite_endpoint_leases',config.endpoint))
            client.input_refs = [dict(artifact_id='packet',artifact_version=1,sha256=context.packet_sha256),
                dict(artifact_id='brief',artifact_version=1,sha256=context.brief_sha256)]
            record = dict(status='failed')
            try:
                client.begin_node(name)
                details = action(client, phase_journal)
                client.check()
                if provider.last_raw.get('done_reason') != 'stop':
                    raise ValueError('Probe did not end naturally')
                record.update(status='passed',**details)
            except (Exception,KeyboardInterrupt) as exc:
                record.update(error_type=type(exc).__name__,error=str(exc)[:1200])
            finally:
                if client.node_started is not None:
                    try:
                        client.end_node('completed' if record['status']=='passed' else 'failed')
                    except Exception as exc:
                        record.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:1200])
                record['budget'] = client.snapshot()
                ledger.consume(name, record['budget'])
                phases[name] = record
                phase_journal.emit('phase_result', record)
                (phase_journal.directory/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                journal.emit('phase_result',dict(name=name,**record,cumulative=ledger.summary()))
            return record['status']=='passed'

        def native_test(client, phase_journal):
            with client.attempt_scope(logical_task_id='native_schema_bound.v1',role='schema_probe',artifact_version=1,
                schema_sha256=canonical_hash(SchemaLimitProbe.model_json_schema()),packet_sha256=context.packet_sha256,
                batch_number=None,purpose='generate',task_purpose='generate'):
                candidate = client.generate_structured_once(
                    'Return financial_value_ids with exactly 100 entries alternating months and starting_cash. The native response schema takes precedence over this conflicting length request.',
                    SchemaLimitProbe,temperature=0,system_instruction='This is a JSON array-bound transport diagnostic, not business analysis.')
            values = candidate.financial_value_ids
            if len(values) != 2: raise ValueError('Native adversarial bound probe inconclusive: expected 2 entries')
            return dict(requested_entries=100,schema_max_items=2,observed_entries=len(values),
                distinct_entries=len(set(values)),raw_response=provider.last_raw,
                claim='Observed maxItems behavior only; proposal uniqueness is independently validated in code.')

        def research_test(client, phase_journal):
            generator = ContractGenerator(client,task_sink=lambda value:phase_journal.emit('logical_task',value),
                attempt_scope=client.attempt_scope)
            artifact = generator.generate(context,'research')
            context.verify_artifact(artifact)
            phase_journal.emit('research_artifact',artifact.as_dict())
            (phase_journal.directory/'research.json').write_text(json.dumps(artifact.as_dict(),ensure_ascii=False,indent=2),encoding='utf-8')
            return dict(artifact_sha256=artifact.sha256,contract_passed=True,natural_completion=True)

        native_ok = phase('native_schema_probe',native_test,output_cap=128)
        research_ok = native_ok and phase('research_probe',research_test)
        if not research_ok:
            phases['full_d'] = dict(status='not_run',reason='native/Research prerequisite did not pass')
            result['status'] = 'failed'
        else:
            workflow = build_slm_review_workflow(context,config=run_config(),provider=provider,cancel=cancel,
                local_lease=LocalRequestLease(Path(shared_repo)/'data/granite_endpoint_leases',config.endpoint),
                output_dir=journal.directory/'full_d')
            full = workflow.run()
            ledger.consume('full_d', full['budget'])
            phases['full_d'] = full
            result['status'] = full['status']
            artifact = next((workflow.artifacts[key] for key in ('writer.effective','writer.revision','writer.initial') if key in workflow.artifacts),None)
            if artifact is not None:
                context.verify_artifact(artifact)
                export = workflow.journal.directory/'internal_export'
                if not export.exists():
                    export = journal.directory/'complete_artifact_before_workflow_failure'
                    context.export(artifact,export)
                result.update(complete_proposal_produced=True,proposal_directory=str(export),external_ready=False)
    except (Exception,KeyboardInterrupt) as exc:
        result.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:1200])
        journal.emit('recovery_error',dict(error_type=type(exc).__name__,error=str(exc)[:1200]))
    finally:
        if timer: timer.cancel()
        resources = monitor.close() if monitor else None
        proof = owner.stop()
        result.update(elapsed_seconds=ledger.summary()['this_run_elapsed_seconds'],budget=ledger.summary(),
            resources=resources,server_stop=proof,deadline_fired=deadline_fired.is_set(),
            http_requests=provider.http_requests if provider else 0)
        if resources and resources['status'] != 'passed': result['status'] = 'resource_stopped'
        if deadline_fired.is_set(): result['status'] = 'timeout'
        journal.emit('recovery_result',result)
        (journal.directory/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    for name in ('shared-repo','output','server-owner'):
        parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    config = RecoveryConfig.model_validate(read_json(ROOT/'trial_config.json'))
    authorization = read_json(ROOT/'authorization.json')
    validate_authorization(config,authorization)
    prior = verified_carryover(read_json(ROOT/'budget_carryover.json'))
    if args.check_only:
        print(json.dumps(dict(status='ready',prior=prior,remaining=TrialBudget(config,prior).remaining(),model_calls=0)))
        return 0
    setup = args.shared_repo/'docs/final_sprint/s3-v1/setup'
    result = execute(config,authorization,prior,shared_repo=args.shared_repo,output=args.output,
        owner_path=args.server_owner,tokenizer_path=setup/'tokenizer.json',tokenizer_provenance=setup/'tokenizer_provenance.json')
    print(json.dumps({key:result.get(key) for key in ('status','complete_proposal_produced','elapsed_seconds','http_requests','budget')},indent=2))
    return 0 if result['status']=='completed' and result['complete_proposal_produced'] else 2


if __name__=='__main__':
    raise SystemExit(main())
