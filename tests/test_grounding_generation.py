import json
from copy import deepcopy
from pathlib import Path

import pytest

from evaluation.s2_fixtures import synthetic_artifact
from schemas.contract_outputs import ContractResearchAnalysis
from workflow.contract_context import ContractContext
from workflow.generation_constraints import bounded_response_model, repair_feedback
from workflow.grounding_generation import grounding_issues, grounding_reference_contract
from workflow.gemini_schema import relaxed_response_schema

ROOT = Path(__file__).resolve().parents[1] / 'docs/final_sprint/s0-v1'


def context(case='ai_education',condition='D'):
    return ContractContext.from_case(ROOT,case,condition=condition)


@pytest.mark.parametrize('case',['ai_education','intelligent_ring'])
def test_frozen_native_reference_closures_are_exact_and_do_not_modify_base(case):
    ctx=context(case)
    original=deepcopy(ContractResearchAnalysis.model_json_schema())
    model=bounded_response_model(ContractResearchAnalysis,ctx.finance.value_ids,packet=ctx.packet)
    schema=model.model_json_schema()
    assert set(schema['$defs']['GroundedClaim']['properties']['source_ids']['items']['enum'])==set(ctx.packet.allowlist_source_ids)
    props=schema['$defs']['SourceAnchor']['properties']
    assert set(props['source_id']['enum'])==set(ctx.packet.allowlist_source_ids)
    assert set(props['chunk_id']['enum'])=={c.chunk_id for c in ctx.packet.chunks}
    assert set(props['snapshot_sha256']['enum'])=={s.txt_sha256 for s in ctx.packet.sources}
    assert ContractResearchAnalysis.model_json_schema()==original
    data=synthetic_artifact(ctx,'research',version=1,inputs={})
    ctx.validate(model.model_validate(data),version=1)
    relaxed_response_schema(model)


def test_content_anchor_feedback_uses_actual_parent_prose_not_own_claim_text():
    ctx=context()
    raw={'market_trends':[{'finding':'Demand requires validation.','rationale':'No pilot data.',
        'claims':[{'claim_text':'Elsewhere','content_anchor':'Elsewhere','source_ids':[]}]}]}
    original=deepcopy(raw)
    issues=grounding_issues(json.dumps(raw),ctx.packet)
    assert issues[0]['path']=='$.market_trends[0].claims[0].content_anchor'
    assert issues[0]['legal_exact_example']=='Demand requires validation.'
    assert raw==original
    raw['market_trends'][0]['claims'][0]['content_anchor']='Demand requires validation.'
    assert grounding_issues(json.dumps(raw),ctx.packet)==[]


def test_schema_failure_feedback_also_includes_hidden_grounding_errors():
    ctx=context()
    data=synthetic_artifact(ctx,'research',version=1,inputs={})
    claim=data['market_trends'][0]['claims'][0]
    claim['financial_value_ids']=['months','months']
    claim['content_anchor']='not in parent'
    claim['source_ids']=['packet']
    feedback=json.loads(repair_feedback(ValueError('schema failed'),json.dumps(data),ctx.finance.value_ids,packet=ctx.packet))
    paths={item['path'] for item in feedback['violations']}
    assert '$.market_trends[0].claims[0].financial_value_ids' in paths
    assert '$.market_trends[0].claims[0].content_anchor' in paths
    assert '$.market_trends[0].claims[0].source_ids' in paths


def test_source_quote_diagnostics_respect_exact_frozen_location():
    ctx=context()
    chunk=ctx.packet.chunks[0]
    source=next(s for s in ctx.packet.sources if s.source_id==chunk.source_id)
    anchor=dict(source_id=chunk.source_id,chunk_id=chunk.chunk_id,snapshot_sha256=source.txt_sha256,
        line_start=chunk.line_start,line_end=chunk.line_end,quote='invented quote')
    issues=grounding_issues(json.dumps(anchor),ctx.packet)
    assert issues[0]['path']=='$.quote'
    anchor['quote']=chunk.text.splitlines()[0]
    assert grounding_issues(json.dumps(anchor),ctx.packet)==[]


def test_all_conditions_share_same_grounding_schema_and_exact_anchor_examples():
    contexts=[context(condition=condition) for condition in 'ABCD']
    prompts=[grounding_reference_contract(ctx.packet) for ctx in contexts]
    assert len(set(prompts))==1
    models=[bounded_response_model(ContractResearchAnalysis,ctx.finance.value_ids,packet=ctx.packet).model_json_schema() for ctx in contexts]
    assert all(schema==models[0] for schema in models)
    examples=json.loads(prompts[0].split('\n')[-1])
    for example in examples:
        assert grounding_issues(json.dumps(example),contexts[0].packet)==[]
    assert grounding_issues('{"incomplete":',contexts[0].packet)==[]
