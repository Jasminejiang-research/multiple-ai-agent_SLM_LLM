"""Offline product regressions; fabricated proposals below are test fixtures only."""
import json
from pathlib import Path
import pytest

from agents.writer import WriterAgent, build_writer_prompt
from schemas.workflow import ProposalDraft, RevisedProposal, PROPOSAL_SECTION_FIELD_NAMES
from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS, PROPOSAL_SECTION_BATCHES
from workflow.product_checkpoint import checkpoint_path, writer_checkpoint
from workflow.product_output_policy import (resolve_output_language, normalize_markers,
    validate_text_language, validate_product_batch)
from workflow.multi_agent_graph import build_multi_agent_workflow_graph
from workflow.nodes import export_node
from workflow.run_budget import run_budget
from test_rag_enabled_writer import _writer_input
from test_multi_agent_graph import _complete_brief, _critique, FakeJsonLLM


def proposal(language='zh'):
    from schemas.workflow import PROPOSAL_SECTION_TITLES
    text=('本段为离线测试专用的中文内容，说明业务假设尚需验证，不能用于真实商业决策，所有内容均属于测试样本而非实际商业建议。' if language=='zh'
          else 'This is exclusively a deterministic offline test fixture; every business assumption requires validation.')
    data={'title':'Offline test proposal'}
    for name,title in zip(PROPOSAL_SECTION_FIELD_NAMES,PROPOSAL_SECTION_TITLES):
        data[name]=dict(title=title,content=text,key_claims=[],source_ids=[],confidence='low')
    return ProposalDraft.model_validate(data)


class BatchLLM:
    def __init__(self, *, fail_on=None, language='zh'):
        self.calls=[]
        self.fail_on=fail_on
        self.data=proposal(language).model_dump()

    def generate_json_for_schema(self,prompt,schema,output_validator=None):
        number=PROPOSAL_DRAFT_BATCH_MODELS.index(schema)+1
        self.calls.append(number)
        if number==self.fail_on:
            raise RuntimeError('simulated interruption')
        candidate=schema.model_validate({k:self.data[k] for k in schema.model_fields})
        if output_validator:
            output_validator(candidate)
        return candidate.model_dump_json()


def packet(language='zh'):
    return _writer_input([]).model_copy(update={'output_language':language})


@pytest.mark.parametrize('brief',[
    {'output_language':'zh-CN'}, {'proposal_goal':'生成中文商业计划书'},
    {'output_language':'en','proposal_goal':'中文'}, {'proposal_goal':'investor'},
    {'output_language':'unsupported'}])
def test_language_resolution_is_system_owned_english(brief):
    assert resolve_output_language(brief)=='en'


def test_writer_prompt_explicit_language():
    assert 'All narrative section content and claim text must be in Simplified Chinese' in build_writer_prompt(packet())


def test_english_batch_rejected_in_chinese_run():
    with pytest.raises(ValueError,match='English narrative'):
        WriterAgent(llm_client=BatchLLM(language='en')).run(packet())


def test_names_urls_ids_not_translated():
    validate_text_language('中文方案需要审查 GDPR、AI 和德国品牌。来源 [web-abc] https://example.org','zh')


def test_group_markers_only_known_ids_are_expanded():
    assert normalize_markers('事实 [web-a, web-b]',{'web-a','web-b'})=='事实 [web-a] [web-b]'
    assert normalize_markers('事实 [web-a, web-typo]',{'web-a','web-b'})=='事实 [web-a, web-typo]'


def test_unknown_source_not_guessed():
    batch=PROPOSAL_DRAFT_BATCH_MODELS[0].model_validate({k:v for k,v in proposal().model_dump().items()
                                                       if k in PROPOSAL_DRAFT_BATCH_MODELS[0].model_fields})
    batch.problem.source_ids=['web-typo']
    with pytest.raises(ValueError,match='unknown source IDs'):
        validate_product_batch(batch,language='zh',allowed={'web-correct'})


def test_checkpoint_survives_failure_and_skips_validated_batches(tmp_path):
    path=tmp_path/'checkpoint'
    first=BatchLLM(fail_on=3)
    with pytest.raises(RuntimeError,match='interruption'),writer_checkpoint(path):
        WriterAgent(llm_client=first).run(packet())
    assert (path/'batch-1.json').exists() and (path/'batch-2.json').exists()
    assert not (path/'batch-3.json').exists()
    second=BatchLLM()
    with writer_checkpoint(path,resume=True):
        output=WriterAgent(llm_client=second).run(packet())
    assert second.calls==[3,4]
    assert all(getattr(output,k).content for k in PROPOSAL_SECTION_FIELD_NAMES)


def test_changed_input_refuses_before_generation(tmp_path):
    with writer_checkpoint(tmp_path/'cp'):
        WriterAgent(llm_client=BatchLLM()).run(packet())
    llm=BatchLLM()
    with pytest.raises(ValueError,match='changed'),writer_checkpoint(tmp_path/'cp',resume=True):
        WriterAgent(llm_client=llm).run(packet('en'))
    assert llm.calls==[]


def test_tampered_batch_refuses_before_generation(tmp_path):
    path=tmp_path/'cp'
    with writer_checkpoint(path):
        WriterAgent(llm_client=BatchLLM()).run(packet())
    data=json.loads((path/'batch-1.json').read_text(encoding='utf-8'))
    data['payload']['problem']['content']='tampered'
    (path/'batch-1.json').write_text(json.dumps(data),encoding='utf-8')
    llm=BatchLLM()
    with pytest.raises(ValueError,match='integrity'),writer_checkpoint(path,resume=True):
        WriterAgent(llm_client=llm).run(packet())
    assert llm.calls==[]


def test_checkpoint_lock_prevents_concurrent_writer(tmp_path):
    with writer_checkpoint(tmp_path/'cp'):
        with pytest.raises(FileExistsError),writer_checkpoint(tmp_path/'cp',resume=True):
            pass


def test_original_batch_not_overwritten(tmp_path):
    path=tmp_path/'cp'
    with writer_checkpoint(path):
        WriterAgent(llm_client=BatchLLM()).run(packet())
    before=(path/'batch-1.json').read_bytes()
    with pytest.raises(FileExistsError),writer_checkpoint(path):
        WriterAgent(llm_client=BatchLLM()).run(packet())
    assert (path/'batch-1.json').read_bytes()==before


def test_export_refuses_wrong_language_without_writing(tmp_path):
    state={'user_brief':{'output_language':'zh'},'proposal_draft':proposal('zh').model_dump()}
    with pytest.raises(ValueError,match='must be English'):
        export_node(state,output_dir=tmp_path)
    assert not list(tmp_path.glob('*.md'))


def test_resume_graph_completes_critic_revision_export_without_search(tmp_path):
    brief=_complete_brief()
    brief['output_language']='zh'
    run_id='offline-recovery'
    cp_root=tmp_path/'checkpoints'
    path=checkpoint_path(cp_root,run_id)
    from schemas.agent_outputs import WriterInput
    bound_packet=WriterInput.model_validate({**packet('en').model_dump(),'user_brief':brief})
    with pytest.raises(RuntimeError),writer_checkpoint(path):
        WriterAgent(llm_client=BatchLLM(fail_on=3,language='en')).run(bound_packet)
    state=bound_packet.model_dump()
    state.pop('output_language')
    state.update(user_brief=brief,run_id=run_id)
    def forbidden(*args,**kwargs):
        pytest.fail('Resume must not research again')
    writer=BatchLLM(language='en')
    critic=FakeJsonLLM(_critique().model_dump_json())
    revision=FakeJsonLLM(RevisedProposal(proposal=proposal('en'),
        applied_critique_summary=['Offline deterministic revision fixture.'],unresolved_issues=[]).model_dump_json())
    graph=build_multi_agent_workflow_graph(writer_llm=writer,critic_llm=critic,revision_llm=revision,
        web_search_tool=forbidden,evidence_provider=forbidden,resume_writer=True,
        writer_checkpoint_root=cp_root,output_dir=tmp_path/'output')
    with run_budget(max_requests=24,max_total_tokens=240000):
        result=graph.invoke(state)
    assert writer.calls==[3,4]
    assert len(critic.prompts)==1 and len(revision.prompts)==1
    assert Path(result['output_path']).exists()
    assert 'financial_assumptions' in result['proposal_draft']
    assert (path/'downstream-started.json').exists()
    from workflow.product_checkpoint import restore_checkpoint_budget
    with pytest.raises(ValueError,match='already entered Critic'):
        restore_checkpoint_budget(path)
    with run_budget(max_requests=24,max_total_tokens=240000):
        with pytest.raises(ValueError,match='already entered Critic'):
            graph.invoke(state)
    assert writer.calls==[3,4]
    assert len(critic.prompts)==1


def test_resume_requires_caller_budget(tmp_path):
    graph=build_multi_agent_workflow_graph(resume_writer=True,output_dir=tmp_path)
    with pytest.raises(ValueError,match='cumulative run budget'):
        graph.invoke({'user_brief':_complete_brief(),'run_id':'x'})


def test_historical_b_faults_rejected_without_changing_files():
    root=Path(__file__).resolve().parents[2]/'multiple_ai_agent/docs/comparisons/pet-trust-product-ab-20260911'
    state=json.loads((root/'B/state.json').read_text(encoding='utf-8'))
    allowed={s['source_id'] for s in state['web_sources']}|{s['source_id'] for s in state['evidence_chunks']}
    for number,model in zip(('006','007'),PROPOSAL_DRAFT_BATCH_MODELS):
        path=root/f'B/calls/{number}.response.json'
        before=path.read_bytes()
        response=json.loads(before)
        raw=''.join(p.get('text','') for p in response['candidates'][0]['content']['parts'] if not p.get('thought'))
        candidate=model.model_validate_json(raw)
        with pytest.raises(ValueError):
            validate_product_batch(candidate,language='zh',allowed=allowed)
        assert path.read_bytes()==before


def test_resume_does_not_reset_historical_tokens_or_requests(tmp_path):
    from workflow.product_checkpoint import restore_checkpoint_budget
    from workflow.run_budget import activate_run_budget
    path=tmp_path/'cp'
    with run_budget(max_requests=24,max_total_tokens=240000) as budget:
        budget.reserve_request()
        budget.record_usage(prompt_tokens=100,output_tokens=200,total_tokens=350)
        with writer_checkpoint(path):
            WriterAgent(llm_client=BatchLLM()).run(packet())
    with run_budget(max_requests=24,max_total_tokens=240000):
        with pytest.raises(ValueError,match='reset historical'),writer_checkpoint(path,resume=True):
            WriterAgent(llm_client=BatchLLM()).run(packet())
    restored=restore_checkpoint_budget(path)
    assert restored.snapshot()['request_count']==1
    assert restored.snapshot()['total_tokens']==350
    assert restored.snapshot()['max_total_tokens']==240000
    llm=BatchLLM()
    with activate_run_budget(restored),writer_checkpoint(path,resume=True):
        WriterAgent(llm_client=llm).run(packet())
    assert llm.calls==[]


@pytest.mark.parametrize('corrected',[True,False])
def test_production_adapter_corrects_batch_once_before_any_checkpoint(tmp_path,corrected):
    from test_llm_client import _client, _response
    from workflow.llm_client import StructuredJsonLLM, StructuredOutputValidationError
    def batch_payload(language,model):
        data=proposal(language).model_dump(mode='json')
        return {key:data[key] for key in model.model_fields}
    first=PROPOSAL_DRAFT_BATCH_MODELS[0]
    patch_payload=batch_payload('zh' if corrected else 'en',first)
    patch_payload.pop('title')  # All four narratives fail language, not the immutable title.
    responses=[_response(batch_payload('en',first)),_response(patch_payload)]
    if corrected:
        responses.extend(_response(batch_payload('zh',model)) for model in PROPOSAL_DRAFT_BATCH_MODELS[1:])
    client=_client(responses,max_prompt_chars=100000)
    adapter=StructuredJsonLLM(client,ProposalDraft)
    path=tmp_path/'cp'
    with run_budget(max_requests=12,max_total_tokens=240000) as budget,writer_checkpoint(path):
        if corrected:
            WriterAgent(llm_client=adapter).run(packet())
            assert len(list(path.glob('batch-*.json')))==4
        else:
            with pytest.raises(StructuredOutputValidationError,match='English narrative'):
                WriterAgent(llm_client=adapter).run(packet())
            assert not list(path.glob('batch-*.json'))
    assert len(client._client.models.calls)==(5 if corrected else 2)
    assert budget.snapshot()['retry_count']==1
    assert 'English narrative' in client._client.models.calls[1]['contents']


def test_legacy_explicit_downgrade_never_manufactures_a_source():
    from test_writer_agent import _proposal_with_missing_citations
    from agents.writer import downgrade_failed_writer_citations
    from rag.citation_checker import collect_proposal_citation_failures
    original=_proposal_with_missing_citations('problem')
    failures=collect_proposal_citation_failures(original,allowed_source_ids={'web-market-research','framework-unit-economics'})
    result=downgrade_failed_writer_citations(original,failures)
    assert result.problem.key_claims[0].evidence_status=='needs_validation'
    assert result.problem.key_claims[0].source_ids==[]
    assert result.problem.confidence=='low'
