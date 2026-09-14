"""Read only; compact progress from the recorded journal and server log."""
from pathlib import Path
from datetime import datetime, timezone
import json

REPORT=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-research-15m-v2')
run=REPORT/'run_01'
out=dict(observed_at_utc=datetime.now(timezone.utc).isoformat())
rows=[]
path=run/'probe/events.jsonl'
if path.exists():
    for line in path.read_text(encoding='utf-8').splitlines():
        try: rows.append(json.loads(line))
        except ValueError: pass
calls={}
for row in rows:
    if row['kind']=='call': calls[row['payload']['attempt_id']]=row['payload']
    if row['kind']=='telemetry':
        out['sample']={k:row['payload'].get(k) for k in ('elapsed_seconds','ram_available_bytes','pagefile_delta_bytes')}
out['calls']=[{k:c.get(k) for k in ('attempt_id','role','purpose','generation_stage','status','elapsed_seconds','prompt_tokens','output_tokens','total_tokens','finish_reason','error_type')} for c in calls.values()]
if (run/'probe/result.json').exists():
    result=json.loads((run/'probe/result.json').read_text(encoding='utf-8-sig'))
    out['result']={k:result.get(k) for k in ('status','research_probe_passed','research_artifact_produced','elapsed_seconds','error_type','error','http_requests','pool_remaining','server_stop')}
log=run/'server/server.stderr.log'
if log.exists(): out['server_tail']=log.read_text(encoding='utf-8',errors='replace').splitlines()[-2:]
print(json.dumps(out,ensure_ascii=False,indent=2))
