"""Read existing S3 events and write a compact audit; never starts a model or next package."""
import json
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import sys

root=Path(sys.argv[1]).resolve()
report=root/'docs/final_sprint/s3-v1'
runs=[]
attempts=[]
for folder in sorted(report.glob('real_preflight_*')):
    result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    runs.append(dict(directory=folder.name,result=result))
    for log in sorted(folder.glob('*/events.jsonl')):
        calls={}
        for line in log.read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event['kind']=='call':
                calls[event['payload']['attempt_id']]=event['payload']
        for call in calls.values():
            usage=call['usage_raw'] or {}
            attempts.append(dict(run=folder.name,phase=log.parent.name,role=call['role'],purpose=call['purpose'],
                status=call['status'],error_type=call['error_type'],elapsed_seconds=call['elapsed_seconds'],
                prompt_tokens=call['prompt_tokens'],output_tokens=call['output_tokens'],total_tokens=call['total_tokens'],
                prefill_ns=usage.get('prompt_eval_duration'),generation_ns=usage.get('eval_duration'),
                prefill_tokens_per_second=usage.get('prefill_tokens_per_second'),prefill_rate_basis=usage.get('prefill_rate_basis'),
                generation_tokens_per_second=usage.get('generation_tokens_per_second'),finish_reason=call['finish_reason'],
                usage_missing_reason=call['usage_missing_reason'],prompt_hash=call['prompt_hash'],schema_hash=call['schema_hash'],
                raw_output_chars=None if call['raw_output'] is None else len(call['raw_output']),
                event_path=str(log.relative_to(root)).replace('\\','/')))
preserved=[]
baseline=json.loads((report/'installation_receipt.json').read_text(encoding='utf-8-sig'))
for file in baseline['preserved_history']:
    actual=hashlib.sha256(Path(file['path']).read_bytes()).hexdigest()
    preserved.append(dict(path=file['path'],sha256=actual,unchanged=actual==file['sha256']))
assert all(f['unchanged'] for f in preserved)
authorities=[]
for doc in baseline['authority_documents']:
    actual=hashlib.sha256(Path(doc['path']).read_bytes()).hexdigest()
    authorities.append(dict(path=doc['path'],sha256=actual,unchanged=actual==doc['sha256']))
assert all(d['unchanged'] for d in authorities)
code={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted((root/'slm').glob('*granite*')) if p.is_file()}
code['slm/owned_ollama.py']=hashlib.sha256((root/'slm/owned_ollama.py').read_bytes()).hexdigest()
code['slm/resource_monitor.py']=hashlib.sha256((root/'slm/resource_monitor.py').read_bytes()).hexdigest()
audit=dict(package='S3',recorded_at_utc=datetime.now(timezone.utc).isoformat(),runs=runs,attempts=attempts,
    physical_model_calls=len(attempts),known_prompt_tokens=sum(a['prompt_tokens'] or 0 for a in attempts),
    known_output_tokens=sum(a['output_tokens'] or 0 for a in attempts),
    attempts_with_missing_total_usage=sum(a['total_tokens'] is None for a in attempts),
    gemini_calls=0,formal_runs_started=0,formal_planned_count=8,next_package_started=False,
    historical_files=preserved,authority_documents=authorities,code_sha256=code)
destination=report/'evidence_audit.json'
with destination.open('x',encoding='utf-8') as stream:
    json.dump(audit,stream,ensure_ascii=False,indent=2)
print(json.dumps(dict(physical_model_calls=len(attempts),attempts=attempts,
    last_result=runs[-1]['result'],preserved_history=len(preserved)),ensure_ascii=False,indent=2))
