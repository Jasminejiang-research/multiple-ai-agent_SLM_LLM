"""Product output-language and citation policy; no fabricated source repairs."""
from __future__ import annotations
import re
from typing import Any

POLICY_VERSION = 'product-language-citations-v5-always-english'


class OutputLanguageContractError(ValueError):
    """Hard product contract: exported A/B narrative must be English."""


class ProductBatchValidationError(ValueError):
    def __init__(self, section, message):
        self.sections=(section,) if isinstance(section,str) else tuple(section)
        super().__init__(f'{section}: {message}')


def resolve_output_language(brief: dict[str, Any]) -> str:
    """Return the system-owned product language, ignoring untrusted user hints."""
    return 'en'


def language_instruction(language: str) -> str:
    if language == 'auto':
        return ''
    name = {'zh':'Simplified Chinese','en':'English'}[language]
    return (f'\n\n# Required Output Language\nAll narrative section content and claim text must be in {name}. '
            'This overrides examples or default language elsewhere. Preserve schema field names, '
            'fixed section titles, source IDs, URLs and proper names. Do not switch languages between batches.')


def validate_text_language(text: str, language: str) -> None:
    if language == 'auto':
        return
    cleaned = re.sub(r'\[[^\]]*\]|https?://\S+', '', text)
    for paragraph in re.split(r'\n\s*\n', cleaned):
        chinese = len(re.findall(r'[\u4e00-\u9fff]',paragraph))
        latin = len(re.findall(r'[A-Za-z]',paragraph))
        if language == 'zh' and latin >= 40 and chinese/max(1,latin+chinese) < 0.15:
            raise OutputLanguageContractError(
                'output_language=zh: English narrative detected; rewrite in Chinese without changing source IDs')
        if language == 'en' and chinese >= 4 and chinese/max(1,latin+chinese) > 0.05:
            raise OutputLanguageContractError('Product output must be English: non-English narrative detected')


def validate_english_document(text: str) -> None:
    """Strict final-output gate, including deterministic headings and tables."""
    cleaned = re.sub(r'https?://\S+', '', text)
    if re.search(r'[\u4e00-\u9fff]', cleaned):
        raise OutputLanguageContractError('Product output must be English: final document contains Han characters')


def normalize_markers(text: str, allowed: set[str]) -> str:
    """Expand grouped *known* IDs only; never guess a typo or add evidence."""
    def replace(match):
        ids = [s.strip() for s in match.group(1).split(',')]
        if len(ids)>1 and all(s in allowed for s in ids):
            return ' '.join(f'[{s}]' for s in ids)
        return match.group(0)
    return re.sub(r'\[([^\[\]\n]+)\]',replace,text)


def _validate_product_batch(candidate, *, language: str, allowed: set[str], citations=True, source_roles=None,only_section=None):
    """Normalize harmless syntax and reject errors before persisting a batch."""
    from rag.citation_checker import check_citations
    if only_section is None and isinstance(getattr(candidate, 'title', None), str):
        try:
            validate_text_language(candidate.title, language)
        except OutputLanguageContractError as exc:
            raise ProductBatchValidationError('title', str(exc)) from exc
    for name in type(candidate).model_fields:
        if only_section is not None and name != only_section:
            continue
        section = getattr(candidate,name)
        if not hasattr(section,'content') or not hasattr(section,'key_claims'):
            continue
        section.content = normalize_markers(section.content,allowed)
        try:
            validate_text_language(section.content,language)
            from workflow.product_research import validate_certainty
            validate_certainty(section.content)
        except ValueError as exc:
            raise ProductBatchValidationError(name,str(exc)) from exc
        referenced=set(section.source_ids)
        texts=[section.content]
        for claim in section.key_claims:
            claim.text=normalize_markers(claim.text,allowed)
            claim.content_anchor=normalize_markers(claim.content_anchor,allowed)
            try:
                validate_text_language(claim.text,language)
            except ValueError as exc:
                raise ProductBatchValidationError(name,str(exc)) from exc
            if citations and source_roles is not None and claim.evidence_status=='sourced_fact':
                for source_id in claim.source_ids:
                    role=source_roles.get(source_id,'unverified')
                    if role=='unverified' or (role=='framework' and claim.claim_type!='general'):
                        raise ProductBatchValidationError(name,
                            f'{source_id} is {role}, not verified local evidence for {claim.claim_type}; '
                            'set evidence_status="needs_validation", clear claim.source_ids, and qualify the prose; '
                            'do not change claim_type to an evidence status')
            referenced.update(claim.source_ids)
            texts.extend((claim.text,claim.content_anchor))
        for text in texts:
            referenced.update(re.findall(r'\b(?:web-[A-Za-z0-9-]+|source_[A-Za-z0-9_]+)',text))
        if not citations:
            continue
        unknown=sorted(referenced-allowed)
        if unknown:
            raise ProductBatchValidationError(name,f'unknown source IDs {unknown}; use exact provided IDs only; '
                             'if evidence does not support the claim set evidence_status="needs_validation" '
                             'and clear claim.source_ids; never guess a replacement or change claim_type to an evidence status')
        failures=[check.claim_index for check in check_citations(section).checks if not check.has_source]
        if failures:
            raise ProductBatchValidationError(name,f'sourced_fact claims {failures} need each exact [source_id] '
                             'in both the anchored content and claim text; otherwise set evidence_status="needs_validation", '
                             'clear claim.source_ids, qualify the prose and retain a valid claim_type')
    return candidate


def validate_product_batch(candidate, *, language: str, allowed: set[str], citations=True, source_roles=None):
    failures=[]
    if isinstance(getattr(candidate, 'title', None), str):
        try:
            validate_text_language(candidate.title, language)
        except OutputLanguageContractError as exc:
            failures.append(ProductBatchValidationError('title', str(exc)))
    for name in type(candidate).model_fields:
        try:
            _validate_product_batch(candidate,language=language,allowed=allowed,citations=citations,
                                    source_roles=source_roles,only_section=name)
        except ProductBatchValidationError as exc:
            failures.append(exc)
    if failures:
        raise ProductBatchValidationError([s for error in failures for s in error.sections],
                                         '\n'.join(str(error) for error in failures))
    return candidate


def product_batch_validator(*,language,allowed,source_roles=None,financial_model=None):
    """One full validator plus a safe, explicit partial-diagnostics protocol.

    Each diagnostic object is strictly parsed with its real field schema. No
    invalid full model is constructed and partial output can never be exported.
    """
    from copy import deepcopy
    from pydantic import ConfigDict, create_model
    from workflow.product_finance import validate_financial_prose
    from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES

    def validate(candidate):
        errors=[]
        for check in (lambda:validate_product_batch(candidate,language=language,allowed=allowed,
                                                    source_roles=source_roles),
                      lambda:validate_financial_prose(candidate,financial_model)):
            try: check()
            except ValueError as exc: errors.append(exc)
        if errors:
            fields=set()
            for exc in errors:
                fields.update(getattr(exc,'sections',type(candidate).model_fields))
            raise ProductBatchValidationError(sorted(fields),'\n'.join(map(str,errors)))
        return candidate

    def diagnose(schema,payload):
        failures={}
        for name,field in schema.model_fields.items():
            if name not in PROPOSAL_SECTION_FIELD_NAMES: continue
            section_schema=create_model('DiagnosticSection',__config__=ConfigDict(extra='forbid'),
                **{name:(field.annotation,deepcopy(field))})
            try:
                section=section_schema.model_validate({name:payload[name]} if name in payload else {})
                validate(section)
            except ValueError as exc:
                failures[name]=str(exc)
        return failures

    validate.diagnose_sections=diagnose
    return validate
