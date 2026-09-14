"""Explicit, input-bound product Writer batch checkpoints (not run budgets)."""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

_STORE = ContextVar('product_writer_batch_store',default=None)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,
                                     separators=(',',':')).encode('utf-8')).hexdigest()


def checkpoint_path(root: Path, run_id: str) -> Path:
    if not isinstance(run_id,str) or not run_id.strip():
        raise ValueError('Writer checkpoint requires a nonempty run_id')
    return Path(root)/hashlib.sha256(run_id.encode('utf-8')).hexdigest()[:32]


def current_store():
    return _STORE.get()


def write_once(path, data):
    # A partial file after a crash fails closed on read; it is never interpreted
    # as completed work or automatically overwritten with a fresh paid attempt.
    with path.open('x',encoding='utf-8') as handle:
        json.dump(data,handle,ensure_ascii=False,indent=2)
        handle.flush()
        os.fsync(handle.fileno())


class WriterBatchStore:
    def __init__(self, directory: Path, *, resume=False):
        self.directory=Path(directory)
        self.resume=resume
        self.identity=None

    def bind(self, writer_input, prompt):
        from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
        from workflow.product_output_policy import POLICY_VERSION
        root=Path(__file__).resolve().parents[1]
        code={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in (
            'workflow/product_output_policy.py','workflow/product_checkpoint.py','agents/writer.py',
            'schemas/workflow.py','schemas/agent_outputs.py','workflow/generation_batches.py',
            'workflow/product_finance.py','workflow/product_research.py','workflow/structured_repair.py',
            'workflow/product_repair_context.py','workflow/product_acceptance.py',
            'workflow/llm_client.py','workflow/schema_contract.py')}
        identity=digest(dict(input=writer_input.model_dump(mode='json'),prompt=prompt,code=code,
                             policy=POLICY_VERSION,schemas=[m.model_json_schema() for m in PROPOSAL_DRAFT_BATCH_MODELS]))
        manifest=self.directory/'manifest.json'
        if self.resume:
            require_writer_recovery_boundary(self.directory)
            data=json.loads(manifest.read_text(encoding='utf-8'))
            if data.get('identity') != identity:
                raise ValueError('Checkpoint input/evidence/prompt/schema/policy changed; explicit migration required')
            from workflow.run_budget import get_active_run_budget
            history=usage_history(self.directory)
            if history:
                budget=get_active_run_budget()
                if budget is None:
                    raise ValueError('Restore historical run budget before resuming this checkpoint')
                actual=budget.snapshot()
                for key in ('request_count','prompt_tokens','output_tokens','total_tokens','retry_count'):
                    if actual[key] < max(item[key] for item in history):
                        raise ValueError('Resume budget would reset historical usage')
                for key in ('max_requests','max_total_tokens'):
                    prior=[item[key] for item in history if item[key] is not None]
                    if prior and (actual[key] is None or actual[key] > min(prior)):
                        raise ValueError('Resume budget would expand historical limits')
        else:
            write_once(manifest,dict(version=1,identity=identity))
        self.identity=identity
        if self.resume:
            from workflow.product_acceptance import current_acceptance, acceptance_scope
            active = current_acceptance()
            for path in sorted(self.directory.glob('acceptance-*.json')):
                record = json.loads(path.read_text(encoding='utf-8'))
                if record.get('identity') != identity or record.get('sha256') != digest(record['payload']):
                    raise ValueError('Acceptance checkpoint integrity failure')
                if active is None:
                    raise ValueError('Accepted Writer checkpoint requires an active acceptance policy')
                with acceptance_scope(record['payload']) as saved:
                    for actor, count in saved.corrections.items():
                        active.corrections[actor] = max(active.corrections.get(actor,0), count)
                    for issue in saved.issues:
                        active.flag(issue['message'], stage=issue['stage'])
                    for event in saved.events:
                        if event not in active.events:
                            active.events.append(event)

    def get(self, number, model):
        path=self.directory/f'batch-{number}.json'
        if not path.exists():
            return None
        data=json.loads(path.read_text(encoding='utf-8'))
        payload=data['payload']
        if data.get('identity') != self.identity or data.get('batch') != number or data.get('sha256') != digest(payload):
            raise ValueError('Writer batch checkpoint integrity failure')
        return model.model_validate(payload)

    def save(self, number, candidate):
        payload=candidate.model_dump(mode='json')
        write_once(self.directory/f'batch-{number}.json',
                   dict(identity=self.identity,batch=number,sha256=digest(payload),payload=payload))

    def record_usage(self):
        from workflow.product_acceptance import current_acceptance
        active = current_acceptance()
        if self.identity is not None and active is not None:
            payload = active.snapshot()
            write_once(self.directory/f'acceptance-{uuid4().hex}.json',
                       dict(identity=self.identity,payload=payload,sha256=digest(payload)))
        from workflow.run_budget import get_active_run_budget
        budget=get_active_run_budget()
        if self.identity is not None and budget is not None:
            payload=budget.snapshot()
            write_once(self.directory/f'usage-{uuid4().hex}.json',
                       dict(identity=self.identity,payload=payload,sha256=digest(payload)))


def usage_history(directory):
    """Read immutable snapshots, rejecting corrupt or foreign accounting."""
    root=Path(directory)
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    result=[]
    for path in root.glob('usage-*.json'):
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('identity') != manifest['identity'] or data.get('sha256') != digest(data['payload']):
            raise ValueError('Writer checkpoint accounting integrity failure')
        result.append(data['payload'])
    return result


def restore_checkpoint_budget(directory):
    """Restore tokens/requests without any API call; money ledgers remain caller-owned."""
    from workflow.run_budget import RunBudget
    require_writer_recovery_boundary(directory)
    history=usage_history(directory)
    if not history:
        raise ValueError('Checkpoint has no recorded budget; explicit historical accounting is required')
    latest=max(history,key=lambda item:(item['request_count'],item['total_tokens'],item['retry_count']))
    budget=RunBudget(max_requests=latest['max_requests'],max_total_tokens=latest['max_total_tokens'])
    for _ in range(latest['request_count']):
        budget.reserve_request()
    budget.record_usage(prompt_tokens=latest['prompt_tokens'],output_tokens=latest['output_tokens'],total_tokens=latest['total_tokens'])
    for _ in range(latest['retry_count']):
        budget.record_retry()
    return budget


def require_writer_recovery_boundary(directory):
    if (Path(directory)/'downstream-started.json').exists():
        raise ValueError('Checkpoint already entered Critic; Writer-only accounting cannot '
                         'authorize another resume. Use downstream recovery with its complete ledger.')


@contextmanager
def writer_checkpoint(directory, *, resume=False):
    store=WriterBatchStore(directory,resume=resume)
    if resume and not store.directory.is_dir():
        raise FileNotFoundError('Writer checkpoint does not exist')
    store.directory.mkdir(parents=True,exist_ok=True)
    lock=store.directory/'.lock'
    with lock.open('x',encoding='utf-8') as handle:
        handle.write(str(os.getpid()))
    token=_STORE.set(store)
    try:
        yield store
    finally:
        try:
            store.record_usage()
        finally:
            _STORE.reset(token)
            lock.unlink()
