"""Actual native request construction uses the shared case-specific schema."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from evaluation.s2_fixtures import synthetic_artifact
from schemas.contract_outputs import ContractResearchAnalysis
from slm.granite_config import GraniteConfig
from slm.granite_provider import GranitePhysicalProvider
from workflow.contract_context import ContractContext
from workflow.generation_constraints import bounded_response_model
from workflow.review_runtime import PhysicalRequest

ROOT = Path(__file__).resolve().parents[2]


def test_native_payload_has_case_derived_enum_limit_and_cpu_mode():
    ctx = ContractContext.from_case(ROOT/'docs/final_sprint/s0-v1','ai_education',condition='D')
    model = bounded_response_model(ContractResearchAnalysis, ctx.finance.value_ids)
    calls = []
    data = synthetic_artifact(ctx,'research',version=1,inputs={})
    def post(url, **kwargs):
        calls.append(kwargs['json'])
        return SimpleNamespace(status_code=200, json=lambda:dict(model='granite-h-micro-32k',done=True,done_reason='stop',message={'content':json.dumps(data)},prompt_eval_count=1,eval_count=1))
    session = SimpleNamespace(mount=lambda *a:None, post=post)
    config = GraniteConfig.model_validate_json((ROOT/'slm/configs/granite_preflight_cpu_v2.json').read_text())
    provider = GranitePhysicalProvider(config,model_digest='offline',session=session)
    response = provider.invoke(PhysicalRequest('prompt',model,'system',0,8192,10))
    body = calls[0]
    field = body['format']['$defs']['GroundedClaim']['properties']['financial_value_ids']
    assert field['maxItems'] == len(ctx.finance.value_ids)
    assert field['items']['enum'] == sorted(ctx.finance.value_ids)
    assert body['options']['num_gpu'] == 0 and body['options']['num_predict'] == 8192
    assert model.model_validate_json(response.text)


def test_duplicate_references_still_fail_when_native_engine_returns_them():
    ctx = ContractContext.from_case(ROOT/'docs/final_sprint/s0-v1','ai_education',condition='D')
    model = bounded_response_model(ContractResearchAnalysis, ctx.finance.value_ids)
    data = synthetic_artifact(ctx,'research',version=1,inputs={})
    data['market_trends'][0]['claims'][0]['financial_value_ids'] = ['months','months']
    with pytest.raises(ValidationError,match='unique IDs'):
        model.model_validate_json(json.dumps(data))
