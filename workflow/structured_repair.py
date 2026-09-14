"""Deterministic section metadata and bounded local structured-output repair."""
from copy import deepcopy
import json
from pydantic import ConfigDict, create_model


def canonical_payload(raw, schema):
    """Normalize program-owned titles and an exact section-name/category mix-up."""
    from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES
    data=json.loads(raw)
    titles=dict(zip(PROPOSAL_SECTION_FIELD_NAMES,PROPOSAL_SECTION_TITLES))
    claim_type_by_section={
        'executive_summary':'general','problem':'customer','target_customer':'customer',
        'market_opportunity':'market_size','solution':'product','value_proposition':'product',
        'competitor_analysis':'competitor','business_model':'operational',
        'go_to_market_strategy':'operational','financial_assumptions':'financial_benchmark',
        'risks_and_mitigations':'operational','implementation_roadmap':'operational','appendix':'general'}
    def apply_sections(payload, fields):
        if isinstance(payload,dict):
            for name in fields:
                if name in titles and isinstance(payload.get(name),dict):
                    payload[name]['title']=titles[name]
                    for claim in payload[name].get('key_claims',[]):
                        # Models sometimes copy a proposal section field into the
                        # claim_type enum. Normalize only that exact, unambiguous
                        # metadata error; never rewrite arbitrary invalid values.
                        if (isinstance(claim,dict)
                                and claim.get('claim_type') in PROPOSAL_SECTION_FIELD_NAMES):
                            claim['claim_type']=claim_type_by_section[name]
    # Scope to the actual proposal schema, not arbitrary user JSON with a
    # coincidentally named field. Other required/malformed fields remain strict.
    name=schema.__name__
    if name.startswith(('ProposalDraft','RevisedProposalBatch','LocalRepair_')):
        apply_sections(data,schema.model_fields)
    elif name=='RevisedProposal' and isinstance(data,dict):
        apply_sections(data.get('proposal'),titles)
    return data


def local_repair_spec(schema, raw, error, output_validator=None):
    """Return a subset schema only when errors identify existing section fields."""
    from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES
    if not schema.__name__.startswith(('ProposalDraftBatch','RevisedProposalBatch')):
        return None
    try:
        payload=canonical_payload(raw,schema)
    except (ValueError,TypeError):
        return None
    if not isinstance(payload,dict) or set(payload)!=set(schema.model_fields):
        return None
    fields=set()
    current=error
    for _ in range(5):
        fields.update(getattr(current,'sections',()))
        errors=getattr(current,'errors',None)
        if callable(errors):
            for item in errors():
                location=item.get('loc',())
                if not location or location[0] not in PROPOSAL_SECTION_FIELD_NAMES:
                    return None
                fields.add(location[0])
        current=getattr(current,'__cause__',None)
        if current is None: break
    if not fields or not fields.issubset(set(schema.model_fields)&set(PROPOSAL_SECTION_FIELD_NAMES)):
        return None
    diagnostics={}
    diagnose=getattr(output_validator,'diagnose_sections',None)
    if callable(diagnose):
        diagnostics=diagnose(schema,payload)
        if not set(diagnostics).issubset(set(schema.model_fields)&set(PROPOSAL_SECTION_FIELD_NAMES)):
            return None
        fields.update(diagnostics)
    elif output_validator is not None:
        # With an opaque validator, schema errors can hide semantic defects in
        # any section. Fall back to the existing full-object correction safely.
        try: schema.model_validate(deepcopy(payload))
        except ValueError: return None
    definitions={key:(schema.model_fields[key].annotation,deepcopy(schema.model_fields[key])) for key in sorted(fields)}
    patch_schema=create_model('LocalRepair_'+schema.__name__,__config__=ConfigDict(extra='forbid'),**definitions)
    return payload,patch_schema,fields,diagnostics
