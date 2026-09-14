"""Reconcile only the known stopped request; preserve its original lease bytes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,os,shutil,subprocess

REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-90m-fix-v1'
RUN=REPORT/'run_01'; AUDIT=RUN/'audit'; AUDIT.mkdir(exist_ok=True)
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
result=load(RUN/'probe/result.json')
owner=load(RUN/'server/server_owner.json')
if result['server_stop']['status']!='owned_process_tree_terminated' or result['server_stop']['pid']!=owner['pid']:
    raise RuntimeError('Owned tree termination is not confirmed')
shell=shutil.which('pwsh') or shutil.which('powershell')
script="""$ErrorActionPreference='Stop'
$models=@(Get-CimInstance Win32_Process -Filter "Name = 'ollama.exe' OR Name = 'llama-server.exe'" | Select-Object ProcessId,ParentProcessId,Name)
$listeners=@(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object LocalPort -eq 11434 | Select-Object LocalPort,OwningProcess)
@{model_processes=$models;listeners=$listeners} | ConvertTo-Json -Depth 4 -Compress
"""
response=subprocess.run([shell,'-NoProfile','-Command',script],capture_output=True,text=True,
    check=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
observed=json.loads(response.stdout)
if observed['model_processes'] or observed['listeners']: raise RuntimeError('Model process or endpoint still active')
lease_root=(REPO/'data/granite_endpoint_leases').resolve()
leases=list(lease_root.glob('*.lease.json'))
if len(leases)!=1: raise RuntimeError('Expected exactly the known quarantined request')
source=leases[0].resolve(); record=load(source)
if source.parent!=lease_root or record != dict(run_id='8e16b33a-073f-4e95-91fc-f9963f0a2c7d',
    attempt_id='07b71c1a-934b-48ae-a937-e54a9ba713fa',status='inflight_or_unknown'):
    raise RuntimeError('Unexpected lease; do not reconcile')
target=(AUDIT/'terminated_unknown_request.lease.json').resolve()
if not target.is_relative_to(AUDIT.resolve()) or target.exists(): raise RuntimeError('Preserve prior archive')
digest=sha(source)
source.rename(target)
if sha(target)!=digest: raise RuntimeError('Lease bytes changed')
proof=dict(observed_at_utc=datetime.now(timezone.utc).isoformat(),**observed,
    active_leases_after=len(list(lease_root.glob('*.lease.json'))),
    confirmed_owned_stop=result['server_stop'],lease_archive=str(target),lease_sha256=digest,
    unknown_usage_remains_unknown=True,retained_unknown_token_reservation=83219)
(AUDIT/'external_cleanup.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
power=Path('C:/Users/JasmineJiang/Projects/multiple_ai_agent/.slm-claim-id-fix-stage/validation/power_events.json')
if power.exists(): shutil.copy2(power,AUDIT/power.name)
(AUDIT/'RESOURCE_COVERAGE.md').write_text('''# Retrospective resource coverage correction

The original result.json is preserved unchanged. Its resource status `passed`
only means no observed sample triggered the previous RAM/pagefile conditions.
It does **not** certify continuous coverage: the maximum sample gap was
2423.437 seconds. Windows power events confirm Modern Standby, with three
reported sleep durations totalling 2989.447614 seconds (about 49m49s).

The run hit its shared 5400-second deadline during its only structure repair.
The controller reports failed/WallClockExceeded even though deadline_fired is
false (the client clock stopped first). 5405.172 seconds includes cleanup.
Full D was not started. No valid complete plan was generated. The known first
grounding response ended naturally and failed claim identity consistency, not
reference-array duplication. CPU throughput including standby is not a valid
estimate of continuously active inference throughput.
''',encoding='utf-8')
shutil.copy2(__file__,REPORT/Path(__file__).name)
print(json.dumps(proof))
