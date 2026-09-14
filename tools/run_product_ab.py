"""One-shot, audited comparison of existing product entry points; no frozen cases.

This harness lives outside the inspected source tree. It changes transport
accounting/timeouts only, not generation prompts, schemas, retrieval, or outputs.
Prepare is offline. Execute requires an explicit flag and never resumes a run.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

HARNESS_VERSION = 'product-ab-v3-accepted-per-agent'


class BudgetAdmissionError(RuntimeError):
    """A durable, dimension-specific refusal before a generation dispatch."""

    def __init__(self, details):
        self.details = details
        super().__init__('Comparison budget rejected before dispatch: ' +
                         ', '.join(item['metric'] for item in details['violations']))


def request_bounds(contents, config, *, content_tokens=None):
    """Never label UTF-8 bytes as measured tokens.

    Developer API count_tokens accepts contents but not system/schema config
    in the installed SDK. Count the contents, bound the remaining serialized
    configuration separately, and retain explicit framing/output headroom.
    This is still conservative admission, not an exact full-request count.
    """
    if not isinstance(contents, str):
        raise ValueError('This text-only harness does not admit multimodal requests')
    output_limit = config.get('max_output_tokens')
    if isinstance(output_limit, bool) or not isinstance(output_limit, int) or output_limit < 1:
        raise ValueError('An explicit positive output limit is required')
    if content_tokens is not None and (isinstance(content_tokens, bool) or
            not isinstance(content_tokens, int) or content_tokens < 1):
        raise ValueError('Invalid provider content token count')
    # Full thinking headroom is deliberately retained; no change to generation
    # config or removal of thinking accounting is needed to fix the byte gate.
    output_bound = output_limit + 32768
    if content_tokens is None:
        input_bound = len(json.dumps({'contents':contents, 'config':config},
                                    ensure_ascii=False).encode('utf-8')) + 4096
        method = 'utf8_upper_bound_not_measured_tokens'
    else:
        input_bound = content_tokens + len(json.dumps(config, ensure_ascii=False).encode('utf-8')) + 4096
        method = 'provider_content_count_plus_config_byte_bound_and_framing'
    return dict(input_bound=input_bound, output_bound=output_bound,
                total_bound=input_bound+output_bound,
                reserved_usd=(input_bound*0.30+output_bound*2.50)/1e6,
                method=method, measured_content_tokens=content_tokens)


def arm_token_limit(limits, arm):
    return limits.get('arm_total_tokens', {}).get(arm, limits.get('per_arm_total_tokens', float('inf')))


def admission_violations(snapshot, limits, bound, arm=None):
    """Keep currency and token constraints separate, including arm scopes."""
    checks = [('requests', snapshot['llm_requests']+1, limits['llm_requests']),
              ('total_tokens', snapshot['total_tokens']+bound['total_bound'], limits['total_tokens']),
              ('cost_usd', snapshot['llm_cost_usd']+snapshot.get('unresolved_reservation_usd',0)+bound['reserved_usd'],
               limits['llm_cost_usd'])]
    if 'per_arm_requests' in limits:
        checks.append(('arm_requests', snapshot.get('arm_requests',0)+1, limits['per_arm_requests']))
    if 'per_arm_total_tokens' in limits or 'arm_total_tokens' in limits:
        checks.append(('arm_tokens', snapshot.get('arm_tokens',0)+bound['total_bound'], arm_token_limit(limits, arm)))
    return [dict(metric=metric, projected=projected, limit=limit)
            for metric, projected, limit in checks if projected > limit]


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=encode), encoding='utf-8')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(source):
    paths = [source / 'app.py']
    for folder in ('agents', 'workflow', 'schemas', 'prompts', 'rag', 'tools', 'storage', 'knowledge_base'):
        paths.extend(p for p in (source / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix in ('.py', '.md', '.json', '.txt', '.yaml', '.yml'))
    return {p.relative_to(source).as_posix(): sha(p) for p in sorted(paths)}


def bootstrap(source):
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source / '.venv/Lib/site-packages'))
    sys.path.insert(0, str(source))
    from dotenv import load_dotenv
    load_dotenv(source / '.env', override=False)
    os.environ['DEFAULT_MODEL'] = 'gemini-2.5-flash'
    os.environ['LLM_MAX_OUTPUT_TOKENS_PER_REQUEST'] = '16384'
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'


def selected_arms(values=None):
    arms=list(values or ('A','B'))
    if not arms or len(arms)!=len(set(arms)) or any(arm not in ('A','B') for arm in arms):
        raise ValueError('Arms must be a unique non-empty subset of A and B')
    return arms


def prepare(source, input_path, directory, arms=None):
    if directory.exists():
        raise FileExistsError('Refusing to replace any prior comparison')
    payload = read(input_path)
    from workflow.nodes import input_validator_node
    from workflow.preflight import check_preflight
    from rag.knowledge_base import load_knowledge_base_documents
    from google.genai import types
    assert types.HttpOptions(timeout=120000, retry_options=types.HttpRetryOptions(attempts=1))
    validation = input_validator_node({'user_brief': payload['brief']})
    if validation.get('missing_info'):
        raise ValueError(validation['missing_info'])
    preflight = check_preflight(knowledge_base_dir=source/'knowledge_base',
                               output_dir=directory.parent, allow_tavily_degradation=False)
    if not preflight.is_ready:
        raise ValueError([asdict(i) for i in preflight.errors])
    documents = load_knowledge_base_documents(source/'knowledge_base')
    order = selected_arms(arms)
    if len(order)>1:
        random.Random(20260911).shuffle(order)
    manifest = dict(harness_version=HARNESS_VERSION, prepared_at=now(), source=str(source), input=payload, order=order,
        seed=20260911, classification='one_case_one_run_per_arm_exploratory_product_comparison',
        model='gemini-2.5-flash', code_sha256=inventory(source), harness_sha256=sha(Path(__file__)),
        limits=dict(llm_cost_usd=0.80, llm_requests=28, total_tokens=540000,
                    per_arm_requests=24, per_arm_total_tokens=240000,
                    arm_total_tokens={'A':240000,'B':420000},
                    web_requests=2, web_payg_upper_usd=0.016, per_arm_seconds=2400,
                    token_count_requests=28),
        admission_policy='B token allowance 420000, A 240000, combined 540000; currency cap unchanged. Conservative logged count refinement; count failure stops generation.',
        output_acceptance_policy='Formal product output after at most one correction for A / each B actor; residual issues retained, not a draft or quality approval.',
        pricing=dict(input_per_million=0.30, output_including_thinking_per_million=2.50,
                     checked_date='2026-09-11', llm_url='https://ai.google.dev/gemini-api/docs/pricing',
                     search_url='https://docs.tavily.com/documentation/api-credits'),
        entrypoints=dict(A='app.generate_proposal: single role, no Web/RAG, BusinessProposal, temperature 0.4',
            B='workflow.multi_agent_graph.build_multi_agent_workflow_graph: exact graph used by app.run_multi_agent_pipeline, live Web/RAG, ProposalDraft, native role temperatures'),
        differences=['Native schemas, role prompts, temperatures and retrieval differ; not an isolated agent-count effect.',
            'No app.db writes: graph updates and raw responses persisted in this comparison instead.',
            'SDK automatic retries disabled; native explicit validation/503 corrections remain counted.',
            'No frozen evidence, case whitelist, manually supplied finance model or outcome edits.',
            'Brief fields transcribed from user idea; common verification/output instructions are explicit in input.',
            'No statistical significance or generalization from one case.'],
        preflight=dict(gemini_configured=preflight.gemini_available,
                       tavily_configured=preflight.tavily_available, knowledge_documents=len(documents)))
    directory.mkdir(parents=True, exist_ok=False)
    save(directory/'manifest.json', manifest)
    save(directory/'manifest_lock.json', {'sha256': sha(directory/'manifest.json')})
    print(json.dumps({'status':'prepared_no_api_calls','directory':str(directory),
                      'preflight':manifest['preflight'],'order':order}, ensure_ascii=False), flush=True)


class Audit:
    def __init__(self, directory, limits):
        self.directory, self.limits = directory, limits
        self.arm = ''
        self.deadline = float('inf')
        self.requests = self.tokens = self.web_requests = 0
        self.cost = self.unresolved_reservation = 0.0
        self.usage_incomplete = False
        self.token_count_requests = 0
        self.arm_usage = {}
        self.rejections = 0

    def event(self, kind, **data):
        with (self.directory/'events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(dict(at=now(),arm=self.arm,kind=kind,**data), ensure_ascii=False, default=encode)+'\n')
        print(json.dumps(dict(arm=self.arm,kind=kind,**{k:v for k,v in data.items()
                         if k in ('call','node','status','cost_usd','error_type','results')}), ensure_ascii=False), flush=True)

    def snapshot(self):
        arm = self.arm_usage.get(self.arm, {'requests':0, 'tokens':0})
        return dict(llm_requests=self.requests, total_tokens=self.tokens,
                    llm_cost_usd=self.cost, unresolved_reservation_usd=self.unresolved_reservation,
                    usage_incomplete=self.usage_incomplete, web_requests=self.web_requests,
                    web_payg_upper_usd=self.web_requests*0.008,
                    token_count_requests=self.token_count_requests,
                    arm_requests=arm['requests'], arm_tokens=arm['tokens'])

    def guard(self):
        if time.monotonic() >= self.deadline:
            raise RuntimeError('Per-arm dispatch deadline reached')
        if self.usage_incomplete:
            raise RuntimeError('Uncertain provider usage: refusing further paid calls')

    def reject(self, kwargs, details):
        self.rejections += 1
        details.update(snapshot=self.snapshot(), next_call=self.requests+1)
        save(self.directory/self.arm/'rejections'/f'{self.rejections:03d}.json',
             dict(request=dict(model=kwargs['model'], contents=kwargs['contents'],
                               config=kwargs['config'].model_dump(mode='json',exclude_none=True)),
                  admission=details))
        self.event('admission_rejected', violations=details['violations'])
        raise BudgetAdmissionError(details)

    def admit(self, delegate, kwargs):
        self.guard()
        config = kwargs['config'].model_dump(mode='json', exclude_none=True)
        if kwargs['model'] != 'gemini-2.5-flash':
            raise ValueError('No verified pricing/admission policy for this model')
        initial = request_bounds(kwargs['contents'], config)
        violations = admission_violations(self.snapshot(), self.limits, initial, self.arm)
        if not violations:
            return initial
        # A measured count cannot rescue an exhausted actual budget/count cap.
        actual = self.snapshot()
        exhausted = (self.tokens >= self.limits['total_tokens'] or
                     self.cost >= self.limits['llm_cost_usd'] or
                     actual['arm_tokens'] >= arm_token_limit(self.limits, self.arm))
        if exhausted or any(v['metric'] in ('requests','arm_requests') for v in violations):
            self.reject(kwargs, dict(violations=violations, bound=initial, refined=False))
        if self.token_count_requests >= self.limits.get('token_count_requests', self.limits['llm_requests']):
            self.reject(kwargs, dict(violations=[dict(metric='token_count_requests',
                projected=self.token_count_requests+1,
                limit=self.limits.get('token_count_requests',self.limits['llm_requests']))], bound=initial))
        self.token_count_requests += 1
        self.event('token_count_dispatch', next_call=self.requests+1)
        try:
            counted = delegate.count_tokens(model=kwargs['model'], contents=kwargs['contents'])
            bound = request_bounds(kwargs['contents'], config, content_tokens=counted.total_tokens)
            if counted.total_tokens is None:
                raise ValueError('Provider omitted content token count')
        except Exception as exc:
            self.event('token_count_error', error_type=type(exc).__name__)
            self.reject(kwargs, dict(violations=[dict(metric='token_count_unavailable',
                error_type=type(exc).__name__)], bound=initial))
        self.guard()  # Counting must not grant extra run time.
        self.event('token_count_response', content_tokens=counted.total_tokens, bound=bound)
        violations = admission_violations(self.snapshot(), self.limits, bound, self.arm)
        if violations:
            self.reject(kwargs, dict(violations=violations, bound=bound, refined=True))
        return bound

    def generate(self, delegate, **kwargs):
        bound = self.admit(delegate, kwargs)
        reserve = bound['reserved_usd']
        config = kwargs['config'].model_dump(mode='json', exclude_none=True)
        self.requests += 1
        arm_usage = self.arm_usage.setdefault(self.arm, dict(requests=0,tokens=0))
        arm_usage['requests'] += 1
        call = self.requests
        prefix = self.directory/self.arm/'calls'/f'{call:03d}'
        save(prefix.with_suffix('.request.json'), dict(model=kwargs['model'], contents=kwargs['contents'], config=config))
        self.unresolved_reservation += reserve
        self.event('llm_dispatch', call=call, reserved_usd=reserve, admission=bound)
        started = time.monotonic()
        try:
            response = delegate.generate_content(**kwargs)
        except Exception as exc:
            status = getattr(exc, 'code', None)
            rejected = status in (400, 401, 403, 404, 429)
            if rejected:
                self.unresolved_reservation -= reserve
            else:
                self.usage_incomplete = True
            save(prefix.with_suffix('.error.json'), dict(error_type=type(exc).__name__, message=str(exc),
                 status=status, usage_unknown=not rejected, seconds=time.monotonic()-started))
            self.event('llm_error', call=call, error_type=type(exc).__name__, status=status)
            raise
        # Until valid accounting is processed, any persistence/metadata failure
        # must leave the reservation locked and prevent the other arm dispatching.
        self.usage_incomplete = True
        save(prefix.with_suffix('.response.json'), response)
        usage = response.usage_metadata
        if usage is None or usage.total_token_count is None:
            raise RuntimeError('Missing provider usage; raw response preserved, further dispatch blocked')
        prompt = usage.prompt_token_count or 0
        candidates = usage.candidates_token_count or 0
        thoughts = usage.thoughts_token_count or 0
        if any(isinstance(n,bool) or not isinstance(n,int) or n < 0
               for n in (prompt,candidates,thoughts,usage.total_token_count)) or usage.total_token_count < prompt+candidates+thoughts:
            raise RuntimeError('Inconsistent provider usage; reservation remains locked')
        output = max(candidates+thoughts,
                     usage.total_token_count-prompt)
        cost = (prompt*0.30+output*2.50)/1e6
        self.cost += cost
        self.tokens += usage.total_token_count
        arm_usage['tokens'] += usage.total_token_count
        self.unresolved_reservation -= reserve
        self.usage_incomplete = False
        self.event('llm_response', call=call, tokens=usage.total_token_count,
                   cost_usd=cost, seconds=time.monotonic()-started)
        if usage.total_token_count > bound['total_bound'] or cost > reserve:
            self.usage_incomplete = True
            self.event('admission_bound_exceeded', call=call)
            raise RuntimeError('Provider usage exceeded reserved bound; further dispatch blocked')
        return response

    def search(self, query, allowed_domains, recency, max_results):
        from tools.web_search import search_web
        self.guard()
        if self.web_requests >= self.limits['web_requests']:
            raise RuntimeError('Search budget exhausted')
        self.web_requests += 1
        self.event('web_dispatch', query=query, allowed_domains=allowed_domains, recency=recency)
        try:
            results = search_web(query, allowed_domains, recency, max_results)
        except Exception as exc:
            self.event('web_error', error_type=type(exc).__name__, message=str(exc))
            raise
        save(self.directory/self.arm/f'search_{self.web_requests}.json', dict(query=query, results=results))
        self.event('web_response', results=len(results))
        return results


def execute(source, directory):
    if (directory/'EXECUTION_STARTED.json').exists():
        raise FileExistsError('Run already started; cannot reset accounting or implicitly resume')
    manifest = read(directory/'manifest.json')
    if (manifest.get('harness_version') != HARNESS_VERSION or
        sha(directory/'manifest.json') != read(directory/'manifest_lock.json')['sha256'] or
        manifest['source'] != str(source) or manifest['code_sha256'] != inventory(source) or
        manifest['harness_sha256'] != sha(Path(__file__))):
        raise ValueError('Source/input/harness changed after offline preparation')
    # Exclusive marker must precede all imports that could create provider clients.
    with (directory/'EXECUTION_STARTED.json').open('x', encoding='utf-8') as handle:
        json.dump(dict(at=now(), authorization='Current user explicitly requested this A/B experiment; execute flag acknowledged'), handle)
    import app
    from google import genai
    from google.genai import types
    from workflow.llm_client import LLMClient
    from workflow.multi_agent_graph import build_multi_agent_workflow_graph
    from workflow.run_budget import run_budget
    audit = Audit(directory, manifest['limits'])
    original_init = LLMClient.__init__
    clients = []

    def instrumented_init(instance, *args, **kwargs):
        original_init(instance, *args, **kwargs)
        instance._client.close()
        client = genai.Client(api_key=os.environ['GEMINI_API_KEY'],
            http_options=types.HttpOptions(timeout=120000, retry_options=types.HttpRetryOptions(attempts=1)))
        clients.append(client)
        instance._client = SimpleNamespace(models=SimpleNamespace(
            generate_content=lambda **kw: audit.generate(client.models, **kw)))

    results = {}
    with patch.object(LLMClient, '__init__', instrumented_init):
        for arm in manifest['order']:
            audit.arm = arm
            audit.deadline = time.monotonic() + manifest['limits']['per_arm_seconds']
            arm_dir = directory/arm
            arm_dir.mkdir()
            state = {}
            start = time.monotonic()
            before = audit.snapshot()
            audit.event('arm_start')
            try:
                if inventory(source) != manifest['code_sha256']:
                    raise RuntimeError('Source changed between arms')
                with run_budget(max_requests=manifest['limits']['per_arm_requests'],
                                max_total_tokens=arm_token_limit(manifest['limits'], arm)) as budget:
                    if arm == 'A':
                        proposal = app.generate_proposal(app.create_client(), json.dumps(manifest['input']['brief'],ensure_ascii=False,indent=2))
                        (arm_dir/'proposal.md').write_text(app.proposal_to_markdown(proposal),encoding='utf-8')
                        (arm_dir/'audit_report.md').write_text(app.proposal_audit_to_markdown(proposal),encoding='utf-8')
                        save(arm_dir/'proposal.json', proposal)
                        state = dict(proposal=proposal.model_dump(), product_acceptance=proposal.product_acceptance,
                                     output_path=str(arm_dir/'proposal.md'), audit_path=str(arm_dir/'audit_report.md'))
                    else:
                        graph = build_multi_agent_workflow_graph(web_search_tool=audit.search,
                            knowledge_base_dir=source/'knowledge_base', output_dir=arm_dir, logging_session_factory=None)
                        initial = dict(user_brief=manifest['input']['brief'], run_id=f'product_ab_{directory.name}_{arm}')
                        state.update(initial)
                        for update in graph.stream(initial, stream_mode='updates'):
                            for node, value in update.items():
                                if value:
                                    state.update(value)
                                save(arm_dir/'nodes'/f'{node}.json', value)
                                save(arm_dir/'state.json', state)
                                audit.event('node_complete', node=node)
                        if not state.get('output_path'):
                            raise RuntimeError('Product graph did not export a proposal')
                    state['run_budget'] = budget.snapshot()
                results[arm] = dict(status=state.get('product_acceptance',{}).get('status','output_generated'),
                                    output_path=state['output_path'], audit_path=state.get('audit_path'),
                                    product_acceptance=state.get('product_acceptance'))
            except Exception as exc:
                import traceback
                error = dict(error_type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
                save(arm_dir/'failure.json', error)
                results[arm] = dict(status='failed', error_type=type(exc).__name__, message=str(exc))
            finally:
                save(arm_dir/'state.json', state)
                results[arm].update(seconds=time.monotonic()-start, accounting_before=before,
                                    accounting_after=audit.snapshot(), needs_citation_review=state.get('needs_citation_review'))
                save(arm_dir/'result.json', results[arm])
                save(directory/'results.json',dict(arms=results,accounting=audit.snapshot(),completed_at=now()))
                audit.event('arm_end', status=results[arm]['status'])
    for client in clients:
        client.close()
    print(json.dumps(dict(arms=results,accounting=audit.snapshot()),ensure_ascii=False),flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare','execute'))
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--arms', nargs='+', choices=('A','B'), default=['A','B'],
                        help='Arms to freeze during prepare; execute reads the frozen manifest.')
    parser.add_argument('--allow-paid-execution', action='store_true')
    args = parser.parse_args()
    source, directory = args.source.resolve(), args.directory.resolve()
    bootstrap(source)
    if args.mode == 'prepare':
        if args.input is None:
            parser.error('--input is required for prepare')
        prepare(source, args.input.resolve(), directory, args.arms)
    elif not args.allow_paid_execution:
        parser.error('execute requires --allow-paid-execution')
    else:
        execute(source, directory)


if __name__ == '__main__':
    main()
