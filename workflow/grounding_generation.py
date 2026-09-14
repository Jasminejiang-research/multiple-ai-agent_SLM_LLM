"""Explain existing content/source anchoring rules; diagnose without altering outputs."""
from __future__ import annotations
import json


def grounding_reference_contract(packet):
    sources = {source.source_id: source for source in packet.sources}
    examples = []
    for chunk in packet.chunks:
        # Existing frozen text only, with its original line number and hash.
        for offset, line in enumerate(chunk.text.splitlines()):
            if line.strip():
                examples.append(dict(source_id=chunk.source_id, chunk_id=chunk.chunk_id,
                    line_start=chunk.line_start+offset, line_end=chunk.line_start+offset,
                    snapshot_sha256=sources[chunk.source_id].txt_sha256, quote=line))
                break
    return ('# Content anchor and frozen source contract\n'
        'content_anchor locates YOUR OWN prose, not the source. It must be an exact substring of the '
        'same parent finding/recommendation/assumption or rationale; in proposal sections it must occur '
        'in that section.content. The claim_text, topic and source quote do NOT count as parent prose. '
        'Choose a short exact phrase already written in the parent. '
        'Format-only example: {"finding":"Demand requires validation.","claims":[{"content_anchor":"Demand requires validation."}]}. '
        'This is a fragment, not a substitute for the full required schema.\n'
        f'Only these source IDs are legal: {json.dumps(sorted(sources))}. '
        'packet, brief, user_brief and source packet are NOT source IDs. The brief describes user assumptions, '
        'not externally verified facts: use claim_type=assumption, evidence_status=assumption, '
        'source_ids=[], source_anchors=[], source_support=none, a clear premise, and financial_value_ids=[] '
        'when no supplied financial value is actually referenced. Do not classify missing market evidence as sourced_fact.\n'
        'source_anchors locate frozen evidence. Copy source/chunk/hash and exact quote with matching line numbers '
        'from the packet. Do not paraphrase a quote or add citations inside the quote. '
        'The following are valid anchor FORMAT examples taken verbatim from the existing frozen packet; '
        'use one only if its actual text supports your claim, otherwise select a relevant exact passage '
        'from the same packet or explicitly retain the evidence gap. They are not new evidence.\n'
        + json.dumps(examples,ensure_ascii=False,separators=(',', ':')))


def grounding_issues(raw, packet):
    if not raw or len(raw) > 200000:
        return []
    try:
        value = json.loads(raw)
    except (ValueError,RecursionError):
        return []
    sources = {source.source_id: source for source in packet.sources}
    chunks = {chunk.chunk_id: chunk for chunk in packet.chunks}
    issues = []

    def add(path, problem, **details):
        if len(issues) < 10:
            issues.append(dict(path=path,problem=problem,**details))

    def walk(obj, path='$', depth=0):
        if depth > 32 or len(issues) >= 10:
            return
        if isinstance(obj,dict):
            fields = ('content',) if 'key_claims' in obj else ('finding','recommendation','assumption','rationale')
            body = '\n'.join(obj[k] for k in fields if isinstance(obj.get(k),str))
            claims_key = 'key_claims' if 'key_claims' in obj else 'claims'
            claims = obj.get(claims_key,[])
            if body and isinstance(claims,list):
                for i,claim in enumerate(claims):
                    if not isinstance(claim,dict): continue
                    anchor = claim.get('content_anchor')
                    if isinstance(anchor,str) and anchor not in body:
                        add(f'{path}.{claims_key}[{i}].content_anchor','content anchor not present in parent prose',
                            observed=anchor[:160],parent_fields=list(fields),legal_exact_example=body.split('\n')[0][:120])
            ids = obj.get('source_ids')
            if isinstance(ids,list):
                unknown = [v for v in ids if isinstance(v,str) and v not in sources]
                if unknown: add(path+'.source_ids','unknown source IDs',observed=unknown[:3],allowed=sorted(sources))
            if all(k in obj for k in ('source_id','chunk_id','snapshot_sha256','quote','line_start','line_end')):
                source = sources.get(obj['source_id']) if isinstance(obj['source_id'],str) else None
                chunk = chunks.get(obj['chunk_id']) if isinstance(obj['chunk_id'],str) else None
                if not source or not chunk or chunk.source_id != obj['source_id']:
                    add(path,'unknown or mismatched source/chunk ID')
                elif obj['snapshot_sha256'] != source.txt_sha256:
                    add(path+'.snapshot_sha256','source snapshot hash mismatch',expected=source.txt_sha256)
                else:
                    start,end = obj['line_start'],obj['line_end']
                    if type(start) is not int or type(end) is not int or not chunk.line_start <= start <= end <= chunk.line_end:
                        add(path,'source anchor lines outside frozen chunk',allowed_lines=[chunk.line_start,chunk.line_end])
                    else:
                        excerpt = '\n'.join(chunk.text.splitlines()[start-chunk.line_start:end-chunk.line_start+1])
                        if not isinstance(obj['quote'],str) or obj['quote'] not in excerpt:
                            add(path+'.quote','quote not found verbatim at supplied frozen lines',
                                observed=str(obj['quote'])[:120],frozen_excerpt=excerpt[:220])
            for key,child in obj.items(): walk(child,f'{path}.{key}',depth+1)
        elif isinstance(obj,list):
            for i,child in enumerate(obj): walk(child,f'{path}[{i}]',depth+1)
    walk(value)
    return issues
