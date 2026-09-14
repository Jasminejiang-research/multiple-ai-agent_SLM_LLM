"""Archive the confirmed stopped request; record user-confirmed interruption."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, shutil, subprocess
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-90m-fix-v2'
RUN=REPORT/'run_01'; AUDIT=RUN/'audit'; AUDIT.mkdir(exist_ok=True)
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
result=load(RUN/'probe/result.json')
if result['server_stop'] != dict(status='owned_process_tree_terminated',pid=21440,
    identity_method='native_handle_and_persisted_identity',lease_released=False,restart_requires_explicit_reconciliation=True):
    raise RuntimeError('Unexpected termination proof')
shell=shutil.which('pwsh') or shutil.which('powershell')
command="""$ErrorActionPreference='Stop'
$models=@(Get-Process -Name 'ollama','llama-server' -ErrorAction SilentlyContinue | Select-Object Id,ProcessName)
$listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 11434 | Select-Object LocalPort,OwningProcess)
@{model_processes=$models;listeners=$listeners} | ConvertTo-Json -Depth 4 -Compress
"""
response=subprocess.run([shell,'-NoProfile','-Command',command],capture_output=True,text=True,timeout=20,
    check=True,creationflags=subprocess.CREATE_NO_WINDOW)
observed=json.loads(response.stdout)
if observed['model_processes'] or observed['listeners']: raise RuntimeError('Active model process or listener')
lease_root=(REPO/'data/granite_endpoint_leases').resolve()
leases=list(lease_root.glob('*.lease.json'))
if len(leases)!=1: raise RuntimeError('Unexpected active leases')
source=leases[0].resolve()
if source.parent!=lease_root or load(source)!=dict(run_id='ec727380-df80-4429-afcb-98075fdf6639',
    attempt_id='ed35c676-08ab-4b6d-9b5a-462a557ab921',status='inflight_or_unknown'):
    raise RuntimeError('Unexpected lease; preserve it')
target=(AUDIT/'terminated_unknown_request.lease.json').resolve()
if not target.is_relative_to(AUDIT.resolve()) or target.exists(): raise RuntimeError('Preserve existing archive')
raw=source.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
source.rename(target)
if target.read_bytes()!=raw: raise RuntimeError('Lease content changed')
proof=dict(observed_at_utc=datetime.now(timezone.utc).isoformat(),**observed,
    active_leases_after=len(list(lease_root.glob('*.lease.json'))), confirmed_owned_stop=result['server_stop'],
    lease_archive=str(target), lease_sha256=digest, retained_unknown_token_reservation=85923,
    user_confirmed_interruption='你的测试被我手动中断，因为我预告SLM生成一份完整的计划书将会超过90分钟',
    technical_stop_reason=result['resources']['reason'],maximum_sample_gap_seconds=result['resources']['maximum_observed_sample_gap_seconds'])
(AUDIT/'external_cleanup.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
(AUDIT/'INTERRUPTION.md').write_text('''# User-confirmed interruption

The user explicitly confirmed manually interrupting this test because Research already took more than 20 minutes.
Original controller result remains `resource_stopped`: after a 2048.078-second observation gap the new guard cancelled the request.
This is not evidence of an unexplained automatic Windows sleep or a new model decode error. System/Execution requests were accepted and released; explicit user power actions remain authoritative.

The body passed (703 output tokens, 196.359 seconds). Grounding never returned a complete response; its output and usage remain unknown.
Server progress counters are not final usage or a complete plan. No structure repair or Critic was invoked.
Real run: 2 requests, 4994 known total tokens plus 85923 retained unknown reservation, 3584.688 seconds including the interruption and cleanup.
The fresh 5400-second allowance has 1815.312 seconds and 34 requests/409083 charged tokens remaining.
All-history cumulative: 18 requests, 387486 charged tokens, 13778.171 seconds. No previous consumption is refunded.

Latest user instruction authorizes simplifying Research and limiting its total generation time to 20 minutes. No full-D restart was authorized by this interruption record.
''',encoding='utf-8')
shutil.copy2(Path(__file__),REPORT/Path(__file__).name)
print(json.dumps(proof,ensure_ascii=False))
