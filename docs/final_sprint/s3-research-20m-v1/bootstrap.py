from pathlib import Path
import hashlib, json, shutil
ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
PRIOR=REPO/'docs/final_sprint/s3-90m-fix-v2'
files=json.loads((PRIOR/'runtime_manifest.json').read_text())['files']
for entry in files:
    if hashlib.sha256((REPO/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:
        raise RuntimeError('Concurrent modification: '+entry['path'])
for entry in files:
    target=ROOT/'runtime'/entry['path']; target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): raise RuntimeError('Preserve existing source')
    shutil.copy2(REPO/entry['path'],target)
(ROOT/'source_inventory.json').write_text(json.dumps(files,indent=2),encoding='utf-8')
(ROOT/'validation').mkdir(exist_ok=True)
print('Copied',len(files),'installed source/input files; no running source changed.')
