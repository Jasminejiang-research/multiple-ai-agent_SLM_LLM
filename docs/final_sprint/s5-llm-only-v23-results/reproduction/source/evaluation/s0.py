"""Validate S0 inputs offline. This module cannot execute a model or a run."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse


def sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical_hash(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def local_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError(f'Path escapes packet root: {relative}')
    return path


def request_requirements(batches: int = 4) -> dict[str, dict[str, int]]:
    """Bounds, not approved caps; optional transport retry is shown separately."""
    if isinstance(batches, bool) or not isinstance(batches, int) or batches < 1:
        raise ValueError('batches must be a positive integer')
    result = {}
    for condition, fixed, revision in [('A', 0, 0), ('B', 4, batches), ('C', 7, 3 + batches), ('D', 7, 3 + batches)]:
        base = fixed + batches
        maximum = base + revision
        result[condition] = {'minimum': base, 'all_semantic_revisions': maximum,
                             'with_one_structure_repair_per_task': 2 * maximum,
                             'including_one_transport_retry_per_attempt': 4 * maximum}
    return result


def validate_packet(root: Path, packet: dict) -> list[str]:
    errors = []
    body = {k: v for k, v in packet.items() if k != 'packet_sha256'}
    if packet.get('packet_sha256') != canonical_hash(body):
        errors.append('packet hash mismatch')
    if packet.get('review_status') not in ('pending', 'approved'):
        errors.append('invalid review status')
    if packet.get('review_status') == 'approved' and not packet.get('approval_record'):
        errors.append('approval requires an explicit user record')
    sources = packet.get('sources', [])
    ids = [source['source_id'] for source in sources]
    if not ids or len(ids) != len(set(ids)):
        errors.append('source IDs must be nonempty and unique')
    if set(ids) != set(packet.get('allowlist_source_ids', [])):
        errors.append('source allowlist mismatch')
    urls = set(packet.get('allowlist_urls', []))
    for source in sources:
        if source.get('status') != 'captured_pending_review':
            errors.append(f"{source['source_id']}: source not captured")
        for key in ('url', 'final_url'):
            url = source.get(key, '')
            if url not in urls or urlparse(url).scheme != 'https':
                errors.append(f"{source['source_id']}: URL outside allowlist")
        for kind in ('html', 'txt'):
            try:
                path = local_path(root, source[kind + '_path'])
                if sha256(path) != source[kind + '_sha256']:
                    errors.append(f"{source['source_id']}: {kind} hash mismatch")
            except (OSError, ValueError, KeyError) as exc:
                errors.append(str(exc))
    if not packet.get('chunks'):
        errors.append('packet must contain fixed evidence chunks')
    source_map = {s['source_id']: s for s in sources}
    for chunk in packet.get('chunks', []):
        source = source_map.get(chunk['source_id'])
        if not source:
            errors.append('chunk has unknown source ID')
            continue
        try:
            lines = local_path(root, source['txt_path']).read_text(encoding='utf-8').splitlines()
            start, end = chunk['line_start'], chunk['line_end']
            if start < 1 or end < start or end > len(lines):
                raise ValueError('invalid chunk line range')
            if chunk['text'] != '\n'.join(lines[start - 1:end]):
                errors.append('chunk content differs from snapshot')
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    return errors


def validate_bundle(root: Path, *, require_frozen: bool = False) -> dict:
    errors = []
    pending = []
    manifest = json.loads((root / 'bundle_manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        try:
            if sha256(local_path(root, entry['path'])) != entry['sha256']:
                errors.append('artifact hash mismatch: ' + entry['path'])
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
    protocol = json.loads((root / 'protocol.json').read_text(encoding='utf-8'))
    if protocol['condition_order'] != ['A', 'B', 'C', 'D'] or protocol['planned_runs'] != 8 or protocol['independent_cases'] != 2:
        errors.append('protocol matrix must remain two cases by A-D')
    if protocol['academic_weights'] != [0.25, 0.20, 0.15, 0.15, 0.15, 0.10]:
        errors.append('academic weights differ from authority')
    if protocol['comparisons'] != [['B','A'], ['C','B'], ['C','D']]:
        errors.append('comparison scope differs from authority')
    if protocol['request_requirements'] != request_requirements():
        errors.append('request arithmetic mismatch')
    if protocol['formal_freeze_status'] != 'frozen':
        pending.append('formal code/model/config freeze is pending')
    for field in ('code_snapshot_hash', 'prompt_version', 'schema_version', 'model_config_version',
                  'max_output_tokens', 'run_max_requests', 'run_max_total_tokens'):
        if not protocol['runtime_freeze'].get(field):
            pending.append('runtime freeze missing: '+field)
    for gate in ('S1', 'S2', 'S3_D_preflight', 'S4'):
        if protocol['acceptance'].get(gate) != 'passed':
            pending.append('acceptance pending: '+gate)
    from workflow.nodes import validate_user_brief
    for case_id in protocol['case_ids']:
        folder = root / 'cases' / case_id
        case = json.loads((folder/'case.json').read_text(encoding='utf-8'))
        brief = json.loads((folder/'brief.json').read_text(encoding='utf-8'))
        packet = json.loads((folder/'packet.json').read_text(encoding='utf-8'))
        errors += [case_id+': '+e for e in validate_user_brief(brief)]
        errors += [case_id+': '+e for e in validate_packet(root, packet)]
        if case['brief_sha256'] != sha256(folder/'brief.json') or case['packet_sha256'] != packet['packet_sha256']:
            errors.append(case_id+': case input hash mismatch')
        if packet['case_id'] != case_id or case['case_id'] != case_id:
            errors.append(case_id+': case ID mismatch')
        if case['review_status'] != 'approved' or packet['review_status'] != 'approved':
            pending.append(case_id+': complete brief/evidence awaiting user review')
        elif not case.get('approval_record'):
            errors.append(case_id+': approval record missing')
    with (root/'planned_runs.csv').open(encoding='utf-8',newline='') as stream:
        rows = list(csv.DictReader(stream))
    expected = {(c,a) for c in protocol['case_ids'] for a in 'ABCD'}
    if len(rows) != 8 or {(r['case_id'],r['condition']) for r in rows} != expected:
        errors.append('planned rows must contain exactly two cases by A-D once')
    if len({r['planned_id'] for r in rows}) != len(rows):
        errors.append('duplicate planned ID')
    for row in rows:
        case = json.loads((root/'cases'/row['case_id']/'case.json').read_text(encoding='utf-8'))
        if row['brief_sha256'] != case['brief_sha256'] or row['packet_sha256'] != case['packet_sha256']:
            errors.append('planned input hash mismatch')
        if row['execution_status'] != 'not_run' or row['run_id']:
            errors.append('S0 planning manifest must not contain executed runs')
    return {'status':'invalid' if errors else 'valid_preparation', 'errors':errors, 'pending':pending,
            'formal_execution_allowed':not errors and not pending, 'require_frozen':require_frozen}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1]/'docs/final_sprint/s0-v1')
    parser.add_argument('--require-frozen', action='store_true')
    args = parser.parse_args()
    result = validate_bundle(args.root, require_frozen=args.require_frozen)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if result['errors'] else (2 if args.require_frozen and not result['formal_execution_allowed'] else 0)


if __name__ == '__main__':
    raise SystemExit(main())
