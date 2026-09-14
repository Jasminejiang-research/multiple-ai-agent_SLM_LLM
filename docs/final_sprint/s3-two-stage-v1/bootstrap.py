from pathlib import Path
import hashlib,json,shutil

STAGE=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
prior=REPO/'docs/final_sprint/s3-reference-fix-v2'
files=json.loads((prior/'runtime_manifest.json').read_text())['files']
for entry in files:
    src=REPO/entry['path']
    if hashlib.sha256(src.read_bytes()).hexdigest()!=entry['sha256']:
        raise RuntimeError('Source differs from last verified retained version: '+entry['path'])
for entry in files:
    dest=STAGE/'runtime'/entry['path']
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists(): raise RuntimeError('Existing stage file: '+str(dest))
    shutil.copy2(REPO/entry['path'],dest)
for name in ('trial_runner.py','test_trial_runner.py','trial_config.json','authorization.json',
             'Invoke-RecoveryTrial.ps1','cleanup_owned.py','inspect_recovery.py','install_bundle.py','prepare_bundle.py'):
    shutil.copy2(prior/name,STAGE/name)
shutil.copytree(prior/'support',STAGE/'support')
(STAGE/'source_inventory.json').write_text(json.dumps(files,indent=2))
(STAGE/'validation').mkdir(exist_ok=True)
print('Copied and verified',len(files),'files; no model calls.')
