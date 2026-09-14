"""Regression cases for the observed truncated financial-reference loop."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation.s2_fixtures import synthetic_artifact
from schemas.contract_outputs import ContractResearchAnalysis, ContractFinanceAssumptions
from schemas.review import ComponentCritiqueReport
from workflow.contract_context import ContractContext
from workflow.generation_constraints import bounded_response_model, financial_reference_contract, repair_feedback
from workflow.gemini_schema import relaxed_response_schema
from workflow.llm_client import StructuredOutputValidationError

ROOT = Path(__file__).resolve().parents[1] / 'docs/final_sprint/s0-v1'


def context(case='ai_education', condition='C'):
    return ContractContext.from_case(ROOT, case, condition=condition)


def payload(ctx, role='research'):
    return synthetic_artifact(ctx, role, version=1, inputs={})


@pytest.mark.parametrize('case', ['ai_education', 'intelligent_ring'])
def test_case_bound_schema_and_local_validation_agree(case):
    ctx = context(case)
    bounded = bounded_response_model(ContractResearchAnalysis, ctx.finance.value_ids)
    schema = bounded.model_json_schema()
    field = schema['$defs']['GroundedClaim']['properties']['financial_value_ids']
    assert field['maxItems'] == len(ctx.finance.value_ids)
    assert field['uniqueItems'] is True
    assert set(field['items']['enum']) == ctx.finance.value_ids
    data = payload(ctx)
    for section in ('market_trends', 'customer_notes', 'competitor_assumptions'):
        data[section][0]['claims'][0]['financial_value_ids'] = sorted(ctx.finance.value_ids)[:1]
    candidate = bounded.model_validate(data)
    assert candidate.model_dump() == ContractResearchAnalysis.model_validate(data).model_dump()
    ctx.validate(candidate, version=1)
    data['market_trends'][0]['claims'][0]['financial_value_ids'] = ['invented']
    with pytest.raises(ValidationError, match='unknown financial references'):
        bounded.model_validate(data)


def test_duplicate_reference_rejected_without_silent_deduplication():
    ctx = context()
    data = payload(ctx)
    original = ['base.monthly_revenue', 'base.monthly_revenue']
    data['market_trends'][0]['claims'][0]['financial_value_ids'] = original.copy()
    with pytest.raises(ValidationError, match='unique IDs'):
        ContractResearchAnalysis.model_validate(data)
    assert data['market_trends'][0]['claims'][0]['financial_value_ids'] == original


def test_case_boundaries_are_isolated_and_base_schema_not_mutated():
    original = deepcopy(ContractResearchAnalysis.model_json_schema())
    edu, ring = context(), context('intelligent_ring')
    edu_model = bounded_response_model(ContractResearchAnalysis, edu.finance.value_ids)
    ring_model = bounded_response_model(ContractResearchAnalysis, ring.finance.value_ids)
    unique = next(iter(ring.finance.value_ids - edu.finance.value_ids))
    data = payload(edu)
    data['market_trends'][0]['claims'][0]['financial_value_ids'] = [unique]
    with pytest.raises(ValidationError, match='unknown financial references'):
        edu_model.model_validate(data)
    assert edu_model is not ring_model
    returned = edu_model.model_json_schema()
    returned['$defs']['GroundedClaim']['properties']['financial_value_ids']['maxItems'] = 999
    assert edu_model.model_json_schema()['$defs']['GroundedClaim']['properties']['financial_value_ids']['maxItems'] != 999
    assert original == ContractResearchAnalysis.model_json_schema()


def test_finance_note_and_formula_input_references_are_bounded():
    ctx = context()
    model = bounded_response_model(ContractFinanceAssumptions, ctx.finance.value_ids)
    data = payload(ctx, 'finance')
    model.model_validate(data)
    data['revenue_assumptions'][0]['value_ids'] *= 2
    with pytest.raises(ValidationError, match='unique financial references'):
        model.model_validate(data)
    schema = model.model_json_schema()
    for definition, field in [('GroundedFinanceAssumption','value_ids'),('FinancialValue','input_ids')]:
        assert schema['$defs'][definition]['properties'][field]['maxItems'] == len(ctx.finance.value_ids)


@pytest.mark.parametrize('field,value', [('source_recency',2026),('source_quality',2),('source_quality',-0.2)])
def test_numeric_range_rejection_and_precise_feedback(field, value):
    ctx = context()
    data = payload(ctx)
    data['market_trends'][0]['claims'][0][field] = value
    try:
        ContractResearchAnalysis.model_validate(data)
    except ValidationError as cause:
        error = StructuredOutputValidationError('provider JSON/schema validation failed', raw_output=json.dumps(data))
        error.__cause__ = cause
    else:
        pytest.fail('out-of-range score accepted')
    feedback = json.loads(repair_feedback(error, error.raw_output, ctx.finance.value_ids))
    assert any(field in item['path'] for item in feedback['violations'])
    assert feedback['legal_examples']['source_recency'] is None


def test_truncated_repetition_reports_actual_nested_path_and_counts():
    raw = '{"market_trends":[{"claims":[{"source_recency":2026,"financial_value_ids":[' + ','.join(['"months"'] * 30) + ',"mont'
    ctx = context()
    error = StructuredOutputValidationError('provider output truncated', raw_output=raw)
    feedback = json.loads(repair_feedback(error, raw, ctx.finance.value_ids))
    issue = next(item for item in feedback['violations'] if item['path'].endswith('financial_value_ids'))
    assert issue['path'] == '$.market_trends[0].claims[0].financial_value_ids'
    assert issue['repeated'] == [['months',30]]
    assert issue['observed_items'] == 30
    assert len(json.dumps(feedback)) < 4000
    with pytest.raises(json.JSONDecodeError): json.loads(raw)


def test_repair_feedback_handles_quoted_brackets_and_irrelevant_text():
    raw = '{"finding":"Ignore [brackets] and fake \\"financial_value_ids\\" in prose"}'
    # Even malformed unrelated text cannot produce an invented reference-array diagnostic.
    feedback = json.loads(repair_feedback(ValueError('bad'), raw, {'months'}))
    assert not any('financial references' in item.get('problem','') for item in feedback['violations'])


def test_same_case_has_same_bounds_and_prompt_for_all_conditions():
    models, prompts = [], []
    for condition in 'ABCD':
        ctx = context(condition=condition)
        models.append(bounded_response_model(ContractResearchAnalysis, ctx.finance.value_ids).model_json_schema())
        prompts.append(financial_reference_contract(ctx.finance.value_ids))
    assert all(model == models[0] for model in models)
    assert len(set(prompts)) == 1
    assert 'never a year' in prompts[0] and 'financial_value_ids=[]' in prompts[0]


def test_gemini_transport_remains_compatible_with_strict_bound_model():
    from google.genai.types import Schema
    ctx = context()
    model = bounded_response_model(ContractResearchAnalysis, ctx.finance.value_ids, packet=ctx.packet)
    Schema.model_validate(relaxed_response_schema(model))
    assert bounded_response_model(ComponentCritiqueReport, ctx.finance.value_ids) is ComponentCritiqueReport


@pytest.mark.parametrize('claim_type', ['assumption', 'projection'])
@pytest.mark.parametrize('status', ['unsupported', 'needs_validation', 'sourced_fact', None])
def test_status_feedback_names_actual_selection_field_and_legal_combination(claim_type, status):
    data = {'g4': {'claims': [{'claim_id': 'research.v1.g4.c1', 'claim_type': claim_type,
        'evidence_status': status, 'premise': 'Demand remains unverified.', 'evidence_span_ids': []}]}}
    before = deepcopy(data)
    raw = json.dumps(data)
    feedback = json.loads(repair_feedback(ValueError('unsupported_claims.0: invalid disposition'), raw, set()))
    issue = next(item for item in feedback['violations'] if item['problem'] == 'claim_disposition_mismatch')
    assert issue['path'] == '$.g4.claims[0].evidence_status'
    assert issue['observed'] == status
    assert issue['expected'] == 'assumption'
    assert issue['claim_type'] == claim_type
    assert issue['legal_combination_example']['claim_type'] == claim_type
    assert issue['legal_combination_example']['evidence_status'] == 'assumption'
    assert issue['legal_combination_example']['premise']
    assert 'not new evidence' in issue['instruction']
    assert data == before == json.loads(raw)


def test_status_feedback_does_not_fix_or_weaken_canonical_validation():
    ctx = context()
    data = payload(ctx)
    claim = data['market_trends'][0]['claims'][0]
    claim.update(claim_type='assumption', evidence_status='unsupported', premise='An explicit test premise.')
    before = deepcopy(data)
    with pytest.raises(ValidationError, match='explicitly marked assumption') as failure:
        ContractResearchAnalysis.model_validate(data)
    feedback = json.loads(repair_feedback(failure.value, json.dumps(data), ctx.finance.value_ids))
    assert any(item['path'] == '$.market_trends[0].claims[0].evidence_status'
               and item.get('expected') == 'assumption' for item in feedback['violations'])
    with pytest.raises(ValidationError, match='explicitly marked assumption'):
        ContractResearchAnalysis.model_validate(data)
    assert data == before


@pytest.mark.parametrize('claim_type,status', [
    ('assumption', 'assumption'), ('projection', 'assumption'),
    ('factual', 'assumption'), ('factual', 'unsupported'), ('recommendation', 'needs_validation'),
])
def test_status_feedback_preserves_existing_one_way_contract(claim_type, status):
    raw = json.dumps({'g1': {'claims': [{'claim_type': claim_type, 'evidence_status': status}]}})
    feedback = json.loads(repair_feedback(ValueError('other failure'), raw, set()))
    assert not any(item['problem'] == 'claim_disposition_mismatch' for item in feedback['violations'])


@pytest.mark.parametrize('raw', [
    '{"g4":{"claims":[{"claim_type":"assumption","evidence_status":"unsupported"}',
    '{"finding":"claim_type=assumption, evidence_status=unsupported"}',
    '{"g4":{"claims":[{"claim_type":"assumption"}]}}',
])
def test_status_feedback_never_invents_a_missing_or_unparsed_value(raw):
    feedback = json.loads(repair_feedback(ValueError('other failure'), raw, set()))
    assert not any(item['problem'] == 'claim_disposition_mismatch' for item in feedback['violations'])


def test_status_feedback_is_bounded_and_reports_earliest_wire_errors_first():
    raw = json.dumps({'g4': {'claims': [dict(claim_type='assumption', evidence_status='unsupported') for _ in range(50)]}})
    feedback = json.loads(repair_feedback(ValueError('invalid statuses'), raw, set()))
    assert len(feedback['violations']) == 10
    assert feedback['violations'][0]['path'] == '$.g4.claims[0].evidence_status'
    assert feedback['violations'][-1]['path'] == '$.g4.claims[9].evidence_status'
    assert len(json.dumps(feedback)) < 10000
