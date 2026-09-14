"""Offline regression for the system-owned English product-output contract."""
import pytest

from workflow.product_acceptance import acceptance_notice, acceptance_scope, accept_semantic_error, quality_check
from workflow.product_output_policy import (OutputLanguageContractError,
    language_instruction, resolve_output_language, validate_english_document, validate_text_language)
from workflow.llm_client import StructuredOutputValidationError


@pytest.mark.parametrize('brief', [
    {},
    {'output_language': 'zh-CN'},
    {'proposal_goal': '请生成中文商业计划书'},
    {'output_language': 'auto'},
    {'output_language': 'Klingon'},
])
def test_every_product_brief_resolves_to_english(brief):
    assert resolve_output_language(brief) == 'en'


def test_instruction_explicitly_overrides_user_language_requests():
    instruction = language_instruction(resolve_output_language({'output_language': 'zh'}))
    assert 'must be in English' in instruction
    assert 'overrides examples or default language elsewhere' in instruction


def test_non_english_product_narrative_is_a_hard_error():
    with pytest.raises(OutputLanguageContractError, match='must be English'):
        validate_text_language('这是一个完整的中文商业计划内容，不能作为英文产品输出。', 'en')


def test_language_error_cannot_be_accepted_or_downgraded():
    cause = OutputLanguageContractError('Product output must be English')
    wrapped = StructuredOutputValidationError('invalid output')
    wrapped.__cause__ = cause
    with acceptance_scope(stage='writer'):
        with pytest.raises(StructuredOutputValidationError):
            accept_semantic_error(wrapped, fallback='wrong-language output')
        with pytest.raises(OutputLanguageContractError):
            quality_check(validate_text_language, '这是中文产品输出，不能被接受。', 'en')


def test_acceptance_notice_is_english_only():
    notice = acceptance_notice({'status':'accepted_with_issues','corrections':{'writer':1},
        'unresolved_issues':[{'stage':'writer','message':'A claim still needs validation.'}]})
    validate_text_language(notice, 'en')
    assert 'Formal Output and Unresolved Issues' in notice


def test_deterministic_finance_renderer_and_final_gate_are_english():
    from workflow.product_finance import render_ledger
    from test_product_reliability_v3 import model
    rendered = render_ledger(model())
    validate_english_document(rendered)
    assert 'Financial Assumptions and Deterministic Calculations' in rendered
    with pytest.raises(OutputLanguageContractError, match='final document'):
        validate_english_document(rendered + '\n这是中文。')


def test_writer_section_name_claim_type_is_normalized_without_an_llm_retry():
    import json
    from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
    from workflow.structured_repair import canonical_payload
    from test_product_output_recovery import proposal
    schema = PROPOSAL_DRAFT_BATCH_MODELS[2]
    raw = {key:value for key,value in proposal('en').model_dump().items() if key in schema.model_fields}
    claim = {'text':'An unverified commercial-model hypothesis.', 'claim_type':'business_model',
        'evidence_status':'assumption','source_ids':[],
        'content_anchor':'An unverified commercial-model hypothesis.'}
    raw['business_model']['key_claims']=[claim]
    raw['financial_assumptions']['key_claims']=[dict(claim)]
    normalized = canonical_payload(json.dumps(raw), schema)
    candidate = schema.model_validate(normalized)
    assert candidate.business_model.key_claims[0].claim_type == 'operational'
    assert candidate.financial_assumptions.key_claims[0].claim_type == 'financial_benchmark'


def test_unrelated_invalid_claim_type_stays_strict():
    import json
    from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
    from workflow.structured_repair import canonical_payload
    from test_product_output_recovery import proposal
    schema = PROPOSAL_DRAFT_BATCH_MODELS[2]
    raw = {key:value for key,value in proposal('en').model_dump().items() if key in schema.model_fields}
    raw['business_model']['key_claims']=[{'text':'Test claim.','claim_type':'invented_enum',
        'evidence_status':'assumption','source_ids':[],'content_anchor':'Test claim.'}]
    with pytest.raises(ValueError):
        schema.model_validate(canonical_payload(json.dumps(raw), schema))
