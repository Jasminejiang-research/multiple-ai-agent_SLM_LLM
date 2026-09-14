from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
items=[]
for directory in (REPO/'docs/final_sprint',REPO/'data'):
    for path in sorted(directory.rglob('*')):
        if path.is_file() and 's3-90m-fix-v1' not in path.parts:
            items.append(dict(path=path.relative_to(REPO).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
with (ROOT/'history_inventory.json').open('x',encoding='utf-8') as stream: json.dump(items,stream,indent=2)
public=REPO/'slm/configs/granite_preflight_cpu_v2.json'
launcher=REPO/'slm/start_granite.ps1'
with (ROOT/'external_dependencies.json').open('x',encoding='utf-8') as stream:
    json.dump([dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (public,launcher)],stream,indent=2)
print(json.dumps(dict(historical_files=len(items),public_config_sha256=hashlib.sha256(public.read_bytes()).hexdigest())))
