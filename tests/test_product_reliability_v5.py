"""Offline repair-budget and provenance regressions; no model experiments."""
import json
import re
from copy import deepcopy
from pathlib import Path
import pytest
from schemas.agent_outputs import WriterInput, ResearchAnalysis
from workflow.product_repair_context import writer_repair_context
from workflow.product_output_policy import product_batch_validator
from workflow.product_research import evidence_catalog, validate_research_provenance
from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
from workflow.llm_client import LLMClient, PromptBudgetExceededError, StructuredOutputValidationError, capture_llm_usage
from test_llm_client import _client, _response
from test_product_reliability_v4 import corrected_batch as _base_corrected_batch

HISTORY=Path('C:/Users/JasmineJiang/Projects/multiple_ai_agent/docs/comparisons/pet-trust-product-ab-v4-20260911')

def corrected_batch(raw):
    # Synthetic downgraded response: remove obsolete inline citations as well
    # as structured IDs. This never modifies the historical files.
    def clean(value):
        if isinstance(value,str): return re.sub(r'\[web-[^\]\n]*\]','',value)
        if isinstance(value,list): return [clean(v) for v in value]
        if isinstance(value,dict): return {k:clean(v) for k,v in value.items()}
        return value
    return clean(_base_corrected_batch(raw))

def historical():
    state=json.loads((HISTORY/'B/state.json').read_text(encoding='utf-8'))
    writer_input=WriterInput.model_validate({**{k:v for k,v in state.items() if k in WriterInput.model_fields},'output_language':'zh'})
    response=json.loads((HISTORY/'B/calls/009.response.json').read_text(encoding='utf-8'))
    raw=json.loads(''.join(p.get('text','') for p in response['candidates'][0]['content']['parts'] if not p.get('thought')))
    request=json.loads((HISTORY/'B/calls/009.request.json').read_text(encoding='utf-8'))
    return writer_input,raw,request['contents']

def check_for(writer_input):
    catalog=evidence_catalog(writer_input.user_brief,writer_input.web_sources,writer_input.evidence_chunks)
    check=product_batch_validator(language='zh',allowed={s['source_id'] for s in catalog},
        source_roles={s['source_id']:s['role'] for s in catalog},financial_model=writer_input.finance_assumptions.financial_model)
    check.repair_context=lambda fields,original:writer_repair_context(writer_input,fields,original)
    return check

def replay(client,original_prompt,raw,check):
    # This fixture already contains generated schema contracts. Preserve the
    # exact historical first request; append contracts normally to the repair.
    constrained=LLMClient._constrained_prompt
    client._constrained_prompt=lambda prompt,schema: prompt if prompt==original_prompt else constrained(prompt,schema)
    return client.generate_structured(original_prompt,PROPOSAL_DRAFT_BATCH_MODELS[0],output_validator=check)

def test_real_overflow_replay_now_sends_compact_single_patch(tmp_path):
    writer_input,raw,prompt=historical()
    saved=deepcopy(raw)
    client=_client([_response(raw),_response(corrected_batch(raw))],max_prompt_chars=120000)
    with capture_llm_usage() as usage:
        result=replay(client,prompt,raw,check_for(writer_input))
    repair=client._client.models.calls[1]['contents']
    assert len(prompt)==110949
    assert len(repair)<60000  # substantial headroom, not a 1716-character patch
    assert 'ONLY these section fields: executive_summary, market_opportunity, problem, target_customer' in repair
    assert '# Writer Input JSON' not in repair
    assert 'Writer Repair Context' in repair and 'unverified' in repair
    assert 'Required Output Language' in repair and 'Shared financial calculation contract' in repair
    assert usage.request_count==2 and usage.retry_count==1
    assert result.title==raw['title'] and raw==saved
    (tmp_path/'lengths.json').write_text(json.dumps({'old_original':len(prompt),'old_repair':121716,
        'new_repair':len(repair),'limit':120000}),encoding='utf-8')

def test_repair_complete_contract_is_checked_before_dispatch():
    writer_input,raw,_=historical()
    check=check_for(writer_input)
    check.repair_context=lambda fields,original:'x'*10000
    client=_client([_response(raw)],max_prompt_chars=10000)
    with pytest.raises(PromptBudgetExceededError):
        client.generate_structured('small initial input',PROPOSAL_DRAFT_BATCH_MODELS[0],output_validator=check)
    assert len(client._client.models.calls)==1  # no truncation, no retry dispatched

def test_exact_repair_boundary_includes_schema_contracts():
    writer_input,raw,_=historical(); schema=PROPOSAL_DRAFT_BATCH_MODELS[0]
    check=check_for(writer_input)
    check.repair_context=lambda fields,original:'Small explicit test context.'
    first=_client([_response(raw),_response(corrected_batch(raw))],max_prompt_chars=120000)
    first.generate_structured('task',schema,output_validator=check)
    length=len(first._client.models.calls[1]['contents'])
    for limit,success in ((length,True),(length-1,False)):
        client=_client([_response(raw),_response(corrected_batch(raw))],max_prompt_chars=limit)
        if success:
            client.generate_structured('task',schema,output_validator=check)
            assert len(client._client.models.calls)==2
        else:
            with pytest.raises(PromptBudgetExceededError):client.generate_structured('task',schema,output_validator=check)
            assert len(client._client.models.calls)==1

def test_unparseable_json_uses_same_compact_context_with_full_schema():
    writer_input,raw,prompt=historical()
    bad=_response({}); bad.text='{broken'
    fixed={'title':raw['title'],**corrected_batch(raw)}
    client=_client([bad,_response(fixed)],max_prompt_chars=120000)
    replay(client,prompt,raw,check_for(writer_input))
    repair=client._client.models.calls[1]['contents']
    assert '# Structured Output Correction' in repair and 'Writer Repair Context' in repair
    assert '{broken' in repair and len(repair)<60000

def test_context_keeps_full_eligible_evidence_and_no_weak_source_prose():
    from datetime import date
    writer_input,raw,_=historical()
    source=writer_input.web_sources[0]
    source.published_date=date.today();source.source_quality='official'
    source.summary='Germany eligible text. '+('Important unabridged fact. '*100)
    weak=writer_input.web_sources[1]; weak.summary='UNVERIFIED_SOURCE_SENTINEL'
    context=writer_repair_context(writer_input,set(raw)-{'title'},raw)
    assert source.summary in context and source.source_id in context
    assert 'UNVERIFIED_SOURCE_SENTINEL' not in context and weak.source_id in context
    assert 'content_withheld' in context
    for chunk in writer_input.evidence_chunks:
        # Compare JSON encoding to preserve newlines and quotes exactly.
        assert json.dumps(chunk.text,ensure_ascii=False) in context

def test_writer_main_prompt_minifies_without_losing_input():
    from agents.writer import build_writer_prompt
    writer_input,_,_=historical()
    prompt=build_writer_prompt(writer_input)
    encoded=prompt.split('# Writer Input JSON\n\n',1)[1].split('```json\n',1)[1].split('\n```',1)[0]
    assert json.loads(encoded)==writer_input.model_dump(mode='json')

@pytest.mark.parametrize('role',['unverified','framework'])
def test_research_cannot_promote_weak_evidence(role):
    writer_input,_,_=historical(); analysis=writer_input.research_analysis.model_copy(deep=True)
    finding=analysis.market_trends[0]
    finding.evidence_status='sourced_fact'; finding.source_ids=['source-test']
    with pytest.raises(ValueError,match='eligible_external'):
        validate_research_provenance(analysis,[dict(source_id='source-test',role=role)])

def test_research_declared_fact_requires_known_source_and_hypotheses_stay_low():
    writer_input,_,_=historical(); analysis=writer_input.research_analysis.model_copy(deep=True)
    finding=analysis.market_trends[0]
    finding.evidence_status='sourced_fact'; finding.source_ids=['user_brief']
    with pytest.raises(ValueError,match='user_brief'):validate_research_provenance(analysis,[])
    finding.evidence_status='needs_validation';finding.source_ids=[];finding.confidence='high'
    validate_research_provenance(analysis,[])
    assert finding.confidence=='low' and 'not established facts' in analysis.evidence_notice

def test_research_real_adapter_repairs_provenance_once_without_search():
    from agents.research import ResearchAgent
    from workflow.llm_client import StructuredJsonLLM
    writer_input,_,_=historical(); analysis=writer_input.research_analysis.model_dump()
    analysis['market_trends'][0].update(evidence_status='sourced_fact',source_ids=['user_brief'])
    fixed=deepcopy(analysis)
    fixed['market_trends'][0].update(evidence_status='needs_validation',source_ids=[])
    client=_client([_response(analysis),_response(fixed)],max_prompt_chars=120000)
    agent=ResearchAgent(llm_client=StructuredJsonLLM(client,ResearchAnalysis),
        web_search_tool=lambda *args:pytest.fail('Unexpected search'))
    result=agent.run({**writer_input.user_brief,'web_research_sources':[]})
    assert result.market_trends[0].confidence=='low'
    assert len(client._client.models.calls)==2

def test_strategy_and_finance_get_the_same_eligibility_catalog():
    from workflow.multi_agent_nodes import strategy_agent_node,finance_agent_node
    writer_input,_,_=historical()
    state=json.loads((HISTORY/'B/state.json').read_text(encoding='utf-8'))
    calls=[]
    class Agent:
        def __init__(self,result):self.result=result
        def run(self,input):calls.append(input);return self.result
    strategy_agent_node(state,agent=Agent(writer_input.strategy_analysis))
    finance_agent_node(state,agent=Agent(writer_input.finance_assumptions))
    assert calls[0]['evidence_catalog']==calls[1]['evidence_catalog']
    assert all(s['role']=='unverified' for s in calls[0]['evidence_catalog'])
