from copy import deepcopy

import pytest
from pydantic import ValidationError

from evaluation.s2_fixtures import synthetic_artifact
from schemas.contract_outputs import ContractResearchAnalysis
from workflow.contract_context import ContractContext
from workflow.generation_constraints import bounded_response_model
from workflow.research_profile import BriefResearchAnalysis
from workflow.two_stage_generation import SelectionPlan, draft_model, project_body


@pytest.fixture
def context():
    from pathlib import Path
    return ContractContext.from_case(Path(__file__).resolve().parents[1]/'docs/final_sprint/s0-v1',
        'ai_education', condition='D')


@pytest.fixture
def payload(context):
    return synthetic_artifact(context, 'research', version=1, inputs={})


def test_brief_profile_is_a_full_valid_canonical_research_artifact(context, payload):
    model = BriefResearchAnalysis.model_validate(payload)
    context.validate(model, version=1)
    artifact = context.accept('research', model, version=1)
    assert context.verify_artifact(artifact).model_dump(mode='json') == artifact.payload().model_dump(mode='json')
    assert len(artifact.payload().market_trends) == 1


@pytest.mark.parametrize('field', ['market_trends', 'customer_notes', 'competitor_assumptions'])
def test_profile_rejects_extra_findings_without_truncating_history(payload, field):
    payload[field].append(deepcopy(payload[field][0]))
    before = deepcopy(payload)
    assert len(getattr(ContractResearchAnalysis.model_validate(payload), field)) == 2
    with pytest.raises(ValidationError):
        BriefResearchAnalysis.model_validate(payload)
    assert payload == before


def test_profile_rejects_extra_claims_and_preserves_their_original_data(payload):
    payload['market_trends'][0]['claims'].append(deepcopy(payload['market_trends'][0]['claims'][0]))
    before = deepcopy(payload)
    with pytest.raises(ValidationError):
        BriefResearchAnalysis.model_validate(payload)
    assert payload == before


@pytest.mark.parametrize('field,limit', [('analysis_summary',280)])
def test_overlong_summary_is_rejected_instead_of_cut_off(payload, field, limit):
    payload[field] = 'x' * (limit+1)
    with pytest.raises(ValidationError):
        BriefResearchAnalysis.model_validate(payload)
    assert len(payload[field]) == limit+1


def test_stage_schemas_retain_brief_limits_and_no_financial_references(context, payload):
    body = project_body(BriefResearchAnalysis, payload)
    draft = draft_model(BriefResearchAnalysis).model_validate(body)
    plan = SelectionPlan(BriefResearchAnalysis, draft.model_dump(mode='json'), context,
        logical_task_id='research.v1', version=1)
    wire = bounded_response_model(plan.schema, context.finance.value_ids, packet=context.packet).model_json_schema()
    defs = wire['$defs']
    for group in plan.groups:
        annotation = defs[wire['properties'][group]['$ref'].rsplit('/',1)[-1]]
        claims = annotation['properties']['claims']
        assert claims['maxItems'] == (0 if plan.groups[group]['path'] == ['unsupported_claims'] else 1)
        claim = defs[claims['items']['$ref'].rsplit('/',1)[-1]]['properties']
        assert claim['claim_text']['maxLength'] == 240
        assert claim['premise']['maxLength'] == 200
        assert claim['financial_value_ids']['maxItems'] == 0
        assert claim['evidence_span_ids']['maxItems'] == 2
    assert len(plan.groups) == 4
    original = deepcopy(body)
    body['market_trends'][0]['rationale'] = 'x'*161
    with pytest.raises(ValidationError):
        draft_model(BriefResearchAnalysis).model_validate(body)
    assert original['market_trends'][0]['rationale'] != body['market_trends'][0]['rationale']


def test_draft_and_candidate_evidence_remain_exact(context, payload):
    body = project_body(BriefResearchAnalysis, payload)
    plan = SelectionPlan(BriefResearchAnalysis, body, context, logical_task_id='research.v1')
    assert plan.body == body
    # Narrowing how much the model selects does not hide any source candidate.
    full = SelectionPlan(ContractResearchAnalysis, project_body(ContractResearchAnalysis,payload), context)
    assert set(map(str,plan.evidence_spans.values())) == set(map(str,full.evidence_spans.values()))


def test_research_defers_financial_reference_analysis_without_relaxing_canonical_validation(payload):
    payload['market_trends'][0]['claims'][0]['financial_value_ids']=['months']
    with pytest.raises(ValidationError):
        BriefResearchAnalysis.model_validate(payload)
    assert payload['market_trends'][0]['claims'][0]['financial_value_ids']==['months']


def test_both_research_stages_exclude_conflicting_financial_instructions(context, payload):
    from evaluation.two_stage_fixtures import synthetic_stage_payload
    from workflow.contract_generation import ContractGenerator
    calls = []

    class Client:
        def generate_structured_once(self, prompt, schema, **kwargs):
            calls.append(prompt)
            return schema.model_validate(synthetic_stage_payload(schema, payload))

    artifact = ContractGenerator(Client()).generate(context, 'research')
    context.verify_artifact(artifact)
    assert len(calls) == 2
    for prompt in calls:
        instructions = prompt.split('GENERATION_INSTRUCTIONS:', 1)[1]
        assert 'must be [] wherever present' in instructions
        assert 'For a financial_calculation claim include' not in instructions
        assert 'Legal examples: no related value: []; related value: [' not in instructions
        assert 'source_quality must be a normalized number in [0,1]' in instructions


def test_minimal_research_keeps_gaps_in_review_list_without_a_fourth_claim(payload):
    claim = deepcopy(payload['market_trends'][0]['claims'][0])
    claim['claim_id'] = 'research.v1.extra_gap'
    payload['unsupported_claims'] = [claim]
    assert len(ContractResearchAnalysis.model_validate(payload).unsupported_claims) == 1
    with pytest.raises(ValidationError):
        BriefResearchAnalysis.model_validate(payload)
    assert payload['unsupported_claims'] == [claim]
