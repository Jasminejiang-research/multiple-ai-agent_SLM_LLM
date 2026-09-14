"""Offline only: acceptance semantics, role quotas, native graph and historical replay."""
import json
from pathlib import Path
from copy import deepcopy
import pytest
from pydantic import BaseModel
from test_llm_client import _client, _response
from workflow.llm_client import StructuredJsonLLM, StructuredOutputValidationError, PromptBudgetExceededError
from workflow.product_acceptance import acceptance_scope, current_acceptance, quality_check, product_node

HISTORY = Path('C:/Users/JasmineJiang/Projects/multiple_ai_agent/docs/comparisons/pet-trust-product-ab-v5-20260911')


class Packet(BaseModel):
    text: str


def reject(candidate):
    raise ValueError('Explicit unresolved quality defect')


def raw_response(arm, call):
    response = json.loads((HISTORY/arm/'calls'/f'{call:03}.response.json').read_text(encoding='utf-8'))
    return json.loads(''.join(p.get('text','') for p in response['candidates'][0]['content']['parts'] if not p.get('thought')))


def test_without_product_scope_remains_strict():
    client = _client([_response({'text':'first'}), _response({'text':'second'})])
    with pytest.raises(StructuredOutputValidationError):
        client.generate_structured('task', Packet, output_validator=reject)
    assert len(client._client.models.calls) == 2


def test_one_correction_shared_across_actor_calls_and_latest_text_preserved():
    client = _client([_response({'text':s}) for s in ['first','corrected but bad','next batch']])
    with acceptance_scope(stage='writer') as policy:
        first = client.generate_structured('task', Packet, output_validator=reject)
        second = client.generate_structured('task2', Packet, output_validator=reject)
        assert first.text == 'corrected but bad' and second.text == 'next batch'
        assert policy.corrections == {'writer':1} and policy.issues
    assert len(client._client.models.calls) == 3
    assert current_acceptance() is None


def test_each_actor_has_independent_quota_across_serialized_graph_tasks():
    state = {}
    clients = []
    for actor in ['research','strategy','finance','writer','critic','revision']:
        client = _client([_response({'text':'bad'}),_response({'text':'still bad'})])
        clients.append(client)
        node = product_node(actor, lambda state: {'output':client.generate_structured('task', Packet, output_validator=reject).text})
        state.update(node(state))
    assert state['product_acceptance']['corrections'] == {k:1 for k in ['research','strategy','finance','writer','critic','revision']}
    assert all(len(c._client.models.calls)==2 for c in clients)
    fresh = product_node('validator', lambda state: {})(state)
    assert fresh['product_acceptance']['corrections'] == {}


def test_malformed_correction_retains_complete_first_result_and_flags():
    client = _client([_response({'text':'keep me'}), _response({})])
    with acceptance_scope(stage='A') as policy:
        result=client.generate_structured('task', Packet, output_validator=reject)
        assert result.text=='keep me'
        assert any('previous complete' in i['message'] for i in policy.issues)


def test_no_structured_output_is_not_fabricated():
    client = _client([_response({}),_response({})])
    with acceptance_scope(), pytest.raises(StructuredOutputValidationError):
        client.generate_structured('task', Packet)
    assert len(client._client.models.calls)==2


@pytest.mark.parametrize('error',[TimeoutError('offline'),PermissionError('denied')])
def test_technical_errors_not_accepted(error):
    client = _client([error])
    with acceptance_scope(), pytest.raises(type(error)):
        client.generate_structured('task', Packet)
    assert len(client._client.models.calls)==1


def test_prompt_budget_remains_hard():
    client=_client([], max_prompt_chars=10)
    with acceptance_scope(), pytest.raises(PromptBudgetExceededError):
        client.generate_structured('a'*20,Packet)
    assert client._client.models.calls==[]


def test_real_a_wrong_language_remains_a_hard_contract(tmp_path):
    import app
    from schemas.proposal_schema import BusinessProposal
    plan, first, second = [raw_response('A',n) for n in [1,2,3]]
    client = _client([_response(plan),_response(first),_response(second)], max_prompt_chars=120000)
    with pytest.raises(StructuredOutputValidationError, match='Product output must be English'):
        app.generate_proposal(client, 'German pet care concept; output Chinese; missing finances are assumptions.')
    assert len(client._client.models.calls)==3


def test_b_native_graph_reaches_formal_export_with_residual_issues(tmp_path):
    from test_multi_agent_graph import _analysis_packets, _complete_brief, _proposal, _critique, _revised_proposal, FakeJsonLLM
    from workflow.multi_agent_graph import build_multi_agent_workflow_graph
    research,strategy,finance=_analysis_packets()
    graph=build_multi_agent_workflow_graph(
        research_llm=FakeJsonLLM(research.model_dump_json()),
        strategy_llm=FakeJsonLLM(strategy.model_dump_json()),
        finance_llm=FakeJsonLLM(finance.model_dump_json()),
        writer_llm=FakeJsonLLM(_proposal().model_dump_json()),
        critic_llm=FakeJsonLLM(_critique().model_dump_json()),
        revision_llm=FakeJsonLLM(_revised_proposal().model_dump_json()),
        web_search_tool=lambda *a,**kw:[], evidence_provider=lambda *a:[],output_dir=tmp_path)
    result=graph.invoke({'user_brief':_complete_brief(),'run_id':'offline_acceptance'})
    assert result['current_step']=='export'
    assert result['product_acceptance']['status']=='accepted_with_issues'
    assert 'Formal Output and Unresolved Issues' not in result['final_markdown']
    assert '"status": "accepted_with_issues"' in result['audit_markdown']
    assert '# ⚠ Needs Citation Review' not in result['final_markdown']
    assert Path(result['output_path']).is_file()


def test_real_writer_local_patch_residual_error_preserves_whole_batch():
    from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
    from workflow.product_output_policy import product_batch_validator
    schema=PROPOSAL_DRAFT_BATCH_MODELS[2]
    raw=raw_response('B',11)
    patch={'go_to_market_strategy':deepcopy(raw['go_to_market_strategy'])}
    allowed={s for field in raw.values() if isinstance(field,dict) for s in field.get('source_ids',[])}
    validate=product_batch_validator(language='zh',allowed=allowed,financial_model=None)
    validate.repair_context=lambda fields,original:'Repair requested section, preserve others.'
    client=_client([_response(raw),_response(patch)],max_prompt_chars=120000)
    with acceptance_scope(stage='writer') as policy:
        result=client.generate_structured('task',schema,output_validator=validate)
        assert result.business_model.content==raw['business_model']['content']
        assert result.go_to_market_strategy.content==patch['go_to_market_strategy']['content']
        assert policy.corrections=={'writer':1} and policy.issues
    assert len(client._client.models.calls)==2


def test_export_records_new_finance_errors_without_blocking(tmp_path):
    from test_multi_agent_graph import _proposal
    from workflow.nodes import export_node
    proposal=_proposal()
    proposal.financial_assumptions.content += ' EUR 12345 {{fin:unknown.revenue}}'
    state={'proposal_draft':proposal.model_dump(),'user_brief':{'output_language':'en'},'run_id':'flags'}
    result=product_node('export',lambda s:export_node(s,output_dir=tmp_path))(state)
    assert '{{fin:unknown.revenue}}' not in result['final_markdown']
    assert '{{fin:unknown.revenue}}' in result['audit_markdown']
    assert result['product_acceptance']['status']=='accepted_with_issues'


def test_b_ui_budget_separate_from_a(monkeypatch):
    import app
    monkeypatch.setattr(app,'load_dotenv',lambda *a:None)
    monkeypatch.delenv('LLM_MULTI_AGENT_RUN_MAX_REQUESTS',raising=False)
    monkeypatch.delenv('LLM_MULTI_AGENT_RUN_MAX_TOTAL_TOKENS',raising=False)
    assert app._multi_agent_run_budget_settings()==(24,420000)
    monkeypatch.setenv('LLM_MULTI_AGENT_RUN_MAX_TOTAL_TOKENS','430000')
    assert app._multi_agent_run_budget_settings()==(24,430000)


def test_native_writer_and_revision_each_share_one_correction_across_all_batches(tmp_path):
    from test_multi_agent_graph import _analysis_packets, _complete_brief, _proposal, _critique
    from workflow.multi_agent_graph import build_multi_agent_workflow_graph
    from workflow.generation_batches import PROPOSAL_SECTION_BATCHES
    from schemas.agent_outputs import ResearchAnalysis, StrategyAnalysis, FinanceAssumptions
    from schemas.workflow import ProposalDraft, CritiqueReport, RevisedProposal
    proposal=_proposal().model_dump()
    for field in [k for group in PROPOSAL_SECTION_BATCHES for k in group]:
        section=proposal[field]
        section['content'] += ' A cited but unavailable source [web-missing].'
        section['source_ids']=['web-missing']
    def responses(revision=False):
        values=[]
        for number, fields in enumerate(PROPOSAL_SECTION_BATCHES,1):
            batch={k:proposal[k] for k in fields}
            if number==1:
                batch['title']=proposal['title']
                if revision:
                    batch.update(applied_critique_summary=['Reviewed assumptions.'],unresolved_issues=['Evidence still missing.'])
            values.append(_response(batch))
            if number==1:
                values.append(_response({k:proposal[k] for k in fields}))  # remains bad; one local repair
        return values
    research,strategy,finance=_analysis_packets()
    rclient=_client([_response(raw_response('B',4)),_response(research.model_dump())],max_prompt_chars=120000)
    sclient=_client([_response(strategy.model_dump())],max_prompt_chars=120000)
    fclient=_client([_response(raw_response('B',7)),_response(finance.model_dump())],max_prompt_chars=120000)
    wclient=_client(responses(),max_prompt_chars=120000)
    cclient=_client([_response(_critique().model_dump())],max_prompt_chars=120000)
    vclient=_client(responses(True),max_prompt_chars=120000)
    graph=build_multi_agent_workflow_graph(
        research_llm=StructuredJsonLLM(rclient,ResearchAnalysis),
        strategy_llm=StructuredJsonLLM(sclient,StrategyAnalysis),
        finance_llm=StructuredJsonLLM(fclient,FinanceAssumptions),
        writer_llm=StructuredJsonLLM(wclient,ProposalDraft),
        critic_llm=StructuredJsonLLM(cclient,CritiqueReport),
        revision_llm=StructuredJsonLLM(vclient,RevisedProposal),
        web_search_tool=lambda *a,**kw:[], evidence_provider=lambda *a:[],output_dir=tmp_path)
    result=graph.invoke({'user_brief':_complete_brief(),'run_id':'native_shared_quota'})
    assert result['current_step']=='export'
    assert result['product_acceptance']['corrections']=={'writer':1,'revision':1}
    assert len(wclient._client.models.calls)==5 and len(vclient._client.models.calls)==5
    assert result['revision_applied'] is True
    assert 'web-missing' not in result['final_markdown']
    assert 'web-missing' in result['audit_markdown']
    assert result['product_acceptance']['status']=='accepted_with_issues'
    assert len(list(tmp_path.rglob('batch-*.json')))==4


def test_checkpoint_resume_does_not_reset_writer_quota(tmp_path):
    from workflow.product_checkpoint import writer_checkpoint
    from test_product_reliability_v5 import historical
    writer_input, _, _=historical()
    with acceptance_scope(stage='writer') as original:
        with writer_checkpoint(tmp_path/'checkpoint') as store:
            store.bind(writer_input,'same prompt')
            assert original.claim_correction('initial correction')
            original.flag('remaining problem')
    with acceptance_scope(stage='writer') as resumed:
        with writer_checkpoint(tmp_path/'checkpoint',resume=True) as store:
            store.bind(writer_input,'same prompt')
            assert not resumed.claim_correction('must not retry again')
            assert resumed.corrections=={'writer':1}
            assert resumed.issues==original.issues


def test_parallel_scopes_do_not_share_quota():
    from concurrent.futures import ThreadPoolExecutor
    def run(actor):
        with acceptance_scope(stage=actor) as scope:
            assert scope.claim_correction('one')
            return scope.snapshot()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first,second=list(pool.map(run,['writer','writer']))
    assert first['corrections']==second['corrections']=={'writer':1}
    assert current_acceptance() is None
