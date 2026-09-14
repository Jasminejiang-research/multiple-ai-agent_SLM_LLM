"""Read-only post-run Research audit; exit 0 certifies records, not model success.

The helper only calls pure read-only runner accounting functions. It never
instantiates a provider, starts a model, repairs an artifact, or writes under
the target repository. Call once after probe/result.json exists.
Critic, semantic revision and complete D are outside this component's scope.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
STAGE = Path(__file__).resolve().parents[1]
RUNTIME = STAGE / 'runtime'
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(STAGE))

from research_runner import ResearchConfig, verified_carryover, remaining_allowance, validate_authorization

from schemas.contract_outputs import CONTRACT_VERSION
from schemas.evidence import canonical_hash
from workflow.contract_context import ContractArtifact, ContractContext
from workflow.contract_generation import PROMPT_VERSION
from workflow.generation_constraints import bounded_response_model
from workflow.grounding import claims_in
from workflow.research_profile import BriefResearchAnalysis
from workflow.research_limits import RESEARCH_OUTPUT_CAPS, RESEARCH_PROFILE_VERSION
from workflow.two_stage_generation import SelectionPlan, TWO_STAGE_VERSION, draft_model


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def parsed(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Non-finite JSON: ' + value)))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def close(actual, expected, message):
    require(type(actual) in (float, int) and math.isfinite(actual)
            and abs(actual - expected) < .001, message)


class Audit:
    def __init__(self):
        self.files, self.checks, self.failures = {}, [], []

    def source(self, path):
        path = Path(path).resolve()
        raw = path.read_bytes()
        self.files[str(path)] = dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        return raw

    def json(self, path):
        return parsed(self.source(path).decode('utf-8-sig'))

    def check(self, scope, operation):
        try:
            value = operation()
            self.checks.append(dict(scope=scope, passed=True))
            return value
        except Exception as exc:
            self.failures.append(dict(scope=scope, error_type=type(exc).__name__, detail=str(exc)[:1800]))
            return None

    def stable_sources(self):
        for path, recorded in self.files.items():
            require(digest(path) == recorded['sha256'], 'Source changed during audit: ' + path)


def check_inventory(audit, path, roots, *, expected_count):
    inventory = audit.json(path)
    rows = inventory['files'] if isinstance(inventory, dict) else inventory
    require(len(rows) == expected_count, 'Unexpected inventory count: ' + str(path))
    require(len({row['path'] for row in rows}) == len(rows), 'Duplicate inventory path')
    changed = []
    for root in roots:
        root = root.resolve()
        for row in rows:
            candidate = (root / row['path']).resolve()
            require(candidate.is_relative_to(root), 'Inventory path escapes its root')
            if not candidate.is_file() or digest(candidate) != row['sha256']:
                changed.append(str(candidate))
    require(not changed, 'Missing or changed inventoried files: ' + json.dumps(changed[:25]))
    return dict(files_per_root=len(rows), roots=[str(root.resolve()) for root in roots], unchanged=True,
                coverage='Existing inventoried files; new run files are allowed and not silently added to history.')


def event_log(audit, path):
    text = audit.source(path).decode('utf-8')
    require(text.endswith('\n'), 'Event log is not newline-closed')
    events = [parsed(line) for line in text.splitlines()]
    require(len({event['event_id'] for event in events}) == len(events), 'Duplicate event IDs')
    require(len({event['run_id'] for event in events}) == 1, 'Mixed run IDs')
    calls, dispatched = {}, {}
    for event in events:
        if event['kind'] != 'call':
            continue
        call = event['payload']
        key = call['attempt_id']
        if call['status'] == 'dispatching':
            require(key not in dispatched, 'Repeated physical dispatch: ' + key)
            dispatched[key] = call
        else:
            require(key in dispatched and key not in calls, 'Unmatched or duplicate physical completion: ' + key)
            original = dispatched[key]
            for field in ('logical_task_id', 'generation_stage', 'purpose', 'reservation_tokens', 'schema_hash', 'prompt_hash'):
                require(call[field] == original[field], 'Dispatch/completion identity changed: ' + field)
            calls[key] = call
    require(set(dispatched) == set(calls), 'Final result has an unclosed physical dispatch')
    return events, list(calls.values())


def payloads(events, kind):
    return [event['payload'] for event in events if event['kind'] == kind]


def artifact_from(data):
    artifact = ContractArtifact(role=data['role'], version=data['artifact_version'], case_id=data['case_id'],
        packet_sha256=data['packet_sha256'], brief_sha256=data['brief_sha256'],
        payload_json=json.dumps(data['payload'], ensure_ascii=False),
        changes_json=json.dumps(data['confidence_changes'], ensure_ascii=False), pruned=data['pruned'],
        unresolved_major=data['unresolved_major'], contract_version=data['contract_version'])
    require(artifact.as_dict() == data, 'Artifact serialization differs')
    return artifact


def verify_tasks(ctx, events, calls):
    latest = {event['logical_task_id']: event for event in payloads(events, 'logical_task')}
    require(len(latest) <= 1, 'Research probe created more than one logical generation task')
    require(all(call['logical_task_id'] in latest for call in calls), 'Physical call has no logical task record')
    by_id = {call['attempt_id']: call for call in calls}
    contract_checks = payloads(events, 'contract_check')
    accepted = {(check['logical_task_id'], check['generation_stage']): by_id[check['attempt_id']]
                for check in contract_checks if check['passed'] and check.get('attempt_id') in by_id}
    results, assembled = [], None
    for task_id, task in latest.items():
        require(task['role'] == 'research' and task['artifact_version'] == 1 and task['batch_number'] is None,
                'Unexpected role, revision or Writer batch')
        require(task['protocol'] == TWO_STAGE_VERSION, 'Two-stage version differs')
        require(task['packet_sha256'] == ctx.packet_sha256, 'Task packet differs')
        require(task['schema_sha256'] == canonical_hash(BriefResearchAnalysis.model_json_schema()), 'Research profile schema differs')
        require(sum(a['purpose'] == 'structure_repair' for a in task['attempts']) <= 1, 'Shared structure repair allowance reset')
        require(all(a['generation_stage'] in ('body', 'grounding') and a['purpose'] in ('generate', 'structure_repair')
                    for a in task['attempts']), 'Unexpected logical stage or purpose')
        row = dict(logical_task_id=task_id, completed=task['completed'], logical_attempt_count=len(task['attempts']))
        results.append(row)
        if task['frozen_draft'] is None:
            require(not task['completed'] and task['assembly_mapping'] is None, 'Completed task lacks a frozen body')
            row['state'] = 'no_accepted_body'
            continue
        plan = SelectionPlan(BriefResearchAnalysis, task['frozen_draft'], ctx, logical_task_id=task_id, version=1)
        require(plan.catalog() == task['selection_catalog'], 'Body/catalog reconstruction differs')
        body_schema = bounded_response_model(draft_model(BriefResearchAnalysis), (), packet=ctx.packet)
        grounding_schema = bounded_response_model(plan.schema, (), packet=ctx.packet)

        def physical(stage, schema):
            call = accepted[(task_id, stage)]
            require(call['status'] == 'succeeded' and call['finish_reason'] not in ('length', 'MAX_TOKENS'),
                    'Accepted stage has no untruncated physical success')
            wire = schema.model_validate(parsed(call['raw_output'])).model_dump(mode='json')
            require(canonical_hash(wire) == call['output_artifact_ref']['sha256'], 'Physical payload hash differs')
            require(canonical_hash(schema.model_json_schema()) == call['schema_hash'], 'Physical schema hash differs')
            logical = next(attempt for attempt in reversed(task['attempts'])
                           if attempt['generation_stage'] == stage and attempt['passed'])
            require(logical['schema_sha256'] == call['schema_hash'], 'Logical/physical schema differs')
            require(schema.model_validate(parsed(logical['raw_output'])).model_dump(mode='json') == wire,
                    'Accepted logical raw differs from physical response')
            return wire

        require(physical('body', body_schema) == plan.body, 'Accepted body differs from frozen body')
        row.update(state='accepted_body_grounding_incomplete', body_sha256=plan.body_sha256,
                   body_spans=len(plan.body_spans), evidence_spans=len(plan.evidence_spans),
                   complete_candidate_catalog_preserved=True)
        if not task['completed']:
            require(task['assembly_mapping'] is None and task['assembled_sha256'] is None,
                    'Incomplete task claims a completed assembly')
            continue
        candidate, mapping = plan.assemble(physical('grounding', grounding_schema))
        require(mapping == task['assembly_mapping'], 'Exact span/claim assembly mapping differs')
        require(canonical_hash(candidate.model_dump(mode='json')) == task['assembled_sha256'], 'Assembly hash differs')
        ctx.validate(candidate, version=1)
        assembled = ctx.accept('research', candidate, version=1)
        ctx.verify_artifact(assembled)
        row.update(state='exact_body_grounding_assembly_and_context_verified', claims=len(claims_in(candidate)),
                   assembled_sha256=task['assembled_sha256'])
    return results, assembled


def verify_accounting(summary, calls, audit, report_root):
    carry = summary['inherited_allowance']
    record = audit.json(report_root / 'budget_carryover.json')
    reconstructed = verified_carryover(record)
    require(carry == reconstructed, 'Inherited allowance differs from recursively verified original sources')
    for source_ref in reconstructed.get('source_chain', [reconstructed['source_result']]):
        audit.source(source_ref['result_path'])
        require(audit.files[str(Path(source_ref['result_path']).resolve())]['sha256'] == source_ref['sha256'],
                'Carryover chain source changed after recursive verification')
    old_known = reconstructed['pool_known_usage']
    require(carry['pool_limits'] == dict(request_count=36, charged_total_tokens=500000, elapsed_seconds=5400), 'Pool ceilings changed')
    snapshot = summary['this_probe']['budget_snapshot']
    known = dict(actual_prompt_tokens_known=0, actual_output_tokens_known=0, actual_total_tokens_known=0, usage_missing_calls=0)
    charges, missing = 0, []
    for call in calls:
        values = [call[key] for key in ('prompt_tokens', 'output_tokens', 'total_tokens')]
        require(all(value is None or type(value) is int and value >= 0 for value in values), 'Invalid actual token counter')
        for name, value in zip(('prompt', 'output', 'total'), values):
            known['actual_' + name + '_tokens_known'] += value or 0
        if any(value is None for value in values):
            known['usage_missing_calls'] += 1
            require(bool(call['usage_missing_reason']), 'Unknown usage lacks a reason')
            missing.append({key: call[key] for key in ('attempt_id', 'status', 'prompt_tokens', 'output_tokens',
                'total_tokens', 'reservation_tokens', 'budget_token_charge', 'usage_missing_reason')})
        expected = values[2] if values[2] is not None else max(call['reservation_tokens'], sum(v or 0 for v in values[:2]))
        require(type(call['budget_token_charge']) is int and call['budget_token_charge'] == expected,
                'Unknown call refunded or physical usage charged incorrectly')
        charges += expected
    require(snapshot['request_count'] == len(calls) and snapshot['charged_total_tokens'] == charges, 'Physical call ledger differs')
    require(all(snapshot[key] == value for key, value in known.items()), 'Known usage differs from physical calls')
    require(summary['this_probe']['known_usage'] == known, 'Probe known-usage summary differs')
    require(snapshot['structure_repair_request_count'] == sum(call['purpose'] == 'structure_repair' for call in calls), 'Repair count differs')
    require(snapshot['revision_request_count'] == 0, 'Research-only probe contains semantic revision')
    require(snapshot['transport_retry_count'] == sum(call['transport_retry_of'] is not None for call in calls), 'Transport retry count differs')
    if calls:
        require(snapshot['max_requests'] == 36 - carry['pool_used']['request_count'], 'Remaining requests reset')
        require(snapshot['max_total_tokens'] == 500000 - carry['pool_used']['charged_total_tokens'], 'Remaining tokens reset')
        require(snapshot['research_profile_version'] == RESEARCH_PROFILE_VERSION, 'Snapshot profile version differs')
        require(snapshot['research_output_caps'] == RESEARCH_OUTPUT_CAPS, 'Effective output caps differ')
    require(type(summary['http_requests']) is int and 0 <= summary['http_requests'] <= len(calls), 'HTTP requests exceed reserved calls')
    for key, value in dict(request_count=len(calls), charged_total_tokens=charges, elapsed_seconds=summary['elapsed_seconds']).items():
        close(summary['this_probe'][key], value, 'Probe totals differ: ' + key)
        for result_key, prior_key in (('pool_cumulative', 'pool_used'), ('all_history_cumulative', 'all_history_used')):
            close(summary[result_key][key], carry[prior_key][key] + value, 'History accumulation differs: ' + result_key + '.' + key)
        close(summary['pool_remaining'][key], max(0, carry['pool_limits'][key] - summary['pool_cumulative'][key]), 'Remaining allowance differs')
    for key, value in known.items():
        require(summary['pool_cumulative']['known_usage'][key] == old_known[key] + value, 'Pool known subtotal differs')
    require(summary['all_history_cumulative']['known_usage_before_current_pool'] is None, 'Older unknown usage fabricated')
    require(len(calls) <= 36 - carry['pool_used']['request_count'], 'Request ceiling exceeded')
    if summary['research_probe_passed']:
        require(summary['pool_cumulative']['charged_total_tokens'] <= 500000, 'Successful probe exceeds token ceiling')
    return dict(physical_calls=len(calls), http_requests=summary['http_requests'], charged_total_tokens=charges,
        known_usage=known, unknown_usage_calls=missing, pool_cumulative=summary['pool_cumulative'],
        all_history_cumulative=summary['all_history_cumulative'], pool_remaining=summary['pool_remaining'],
        source_chain=reconstructed.get('source_chain', [reconstructed['source_result']]),
        source_component_budget_scope=reconstructed.get('source_budget_scope', 'initial_90_minute_pool'),
        assembly_tokens_counted_as_model_output=False, unknown_reservations_retained=True)


def verify_cleanup(summary, events, audit, run):
    stops = payloads(events, 'server_stop')
    proof = summary['server_stop']
    if stops:
        require(stops[-1] == proof, 'Durable owner cleanup differs from result')
    if proof['status'] == 'owned_process_tree_terminated':
        require(bool(stops), 'No durable owner termination evidence')
        owner_path = run.parent / 'server/server_owner.json'
        owner = audit.json(owner_path)
        require(owner['pid'] == proof['pid'], 'Terminated PID differs from launched owner')
        owned = payloads(events, 'server_ownership_verified')
        require(owned and owned[0]['pid'] == owner['pid'], 'Owned process was never verified')
        require(proof['lease_released'] is False and proof['restart_requires_explicit_reconciliation'] is True,
                'Termination proof silently grants lease reset')
        bindings = payloads(events, 'native_process_identity_bound')
        if proof.get('identity_method') == 'native_handle_and_persisted_identity':
            require(bindings and bindings[-1]['owner_sha256'] == audit.files[str(owner_path.resolve())]['sha256'],
                    'Native handle was not bound to exact owner record')
            require(audit.json(owner_path.with_name(owner_path.name + '.native_identity.json')) == bindings[-1],
                    'Persisted native process identity differs from binding event')
    released = payloads(events, 'power_requests_released')
    if summary['power_cleanup'] == 'released':
        require(released and released[-1]['status'] == 'released' and not released[-1]['errors'], 'Power release not certified')
        require(bool(payloads(events, 'power_requests_acquired')), 'Power release lacks acquisition record')
    resource_events = payloads(events, 'telemetry_summary')
    if resource_events:
        require(resource_events[-1] == summary['resources'], 'Resource summary differs from durable record')
    if summary['resources'] and summary['resources']['status'] == 'passed':
        require(bool(resource_events), 'Resource pass lacks monitor summary')
        samples = payloads(events, 'telemetry')
        require(len(samples) == summary['resources']['sample_count'], 'Resource sample count differs')
        require(summary['resources']['observation_gap_count'] == 0, 'Resource pass hides observation gaps')
        require(summary['resources']['maximum_observed_sample_gap_seconds'] <=
                summary['resources']['maximum_allowed_sample_gap_seconds'], 'Resource pass exceeds sampling gap bound')
    return dict(server_stop=proof, power_cleanup=summary['power_cleanup'],
                resource_status=(summary.get('resources') or {}).get('status'),
                certification='Persisted exact-owner cleanup evidence; no new process query or termination is performed.')


def audit_run(run, output, repo):
    run, output, repo = run.resolve(), output.resolve(), repo.resolve()
    require((run / 'result.json').is_file(), 'No final result.json yet; call this helper only after the probe finishes')
    require(output.is_relative_to(STAGE / 'validation') and not output.is_relative_to(repo), 'Output must stay in workspace stage validation')
    require(not output.exists(), 'Refusing to overwrite an audit report')
    report_root = run.parent.parent
    audit = Audit()
    summary = audit.json(run / 'result.json')
    report = dict(audit_version='research-probe-integrity-v2-chain', created_at_utc=datetime.now(timezone.utc).isoformat(),
        source_run=str(run), target_repository=str(repo), model_calls=0, recorded_status=summary.get('status'),
        recorded_research_probe_passed=summary.get('research_probe_passed'), research_artifact_verified=False,
        research_probe_verified=False, critic_verified=False, complete_d_verified=False, complete_proposal_verified=False,
        limits='Structural/canonical provenance audit. Semantic source support and human Gold approval are not assessed. '
               'Research generation only; this does not certify its production Critic/revision or downstream plan.')
    audit.source(Path(__file__))
    report['installed_sources'] = audit.check('272_current_sources_unchanged', lambda: check_inventory(audit,
        report_root / 'runtime_manifest.json', [report_root / 'runtime', repo, RUNTIME], expected_count=272))
    report['history'] = audit.check('3622_historical_files_unchanged', lambda: check_inventory(audit,
        report_root / 'history_inventory.json', [repo], expected_count=3622))
    helpers = audit.json(report_root / 'helper_manifest.json')['files']
    audit.check('installed_runner_helpers_unchanged', lambda: require(all(digest(report_root / row['path']) == row['sha256']
        for row in helpers), 'Installed runner/helper differs from frozen manifest'))
    external = audit.json(report_root / 'external_dependencies.json')
    audit.check('public_config_and_launcher_unchanged', lambda: require(all(digest(row['path']) == row['sha256'] for row in external),
        'Public model configuration or server launcher changed'))
    logs = audit.check('closed_event_dispatch_ledger', lambda: event_log(audit, run / 'events.jsonl'))
    events, calls = logs if logs is not None else ([], [])
    report['physical_attempts'] = [{key: call.get(key) for key in ('attempt_id', 'logical_task_id', 'generation_stage',
        'purpose', 'status', 'error_type', 'started_at_utc', 'ended_at_utc', 'elapsed_seconds', 'finish_reason',
        'prompt_tokens', 'output_tokens', 'total_tokens', 'budget_token_charge', 'usage_missing_reason')}
        for call in calls]
    audit.check('durable_result_matches_file', lambda: require(payloads(events, 'research_probe_result') == [summary],
        'Final result file differs from its single durable result event'))
    audit.check('research_only_scope', lambda: require(summary['case_id'] == 'ai_education'
        and summary['formal_eligible'] is False and summary['formal_runs_started'] == 0 and summary['gemini_calls'] == 0
        and summary['complete_proposal_produced'] is False and summary['complete_d_passed'] is False
        and all(call['provider'] == 'local' and call['run_kind'] == 'smoke' and call['task_role'] == 'research'
            and call['task_purpose'] == 'generate' and call['purpose'] in ('generate', 'structure_repair') for call in calls)
        and not any(event['kind'] in ('critique', 'handoff', 'terminal_contract') for event in events),
        'Probe scope misreported as complete D, Critic, revision or another model'))
    ctx = audit.check('frozen_case_and_snapshots', lambda: ContractContext.from_case(
        RUNTIME / 'docs/final_sprint/s0-v1', 'ai_education', condition='D'))
    manifests = payloads(events, 'research_probe_manifest')
    def verify_manifest():
        if not manifests:
            require(not calls and not summary['research_probe_passed'], 'Model call/success lacks a manifest')
            return dict(state='initialization_failed_before_manifest')
        require(len(manifests) == 1, 'Repeated probe manifest')
        manifest = manifests[0]
        require(manifest['packet_sha256'] == ctx.packet_sha256 and manifest['brief_sha256'] == ctx.brief_sha256,
                'Manifest frozen inputs differ')
        require(manifest['prompt_version'] == PROMPT_VERSION and manifest['contract_version'] == CONTRACT_VERSION, 'Prompt/contract differs')
        authorization = audit.json(report_root / 'authorization.json')
        require(manifest['authorization'] == authorization and authorization['approved'] is True
                and authorization['scope'] == 'ai_education_research_20m', 'Research authorization differs')
        parent = audit.json(authorization['parent_authorization_path'])
        require(audit.files[str(Path(authorization['parent_authorization_path']).resolve())]['sha256'] == authorization['parent_authorization_sha256'],
                'Parent authorization hash differs')
        require(parent['approved'] is True and parent['scope'] == 'ai_education_slm_independent_90m_validation', '90-minute parent approval missing')
        require(manifest['config'] == audit.json(report_root / 'trial_config.json'), 'Manifest configuration differs')
        validate_authorization(ResearchConfig.model_validate(manifest['config']), authorization)
        require(manifest['carryover'] == summary['inherited_allowance'], 'Manifest/result carryover differs')
        metadata = manifest['model_metadata']
        require(metadata['model_digest'] == authorization['expected_model_digest']
                and metadata['ollama_version'] == authorization['expected_ollama_version'], 'Model/runtime identity differs')
        effective = manifest['effective_run_config']
        require(all(0 < effective[key] <= summary['probe_deadline_seconds'] for key in ('run_seconds', 'node_seconds', 'request_seconds')),
                'Effective request/node/run deadlines exceed remaining allowance')
        for call in calls:
            require(call['config_sha256'] == canonical_hash(effective) and call['evidence_hash'] == ctx.packet_sha256,
                    'Physical call configuration or packet hash differs from manifest')
            require(call['input_artifact_refs'] == [dict(artifact_id='packet', artifact_version=1, sha256=ctx.packet_sha256),
                    dict(artifact_id='brief', artifact_version=1, sha256=ctx.brief_sha256)], 'Unexpected call input artifacts')
            require(call['model_config_version'] == effective['model_config_version']
                    and call['model_exact_id'] == effective['model_exact_id'], 'Physical call model identity differs')
        return dict(prompt_version=PROMPT_VERSION, contract_version=CONTRACT_VERSION,
            research_profile_version=RESEARCH_PROFILE_VERSION, packet_sha256=ctx.packet_sha256,
            brief_sha256=ctx.brief_sha256, expected_financial_rows_downstream=len(ctx.finance.expected_values()), model_metadata=metadata)
    report['manifest'] = audit.check('manifest_authorization_and_deadlines', verify_manifest)
    task_result = audit.check('two_stage_raw_catalog_assembly_context', lambda: verify_tasks(ctx, events, calls)) if ctx else None
    assembled = None
    if task_result:
        report['tasks'], assembled = task_result
    def verify_artifact():
        artifact_events = payloads(events, 'research_artifact')
        if not summary['research_artifact_produced']:
            require(not artifact_events and not (run / 'artifact.json').exists(), 'Undisclosed Research artifact exists')
            require(not summary['research_probe_passed'], 'Success lacks an artifact')
            return dict(produced=False, state='honest_failed_probe_without_artifact')
        path = Path(summary['artifact_path']).resolve()
        require(path == run / 'artifact.json', 'Artifact path is outside expected probe directory')
        data = audit.json(path)
        artifact = artifact_from(data)
        ctx.verify_artifact(artifact)
        require(artifact.role == 'research' and artifact.version == 1, 'Unexpected saved artifact role/version')
        require(artifact.sha256 == summary['artifact_sha256'], 'Saved artifact hash differs')
        require(len(artifact_events) == 1 and artifact_events[0]['artifact'] == data
                and artifact_events[0]['sha256'] == artifact.sha256 and artifact_events[0]['canonical_verified'] is True,
                'Research artifact event differs from exported file')
        require(assembled is not None and assembled.as_dict() == data, 'Saved artifact differs from exact selected assembly/confidence')
        report['research_artifact_verified'] = True
        return dict(produced=True, sha256=artifact.sha256, claims=len(claims_in(artifact.payload())),
                    context_verified=True, selected_assembly_and_confidence_exact=True)
    report['artifact'] = audit.check('saved_research_artifact', verify_artifact)
    report['accounting'] = audit.check('physical_usage_and_inherited_pool', lambda: verify_accounting(summary, calls, audit, report_root))
    report['cleanup'] = audit.check('owned_cleanup_and_resources', lambda: verify_cleanup(summary, events, audit, run))
    def verify_outcome():
        limit = summary['probe_deadline_seconds']
        inherited = summary['inherited_allowance']
        config = ResearchConfig.model_validate(audit.json(report_root / 'trial_config.json'))
        allowance = remaining_allowance(config, inherited)
        expected = min(config.run_seconds, 1200, 5400 - inherited['pool_used']['elapsed_seconds'])
        close(limit, expected, 'Probe got a new allowance instead of the remaining 90-minute pool')
        require(summary['remaining_before_probe'] == allowance, 'Recorded starting allowance differs from verified pool')
        require(summary['within_probe_deadline'] == (summary['inference_elapsed_seconds'] < limit), 'Probe duration flag differs')
        require(summary['within_pool_generation_deadline'] == (summary['inference_elapsed_seconds'] + inherited['pool_used']['elapsed_seconds'] < 5400),
                'Parent pool deadline flag differs')
        require(summary['inference_elapsed_seconds'] >= 0 and summary['cleanup_elapsed_seconds'] >= 0, 'Negative duration')
        close(summary['elapsed_seconds'], summary['inference_elapsed_seconds'] + summary['cleanup_elapsed_seconds'], 'Wall-clock components differ')
        expected_pass = (summary['status'] == 'completed' and summary['research_artifact_produced']
            and summary['within_probe_deadline'] and summary['within_pool_generation_deadline']
            and bool(summary['resources'] and summary['resources']['status'] == 'passed') and summary['power_cleanup'] == 'released')
        require(summary['research_probe_passed'] == expected_pass, 'Research success flag differs from required gates')
        if expected_pass:
            require(report['research_artifact_verified'] and not summary['deadline_fired']
                    and summary['server_stop']['status'] == 'owned_process_tree_terminated', 'Success lacks artifact, time or cleanup proof')
        if not summary['research_artifact_produced']:
            require(bool(payloads(events, 'research_probe_error')), 'Failed generation lacks a durable error')
        return dict(recorded_pass=expected_pass, inference_seconds=summary['inference_elapsed_seconds'],
            cleanup_seconds=summary['cleanup_elapsed_seconds'], elapsed_seconds=summary['elapsed_seconds'],
            limit_seconds=limit, deadline_fired=summary['deadline_fired'])
    report['outcome'] = audit.check('component_terminal_duration', verify_outcome)
    audit.check('read_sources_unchanged_during_audit', audit.stable_sources)
    report.update(integrity_status='passed' if not audit.failures else 'failed', checks=audit.checks,
        failures=audit.failures, source_sha256=audit.files,
        research_probe_verified=bool(summary['research_probe_passed'] and report['research_artifact_verified'] and not audit.failures),
        reproduction=dict(executable=sys.executable, argv=['-B', str(Path(__file__).resolve()), '--run', str(run),
            '--shared-repo', str(repo), '--output', str(output)]))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True, help='Finished run_01/probe directory containing result.json')
    parser.add_argument('--shared-repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=STAGE / 'validation/research_probe_integrity.json')
    args = parser.parse_args()
    result = audit_run(args.run, args.output, args.shared_repo)
    print(json.dumps({key: result[key] for key in ('integrity_status', 'recorded_status', 'research_artifact_verified',
        'research_probe_verified', 'critic_verified', 'complete_d_verified', 'failures')}, ensure_ascii=False, indent=2))
    return 0 if result['integrity_status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
