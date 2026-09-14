"""Offline regression cases; no fixture below is a real business forecast."""
import json
from copy import deepcopy
from pathlib import Path
import pytest

from workflow.product_finance import (ProductFinancialModel,calculations,validate_financial_prose,
    resolve_tokens,render_ledger)
from workflow.product_output_policy import validate_product_batch
from workflow.product_research import ProductResearchPlan,plan_queries,evidence_catalog
from workflow.structured_repair import canonical_payload
from workflow.llm_client import StructuredJsonLLM,StructuredOutputValidationError,LLMClient
from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
from test_llm_client import _client,_response
from test_product_output_recovery import proposal

HISTORY=Path('C:/Users/JasmineJiang/Projects/multiple_ai_agent/docs/comparisons/pet-trust-product-ab-v2-20260911')

def historical(number):
    data=json.loads((HISTORY/f'B/calls/{number}.response.json').read_text(encoding='utf-8'))
    return json.loads(''.join(p.get('text','') for p in data['candidates'][0]['content']['parts'] if not p.get('thought')))

def model():
    return ProductFinancialModel.model_validate({'scenarios':[dict(scenario_id='base',period_label='month 12',
        currency='EUR',unit_label='customers',monthly_units=100,price_per_unit=100,variable_cost_per_unit=35,
        monthly_fixed_cost=60000,opening_operating_cash=1500000,restricted_customer_funds=900000,
        assumption_basis='Synthetic offline assumptions only; not a verified market forecast.')]})


def english_a_narrative():
    """English-only BusinessProposal fixture migrated from the old multilingual replay."""
    raw=json.loads((HISTORY/'A/proposal.json').read_text(encoding='utf-8'))
    raw.update(project_name='Offline Venture', tagline='A deterministic offline business-plan fixture.',
        executive_summary=('This synthetic executive summary exists only to test the product pipeline. '
            'Every market statement and operating assumption remains unverified and requires validation.'),
        solution=('The synthetic solution describes a configurable service workflow for offline tests; '
            'its features, demand, and commercial feasibility have not been verified.'),
        unique_value_proposition=('Unverified hypothesis: a focused workflow may improve the test customer experience.'),
        business_model='Offline assumed monthly revenue {{fin:base.revenue}} EUR; further validation required.',
        competitive_landscape=('No competitor conclusion is asserted in this offline fixture; alternatives require research.'),
        go_to_market_strategy='Offline assumed monthly revenue {{fin:base.revenue}} EUR; further validation required.',
        funding_ask='Offline assumed monthly revenue {{fin:base.revenue}} EUR; further validation required.',
        key_metrics=['Monthly revenue {{fin:base.revenue}} EUR','Cash flow {{fin:base.cash_flow}} EUR'],
        risks_and_mitigations=['Risk: assumptions are unverified. Mitigation: validate them before any decision.'])
    for index,item in enumerate(raw['pain_points'],1):
        item.update(title=f'Synthetic pain point {index}',
            description='This offline test pain point is an unverified hypothesis that requires customer research.')
    for index,item in enumerate(raw['target_audiences'],1):
        item.update(segment_name=f'Synthetic segment {index}',demographics='Unverified customer profile for offline testing.',
            needs='Unverified customer needs requiring discovery interviews.',estimated_size='Unknown; research required.')
    raw['market_size'].update(tam='Unknown; research required.',sam='Unknown; research required.',
        som='Unknown; research required.',growth_rate='Unknown; research required.')
    for index,item in enumerate(raw['competitive_advantages'],1):
        item.update(advantage=f'Unverified advantage {index}',
            description='This potential advantage is an unverified hypothesis requiring competitive research.')
    for key,value in raw['financial_assumptions'].items():
        if isinstance(value,str): raw['financial_assumptions'][key]='Assumptions require validation; consult the deterministic scenario ledger.'
    raw['financial_assumptions']['runway_months']=None
    raw['financial_model']=None
    return raw

def test_fixed_titles_are_program_owned_not_claim_type():
    raw=historical('007')
    normalized=canonical_payload(json.dumps(raw),PROPOSAL_DRAFT_BATCH_MODELS[0])
    assert normalized['executive_summary']['title']=='Executive Summary'
    assert normalized['problem']['key_claims'][4]['claim_type']=='needs_validation'
    with pytest.raises(ValueError,match='claim_type'):
        PROPOSAL_DRAFT_BATCH_MODELS[0].model_validate(normalized)

def test_enum_contract_reaches_real_llm_entry():
    text=LLMClient._constrained_prompt('task',PROPOSAL_DRAFT_BATCH_MODELS[0])
    assert 'claim_type' in text and 'evidence_status' in text and 'needs_validation' in text

def test_semantic_error_retains_raw_output():
    client=_client([_response({'items':['one']})])
    from test_llm_client import LimitedOutput
    def fail(output): raise ValueError('semantic test')
    with pytest.raises(StructuredOutputValidationError) as error:
        client.generate_structured_once('test',LimitedOutput,output_validator=fail)
    assert json.loads(error.value.raw_output)=={'items':['one']}

def test_historical_citation_errors_repaired_in_one_bounded_patch():
    raw=historical('006')
    saved=deepcopy(raw)
    state=json.loads((HISTORY/'B/state.json').read_text(encoding='utf-8'))
    allowed={s['source_id'] for k in ('web_sources','evidence_chunks') for s in state[k]}
    def validate(candidate): validate_product_batch(candidate,language='zh',allowed=allowed)
    from workflow.product_output_policy import ProductBatchValidationError
    normalized_original=PROPOSAL_DRAFT_BATCH_MODELS[0].model_validate(deepcopy(raw))
    with pytest.raises(ProductBatchValidationError) as failures:
        validate(normalized_original)
    patch={name:deepcopy(raw[name]) for name in failures.value.sections}
    for section in patch.values():
        for claim in section['key_claims']:
            claim['evidence_status']='needs_validation'
            claim['source_ids']=[]
        section['confidence']='low'
    client=_client([_response(raw),_response(patch)],max_prompt_chars=100000)
    result=client.generate_structured('Test grounded batch, supplied source IDs: '+str(sorted(allowed)),
        PROPOSAL_DRAFT_BATCH_MODELS[0],output_validator=validate)
    assert len(client._client.models.calls)==2
    prompt=client._client.models.calls[1]['contents']
    assert 'Local Structured Output Correction' in prompt
    assert 'ONLY these section fields:' in prompt
    assert result.title==saved['title']
    for field in PROPOSAL_DRAFT_BATCH_MODELS[0].model_fields:
        if field not in patch and field!='title':
            assert getattr(result,field).model_dump()==getattr(normalized_original,field).model_dump()
    assert raw==saved

def test_local_patch_cannot_overwrite_unlisted_section():
    batch=PROPOSAL_DRAFT_BATCH_MODELS[0]
    raw={k:v for k,v in proposal().model_dump().items() if k in batch.model_fields}
    from workflow.product_output_policy import ProductBatchValidationError
    def validator(candidate): raise ProductBatchValidationError('problem','test correction')
    client=_client([_response(raw),_response({'problem':raw['problem'],'target_customer':raw['target_customer']})],max_prompt_chars=100000)
    with pytest.raises(StructuredOutputValidationError):
        client.generate_structured('task',batch,output_validator=validator)
    assert len(client._client.models.calls)==2

@pytest.mark.parametrize('name,region',[('Pet care','Germany'),('Textile repair','France'),('Bakery subscription','Japan')])
def test_query_plans_are_not_frozen_cases(name,region):
    class Fake:
        def generate_json_for_schema(self,prompt,schema):
            assert name in prompt and 'regardless of report language' in prompt
            return json.dumps(dict(jurisdiction=region,market_query=f'{region} {name} official demand',
                                  service_and_regulatory_query=f'{region} {name} services licensing'))
    p=plan_queries({'industry':name,'geography':region,'output_language':'zh'},Fake())
    assert p.jurisdiction==region
    assert len(p.market_query)<=180

def test_query_plan_must_anchor_region():
    class Fake:
        def generate_json_for_schema(self,*args):
            return json.dumps(dict(jurisdiction='Germany',market_query='worldwide demand',service_and_regulatory_query='worldwide regulations'))
    with pytest.raises(ValueError,match='jurisdiction'): plan_queries({},Fake())

def test_historical_sources_not_promoted_to_verified_local_facts():
    from schemas.source import SourceRecord
    from rag.retriever import EvidenceChunk
    state=json.loads((HISTORY/'B/state.json').read_text(encoding='utf-8'))
    catalog=evidence_catalog(state['user_brief'],[SourceRecord.model_validate(s) for s in state['web_sources']],
                             [EvidenceChunk.model_validate(s) for s in state['evidence_chunks']])
    assert sum(s['role']=='unverified' for s in catalog)==10
    assert sum(s['role']=='framework' for s in catalog)==4

def test_unsupported_fact_does_not_gain_a_citation_by_repair():
    raw=historical('006')
    candidate=PROPOSAL_DRAFT_BATCH_MODELS[0].model_validate(raw)
    ids=set(candidate.executive_summary.source_ids)
    with pytest.raises(ValueError,match='unverified'):
        validate_product_batch(candidate,language='zh',allowed=ids,source_roles={s:'unverified' for s in ids})

def test_financial_math_preserves_deficit_and_excludes_restricted_funds():
    v=calculations(model().scenarios[0])
    assert v['revenue']==10000
    assert v['gross_profit']==6500
    assert v['cash_flow']==-53500
    assert v['break_even_units']==924
    assert v['runway_months']<29
    assert '-53500.00' in render_ledger(model())

def test_zero_contribution_does_not_invent_break_even():
    s=model().scenarios[0].model_copy(update={'variable_cost_per_unit':100})
    assert calculations(s)['break_even_units'] is None

def test_shared_reference_is_identical_across_sections():
    p={'business_model':'Monthly EUR {{fin:base.revenue}}',
       'financial_assumptions':'Monthly EUR {{fin:base.revenue}}; deficit {{fin:base.cash_flow}} EUR'}
    validate_financial_prose(p,model())
    assert resolve_tokens(p['business_model'],model())=='Monthly EUR 10000.00'

@pytest.mark.parametrize('reference',['{{fin:other.revenue}}','{{fin:base.invented}}','{{fin:bad}}'])
def test_unknown_financial_references_fail_closed(reference):
    with pytest.raises(ValueError): resolve_tokens(reference,model())

def test_historical_a_numeric_inconsistency_cannot_export_unchanged():
    from schemas.proposal_schema import BusinessProposal
    import app
    original=BusinessProposal.model_validate_json((HISTORY/'A/proposal.json').read_text(encoding='utf-8'))
    with pytest.raises(ValueError,match='financial_model'): app.proposal_to_markdown(original)

def test_b_financial_error_cannot_export(tmp_path):
    from workflow.nodes import export_node
    raw=proposal().model_dump()
    raw['financial_assumptions']['content']='Test fixture: expected revenue EUR 50000 from only 100 customers paying EUR 100.'
    with pytest.raises(ValueError,match='financial_model'):
        export_node({'proposal_draft':raw},output_dir=tmp_path)
    assert not list(tmp_path.glob('*.md'))

def test_b_deterministic_financial_export(tmp_path):
    from workflow.nodes import export_node
    raw=proposal('en').model_dump()
    raw['financial_assumptions']['content']=('This scenario is an offline test, not a forecast: monthly revenue '
        '{{fin:base.revenue}} EUR and monthly operating cash flow {{fin:base.cash_flow}} EUR.')
    result=export_node({'proposal_draft':raw,'finance_assumptions':{'financial_model':model().model_dump()}},output_dir=tmp_path)
    text=Path(result['output_path']).read_text(encoding='utf-8')
    assert '{{fin:' not in text and '-53500.00' in text and '10000.00' in text

def test_cross_currency_reference_rejected():
    with pytest.raises(ValueError,match='currency'):
        resolve_tokens('Projected {{fin:base.revenue}} USD',model())

def test_unverified_unique_market_claim_rejected():
    from workflow.product_research import validate_certainty
    with pytest.raises(ValueError,match='Unverified'):
        validate_certainty('这是德国首个提供此类服务的平台。')
    validate_certainty('是否属于德国首个此类平台尚需验证，不能作此断言。')

def test_a_uses_the_same_ledger_and_does_not_guess_runway():
    import app
    from schemas.proposal_schema import BusinessProposal
    raw=english_a_narrative()
    raw['financial_model']=model().model_dump()
    text=app.proposal_to_markdown(BusinessProposal.model_validate(raw))
    assert '10000.00' in text and '-53500.00' in text and '| Runway | 28.04 months |' in text
    assert '{{fin:' not in text

def test_legacy_runway_cannot_override_ledger():
    with pytest.raises(ValueError,match='sole source'):
        validate_financial_prose({'financial_assumptions':{'runway_months':20}},model())
