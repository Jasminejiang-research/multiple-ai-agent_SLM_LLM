from pathlib import Path
import hashlib,json,shutil
STAGE=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
PRIOR=REPO/'docs/final_sprint/s3-two-stage-v1'
files=json.loads((PRIOR/'runtime_manifest.json').read_text(encoding='utf-8'))['files']
for entry in files:
    if hashlib.sha256((REPO/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
        raise RuntimeError('Concurrent modification: '+entry['path'])
for entry in files:
    dest=STAGE/'runtime'/entry['path']
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists(): raise RuntimeError('Preserve existing staging file')
    shutil.copy2(REPO/entry['path'],dest)
for name in ('trial_runner.py','test_trial_runner.py','trial_config.json','authorization.json',
             'Invoke-RecoveryTrial.ps1','cleanup_owned.py','inspect_recovery.py','install_bundle.py',
             'audit_assembly.py','history_inventory.py'):
    shutil.copy2(PRIOR/name,STAGE/name)
shutil.copytree(PRIOR/'support',STAGE/'support')
(STAGE/'source_inventory.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
(STAGE/'validation').mkdir(exist_ok=True)
(STAGE/'PREVIOUS_STATUS.md').write_bytes((REPO/'docs/final_sprint_status.md').read_bytes())
print('Verified and copied',len(files),'retained source/input files.')
