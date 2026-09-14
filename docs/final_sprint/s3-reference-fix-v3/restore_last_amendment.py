"""Only restore this task's exact unsuccessful alias amendment; preserve all evidence."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,shutil

REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM').resolve()
REPORT=REPO/'docs/final_sprint/s3-reference-fix-v3'
PREVIOUS=REPO/'docs/final_sprint/s3-reference-fix-v2'
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
result=load(REPORT/'run_01/probe/result.json')
if result['phases']['research_probe']['status']!='failed' or result['complete_proposal_produced']:
    raise RuntimeError('Only an unsuccessful Research alias trial can be restored by this helper')
receipt_path=REPORT/'restore_receipt.json'
if receipt_path.exists(): raise RuntimeError('Restoration already recorded; do not repeat')
changes=load(REPORT/'change_manifest.json')['changes']
for entry in changes:
    path=(REPO/entry['path']).resolve()
    path.relative_to(REPO)
    if digest(path)!=entry['after_sha256']:
        raise RuntimeError('Concurrent modification; preserve it: '+entry['path'])
    if entry['before_sha256'] is not None and digest(REPORT/'before'/entry['path'])!=entry['before_sha256']:
        raise RuntimeError('Backup verification failed')
for entry in changes:
    path=REPO/entry['path']
    if entry['before_sha256'] is None:
        # This exact task-created file remains preserved in REPORT/runtime and its source archive.
        path.unlink()
    else:
        shutil.copy2(REPORT/'before'/entry['path'],path)
baseline=load(PREVIOUS/'runtime_manifest.json')['files']
mismatches=[entry['path'] for entry in baseline if digest(REPO/entry['path'])!=entry['sha256']]
receipt=dict(restored_at_utc=datetime.now(timezone.utc).isoformat(),
    reason='Alias trial did not pass Research; retain the fully tested reference/grounding fix without extra wire alias complexity.',
    restored_to='s3-reference-fix-v2',files=changes,verified_file_count=len(baseline),mismatches=mismatches,
    historical_trial_preserved=True,shared_budget_reset=False)
receipt_path.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
if mismatches: raise RuntimeError('Restoration hash verification failed')
print(json.dumps(receipt,indent=2))
