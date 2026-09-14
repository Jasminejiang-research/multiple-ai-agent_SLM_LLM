"""Freeze tested sources and exact before/after hashes for narrow installation."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, zipfile

ROOT=Path(__file__).resolve().parent
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
before={row['path']:row['sha256'] for row in json.loads((ROOT/'source_inventory.json').read_text())}
files=[]
for path in sorted((ROOT/'runtime').rglob('*')):
    if not path.is_file() or any(part in ('__pycache__','.pytest_cache') for part in path.parts): continue
    relative=path.relative_to(ROOT/'runtime').as_posix()
    files.append(dict(path=relative,sha256=sha(path)))
if set(before)-{row['path'] for row in files}: raise RuntimeError('Source deletion is not allowed')
changes=[dict(path=row['path'],before_sha256=before.get(row['path']),after_sha256=row['sha256'])
         for row in files if before.get(row['path'])!=row['sha256']]
(ROOT/'runtime_manifest.json').write_text(json.dumps(dict(files=files),indent=2),encoding='utf-8')
(ROOT/'change_manifest.json').write_text(json.dumps(dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
    changes=changes),indent=2),encoding='utf-8')
with zipfile.ZipFile(ROOT/'runtime_source.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for row in files: archive.write(ROOT/'runtime'/row['path'],row['path'])
print(json.dumps(dict(runtime_files=len(files),changed_files=len(changes),changes=[row['path'] for row in changes])))
