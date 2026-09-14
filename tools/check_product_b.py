"""Read-only inspection of recorded B; writes a separate offline audit folder.

No filler sections, citation edits, provider clients or experiment resumes.
The budget regression uses a recorded prompt-count test double, explicitly not
a fresh token count or evidence that the remaining run fits its budgets.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import patch

from run_product_ab import Audit, bootstrap, inventory, read, save, sha


def file_inventory(folder):
    return {p.relative_to(folder).as_posix():sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def response_payload(path):
    response = read(path)
    return json.loads(''.join(part.get('text','') for part in response['candidates'][0]['content']['parts']
                              if not part.get('thought')))


def referenced_source_ids(section):
    """Inspect values, never JSON field names such as `source_ids`."""
    cited = set(section.get('source_ids', []))
    texts = [section.get('content','')]
    for claim in section.get('key_claims',[]):
        cited.update(claim.get('source_ids',[]))
        texts.extend((claim.get('text',''),claim.get('content_anchor','')))
    for text in texts:
        cited.update(re.findall(r'\b(?:web-[A-Za-z0-9-]+|source_[A-Za-z0-9_]+)',text))
    return cited


def check_recorded_b(directory, output):
    if output.exists():
        raise FileExistsError('Refusing to overwrite an earlier offline inspection')
    if output == directory or directory in output.parents:
        raise ValueError('Inspection output must be outside the original experiment')
    before = file_inventory(directory)
    manifest = read(directory/'manifest.json')
    if sha(directory/'manifest.json') != read(directory/'manifest_lock.json')['sha256']:
        raise ValueError('Historical manifest failed its integrity check')
    source = Path(manifest['source'])
    if inventory(source) != manifest['code_sha256']:
        raise ValueError('Source changed since run; inspection requires the recorded code version')
    from rag.citation_checker import check_citations
    from schemas.workflow import ProposalDraft
    from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS, PROPOSAL_SECTION_BATCHES
    state = read(directory/'B/state.json')
    allowed = {s['source_id'] for s in state['web_sources']} | {s['source_id'] for s in state['evidence_chunks']}
    sections, batches = {}, []
    partial = {}
    for request_path in sorted((directory/'B/calls').glob('*.request.json')):
        request = read(request_path)
        match = re.search(r'Return one `ProposalDraftBatch([1-4])`', request['contents'])
        response_path = request_path.with_name(request_path.name.replace('.request.json','.response.json'))
        if match is None or not response_path.exists():
            continue
        number = int(match.group(1))
        raw = response_payload(response_path)
        validated = PROPOSAL_DRAFT_BATCH_MODELS[number-1].model_validate(raw).model_dump(mode='json')
        partial.update(validated)
        batches.append(dict(batch=number, call=request_path.stem.split('.')[0],
                            request_sha256=sha(request_path),response_sha256=sha(response_path),
                            fields=list(PROPOSAL_SECTION_BATCHES[number-1]),structure_valid=True))
        for name in PROPOSAL_SECTION_BATCHES[number-1]:
            section = validated[name]
            coverage = check_citations(section).model_dump(mode='json')
            cited_ids = referenced_source_ids(section)
            chars = len(section['content'])
            chinese = len(re.findall(r'[\u4e00-\u9fff]',section['content']))
            sections[name] = dict(characters=chars, chinese_characters=chinese,
                language_heuristic='Chinese' if chinese/max(chars,1)>0.2 else 'English_or_other',
                raw_confidence=raw[name]['confidence'], validated_confidence=section['confidence'],
                unknown_source_ids=sorted(cited_ids-allowed),citation_coverage=coverage)
    complete_validation_errors = []
    try:
        ProposalDraft.model_validate(partial)
    except Exception as exc:
        complete_validation_errors = [dict(location=list(e['loc']),type=e['type']) for e in exc.errors()]
    response_files = sorted(directory.glob('*/calls/*.response.json'))
    responses = [read(p) for p in response_files]
    total_tokens = sum(r['usage_metadata']['total_token_count'] for r in responses)
    expected = read(directory/'results.json')['accounting']
    if total_tokens != expected['total_tokens']:
        raise ValueError('Historical provider usage does not reconcile')
    missing = [name for batch in PROPOSAL_SECTION_BATCHES for name in batch if name not in partial]
    result = dict(classification='offline_partial_inspection_not_final_critic_or_repaired_proposal',
        source_code_matches_manifest=True, original_experiment=str(directory),
        validated_batches=batches, available_sections=list(sections), missing_sections=missing,
        sections=sections, full_proposal_valid=not complete_validation_errors,
        full_proposal_validation_errors=complete_validation_errors,
        completed_nodes=sorted(p.stem for p in (directory/'B/nodes').glob('*.json')),
        checkpoint=dict(native_graph_checkpointer=False, saved_state_step=state.get('current_step'),
            raw_batches_recoverable=len(batches), ready_to_resume=False,
            reason='Raw validated batches can be recovered, but the original graph has no persisted Writer batch cursor; no resume adapter has been implemented or authorized.'),
        evidence=dict(web_count=len(state['web_sources']),
            unknown_publication_dates=sum(s.get('published_date') is None for s in state['web_sources']),
            rag_files=[s['metadata'].get('file_name') for s in state['evidence_chunks']],
            market_uses_2013_data='2013' in partial.get('market_opportunity',{}).get('content','')),
        historical_usage_reconciled=dict(response_count=len(responses),total_tokens=total_tokens),
        new_network_calls=0,new_generation_calls=0)
    output.mkdir(parents=True)
    # Replay the already observed long Writer request at the stop-point balance.
    # Full recorded prompt count is a conservative stand-in for contents count;
    # it is not an exact measurement for unissued Writer batch 3.
    request = read(directory/'B/calls/007.request.json')
    usage = read(directory/'B/calls/007.response.json')['usage_metadata']
    audit = Audit(output,manifest['limits'])
    audit.arm='B'
    audit.requests=expected['llm_requests']
    audit.tokens=expected['total_tokens']
    audit.cost=expected['llm_cost_usd']
    a_usage=read(directory/'A/result.json')['accounting_after']
    audit.arm_usage['B']=dict(requests=audit.requests-a_usage['llm_requests'],tokens=audit.tokens-a_usage['total_tokens'])
    fake_count = SimpleNamespace(count_tokens=lambda **kw:SimpleNamespace(total_tokens=usage['prompt_token_count']))
    with patch('socket.socket.connect',side_effect=AssertionError('Offline inspection forbids network')):
        bound = audit.admit(fake_count,dict(model=request['model'],contents=request['contents'],
                            config=SimpleNamespace(model_dump=lambda **kw:request['config'])))
    result['admission_regression'] = dict(kind='recorded_long_request_replay_with_simulated_count_endpoint',
        bound=bound, admitted=True, combined_projected_tokens=audit.tokens+bound['total_bound'],
        arm_projected_tokens=audit.arm_usage['B']['tokens']+bound['total_bound'],
        limits_unchanged=True, complete_remaining_run_feasibility='not established')
    after = file_inventory(directory)
    if before != after:
        raise RuntimeError('Historical experiment changed during inspection')
    save(output/'historical_files.sha256.json',before)
    result['historical_files_unchanged']=True
    save(output/'B_CHECK.json',result)
    summary=dict(available=len(sections),missing=missing,
        structural_citation_failures=sum(sum(not c['has_source'] for c in s['citation_coverage']['checks']) for s in sections.values()),
        unknown_ids=sorted({sid for s in sections.values() for sid in s['unknown_source_ids']}),
        language_counts=dict(Counter(s['language_heuristic'] for s in sections.values())),
        ready_to_resume=False,regression=result['admission_regression'])
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest=read(args.experiment/'manifest.json')
    bootstrap(Path(manifest['source']))
    with patch('socket.socket.connect',side_effect=AssertionError('Offline inspection forbids network')):
        check_recorded_b(args.experiment.resolve(),args.output.resolve())
