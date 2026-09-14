"""Read-only compact observation; --audit preserves final responses and verifies files."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT = REPO / 'docs/final_sprint/s3-two-stage-v1'
RUN = REPORT / 'run_01'


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def events(path):
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            pass  # An in-progress final append is inspected on the next read.
    return records


def collect():
    output = dict(observed_at_utc=datetime.now(timezone.utc).isoformat(), phases={})
    records = events(RUN / 'probe/events.jsonl')
    sample = next((row for row in reversed(records) if row['kind'] == 'telemetry'), None)
    if sample:
        output['latest_sample'] = {key:sample['payload'].get(key) for key in
            ('elapsed_seconds','ram_available_bytes','pagefile_delta_bytes')}
        output['latest_sample']['time'] = sample['occurred_at_utc']
    attempts = []
    for phase in ('native_schema_probe','research_probe','full_d'):
        directory = RUN / 'probe' / phase
        if not directory.exists():
            output['phases'][phase] = {'status':'not_started'}
            continue
        latest = {}
        for event in events(directory/'events.jsonl'):
            if event['kind'] == 'call':
                value = event['payload']
                latest[value['attempt_id']] = value
        phase_result = load(directory/'result.json') if (directory/'result.json').exists() else {'status':'running'}
        output['phases'][phase] = {key:phase_result.get(key) for key in
            ('status','error_type','error','contract_passed','natural_completion','observed_entries','distinct_entries')
            if key in phase_result}
        output['phases'][phase]['calls'] = [
            {key:value.get(key) for key in ('attempt_id','role','purpose','generation_stage','status','elapsed_seconds',
                'prompt_tokens','output_tokens','total_tokens','finish_reason','error_type')}
            for value in latest.values()]
        attempts.extend(dict(phase=phase,**value) for value in latest.values())
    result_path = RUN/'probe/result.json'
    if result_path.exists():
        result = load(result_path)
        output['final'] = {key:result.get(key) for key in ('status','complete_proposal_produced',
            'proposal_directory','budget','resources','deadline_fired','http_requests','server_stop')}
    log = RUN/'server/server.stderr.log'
    if log.exists():
        output['server_tail'] = log.read_text(encoding='utf-8',errors='replace').splitlines()[-2:]
    return output, attempts


def audit(output, attempts):
    if (REPORT/'restore_receipt.json').exists():
        raise RuntimeError('Pre-restoration trial audit is frozen; use restore_receipt.json for the retained code state')
    if 'final' not in output:
        raise RuntimeError('Do not finalize audit before the real trial terminates')
    directory = RUN / 'audit'
    directory.mkdir(exist_ok=True)
    sys.path.insert(0, str(REPORT/'runtime'))
    from workflow.generation_constraints import _prefix_issues
    from workflow.grounding_generation import grounding_issues
    from workflow.contract_context import ContractContext
    context = ContractContext.from_case(REPORT/'runtime/docs/final_sprint/s0-v1','ai_education',condition='D')
    call_audit = []
    for index, attempt in enumerate(attempts,1):
        raw = attempt.get('raw_output')
        item = {key:attempt.get(key) for key in ('phase','attempt_id','role','purpose','generation_stage','status',
            'elapsed_seconds','prompt_tokens','output_tokens','total_tokens','finish_reason','error_type')}
        if raw:
            raw_path = directory / f'{index:02d}_{attempt["role"]}_{attempt["purpose"]}.raw.txt'
            raw_path.write_text(raw,encoding='utf-8')
            item.update(raw_file=raw_path.name,raw_sha256=digest(raw_path),
                detected_reference_score_issues=_prefix_issues(raw,set(context.finance.value_ids)))
            item['detected_grounding_issues'] = grounding_issues(raw,context.packet)
        usage = attempt.get('usage_raw')
        if usage:
            usage_path = directory / f'{index:02d}_{attempt["role"]}_{attempt["purpose"]}.usage.json'
            usage_path.write_text(json.dumps(usage,ensure_ascii=False,indent=2),encoding='utf-8')
            item.update(usage_file=usage_path.name,usage_sha256=digest(usage_path))
        call_audit.append(item)
    changes = load(REPORT/'change_manifest.json')['changes']
    expected = {row['path']:row['sha256'] for name in ('source_inventory.json','fixture_inventory.json')
                for row in load(REPORT/name)}
    expected.update({row['path']:row['after_sha256'] for row in changes})
    preservation = dict(installed_file_count=len(expected),
        installed_mismatches=[path for path,sha in expected.items() if not (REPO/path).exists() or digest(REPO/path)!=sha],
        backup_mismatches=[row['path'] for row in changes if row['before_sha256'] and
            digest(REPORT/'before'/row['path'])!=row['before_sha256']],
        runtime_file_count=len(load(REPORT/'runtime_manifest.json')['files']),
        runtime_mismatches=[row['path'] for row in load(REPORT/'runtime_manifest.json')['files'] if
            digest(REPORT/'runtime'/row['path'])!=row['sha256']],
        prior_trial_evidence_unchanged=digest(Path(load(REPORT/'budget_carryover.json')['result_path']))==load(REPORT/'budget_carryover.json')['sha256'],
        archive_sha256=digest(REPORT/'runtime_source.zip'))
    output.update(attempts=call_audit,preservation=preservation)
    (directory/'audit_summary.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    return dict(audit_file=str(directory/'audit_summary.json'),preservation=preservation,
                final=output['final'],attempts=call_audit)


if __name__=='__main__':
    snapshot, calls = collect()
    print(json.dumps(audit(snapshot,calls) if '--audit' in sys.argv else snapshot,ensure_ascii=False,indent=2))
