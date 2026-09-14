"""Offline synthetic envelope check using the existing exact Granite tokenizer."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
from evaluation.s2_fixtures import SyntheticProvider
from workflow.contract_context import ContractContext
from workflow.review_config import ReviewRunConfig
from workflow.review_graph import build_review_workflow
from slm.granite_preflight import load_context_tokenizer
from slm.granite_provider import render_granite_pair
setup=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-v1/setup')
tokenizer=load_context_tokenizer(setup/'tokenizer.json',setup/'tokenizer_provenance.json')
results=[]
for case in ('ai_education','intelligent_ring'):
    ctx=ContractContext.from_case(ROOT/'runtime/docs/final_sprint/s0-v1',case,condition='D')
    provider=SyntheticProvider(ctx)
    config=ReviewRunConfig(condition='D',run_kind='debug',provider='mock',model_exact_id=provider.model_exact_id,
        model_config_version='synthetic-only-two-stage',max_requests=40,max_total_tokens=20_000_000,
        max_output_tokens=8192,max_prompt_chars=1_000_000,request_seconds=10)
    workflow=build_review_workflow(ctx,config=config,provider=provider,output_dir=ROOT/'validation'/('synthetic_envelope_v2_'+case))
    result=workflow.run()
    assert result['status']=='completed',result['error']
    calls=[]
    for req in provider.calls:
        messages=[dict(role='system',content=req.system_instruction),dict(role='user',content=req.prompt)]
        count=len(tokenizer.encode(render_granite_pair(messages),add_special_tokens=False).ids)
        calls.append(dict(stage=getattr(req.schema,'__generation_stage__','critic'),schema=req.schema.__name__,
            input_tokens=count,prompt_chars=len(req.prompt)+len(req.system_instruction),
            input_plus_output=count+8192,within_32k=count+8192<=32768,within_90k_chars=len(req.prompt)+len(req.system_instruction)<=90000))
    results.append(dict(case_id=case,synthetic=True,real_model_calls=0,calls=calls))
path=ROOT/'validation/prompt_envelope_v2.json'
path.write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps([dict(case_id=r['case_id'],calls=len(r['calls']),max_input_tokens=max(c['input_tokens'] for c in r['calls']),
    max_prompt_chars=max(c['prompt_chars'] for c in r['calls']),blocked=[c for c in r['calls'] if not c['within_32k'] or not c['within_90k_chars']]) for r in results],indent=2))

