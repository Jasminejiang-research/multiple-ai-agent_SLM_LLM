"""Assemble only inventoried source/input files and explicit new repair files."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile
from trial_runner import RecoveryConfig

root = Path(__file__).resolve().parent
repo = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(name, obj): (root/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
baseline = read(root/'source_inventory.json') + read(root/'fixture_inventory.json')
new_paths = ['workflow/generation_constraints.py','tests/test_generation_constraints.py','slm/tests/test_reference_bounds.py']
entries, changes = [], []
for entry in baseline:
    path = entry['path']
    if sha(repo/path) != entry['sha256']: raise ValueError(f'Target changed since audit: {path}')
    digest = sha(root/'runtime'/path)
    entries.append(dict(path=path,sha256=digest))
    if digest != entry['sha256']:
        changes.append(dict(path=path,before_sha256=entry['sha256'],after_sha256=digest))
for path in new_paths:
    if (repo/path).exists(): raise ValueError(f'New path collision: {path}')
    digest = sha(root/'runtime'/path)
    entries.append(dict(path=path,sha256=digest))
    changes.append(dict(path=path,before_sha256=None,after_sha256=digest))
archive = root/'runtime_source.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as out:
    for entry in sorted(entries,key=lambda item:item['path']): out.write(root/'runtime'/entry['path'],entry['path'])
write('runtime_manifest.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
    source_repository=str(repo),files=entries,archive_sha256=sha(archive),formal_eligible=False,secrets_excluded=True))
write('change_manifest.json',dict(changes=changes,baseline_file_count=len(baseline),
    full_regression='667 passed, 25 deselected, 3 subtests passed in 115.87s',
    trial_runner_tests='6 passed in 2.26s',public_budget_config_changed=False))
write('trial_config.json',RecoveryConfig().model_dump(mode='json'))
authorization = read(repo/'docs/final_sprint/s3-capability-v1/authorization.json')
authorization.update(repair_confirmation='请按照上述建议，为我修复代码。',
    repair_scope='Shared reference bounds, explicit normalized scores, targeted repair feedback; native schema probe, real Research, then complete D only on Research pass. Prior consumption is carried over.',
    repair_recorded_at_utc=datetime.now(timezone.utc).isoformat())
write('authorization.json',authorization)
prior_path = repo/'docs/final_sprint/s3-capability-v1/run_01/probe/result.json'
write('budget_carryover.json',dict(result_path=str(prior_path),sha256=sha(prior_path)))
print(json.dumps(dict(files=len(entries),changed_files=len(changes),archive_sha256=sha(archive)),indent=2))
