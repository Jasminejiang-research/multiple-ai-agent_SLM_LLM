from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,shutil

STAGE=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-research-20m-v1'
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
if REPORT.exists(): raise RuntimeError('Preserve existing report; installation target already exists')
for entry in load(STAGE/'source_inventory.json'):
    if digest(REPO/entry['path'])!=entry['sha256']:
        raise RuntimeError('Concurrent modification: '+entry['path'])
changes=load(STAGE/'change_manifest.json')['changes']
for entry in changes:
    path=REPO/entry['path']
    if entry['before_sha256'] is None and path.exists():
        raise RuntimeError('New destination now exists: '+entry['path'])
    if digest(STAGE/'runtime'/entry['path'])!=entry['after_sha256']:
        raise RuntimeError('Stage changed: '+entry['path'])
shutil.copytree(STAGE,REPORT)
for entry in changes:
    path=REPO/entry['path']
    if path.exists():
        backup=REPORT/'before'/entry['path']
        backup.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,backup)
    path.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(REPORT/'runtime'/entry['path'],path)
    if digest(path)!=entry['after_sha256']: raise RuntimeError('Install verification failed')
for entry in load(REPORT/'runtime_manifest.json')['files']:
    if digest(REPORT/'runtime'/entry['path'])!=entry['sha256']: raise RuntimeError('Snapshot mismatch')
receipt=dict(installed_at_utc=datetime.now(timezone.utc).isoformat(),changes=changes,
    runtime_files_verified=len(load(REPORT/'runtime_manifest.json')['files']),model_calls=0,
    previous_uncommitted_versions_backed_up=True,public_budget_config_changed=False)
(REPORT/'install_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps(dict(installed_files=len(changes),runtime_files_verified=receipt['runtime_files_verified'],report=str(REPORT))))
