"""Separate B's formal business narrative from machine-readable audit metadata."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re

AUDIT_VERSION='b-product-audit-v1'
_SOURCE_ID=r'(?:web-[A-Za-z0-9-]+|source_[A-Za-z0-9_]+)'
_SOURCE_GROUP=re.compile(r'\[(?:'+_SOURCE_ID+r')(?:\s*,\s*'+_SOURCE_ID+r')*\]')
_STATUS=re.compile(r'\*{0,2}\[(?:NEEDS_VALIDATION|UNSUPPORTED|ASSUMPTION|SOURCED_FACT)\]\*{0,2}',re.I)
_CONFIDENCE_LINE=re.compile(r'(?mi)^\s*\*{0,2}Confidence:\*{0,2}\s*(?:low|medium|high)\s*$\n?')
_FINANCE_TOKEN=re.compile(r'\{\{fin:[^{}]+\}\}')


def clean_business_content(text: str) -> str:
    """Remove audit/evidence transport markers without deleting business prose."""
    text=_CONFIDENCE_LINE.sub('',text)
    text=_STATUS.sub('',text)
    text=_SOURCE_GROUP.sub('',text)
    text=re.sub(_SOURCE_ID,'',text)
    text=_FINANCE_TOKEN.sub('needs validation',text)
    text=re.sub(r'\[\s*\]','',text)
    text=re.sub(r'[ \t]+(?=[,.;:])','',text)
    text=re.sub(r'[ \t]{2,}',' ',text)
    text=re.sub(r'\n[ \t]+\n','\n\n',text)
    return text.strip()


def render_formal_b_proposal(proposal) -> str:
    """Render title plus all 13 business sections; omit all audit fields."""
    from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES, PROPOSAL_SECTION_TITLES
    lines=[f'# {clean_business_content(proposal.title)}','']
    for field_name, fixed_title in zip(PROPOSAL_SECTION_FIELD_NAMES,PROPOSAL_SECTION_TITLES,strict=True):
        section=getattr(proposal,field_name)
        lines.extend([f'## {fixed_title}','',clean_business_content(section.content),''])
    return '\n'.join(lines).rstrip()+'\n'


def _source_registry(state):
    records=[]
    for source in state.get('web_sources') or []:
        records.append({'source_id':source.get('source_id'),'kind':'web','title':source.get('title'),
            'url':source.get('url'),'published_date':source.get('published_date'),
            'retrieved_at':source.get('retrieved_at')})
    for chunk in state.get('evidence_chunks') or []:
        metadata=chunk.get('metadata') or {}
        records.append({'source_id':chunk.get('source_id'),'kind':'rag',
            'file_name':metadata.get('file_name'),'chunk_index':metadata.get('chunk_index'),
            'score':chunk.get('score')})
    return records


def render_b_audit_report(proposal, state, *, acceptance):
    """Return one human-readable heading plus a complete structured JSON audit."""
    from schemas.workflow import PROPOSAL_SECTION_FIELD_NAMES
    sections=[]
    if proposal is not None:
        for field_name in PROPOSAL_SECTION_FIELD_NAMES:
            section=getattr(proposal,field_name)
            sections.append({'field':field_name,'title':section.title,'confidence':section.confidence,
                'content_with_evidence_markers':section.content,
                'key_claims':[claim.model_dump(mode='json') for claim in section.key_claims],
                'source_ids':list(section.source_ids)})
    payload={'audit_version':AUDIT_VERSION,'generated_at':datetime.now(timezone.utc).isoformat(),
        'run_id':state.get('run_id'),'acceptance':acceptance or {},
        'needs_citation_review':bool(state.get('needs_citation_review')),
        'citation_failures':state.get('citation_failures') or [],
        'sections':sections,'source_registry':_source_registry(state)}
    return ('# B Product Audit Report\n\n'
        'The following JSON is the structured audit record and is not part of the business plan.\n\n'
        '```json\n'+json.dumps(payload,ensure_ascii=False,indent=2)+'\n```\n')
