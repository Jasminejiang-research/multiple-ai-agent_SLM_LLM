"""Case-independent offline regression; synthetic corrections are NOT experiments."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from workflow.product_finance import (FinancialPlan, bind_financial_plan, financial_plan_context,
    validate_financial_prose, FinancialConsistencyError)
from workflow.product_output_policy import product_batch_validator
from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
from workflow.structured_repair import canonical_payload
from workflow.llm_client import StructuredJsonLLM, StructuredOutputValidationError, capture_llm_usage
from test_llm_client import _client, _response
from test_product_reliability_v3 import model, english_a_narrative
from test_product_output_recovery import proposal

HISTORY=Path('C:/Users/JasmineJiang/Projects/multiple_ai_agent/docs/comparisons/pet-trust-product-ab-v3-20260911')

def raw(arm,number):
    data=json.loads((HISTORY/arm/'calls'/f'{number}.response.json').read_text(encoding='utf-8'))
    return json.loads(''.join(p.get('text','') for p in data['candidates'][0]['content']['parts'] if not p.get('thought')))

def plan(quantitative=True):
    return FinancialPlan(mode='quantitative' if quantitative else 'qualitative',
        financial_model=model() if quantitative else None,
        reason='Synthetic test assumptions, not verified facts or forecasts.')

def narrative():
    data=english_a_narrative()
    for key in ('business_model','go_to_market_strategy','funding_ask'):
        data[key]='Unverified assumptions; monthly revenue {{fin:base.revenue}} EUR.'
    data['key_metrics']=['Monthly revenue {{fin:base.revenue}} EUR','Cash flow {{fin:base.cash_flow}} EUR']
    for key,value in data['financial_assumptions'].items():
        if isinstance(value,str): data['financial_assumptions'][key]='Assumptions require validation; consult the scenario ledger.'
    data['financial_assumptions']['runway_months']=None
    data['financial_model']=None
    return data

@pytest.mark.parametrize('name',['MBA AI education','German pet legacy care','Bakery subscription'])
def test_a_plans_before_writing_and_attaches_same_ledger(name):
    import app
    from workflow.run_budget import run_budget
    client=_client([_response(plan().model_dump()),_response(narrative())],max_prompt_chars=100000)
    with run_budget(max_requests=4,max_total_tokens=100000) as budget:
        result=app.generate_proposal(client,name)
    assert budget.snapshot()['request_count']==2
    calls=client._client.models.calls
    assert name in calls[0]['contents'] and name in calls[1]['contents']
    assert 'BEFORE narrative' in calls[0]['contents']
    assert 'Locked Financial Plan' in calls[1]['contents']
    assert result.financial_model==plan().financial_model
    text=app.proposal_to_markdown(result)
    assert '{{fin:' not in text and '-53500.00' in text

@pytest.mark.parametrize('name',['MBA AI','Pet care','Bakery'])
def test_b_finance_uses_same_planning_contract(name):
    from agents.finance import FinanceAgent
    from schemas.agent_outputs import FinanceAssumptions
    from test_finance_agent import _finance_assumptions_json
    client=_client([_response(plan().model_dump()),_response(json.loads(_finance_assumptions_json()))],max_prompt_chars=100000)
    result=FinanceAgent(llm_client=StructuredJsonLLM(client,FinanceAssumptions)).run({'user_brief':{'industry':name}})
    assert result.financial_model==plan().financial_model
    assert len(client._client.models.calls)==2

@pytest.mark.parametrize('mode,value',[('quantitative',None),('qualitative',model())])
def test_financial_modes_are_mutually_exclusive(mode,value):
    with pytest.raises(ValueError): FinancialPlan(mode=mode,reason='Explicit test reason for model mode.',financial_model=value)

def test_historical_a_reports_all_reference_and_amount_errors():
    with pytest.raises(FinancialConsistencyError) as error: validate_financial_prose(raw('A','002'))
    text=str(error.value)
    for key in ('base_case_y1.runway_months','base_case_y1.price_per_unit','base_case_y1.monthly_fixed_cost','numeric financial'):
        assert key in text
    assert len(error.value.sections)>1

def test_qualitative_plan_rejects_dangling_references_and_amounts():
    from schemas.proposal_schema import BusinessProposal
    with pytest.raises(ValueError): bind_financial_plan(BusinessProposal.model_validate(narrative()),plan(False))
    data=narrative()
    for key in ('business_model','go_to_market_strategy','funding_ask'):
        data[key]='The operating model remains an unverified qualitative hypothesis.'
    data['key_metrics']=['Revenue requires validation','Cash flow requires validation']
    result=bind_financial_plan(BusinessProposal.model_validate(data),plan(False))
    assert result.financial_model is None

def test_narrative_cannot_replace_locked_ledger():
    from schemas.proposal_schema import BusinessProposal
    data=narrative(); data['financial_model']=model().model_dump()
    data['financial_model']['scenarios'][0]['price_per_unit']=999
    with pytest.raises(ValueError,match='changed the locked'): bind_financial_plan(BusinessProposal.model_validate(data),plan())

def test_adjacent_valid_financial_references():
    validate_financial_prose({'business_model':'{{fin:base.revenue}}{{fin:base.cash_flow}}'},model())

@pytest.mark.parametrize('amount',['EUR 100000','EUR -100000','USD1000','1,000 EUR','€-100','€100','-1000欧元','1,000 customers'])
def test_b_break_even_discussion_cannot_bypass_model(amount):
    with pytest.raises(ValueError,match='numeric financial'):
        validate_financial_prose({'break_even_discussion':f'Reach break-even with {amount} monthly revenue.'})
    validate_financial_prose({'break_even_discussion':'Break-even requires {{fin:base.break_even_units}} customers.'},model())

def test_planning_does_not_reset_or_expand_request_budget():
    import app
    from workflow.run_budget import run_budget, RunBudgetExceededError
    client=_client([_response(plan().model_dump()),_response(narrative())],max_prompt_chars=100000)
    with run_budget(max_requests=1,max_total_tokens=100000):
        with pytest.raises(RunBudgetExceededError): app.generate_proposal(client,'Any new business case')
    assert len(client._client.models.calls)==1

def test_invalid_json_uses_bounded_full_correction_not_partial_guess():
    response=_response({}); response.text='{broken'
    batch=PROPOSAL_DRAFT_BATCH_MODELS[0]
    data={k:v for k,v in proposal().model_dump().items() if k in batch.model_fields}
    client=_client([response,_response(data)],max_prompt_chars=100000)
    check=product_batch_validator(language='auto',allowed=set(),source_roles={})
    client.generate_structured('test',batch,output_validator=check)
    assert len(client._client.models.calls)==2
    assert '# Structured Output Correction' in client._client.models.calls[1]['contents']

def validator():
    state=json.loads((HISTORY/'B/state.json').read_text(encoding='utf-8'))
    ids={s['source_id'] for k in ('web_sources','evidence_chunks') for s in state[k]}
    return product_batch_validator(language='zh',allowed=ids,source_roles={s:'unverified' for s in ids})

def corrected_batch(raw_batch):
    batch=PROPOSAL_DRAFT_BATCH_MODELS[0]
    payload=canonical_payload(json.dumps(raw_batch),batch)
    sections={k:deepcopy(v) for k,v in payload.items() if k!='title'}
    for section in sections.values():
        section['source_ids']=[]; section['confidence']='low'
        section['content']='以下内容均为未经核实的构想，尚需进一步验证。'+section['content']
        for claim in section['key_claims']:
            if claim['claim_type']=='problem': claim['claim_type']='customer'
            claim['evidence_status']='needs_validation'; claim['source_ids']=[]
    return sections

def test_real_b_mixed_errors_all_four_sections_in_single_patch():
    original=raw('B','007'); saved=deepcopy(original)
    client=_client([_response(original),_response(corrected_batch(original))],max_prompt_chars=100000)
    with capture_llm_usage() as usage:
        result=client.generate_structured('Offline historical replay',PROPOSAL_DRAFT_BATCH_MODELS[0],output_validator=validator())
    request=client._client.models.calls[1]['contents']
    assert 'ONLY these section fields: executive_summary, market_opportunity, problem, target_customer' in request
    assert 'unverified' in request and 'claim_type' in request
    assert usage.request_count==2 and usage.retry_count==1
    assert original==saved and result.title==original['title']

def test_real_b_old_single_section_patch_still_fails_without_third_call():
    client=_client([_response(raw('B','007')),_response(raw('B','008'))],max_prompt_chars=100000)
    with pytest.raises(StructuredOutputValidationError):
        client.generate_structured('test',PROPOSAL_DRAFT_BATCH_MODELS[0],output_validator=validator())
    assert len(client._client.models.calls)==2

def test_clean_sections_remain_immutable_with_mixed_errors():
    batch=PROPOSAL_DRAFT_BATCH_MODELS[0]
    data={k:v for k,v in proposal().model_dump().items() if k in batch.model_fields}
    for key in ('executive_summary','problem'):
        data[key]['key_claims']=[dict(text='An unverified test claim about the service.',
            claim_type='general',evidence_status='assumption',source_ids=[],
            content_anchor='An unverified test claim about the service.')]
    data['executive_summary']['key_claims'][0]['claim_type']='invalid_enum'
    data['problem']['key_claims'][0]['evidence_status']='sourced_fact'
    data['problem']['key_claims'][0]['source_ids']=['user_brief']
    check=product_batch_validator(language='auto',allowed=set(),source_roles={})
    fixed=deepcopy(data)
    for key in ('executive_summary','problem'):
        fixed[key]['source_ids']=[]
        for claim in fixed[key]['key_claims']:
            claim['claim_type']='general'; claim['evidence_status']='needs_validation'; claim['source_ids']=[]
    patch={k:fixed[k] for k in ('executive_summary','problem')}
    client=_client([_response(data),_response(patch)],max_prompt_chars=100000)
    result=client.generate_structured('test',batch,output_validator=check)
    assert result.target_customer.model_dump()==data['target_customer']
    assert result.market_opportunity.model_dump()==data['market_opportunity']

def test_diagnostics_collect_financial_and_evidence_errors_together():
    batch=PROPOSAL_DRAFT_BATCH_MODELS[2]
    data={k:v for k,v in proposal().model_dump().items() if k in batch.model_fields}
    field=next(iter(data))
    data[field]['key_claims']=[dict(text='An unverified test claim about the service.',
        claim_type='invalid_enum',evidence_status='assumption',source_ids=[],
        content_anchor='An unverified test claim about the service.')]
    if 'financial_assumptions' in data:
        data['financial_assumptions']['content']='Unverified revenue EUR 5000 with {{fin:missing.revenue}}.'
    check=product_batch_validator(language='auto',allowed=set(),source_roles={})
    errors=check.diagnose_sections(batch,data)
    assert field in errors
    if 'financial_assumptions' in data:
        assert 'financial_assumptions' in errors

def test_financial_plan_schema_failure_is_bounded_before_narrative():
    import app
    bad={'mode':'quantitative','reason':'Missing scenario test for validation.','financial_model':None}
    client=_client([_response(bad),_response(bad)],max_prompt_chars=100000)
    with pytest.raises(StructuredOutputValidationError): app.generate_proposal(client,'Any new business case')
    assert len(client._client.models.calls)==2
