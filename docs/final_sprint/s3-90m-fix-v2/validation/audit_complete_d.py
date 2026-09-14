"""One post-run integrity audit. Never dispatches a model or changes run artifacts.

Exit 0 means the recorded evidence is internally consistent, including an honest
failed run. Check complete_d_verified separately for successful full-plan proof.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


STAGE = Path(__file__).resolve().parents[1]
RUNTIME = STAGE / 'runtime'
sys.path.insert(0, str(RUNTIME))

from schemas.evidence import canonical_hash
from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES
from workflow.contract_context import ContractArtifact, ContractContext, ROLE_SCHEMAS
from workflow.contract_generation import PROMPT_VERSION
from workflow.generation_batches import CONTRACT_BATCH_MODELS, merge_contract_batches
from workflow.generation_constraints import bounded_response_model
from workflow.grounding import claims_in, validate_lineage
from workflow.review_events import replay_events
from workflow.two_stage_generation import SelectionPlan, draft_model, project_body


DEPENDENCIES = {'research': (), 'strategy': ('research',),
                'finance': ('research', 'strategy'), 'writer': ('research', 'strategy', 'finance')}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'Duplicate JSON key: {key}')
        value[key] = item
    return value


def parsed(text):
    return json.loads(text, object_pairs_hook=unique_object)


class Audit:
    def __init__(self):
        self.files, self.failures, self.checks = {}, [], []

    def source(self, path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        self.files[str(path)] = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        return raw

    def json(self, path):
        return parsed(self.source(path).decode('utf-8-sig'))

    def check(self, scope, operation):
        try:
            result = operation()
            self.checks.append(dict(scope=scope, passed=True))
            return result
        except Exception as exc:
            self.failures.append(dict(scope=scope, error_type=type(exc).__name__, detail=str(exc)[:1600]))
            return None

    def stable_sources(self):
        for name, expected in list(self.files.items()):
            assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected['sha256'], f'Source changed: {name}'


def artifact_from(data):
    artifact = ContractArtifact(role=data['role'], version=data['artifact_version'],
        case_id=data['case_id'], packet_sha256=data['packet_sha256'], brief_sha256=data['brief_sha256'],
        payload_json=json.dumps(data['payload'], ensure_ascii=False),
        changes_json=json.dumps(data['confidence_changes'], ensure_ascii=False),
        pruned=data['pruned'], unresolved_major=data['unresolved_major'], contract_version=data['contract_version'])
    assert artifact.as_dict() == data, 'Artifact serialization differs from journal'
    return artifact


def audit_run(run, output):
    # There is no polling path. The parent calls this only after result.json exists.
    if not (run / 'result.json').is_file():
        raise RuntimeError('Run has no final result.json; wait for the real trial to finish')
    if output.exists():
        raise FileExistsError(f'Refusing to replace audit report: {output}')
    if not output.resolve().is_relative_to((STAGE / 'validation').resolve()):
        raise ValueError('Audit output must remain under this stage validation directory')
    if output.resolve().is_relative_to(run.resolve()):
        raise ValueError('Audit must not write inside the source run')
    audit = Audit()
    summary = audit.json(run / 'result.json')
    report = dict(audit_version='complete-d-integrity-v1', source_run=str(run.resolve()),
        created_at_utc=datetime.now(timezone.utc).isoformat(), model_calls=0,
        recorded_status=summary.get('status'), recorded_complete_d_passed=summary.get('complete_d_passed'),
        complete_d_verified=False, tasks=[], artifacts=[],
        limits='Structural, numerical and provenance verification only; semantic support and human Gold approval remain unassessed.')
    # Record the exact validators and helper used for the reconstruction.
    for name in ('workflow/two_stage_generation.py', 'workflow/contract_generation.py',
                 'workflow/contract_context.py', 'workflow/grounding.py', 'workflow/finance_contract.py',
                 'workflow/generation_constraints.py', 'workflow/generation_batches.py',
                 'workflow/review_events.py', 'schemas/contract_outputs.py', 'schemas/evidence.py'):
        audit.source(RUNTIME / name)
    audit.source(Path(__file__))
    case_root = RUNTIME / 'docs/final_sprint/s0-v1'
    for name in ('case.json', 'brief.json', 'packet.json'):
        audit.source(case_root / 'cases/ai_education' / name)
    ctx = ContractContext.from_case(case_root, 'ai_education', condition='D')
    assert len(ctx.finance.expected_values()) == 21
    for source in ctx.packet.sources:
        data = source.model_dump(exclude_unset=True)
        for kind in ('html', 'txt', 'original'):
            if kind + '_path' in data:
                path = (case_root / data[kind + '_path']).resolve()
                assert path.is_relative_to(case_root.resolve())
                audit.source(path)
    report['frozen_inputs'] = dict(packet_sha256=ctx.packet_sha256, brief_sha256=ctx.brief_sha256,
        snapshot_sources=len(ctx.packet.sources), expected_financial_rows=21)
    if (run / 'events.jsonl').exists():
        audit.source(run / 'events.jsonl')
        top = replay_events(run / 'events.jsonl')
        audit.check('top_event_log_closed', lambda: require(not top['truncated_tail'], 'Truncated event log'))
        final_events = [event['payload'] for event in top['events'] if event['kind'] == 'recovery_result']
        audit.check('top_result_matches_durable_event', lambda: require(final_events and final_events[-1] == summary,
                    'Final result does not match its recovery_result event'))
        manifests = [event['payload'] for event in top['events'] if event['kind'] == 'recovery_manifest']
        if manifests:
            manifest = manifests[-1]
            audit.check('manifest_frozen_inputs_and_prompt', lambda: require(
                manifest['packet_sha256'] == ctx.packet_sha256 and manifest['brief_sha256'] == ctx.brief_sha256
                and manifest['prompt_version'] == PROMPT_VERSION, 'Frozen inputs or installed prompt differ'))
    full_dir = run / 'full_d'
    if not (full_dir / 'result.json').exists():
        audit.check('missing_full_d_not_reported_success', lambda: require(
            not summary.get('complete_d_passed') and not summary.get('complete_proposal_produced'),
            'Full-D result absent despite claimed success'))
        report['full_d_started_or_closed'] = False
        return finish_report(audit, report, output)
    full = audit.json(full_dir / 'result.json')
    audit.source(full_dir / 'events.jsonl')
    replay = replay_events(full_dir / 'events.jsonl')
    events, calls = replay['events'], replay['attempts']
    audit.check('full_event_log_closed', lambda: require(not replay['truncated_tail'], 'Truncated full-D log'))
    audit.check('top_full_result_matches', lambda: require(summary['phases']['full_d'] == full,
                'Top result and full-D result differ'))
    result_events = [event['payload'] for event in events if event['kind'] == 'run_result']
    audit.check('full_result_matches_durable_event', lambda: require(result_events and result_events[-1] == full,
                'Full-D result differs from durable event'))
    audit.check('real_nonformal_d_identity', lambda: require(
        summary['formal_eligible'] is False and summary['formal_runs_started'] == 0
        and summary['gemini_calls'] == 0 and full['condition'] == 'D' and full['mock_only'] is False
        and all(call['provider'] == 'local' and call['run_kind'] == 'smoke' for call in calls),
        'Expected a real, non-formal, local D run'))
    artifacts, artifact_data = {}, {}
    for event in events:
        if event['kind'] != 'artifact':
            continue
        payload = event['payload']
        ref, data = payload['artifact_ref'], payload['artifact']
        def verify_record(ref=ref, data=data):
            require(canonical_hash(data) == ref['sha256'], 'Artifact reference hash mismatch')
            artifact = artifact_from(data)
            ctx.verify_artifact(artifact)
            require(artifact.version == ref['artifact_version'], 'Artifact reference version mismatch')
            return artifact
        artifact = audit.check('artifact:' + ref['artifact_id'], verify_record)
        if artifact is not None:
            artifacts[(ref['artifact_id'], ref['sha256'])] = artifact
            artifact_data[ref['artifact_id']] = (artifact, data)
            report['artifacts'].append(dict(artifact_id=ref['artifact_id'], sha256=ref['sha256'],
                claim_occurrences=len(claims_in(artifact.payload()))))
    latest_tasks = {event['payload']['logical_task_id']: event['payload']
                    for event in events if event['kind'] == 'logical_task'}
    call_by_id = {call['attempt_id']: call for call in calls}
    accepted_calls = {(event['payload']['logical_task_id'], event['payload'].get('generation_stage')):
                      call_by_id[event['payload']['attempt_id']]
                      for event in events if event['kind'] == 'contract_check' and event['payload']['passed']
                      and event['payload'].get('attempt_id') in call_by_id}
    reconstructed, provenance = {}, {}
    for task_id, task in latest_tasks.items():
        if task.get('protocol') != 'body-then-grounding-v1':
            continue
        row = dict(logical_task_id=task_id, completed=task.get('completed', False))
        report['tasks'].append(row)
        if task.get('frozen_draft') is None:
            row['state'] = 'no_accepted_body'
            audit.check('task_no_body:' + task_id, lambda task=task: require(not task['completed'], 'Completed task lacks body'))
            continue
        def verify_task(task=task, row=row):
            body, catalog = task['frozen_draft'], task['selection_catalog']
            first_call = next(call for call in calls if call['logical_task_id'] == task['logical_task_id'])
            refs = {ref['artifact_id']: ref for ref in first_call['input_artifact_refs']}
            def referenced(name):
                ref = refs[name]
                return artifacts[(name, ref['sha256'])]
            upstream = tuple(referenced(role + '.effective') for role in DEPENDENCIES[task['role']])
            previous = referenced(task['role'] + '.initial') if task['artifact_version'] == 2 else None
            canonical = CONTRACT_BATCH_MODELS[task['batch_number'] - 1] if task['batch_number'] else ROLE_SCHEMAS[task['role']]
            require(canonical_hash(canonical.model_json_schema()) == task['schema_sha256'], 'Canonical schema hash differs')
            plan = SelectionPlan(canonical, body, ctx, upstream=upstream, previous=previous,
                logical_task_id=task['logical_task_id'], version=task['artifact_version'])
            require(plan.catalog() == catalog, 'Frozen catalog does not match full input/body reconstruction')
            body_attempt = next(attempt for attempt in reversed(task['attempts'])
                                if attempt['generation_stage'] == 'body' and attempt['passed'])
            require(parsed(body_attempt['raw_output']) == plan.body, 'Accepted body differs from logged body output')
            def verify_physical(stage, schema, expected):
                call = accepted_calls[(task['logical_task_id'], stage)]
                require(call['status'] == 'succeeded', 'Accepted stage lacks a succeeded physical call')
                actual = schema.model_validate(parsed(call['raw_output'])).model_dump(mode='json')
                require(actual == expected, 'Physical raw output differs from accepted stage: ' + stage)
                require(canonical_hash(actual) == call['output_artifact_ref']['sha256'], 'Physical response hash differs')
                require(canonical_hash(schema.model_json_schema()) == call['schema_hash'], 'Physical schema hash differs')
            body_schema = bounded_response_model(draft_model(canonical), ctx.finance.value_ids, packet=ctx.packet)
            verify_physical('body', body_schema, plan.body)
            row.update(body_and_full_catalog_verified=True, body_sha256=plan.body_sha256,
                       body_spans=len(plan.body_spans), evidence_spans=len(plan.evidence_spans))
            if not task['completed']:
                row['state'] = 'body_verified_grounding_incomplete'
                return
            chosen = next(attempt for attempt in reversed(task['attempts'])
                          if attempt['generation_stage'] == 'grounding' and attempt['passed'])
            bounded = bounded_response_model(plan.schema, ctx.finance.value_ids, packet=ctx.packet)
            require(canonical_hash(bounded.model_json_schema()) == chosen['schema_sha256'], 'Grounding schema hash differs')
            selections = bounded.model_validate(parsed(chosen['raw_output'])).model_dump(mode='json')
            verify_physical('grounding', bounded, selections)
            candidate, mapping = plan.assemble(selections)
            require(mapping == task['assembly_mapping'], 'Saved assembly mapping differs')
            require(canonical_hash(candidate.model_dump(mode='json')) == task['assembled_sha256'], 'Assembled hash differs')
            ctx.validate(candidate, version=task['artifact_version'], upstream=upstream,
                         previous=previous if not task['batch_number'] else None)
            if hasattr(candidate, 'financial_values'):
                ctx.finance.validate(candidate.financial_values)
            if hasattr(candidate, 'financial_assumptions'):
                ctx.finance.validate(candidate.financial_assumptions.financial_values)
            if task['batch_number'] and previous:
                old = ctx.verify_artifact(previous)
                for field in canonical.model_fields:
                    if field != 'title':
                        validate_lineage(getattr(old, field), getattr(candidate, field), revision=True)
            key = (task['role'], task['artifact_version'])
            reconstructed.setdefault(key, {})[task['batch_number'] or 0] = candidate
            provenance[key] = (upstream, previous)
            row.update(state='exact_assembly_and_strict_lineage_verified', claim_occurrences=len(mapping),
                       assembled_sha256=task['assembled_sha256'])
        audit.check('task:' + task_id, verify_task)
    for key, batches in reconstructed.items():
        role, version = key
        label = role + ('.revision' if version == 2 else '.initial')
        if label not in artifact_data:
            continue  # A later Writer batch may have failed before an artifact existed.
        def verify_generation_artifact(role=role, version=version, batches=batches, label=label, key=key):
            saved, data = artifact_data[label]
            candidate = merge_contract_batches([batches[n] for n in range(1, 5)]) if role == 'writer' else batches[0]
            upstream, previous = provenance[key]
            accepted = ctx.accept(role, candidate, version=version, upstream=upstream, previous=previous,
                                  pruned=saved.pruned, unresolved_major=saved.unresolved_major)
            require(accepted.as_dict() == data, 'Generated artifact differs from reconstructed assembly/confidence rules')
        audit.check('assembled_artifact:' + label, verify_generation_artifact)
    for label, (effective, _) in artifact_data.items():
        if not label.endswith('.effective'):
            continue
        def verify_effective(label=label, effective=effective):
            base_label = effective.role + ('.revision' if effective.version == 2 else '.initial')
            original = artifact_data[base_label][0].payload()
            final = effective.payload()
            require(project_body(type(original), original.model_dump(mode='json')) ==
                    project_body(type(final), final.model_dump(mode='json')), 'Effective stage changed prose or financial values')
            validate_lineage(original, final, revision=True)
        audit.check('effective_lineage:' + label, verify_effective)
    if summary.get('complete_proposal_produced'):
        def verify_export():
            directory = Path(summary['proposal_directory']).resolve()
            require(directory.is_relative_to(run.resolve()), 'Export path is outside this run')
            exported = audit.json(directory / 'proposal.json')
            saved = next((artifact_data[label] for label in ('writer.effective', 'writer.revision', 'writer.initial')
                          if label in artifact_data), None)
            require(saved is not None and saved[1] == exported, 'Export differs from the final recorded Writer artifact')
            artifact = artifact_from(exported)
            proposal = ctx.verify_artifact(artifact)
            require(len(PROPOSAL_SECTION_FIELD_NAMES) == 13, 'Unexpected canonical section contract')
            for field, title in zip(PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES, strict=True):
                require(getattr(proposal, field).title == title, 'Wrong section title: ' + field)
            ctx.finance.validate(proposal.financial_assumptions.financial_values)
            require(len(proposal.financial_assumptions.financial_values) == 21, 'Expected all 21 financial result rows')
            require(audit.json(directory / 'brief.json') == ctx.brief, 'Exported brief changed')
            require(audit.json(directory / 'packet.json') == ctx.input_payload('writer')['evidence_packet'], 'Exported packet changed')
            # Reuse the actual exporter in a disposable audit-only directory.
            # No original artifact is edited and no rendering logic is duplicated.
            with TemporaryDirectory(prefix='expected_export_', dir=STAGE / 'validation') as temporary:
                expected = ctx.export(artifact, Path(temporary) / 'expected')
                for name in ('proposal.json', 'proposal.md', 'packet.json', 'brief.json'):
                    require(audit.source(directory / name) == (expected / name).read_bytes(), 'Export bytes differ: ' + name)
            return dict(sections=13, exact_financial_metadata_rows=21,
                        financial_numeric_validation='existing Decimal recomputation and frozen rounding tolerance',
                        proposal_sha256=artifact.sha256, directory=str(directory))
        report['export'] = audit.check('complete_export', verify_export)
    report['accounting'] = audit.check('usage_accounting', lambda: verify_accounting(summary, full, calls))
    def verify_outcome():
        terminal = [event['payload'] for event in events if event['kind'] == 'terminal_contract']
        passed = bool(terminal and terminal[-1]['passed'])
        require(passed == bool(full['terminal_contract_passed']), 'Terminal event/result disagree')
        limit = summary['per_plan_deadline_seconds']
        require(0 < limit <= 5400, 'Per-plan deadline exceeds approved 90 minutes')
        require(summary['within_deadline'] == (summary['inference_elapsed_seconds'] < limit), 'Deadline result contradicts duration')
        require(summary['elapsed_seconds'] >= summary['inference_elapsed_seconds'], 'Negative cleanup duration')
        if summary.get('complete_d_passed'):
            require(full['status'] == 'completed' and passed and summary['complete_proposal_produced'], 'False complete-D status')
            require(summary['within_deadline'] and not summary['deadline_fired'], 'Completion exceeded deadline')
            require(summary['resources']['status'] == 'passed' and summary['power_cleanup'] == 'released'
                    and summary['server_stop']['status'] == 'owned_process_tree_terminated', 'Cleanup/resource certification missing')
            require(report.get('export') is not None, 'Complete-D status lacks a verified full export')
        return dict(terminal_contract_passed=passed, inference_elapsed_seconds=summary['inference_elapsed_seconds'],
                    wall_clock_limit_seconds=limit, cleanup_elapsed_seconds=summary['cleanup_elapsed_seconds'])
    report['outcome'] = audit.check('terminal_deadline_cleanup', verify_outcome)
    report['complete_d_verified'] = bool(summary.get('complete_d_passed') and not audit.failures)
    return finish_report(audit, report, output)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_accounting(summary, full, calls):
    budget = summary['budget']['per_plan_budget']
    fields = ('prompt_tokens', 'output_tokens', 'total_tokens')
    known = {field: 0 for field in fields}
    charges, missing = 0, []
    for call in calls:
        counts = [call[field] for field in fields]
        require(all(value is None or type(value) is int and value >= 0 for value in counts), 'Invalid token count')
        for field, value in zip(fields, counts):
            known[field] += value if value is not None else 0
        if any(value is None for value in counts):
            require(bool(call['usage_missing_reason']), 'Unknown usage lacks a reason')
            missing.append(dict(attempt_id=call['attempt_id'], status=call['status'],
                prompt_tokens=counts[0], output_tokens=counts[1], total_tokens=counts[2],
                reservation_tokens=call['reservation_tokens'], budget_token_charge=call['budget_token_charge'],
                usage_missing_reason=call['usage_missing_reason']))
        charge = call['budget_token_charge']
        require(type(charge) is int and charge >= 0, 'Final call lacks retained/actual budget charge')
        expected = counts[2] if counts[2] is not None else max(call['reservation_tokens'], sum(v or 0 for v in counts[:2]))
        require(charge == expected, 'Budget charge differs from actual total or retained estimate')
        charges += charge
    require(budget['request_count'] == len(calls), 'Physical request count differs from journal')
    require(budget['charged_total_tokens'] == charges, 'Charged tokens differ from journal')
    require(budget['usage_missing_calls'] == len(missing), 'Unknown usage count differs')
    for field in fields:
        require(budget['actual_' + field + '_known'] == known[field], 'Known token subtotal differs: ' + field)
    for field in ('request_count', 'charged_total_tokens', 'usage_missing_calls'):
        require(full['budget'][field] == budget[field], 'Top/full budget mismatch: ' + field)
    history, aggregate = summary['historical_consumption'], summary['budget']
    require(aggregate['cumulative_request_count'] == history['request_count'] + len(calls), 'History request sum changed')
    require(aggregate['cumulative_charged_total_tokens'] == history['charged_total_tokens'] + charges, 'History token sum changed')
    require(abs(aggregate['cumulative_elapsed_seconds'] - history['elapsed_seconds'] - summary['elapsed_seconds']) < .001,
            'History elapsed sum changed')
    require(budget['request_count'] <= budget['max_requests'], 'Request budget exceeded')
    if full['status'] == 'completed':
        require(budget['charged_total_tokens'] <= budget['max_total_tokens'], 'Completed run exceeded token budget')
    return dict(requests=len(calls), charged_total_tokens=charges, known_token_subtotals=known,
                unknown_usage_calls=missing, unknown_values_preserved=True,
                expanded_assembly_text_counted_as_model_usage=False)


def finish_report(audit, report, output):
    audit.check('sources_unchanged_during_audit', audit.stable_sources)
    report.update(integrity_status='passed' if not audit.failures else 'failed',
                  complete_d_verified=bool(report['complete_d_verified'] and not audit.failures),
                  checks=audit.checks, failures=audit.failures, source_sha256=audit.files,
                  reproduction=dict(executable=sys.executable,
                      argv=['-B', str(Path(__file__).resolve()), '--run', report['source_run'], '--output', str(output)]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path,
                        help='Finished trial directory containing result.json and full_d/')
    parser.add_argument('--output', type=Path, default=STAGE / 'validation/full_d_integrity_audit.json')
    args = parser.parse_args()
    result = audit_run(args.run.resolve(), args.output.resolve())
    print(json.dumps({key: result[key] for key in ('integrity_status', 'recorded_status',
        'recorded_complete_d_passed', 'complete_d_verified', 'failures')}, ensure_ascii=False, indent=2))
    return 0 if result['integrity_status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
