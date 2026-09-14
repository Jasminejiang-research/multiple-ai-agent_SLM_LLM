from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,zipfile

STAGE=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
PREVIOUS=REPO/'docs/final_sprint/s3-reference-fix-v2'

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
    prior_version='s3-reference-fix-v2',public_budget_config_changed=False))
previous_result=REPO/'docs/final_sprint/s3-reference-fix-v3/run_01/probe/result.json'
write('budget_carryover.json',dict(result_path=str(previous_result),sha256=digest(previous_result),
    basis='Cumulative usage includes original failed capability trial and reference-fix-v1/v2/v3; no quota reset.'))
config=load(STAGE/'trial_config.json')
config['model_config_version']='granite-h-micro-cpu-two-stage-v1'
write('trial_config.json',config)
authorization=load(STAGE/'authorization.json')
authorization['amendment']='User approved the uniform A-D two-stage generation proposal on 2026-09-07: immutable body, exact-span selection, strict canonical assembly; one shared structure repair. Continue real Research then complete D within the remaining prior allowance. Public budgets and formal runs unchanged.'
authorization['repair_scope']='Approved uniform two-stage generation for A-D; real Research then fresh complete D only on Research pass. The one structure repair is shared between both stages of each logical unit. Prior cumulative consumption is retained.'
authorization['expected_model_digest']='eec81a822241037c5d8e47a870b3d26423bfa1b010e02fcdf1b5f9f2de5c3b2b'
authorization['expected_ollama_version']='0.33.2'
write('authorization.json',authorization)
(STAGE/'PREVIOUS_STATUS.md').write_bytes((REPO/'docs/final_sprint_status.md').read_bytes())
with zipfile.ZipFile(STAGE/'runtime_source.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
    for entry in files: archive.write(STAGE/'runtime'/entry['path'],entry['path'])
print(json.dumps(dict(runtime_files=len(files),changed_files=len(changes),changes=changes,
    archive_sha256=digest(STAGE/'runtime_source.zip')),indent=2))
