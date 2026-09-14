from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,zipfile

STAGE=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
PREVIOUS=REPO/'docs/final_sprint/s3-reference-fix-v1'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def write(name,value): (STAGE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

baseline=load(PREVIOUS/'runtime_manifest.json')['files']
for entry in baseline:
    if digest(REPO/entry['path'])!=entry['sha256']:
        raise RuntimeError('Concurrent source conflict: '+entry['path'])
files=[dict(path=path.relative_to(STAGE/'runtime').as_posix(),sha256=digest(path))
       for path in sorted((STAGE/'runtime').rglob('*')) if path.is_file()]
changes=[]
for entry in files:
    destination=REPO/entry['path']
    before=digest(destination) if destination.exists() else None
    if before!=entry['sha256']:
        changes.append(dict(path=entry['path'],before_sha256=before,after_sha256=entry['sha256']))
write('source_inventory.json',baseline)
write('fixture_inventory.json',[])
write('runtime_manifest.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
    source_repository=str(REPO),files=files))
write('change_manifest.json',dict(changes=changes,baseline_file_count=len(baseline),
    prior_version='s3-reference-fix-v1',public_budget_config_changed=False))
previous_result=PREVIOUS/'run_01/probe/result.json'
write('budget_carryover.json',dict(result_path=str(previous_result),sha256=digest(previous_result),
    basis='Cumulative usage includes original failed capability trial and reference-fix-v1.'))
config=load(STAGE/'trial_config.json')
config['model_config_version']='granite-h-micro-cpu-reference-fix-v2'
write('trial_config.json',config)
authorization=load(STAGE/'authorization.json')
authorization['amendment']='Clarify existing content-anchor rules and frozen source identity, with the same shared A-D contract and no new budget or retry allowance.'
write('authorization.json',authorization)
(STAGE/'PREVIOUS_STATUS.md').write_bytes((REPO/'docs/final_sprint_status.md').read_bytes())
with zipfile.ZipFile(STAGE/'runtime_source.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
    for entry in files: archive.write(STAGE/'runtime'/entry['path'],entry['path'])
print(json.dumps(dict(runtime_files=len(files),changed_files=len(changes),changes=changes,
    archive_sha256=digest(STAGE/'runtime_source.zip')),indent=2))
