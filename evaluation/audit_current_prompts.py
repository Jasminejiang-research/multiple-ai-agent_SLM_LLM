"""Read-only audit of current prompt surfaces using frozen AI-education fixtures."""
from __future__ import annotations
import json, re, sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO))
from pydantic import BaseModel
from agents.component_critic import ComponentCritic
from evaluation.s2_fixtures import request_payload, synthetic_artifact, synthetic_report
from evaluation.two_stage_fixtures import synthetic_stage_payload
from schemas.review import ComponentCritiqueReport
from workflow.contract_context import ContractContext, ROLE_SCHEMAS
from workflow.contract_generation import ContractGenerator, COMMON_INSTRUCTION, ROLE_INSTRUCTION, PROMPT_VERSION
from workflow.gemini_schema import relaxed_response_schema
from workflow.research_profile import RESEARCH_INSTRUCTION
from workflow.two_stage_generation import BODY_INSTRUCTION
from schemas.evidence import canonical_hash


class Capture:
    def __init__(self,ctx): self.ctx,self.calls=ctx,[]
    def generate_structured_once(self,prompt,schema,**kwargs):
        self.calls.append(dict(prompt=prompt,system=kwargs.get('system_instruction') or '',schema=schema))
        inputs=request_payload(prompt)
        if issubclass(schema,ComponentCritiqueReport):
            data=synthetic_report(inputs['review_role'],score=3)
        else:
            canonical=getattr(schema,'__canonical_schema__',schema)
            role=next((r for r in ('research','strategy','finance') if issubclass(canonical,ROLE_SCHEMAS[r])),
                      'writer')
            data=synthetic_artifact(self.ctx,role,version=1,inputs=inputs)
            data=synthetic_stage_payload(schema,data)
        return schema.model_validate(data)


def count(text):
    return dict(characters=len(text),utf8_bytes=len(text.encode()),whitespace_words=len(re.findall(r'\S+',text)))


def collect(condition):
    ctx=ContractContext.from_case(REPO/'docs/final_sprint/s0-v1','ai_education',condition=condition)
    client=Capture(ctx); gen=ContractGenerator(client); critic=ComponentCritic(gen)
    artifacts={}
    artifacts['research']=gen.generate(ctx,'research')
    critic.review(ctx,artifacts['research'],role='research',artifact_id='research.initial')
    artifacts['strategy']=gen.generate(ctx,'strategy',upstream=(artifacts['research'],))
    critic.review(ctx,artifacts['strategy'],role='strategy',artifact_id='strategy.initial')
    artifacts['finance']=gen.generate(ctx,'finance',upstream=(artifacts['research'],artifacts['strategy']))
    critic.review(ctx,artifacts['finance'],role='finance',artifact_id='finance.initial')
    artifacts['writer']=gen.generate(ctx,'writer',upstream=(artifacts['research'],artifacts['strategy'],artifacts['finance']))
    critic.review(ctx,artifacts['writer'],role='final',artifact_id='writer.initial')
    output=[]
    for call in client.calls:
        prompt=call['prompt']; schema=call['schema']; stage=getattr(schema,'__generation_stage__','single')
        payload=request_payload(prompt)
        if issubclass(schema,ComponentCritiqueReport): role=payload['review_role']+'_critic'
        else:
            canonical=getattr(schema,'__canonical_schema__',schema)
            role=next((r for r in ('research','strategy','finance') if issubclass(canonical,ROLE_SCHEMAS[r])),'writer')
        output.append(dict(role=role,stage=stage,batch=payload.get('batch_number'),prompt=count(prompt),system=count(call['system']),
            request_text_hash=canonical_hash(dict(prompt=prompt,system_instruction=call['system'])),
            native_schema_characters=len(json.dumps(schema.model_json_schema(),ensure_ascii=False,separators=(',',':'))),
            gemini_schema_characters=len(json.dumps(relaxed_response_schema(schema),ensure_ascii=False,separators=(',',':')))))
    return output


result=dict(prompt_version=PROMPT_VERSION, fixed=dict(common_system=count(COMMON_INSTRUCTION),
    role_instructions={k:count(v) for k,v in ROLE_INSTRUCTION.items()},research_addendum=count(RESEARCH_INSTRUCTION),
    body_stage=count(BODY_INSTRUCTION)),C_gemini=collect('C'),D_slm=collect('D'))
print(json.dumps(result,ensure_ascii=False,indent=2))
