"""Explicitly authorized, non-formal four-hour Granite capability trial.

Reuses the complete D graph. These limits are not accepted as formal A-D config.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from threading import Event, Timer
from time import monotonic
from typing import Literal
from uuid import uuid4

from pydantic import Field
from slm.granite_config import GraniteConfig
from slm.granite_provider import GranitePhysicalProvider, inspect_ollama, render_granite_pair
from slm.granite_preflight import load_context_tokenizer
from slm.owned_ollama import OwnedOllama
from slm.resource_monitor import ResourceMonitor, WindowsResourceProbe
from slm.factories import build_slm_review_workflow
from workflow.contract_context import ContractContext
from workflow.review_config import ReviewRunConfig
from workflow.review_events import EventJournal, replay_events
from workflow.review_runtime import LocalRequestLease, ProviderFailure


class CapabilityRunConfig(ReviewRunConfig):
    condition: Literal['D'] = 'D'
    provider: Literal['local'] = 'local'
    run_kind: Literal['smoke'] = 'smoke'
    config_version: Literal['slm-capability-v1'] = 'slm-capability-v1'
    node_seconds: float = Field(default=14400, gt=0, le=14400)
    run_seconds: float = Field(default=14400, gt=0, le=14400)
    request_seconds: float = Field(default=14400, gt=0, le=14400)


class CapabilityConfig(GraniteConfig):
    model_config_version: Literal['granite-h-micro-cpu-4h-capability-v1'] = 'granite-h-micro-cpu-4h-capability-v1'
    gpu_layers: Literal[0] = 0
    context_probe_mode: Literal['chat'] = 'chat'
    status: Literal['nonformal_capability_trial'] = 'nonformal_capability_trial'
    max_requests: Literal[36] = 36
    max_total_tokens: Literal[500000] = 500000
    max_output_tokens: Literal[8192] = 8192
    max_prompt_chars: Literal[90000] = 90000
    node_seconds: float = Field(default=14400, gt=0, le=14400)
    run_seconds: float = Field(default=14400, gt=0, le=14400)
    request_seconds: float = Field(default=14400, gt=0, le=14400)

    def review_config(self, run_kind, *, model_digest):
        if run_kind != 'smoke' or not model_digest:
            raise ValueError('Capability trial requires an identified local non-formal smoke')
        return CapabilityRunConfig(model_exact_id=f'{self.model_alias}@{model_digest}',
            model_config_version=self.model_config_version,max_requests=self.max_requests,
            max_total_tokens=self.max_total_tokens,max_output_tokens=self.max_output_tokens,
            max_prompt_chars=self.max_prompt_chars,node_seconds=self.node_seconds,
            run_seconds=self.run_seconds,request_seconds=self.request_seconds,transport_retries=0)


def validate_authorization(config, record):
    expected={key:getattr(config,key) for key in ('run_seconds','node_seconds','request_seconds',
        'max_output_tokens','max_requests','max_total_tokens','max_prompt_chars')}
    if record.get('scope')!='ai_education_slm_nonformal_4h' or record.get('approved') is not True:
        raise ValueError('Explicit trial authorization is missing')
    if record.get('approved_limits')!=expected:
        raise ValueError('Trial limits do not match the authorized record')


class ContextCheckedProvider(GranitePhysicalProvider):
    def __init__(self,*args,tokenizer,**kwargs):
        super().__init__(*args,**kwargs)
        self.tokenizer=tokenizer
        self.http_requests=0

    def invoke(self,request):
        messages=[]
        if request.system_instruction:
            messages.append(dict(role='system',content=request.system_instruction))
        messages.append(dict(role='user',content=request.prompt))
        expected=len(self.tokenizer.encode(render_granite_pair(messages),add_special_tokens=False).ids)
        if expected+request.max_output_tokens>self.config.context_tokens:
            self.last_raw=None
            self.last_diagnostic=dict(http_dispatched=False,reason='input_plus_output_exceeds_context',
                expected_input_tokens=expected,output_cap=request.max_output_tokens,context_tokens=32768)
            # No HTTP request was sent, so this lease can be released safely.
            raise ProviderFailure('ContextCapacityExceeded',request_finished=True)
        self.http_requests+=1
        response=super().invoke(request)
        self.last_diagnostic.update(http_dispatched=True,expected_input_tokens=expected)
        if type(response.prompt_tokens) is int:
            self.last_diagnostic['input_count_delta']=response.prompt_tokens-expected
            if abs(response.prompt_tokens-expected)>8:
                raise ProviderFailure('OllamaInputCountMismatch',request_finished=True)
        return response


def run_trial(*,config,authorization,shared_repo,output_dir,owner_path,tokenizer_path,tokenizer_provenance):
    validate_authorization(config,authorization)
    root=Path(__file__).resolve().parents[1]
    journal=EventJournal(output_dir,str(uuid4()))
    started=monotonic()
    cancel,deadline_fired=Event(),Event()
    owner=OwnedOllama(owner_path,journal=journal,endpoint=config.endpoint)
    monitor=watchdog=workflow=provider=None
    resources=None
    summary=dict(kind='nonformal_slm_capability_trial',case_id='ai_education',formal_eligible=False,
        formal_runs_started=0,gemini_calls=0,public_config_changed=False,complete_proposal_produced=False)
    def deadline():
        deadline_fired.set()
        cancel.set()
        journal.emit('trial_deadline',dict(seconds=config.run_seconds))
        owner.stop()
    try:
        owner.validate()
        metadata=inspect_ollama(config)
        tokenizer=load_context_tokenizer(tokenizer_path,tokenizer_provenance)
        context=ContractContext.from_case(root/'docs/final_sprint/s0-v1','ai_education',condition='D')
        probe=WindowsResourceProbe(endpoint=config.endpoint)
        def cpu_probe():
            value=probe()
            for loaded in value.get('loaded_models') or []:
                if loaded.get('name','').removesuffix(':latest')!=config.model_alias or loaded.get('context_length')!=32768 or loaded.get('size_vram')!=0:
                    raise ValueError('Loaded model is not the authorized CPU-only 32K model')
            return value
        monitor=ResourceMonitor(cpu_probe,journal,cancel,interval=config.sample_seconds,abort=owner.stop)
        journal.emit('trial_manifest',dict(config=config.model_dump(mode='json'),authorization=authorization,
            model_metadata=metadata,packet_sha256=context.packet_sha256,brief_sha256=context.brief_sha256,
            runtime_root=str(root),shared_lease_root=str(Path(shared_repo)/'data/granite_endpoint_leases'),
            formal_eligible=False,whole_graph_real_upstream=True,synthetic_upstream=False))
        provider=ContextCheckedProvider(config,model_digest=metadata['model_digest'],tokenizer=tokenizer)
        run_config=config.review_config('smoke',model_digest=metadata['model_digest'])
        # Setup consumes part of the same deadline. No node or batch resets the trial timer.
        remaining=config.run_seconds-(monotonic()-started)
        if remaining<=0: raise TimeoutError('Trial deadline reached during setup')
        run_config=run_config.model_copy(update={'run_seconds':remaining})
        workflow=build_slm_review_workflow(context,config=run_config,provider=provider,cancel=cancel,
            local_lease=LocalRequestLease(Path(shared_repo)/'data/granite_endpoint_leases',config.endpoint),
            output_dir=journal.directory/'workflow')
        monitor.start()
        watchdog=Timer(remaining,deadline)
        watchdog.daemon=True
        watchdog.start()
        result=workflow.run()
        summary.update(status=result['status'],workflow=result,model_metadata=metadata)
        # A complete genuine Writer artifact remains reviewable even if its final Critic fails.
        artifact=next((workflow.artifacts[k] for k in ('writer.effective','writer.revision','writer.initial')
            if k in workflow.artifacts),None)
        if artifact is not None:
            context.verify_artifact(artifact)
            export=workflow.journal.directory/'internal_export'
            if not export.exists():
                export=journal.directory/'complete_artifact_before_workflow_failure'
                context.export(artifact,export)
            summary.update(complete_proposal_produced=True,proposal_directory=str(export),
                proposal_status='complete_contract_pending_human_review',external_ready=False)
    except (Exception,KeyboardInterrupt) as exc:
        cancel.set()
        summary.update(status='failed',error_type=type(exc).__name__,error=str(exc))
        journal.emit('trial_failure',dict(error_type=type(exc).__name__,error=str(exc)))
    finally:
        if watchdog is not None: watchdog.cancel()
        if monitor is not None: resources=monitor.close()
        proof=owner.stop()
        summary.update(elapsed_seconds=monotonic()-started,resources=resources,server_stop=proof,
            deadline_fired=deadline_fired.is_set(),http_requests=0 if provider is None else provider.http_requests)
        if resources and resources['status']!='passed': summary['status']='resource_stopped'
        if deadline_fired.is_set(): summary['status']='timeout'
        journal.emit('trial_result',summary)
        (journal.directory/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-only',action='store_true')
    for name in ('config','authorization','shared-repo','output-dir','server-owner','tokenizer','tokenizer-provenance'):
        p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    config=CapabilityConfig.model_validate_json(args.config.read_text(encoding='utf-8-sig'))
    authorization=json.loads(args.authorization.read_text(encoding='utf-8-sig'))
    if args.check_only:
        validate_authorization(config,authorization)
        print(json.dumps(dict(status='authorization_valid',model_calls=0)))
        return 0
    result=run_trial(config=config,authorization=authorization,shared_repo=args.shared_repo,output_dir=args.output_dir,
        owner_path=args.server_owner,tokenizer_path=args.tokenizer,tokenizer_provenance=args.tokenizer_provenance)
    print(json.dumps({key:result.get(key) for key in ('status','complete_proposal_produced','proposal_directory','elapsed_seconds','http_requests')},indent=2))
    return 0 if result['status']=='completed' and result['complete_proposal_produced'] else 2


if __name__=='__main__':
    raise SystemExit(main())
