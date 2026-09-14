"""Prevent observed span-ID confusion without deduplicating model claims."""
from copy import deepcopy
from pathlib import Path
import re

import pytest

from evaluation.s2_fixtures import synthetic_artifact
from evaluation.two_stage_fixtures import synthetic_stage_payload
from schemas.contract_outputs import ContractResearchAnalysis
from workflow.contract_context import ContractContext
from workflow.generation_batches import CONTRACT_BATCH_MODELS
from workflow.schema_contract import schema_enum_contract
from workflow.two_stage_generation import NEW_CLAIM_ID_PATTERN, SelectionPlan, project_body


ROOT = Path(__file__).resolve().parents[1] / 'docs/final_sprint/s0-v1'


@pytest.fixture
def ctx():
    return ContractContext.from_case(ROOT, 'ai_education', condition='D')


def plan_data(ctx, **kwargs):
    data = synthetic_artifact(ctx, 'research', version=kwargs.get('version', 1), inputs={})
    plan = SelectionPlan(ContractResearchAnalysis,
                         project_body(ContractResearchAnalysis, data), ctx, **kwargs)
    return plan, synthetic_stage_payload(plan.schema, data)


@pytest.mark.parametrize('bad_id', [
    'bd29643e307bedd77_86740511',  # First real 6055-token grounding identity collision.
    'ed29643e307bedd77_1', 'research', 'research.', 'research claim',
])
def test_new_claim_id_cannot_be_a_body_or_evidence_identifier(ctx, bad_id):
    plan, data = plan_data(ctx)
    data['g1']['claims'][0]['claim_id'] = bad_id
    with pytest.raises(ValueError, match='claim_id'):
        plan.assemble(data)


def test_native_schema_carries_pattern_exact_version_and_null_parent(ctx):
    plan, _ = plan_data(ctx, logical_task_id='research.v2', version=2)
    field = plan.schema.model_json_schema()['$defs']['SelectedClaim1']['properties']
    assert field['claim_id']['pattern'].startswith('^')
    assert re.fullmatch(field['claim_id']['pattern'], 'research.v2.g1.c1')
    assert not re.fullmatch(field['claim_id']['pattern'], 'bd29643e307bedd77_86740511')
    assert field['artifact_version']['const'] == 2
    assert field['parent_claim_id']['type'] == 'null'
    assert plan.catalog()['artifact_version'] == 2
    assert plan.catalog()['logical_task_id'] == 'research.v2'


@pytest.mark.parametrize('role', ['research', 'strategy', 'finance', 'writer', 'single'])
def test_all_existing_generation_role_prefixes_remain_legal(ctx, role):
    plan, data = plan_data(ctx)
    for annotation in data.values():
        for claim in annotation['claims']:
            claim['claim_id'] = f'{role}.same-claim'
    candidate, _ = plan.assemble(data)
    # Identical meaning/evidence may legally have several content anchors.
    ctx.validate(candidate, version=1)


def test_distinct_meanings_still_fail_original_identity_validation(ctx):
    plan, data = plan_data(ctx)
    first, second = data['g1']['claims'][0], data['g2']['claims'][0]
    assert first['claim_id'] == second['claim_id']
    first.update(claim_text='Content licensing requirements need assessment.',
                 claim_type='assumption', evidence_status='assumption',
                 premise='Licensing costs have not been established.')
    second.update(claim_text='FERPA applies to the proposed student-data handling.',
                  claim_type='factual', premise='')
    candidate, _ = plan.assemble(data)
    with pytest.raises(ValueError, match='claim ID reused with inconsistent'):
        ctx.validate(candidate, version=1)


def test_historical_id_retention_and_split_parent_remain_explicit(ctx):
    data = synthetic_artifact(ctx, 'research', version=1, inputs={})
    legacy_id = 'bd29643e307bedd77_86740511[legacy]'
    for collection in ('market_trends', 'customer_notes', 'competitor_assumptions'):
        data[collection][0]['claims'][0]['claim_id'] = legacy_id
    upstream = ctx.accept('research', data)
    plan = SelectionPlan(ContractResearchAnalysis,
                         project_body(ContractResearchAnalysis, data), ctx,
                         upstream=(upstream,), version=2)
    data2 = deepcopy(data)
    for collection in ('market_trends', 'customer_notes', 'competitor_assumptions'):
        data2[collection][0]['claims'][0]['artifact_version'] = 2
    selections = synthetic_stage_payload(plan.schema, data2)
    retained, _ = plan.assemble(selections)
    ctx.validate(retained, version=2, upstream=(upstream,))
    split = deepcopy(selections)
    split['g1']['claims'][0].update(claim_id='research.v2.g1.c1', parent_claim_id=legacy_id)
    candidate, _ = plan.assemble(split)
    ctx.validate(candidate, version=2, upstream=(upstream,))
    split['g1']['claims'][0]['parent_claim_id'] = 'research.nonexistent'
    with pytest.raises(ValueError, match='parent_claim_id'):
        plan.assemble(split)
    # Regex escaping must not turn the historical literal into a wildcard.
    selections['g1']['claims'][0]['claim_id'] = legacy_id.replace('[legacy]', 'l')
    with pytest.raises(ValueError, match='claim_id'):
        plan.assemble(selections)
    # An enum prompt must not incorrectly close claim_id to just inherited IDs.
    assert '`*.claim_id ' not in schema_enum_contract(plan.schema)


def test_wrong_current_version_or_unknown_parent_is_rejected(ctx):
    plan, data = plan_data(ctx, version=2)
    wrong = deepcopy(data)
    wrong['g1']['claims'][0]['artifact_version'] = 1
    with pytest.raises(ValueError, match='artifact_version'):
        plan.assemble(wrong)
    wrong = deepcopy(data)
    wrong['g1']['claims'][0]['parent_claim_id'] = 'research.pricing'
    with pytest.raises(ValueError, match='parent_claim_id'):
        plan.assemble(wrong)


def test_writer_batch_examples_do_not_collide_and_leave_selection_sets_unchanged(ctx):
    data = synthetic_artifact(ctx, 'writer', version=1, inputs={})
    examples = []
    for number, canonical in enumerate(CONTRACT_BATCH_MODELS, 1):
        body = project_body(canonical, data)
        fallback = SelectionPlan(canonical, body, ctx)
        explicit = SelectionPlan(canonical, body, ctx, logical_task_id=f'writer.v1.batch{number}')
        examples.append(fallback.groups['g1']['new_claim_id_example'])
        assert explicit.groups['g1']['new_claim_id_example'] == f'writer.v1.batch{number}.g1.c1'
        assert fallback.body == explicit.body
        assert fallback.body_spans == explicit.body_spans
        assert fallback.evidence_spans == explicit.evidence_spans
        assert all(re.fullmatch(NEW_CLAIM_ID_PATTERN, group['new_claim_id_example'])
                   for group in fallback.groups.values())
    assert len(set(examples)) == len(CONTRACT_BATCH_MODELS)
