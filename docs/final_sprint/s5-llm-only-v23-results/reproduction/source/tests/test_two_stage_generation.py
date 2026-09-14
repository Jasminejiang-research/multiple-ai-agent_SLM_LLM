"""Protocol invariants independent of real model success or human scoring."""
from copy import deepcopy
import json
from pathlib import Path
import pytest

from evaluation.s2_fixtures import synthetic_artifact
from evaluation.two_stage_fixtures import synthetic_stage_payload
from schemas.contract_outputs import ContractResearchAnalysis, ContractFinanceAssumptions
from schemas.evidence import canonical_hash
from workflow.contract_context import ContractContext
from workflow.contract_generation import ContractGenerator
from workflow.llm_client import StructuredOutputValidationError
from workflow.two_stage_generation import SelectionPlan, draft_model, project_body

ROOT = Path(__file__).resolve().parents[1]/'docs/final_sprint/s0-v1'

@pytest.fixture
def ctx(): return ContractContext.from_case(ROOT,'ai_education',condition='D')

def make_plan(ctx, role='research'):
    model = ContractResearchAnalysis if role == 'research' else ContractFinanceAssumptions
    data = synthetic_artifact(ctx,role,version=1,inputs={})
    plan = SelectionPlan(model,project_body(model,data),ctx)
    return plan, synthetic_stage_payload(plan.schema,data)

def test_stage_one_is_internal_only(ctx):
    plan, selections = make_plan(ctx)
    with pytest.raises(ValueError): ctx.accept('research',plan.body)
    model, mapping = plan.assemble(selections)
    ctx.validate(model,version=1)
    assert project_body(plan.canonical,model.model_dump(mode='json')) == plan.body
    assert len(mapping) == 3
    for m in mapping:
        span=m['body_span']
        value=plan.body
        for key in span['path']: value=value[key]
        assert value[span['start']:span['end']] == span['text']

@pytest.mark.parametrize('mutation',['other_parent','unknown_body','unknown_source','duplicate_source','missing_group','extra_prose','score','repeat_finance'])
def test_selection_rejects_wrong_paths_and_metadata(ctx,mutation):
    plan, data=make_plan(ctx)
    claim=data['g1']['claims'][0]
    if mutation=='other_parent': claim['body_span_id']=data['g2']['claims'][0]['body_span_id']
    if mutation=='unknown_body': claim['body_span_id']='invented'
    if mutation=='unknown_source': claim['evidence_span_ids']=['invented']
    if mutation=='duplicate_source': claim['evidence_span_ids']*=2
    if mutation=='missing_group': del data['g2']
    if mutation=='extra_prose': data['g1']['finding']='Rewritten prose'
    if mutation=='score': claim['source_quality']=3
    if mutation=='repeat_finance': claim['financial_value_ids']=['months','months']
    with pytest.raises(ValueError): plan.assemble(data)

@pytest.mark.parametrize('mutation',['body','body_span','source_quote','source_lines','source_hash','groups'])
def test_mutating_frozen_catalog_is_detected(ctx,mutation):
    plan,data=make_plan(ctx)
    if mutation=='body': plan.body['market_trends'][0]['finding']+='changed'
    if mutation=='body_span': next(iter(plan.body_spans.values()))['end']=999999
    if mutation=='source_quote': next(iter(plan.evidence_spans.values()))['quote']='fabrication'
    if mutation=='source_lines': next(iter(plan.evidence_spans.values()))['line_start']=-1
    if mutation=='source_hash': next(iter(plan.evidence_spans.values()))['snapshot_sha256']='0'*64
    if mutation=='groups': plan.groups['g1']['path']=['customer_notes',0,'claims']
    with pytest.raises(ValueError,match='modified'): plan.assemble(data)

def test_cross_case_selection_cannot_be_reused(ctx):
    first, selections=make_plan(ctx)
    other=ContractContext.from_case(ROOT,'intelligent_ring',condition='D')
    second,_=make_plan(other)
    with pytest.raises(ValueError): second.assemble(selections)
    first.context=other
    with pytest.raises(ValueError,match='Cross-case'): first.assemble(selections)

def test_financial_values_are_model_body_and_cannot_be_edited_in_stage_two(ctx):
    plan,data=make_plan(ctx,'finance')
    body=deepcopy(plan.body)
    candidate,_=plan.assemble(data)
    assert candidate.model_dump(mode='json')['financial_values']==body['financial_values']
    ctx.finance.validate(candidate.financial_values)
    data['financial_values']=[]
    with pytest.raises(ValueError): plan.assemble(data)

class Client:
    def __init__(self,ctx,failures=()): self.ctx,self.failures,self.calls=ctx,set(failures),[]
    def generate_structured_once(self,prompt,schema,**kwargs):
        self.calls.append((prompt,schema))
        if len(self.calls) in self.failures:
            raise StructuredOutputValidationError('Synthetic malformed JSON',raw_output='{broken')
        data=synthetic_artifact(self.ctx,'research',version=1,inputs={})
        return schema.model_validate(synthetic_stage_payload(schema,data))

@pytest.mark.parametrize('failures,passed,stages',[
    ((),True,['body','grounding']), ((1,),True,['body','body','grounding']),
    ((2,),True,['body','grounding','grounding']), ((1,3),False,['body','body','grounding']),
    ((2,3),False,['body','grounding','grounding']), ((1,2),False,['body','body'])])
def test_both_stages_share_one_repair(ctx,failures,passed,stages):
    client=Client(ctx,failures)
    records=[]
    generator=ContractGenerator(client,task_sink=records.append)
    if passed: generator.generate(ctx,'research')
    else:
        with pytest.raises(StructuredOutputValidationError): generator.generate(ctx,'research')
    task=generator.tasks[0]
    assert [s.__generation_stage__ for _,s in client.calls]==stages
    assert sum(a.purpose=='structure_repair' for a in task.attempts)<=1
    assert task.completed is passed
    assert task.first_output_passed is (passed and not failures)
    assert all(not r['first_output_passed'] for r in records if not r['completed'])
    if passed:
        assert task.assembly_mapping and task.assembled_sha256
        assert task.frozen_draft and task.selection_catalog
        assert canonical_hash(task.frozen_draft)==task.selection_catalog['body_sha256']

def test_actual_stage_schemas_have_closed_selection_ids(ctx):
    plan,_=make_plan(ctx)
    raw=json.dumps(plan.schema.model_json_schema())
    assert 'content_anchor' not in raw and 'source_anchors' not in raw
    assert next(iter(plan.body_spans)) in raw and next(iter(plan.evidence_spans)) in raw
    assert '"additionalProperties": false' in raw

def test_compact_source_positions_reconstruct_every_original_candidate(ctx):
    plan,_=make_plan(ctx)
    display=json.loads(plan.prompt().split('FROZEN_DRAFT_AND_SELECTIONS:\n',1)[1])['catalog']
    chunks={c.chunk_id:c for c in ctx.packet.chunks}
    for key,span in display['evidence_spans'].items():
        chunk=chunks[span['chunk_id']]
        lines='\n'.join(chunk.text.splitlines()[span['line_start']-chunk.line_start:span['line_end']-chunk.line_start+1])
        assert lines[span['quote_start']:span['quote_end']] == plan.evidence_spans[key]['quote']

def test_unknown_evidence_choice_is_fatal_without_repair(ctx):
    from workflow.grounding import CitationPollutionError
    class Polluted(Client):
        def generate_structured_once(self,prompt,schema,**kwargs):
            if schema.__generation_stage__ == 'grounding':
                self.calls.append((prompt,schema))
                data=synthetic_stage_payload(schema,synthetic_artifact(ctx,'research',version=1,inputs={}))
                data['g1']['claims'][0]['evidence_span_ids']=['invented']
                raise StructuredOutputValidationError('Wire schema rejected',raw_output=json.dumps(data))
            return super().generate_structured_once(prompt,schema,**kwargs)
    client=Polluted(ctx)
    generator=ContractGenerator(client)
    with pytest.raises(CitationPollutionError): generator.generate(ctx,'research')
    assert len(client.calls)==2
    assert generator.tasks[0].attempts[-1].error_type=='CitationPollutionError'

def test_selection_transport_failure_does_not_become_first_pass(tmp_path):
    from tests.test_s2_review import setup_run
    from workflow.review_runtime import ProviderFailure
    failed=[]
    def fail(req,index):
        if getattr(req.schema,'__generation_stage__',None)=='grounding' and not failed:
            failed.append(True)
            raise ProviderFailure('Synthetic503',retryable=True,request_finished=True)
    workflow,_=setup_run(tmp_path,before=fail,overrides={'transport_retries':1})
    result=workflow.run()
    assert result['status']=='completed'
    assert not workflow.generator.tasks[0].first_output_passed
    assert result['budget']['transport_retry_count']==1
    assert result['budget']['structure_repair_request_count']==0

@pytest.mark.parametrize('case_id',['ai_education','intelligent_ring'])
def test_gemini_stage_schemas_prepare_locally_without_calls(case_id):
    from workflow.contract_context import ROLE_SCHEMAS
    from workflow.generation_batches import CONTRACT_BATCH_MODELS
    from workflow.gemini_schema import relaxed_response_schema
    from workflow.generation_constraints import bounded_response_model
    from google.genai.types import Schema
    ctx=ContractContext.from_case(ROOT,case_id,condition='C')
    for role,model in [('research',ROLE_SCHEMAS['research']),('strategy',ROLE_SCHEMAS['strategy']),
                       ('finance',ROLE_SCHEMAS['finance']), *[('writer',m) for m in CONTRACT_BATCH_MODELS]]:
        data=synthetic_artifact(ctx,role,version=1,inputs={})
        plan=SelectionPlan(model,project_body(model,data),ctx)
        for schema in (draft_model(model),plan.schema):
            bounded=bounded_response_model(schema,ctx.finance.value_ids,packet=ctx.packet)
            Schema.model_validate(relaxed_response_schema(bounded))
