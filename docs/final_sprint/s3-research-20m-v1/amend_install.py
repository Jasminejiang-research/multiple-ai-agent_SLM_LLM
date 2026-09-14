from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil

STAGE = Path(__file__).resolve().parent
REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT = REPO / 'docs/final_sprint/s3-research-20m-v1'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
old = read(REPORT/'runtime_manifest.json')['files']
if (REPORT/'run_01').exists(): raise RuntimeError('Cannot amend a running/final trial')
for row in old:
    if sha(REPO/row['path']) != row['sha256'] or sha(REPORT/'runtime'/row['path']) != row['sha256']:
        raise RuntimeError('Concurrent source change: '+row['path'])
before = {row['path']:row['sha256'] for row in old}
changed = [row for row in read(STAGE/'runtime_manifest.json')['files'] if before.get(row['path']) != row['sha256']]
audit = REPORT/'pre_probe_amendment'
audit.mkdir(exist_ok=False)
for name in ('runtime_manifest.json','change_manifest.json','runtime_source.zip','HANDOFF.md'):
    shutil.copy2(REPORT/name, audit/name)
for row in changed:
    dest = audit/'runtime'/row['path']
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(REPO/row['path'],dest)
    shutil.copy2(STAGE/'runtime'/row['path'],REPO/row['path'])
    shutil.copy2(STAGE/'runtime'/row['path'],REPORT/'runtime'/row['path'])
for name in ('runtime_manifest.json','change_manifest.json','runtime_source.zip','helper_manifest.json'):
    shutil.copy2(STAGE/name,REPORT/name)
shutil.copy2(STAGE/'validation/full_amended.log',REPORT/'validation/full_amended.log')
for row in read(REPORT/'runtime_manifest.json')['files']:
    if sha(REPO/row['path']) != row['sha256']: raise RuntimeError('Post-amendment mismatch')
(audit/'receipt.json').write_text(json.dumps(dict(at_utc=datetime.now(timezone.utc).isoformat(),
    reason='Remove contradictory nonempty financial-reference prompt for brief Research before any real call',
    changes=changed,model_calls=0,runtime_verified=272),indent=2),encoding='utf-8')
shutil.copy2(__file__,REPORT/'amend_install.py')
print(json.dumps(dict(amended_files=len(changed),runtime_verified=272,model_calls=0)))
