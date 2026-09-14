"""Read completed trial evidence and export exact response copies plus a compact audit."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
repo = root.parents[2]
run = root / 'run_01'
result = json.loads((run / 'probe/result.json').read_text(encoding='utf-8-sig'))
events = [json.loads(line) for line in (run / 'probe/workflow/events.jsonl').read_text(encoding='utf-8-sig').splitlines()]
calls, diagnostics, tasks = {}, {}, {}
for event in events:
    payload = event['payload']
    if event['kind'] == 'call': calls[payload['attempt_id']] = payload
    if event['kind'] == 'physical_provider_diagnostic': diagnostics[payload['attempt_id']] = payload['diagnostic']
    if event['kind'] == 'logical_task': tasks[payload['logical_task_id']] = payload
audit_dir = run / 'audit'
audit_dir.mkdir(exist_ok=False)
rows = []
for number, call in enumerate(sorted(calls.values(), key=lambda c: c['started_at_utc']), 1):
    raw = call['raw_output']
    raw_path = audit_dir / f'research_attempt_{number}.raw.txt'
    raw_path.write_bytes(raw.encode('utf-8'))
    diagnostic = diagnostics[call['attempt_id']]
    native_path = audit_dir / f'research_attempt_{number}.native_response.json'
    native_path.write_text(json.dumps(diagnostic['response'], ensure_ascii=False, indent=2), encoding='utf-8')
    match = re.search(r'"financial_value_ids"\s*:\s*\[', raw)
    tail = raw[match.end():] if match else ''
    values = re.findall(r'"([^"\\]*)"', tail.split(']', 1)[0])
    try:
        json.loads(raw)
        parse_error = None
    except json.JSONDecodeError as exc:
        parse_error = str(exc)
    row = {key: call[key] for key in ('attempt_id','purpose','status','elapsed_seconds','prompt_tokens','output_tokens','total_tokens','finish_reason','error_type','started_at_utc','ended_at_utc')}
    row.update(http_status=diagnostic['http_status'], input_count_delta=diagnostic['input_count_delta'],
        gpu_layers=diagnostic['gpu_layers'], usage_raw=call['usage_raw'], raw_characters=len(raw),
        raw_sha256=hashlib.sha256(raw.encode('utf-8')).hexdigest(), json_parse_error=parse_error,
        financial_array_start=None if not match else match.start(),
        financial_array_has_closing_bracket=']' in tail,
        complete_string_values_in_unclosed_array=len(values), most_common_values=Counter(values).most_common(10),
        raw_output_path=str(raw_path), native_response_path=str(native_path))
    rows.append(row)
manifest = json.loads((root / 'runtime_manifest.json').read_text(encoding='utf-8-sig'))
snapshot_mismatches, source_mismatches = [], []
for entry in manifest['files']:
    path = root / 'runtime' / entry['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
        snapshot_mismatches.append(entry['path'])
inventory = json.loads((root / 'snapshot_source_inventory.json').read_text(encoding='utf-8-sig'))
for entry in inventory:
    path = repo / entry['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
        source_mismatches.append(entry['path'])
baseline = json.loads((root / 'launch_baseline.json').read_text(encoding='utf-8-sig'))
public_hash = hashlib.sha256(Path(baseline['public_config_path']).read_bytes()).hexdigest()
summary = dict(observed_at_utc=datetime.now(timezone.utc).isoformat(), status=result['status'],
    complete_proposal_produced=result['complete_proposal_produced'], elapsed_seconds=result['elapsed_seconds'],
    failed_node=result['workflow']['error'], budget=result['workflow']['budget'],
    deadline_fired=result['deadline_fired'], resources=result['resources'], server_stop=result['server_stop'],
    requests=rows, snapshot_file_count=len(manifest['files']), snapshot_mismatches=snapshot_mismatches,
    original_source_file_count=len(inventory), original_source_mismatches=source_mismatches,
    public_config_sha256=public_hash, public_config_unchanged=public_hash == baseline['public_config_sha256'],
    formal_eligible=False, formal_runs_started=0, gemini_calls=0,
    proposal_files=[str(p) for p in run.rglob('proposal.md')],
    logical_tasks=[{k: v for k, v in task.items() if k != 'attempts'} | {'attempts': [{k:v for k,v in attempt.items() if k != 'raw_output'} for attempt in task['attempts']]} for task in tasks.values()])
(audit_dir / 'audit_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key:summary[key] for key in ('status','complete_proposal_produced','elapsed_seconds','snapshot_file_count','snapshot_mismatches','original_source_file_count','original_source_mismatches','public_config_unchanged','proposal_files')}, indent=2))
print(json.dumps([{'purpose':r['purpose'],'http_status':r['http_status'],'repeated_values':r['most_common_values'][:2],'raw_sha256':r['raw_sha256']} for r in rows], indent=2))
