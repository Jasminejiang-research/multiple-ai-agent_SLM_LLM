"""Offline, read-only experiment inspection; output must be a new sibling folder."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from run_product_ab import bootstrap, inventory, read, save, sha


def inspect(directory, output):
    if output.exists() or output == directory or directory in output.parents:
        raise ValueError('Inspection requires a new output directory outside the experiment')
    manifest=read(directory/'manifest.json')
    if sha(directory/'manifest.json') != read(directory/'manifest_lock.json')['sha256']:
        raise ValueError('Manifest integrity failure')
    source=Path(manifest['source'])
    if inventory(source) != manifest['code_sha256']:
        raise ValueError('Product code changed since preparation; use the recorded revision')
    bootstrap(source)
    from schemas.proposal_schema import BusinessProposal
    from schemas.workflow import ProposalDraft, RevisedProposal, PROPOSAL_SECTION_FIELD_NAMES
    from rag.citation_checker import collect_proposal_citation_failures
    from workflow.product_output_policy import resolve_output_language, validate_text_language
    language=resolve_output_language(manifest['input']['brief'])
    results=read(directory/'results.json')
    before=inventory_files(directory)
    unvalidated_lines=[]
    metrics={'classification':manifest['classification'],'results':results,'arms':{}}
    for arm in manifest['order']:
        arm_dir=directory/arm
        outcome=results['arms'][arm]
        state=read(arm_dir/'state.json')
        responses=[read(path) for path in sorted((arm_dir/'calls').glob('*.response.json'))]
        usage=Counter()
        for response in responses:
            for key,value in response.get('usage_metadata',{}).items():
                if key in ('prompt_token_count','candidates_token_count','thoughts_token_count','total_token_count'):
                    usage[key] += value or 0
        detail={'status':outcome['status'],'seconds':outcome['seconds'],
                'completed_responses':len(responses),'usage':dict(usage),
                'model_cost_usd':outcome['accounting_after']['llm_cost_usd']-outcome['accounting_before']['llm_cost_usd']}
        if (arm_dir/'failure.json').exists():
            detail['failure']=read(arm_dir/'failure.json')
        if arm=='A' and (arm_dir/'proposal.json').exists():
            proposal=BusinessProposal.model_validate(read(arm_dir/'proposal.json'))
            markdown=(arm_dir/'proposal.md').read_text(encoding='utf-8')
            detail.update(schema_valid=True,markdown_characters=len(markdown),
                          heading_count=len(re.findall(r'^## ',markdown,re.M)),
                          financial_assumptions=proposal.financial_assumptions.model_dump(mode='json'))
        if arm=='B':
            sections={}
            checkpoints=[]
            for path in sorted((arm_dir/'writer_checkpoints').glob('*/batch-*.json')):
                data=read(path)
                checkpoints.append({'batch':data['batch'],'path':str(path)})
                sections.update({k:v for k,v in data['payload'].items() if k in PROPOSAL_SECTION_FIELD_NAMES})
            final=None
            if state.get('revised_proposal'):
                final=RevisedProposal.model_validate(state['revised_proposal']).proposal
            elif state.get('proposal_draft'):
                final=ProposalDraft.model_validate(state['proposal_draft'])
            if final:
                sections={key:getattr(final,key).model_dump(mode='json') for key in PROPOSAL_SECTION_FIELD_NAMES}
            allowed={item['source_id'] for key in ('web_sources','evidence_chunks') for item in state.get(key,[])}
            language_errors={}
            for name,section in sections.items():
                try:
                    validate_text_language(section['content'],language)
                except ValueError as exc:
                    language_errors[name]=str(exc)
            detail.update(last_step=state.get('current_step'),completed_sections=len(sections),
                          missing_sections=[key for key in PROPOSAL_SECTION_FIELD_NAMES if key not in sections],
                          checkpoints=checkpoints,language_errors=language_errors,
                          section_characters={k:len(v['content']) for k,v in sections.items()},
                          critic_ran=bool(state.get('critique_report')),revision_ran=bool(state.get('revised_proposal')),
                          graph_nodes=[p.stem for p in (arm_dir/'nodes').glob('*.json')],
                          web_sources=len(state.get('web_sources',[])),
                          missing_source_dates=sum(not s.get('published_date') for s in state.get('web_sources',[])),
                          rag_documents=[s['metadata'].get('file_name') for s in state.get('evidence_chunks',[])],
                          evidence_status_counts=dict(Counter(c['evidence_status'] for s in sections.values() for c in s['key_claims'])))
            if final:
                detail['citation_failures']=[f.model_dump(mode='json') for f in collect_proposal_citation_failures(final,allowed_source_ids=allowed)]
            if (arm_dir/'failure.json').exists():
                detail['failure']=read(arm_dir/'failure.json')
            detail['raw_writer_attempts']=[]
            from workflow.generation_batches import PROPOSAL_DRAFT_BATCH_MODELS
            from workflow.product_output_policy import validate_product_batch
            last_writer_batch = None
            for request_path in sorted((arm_dir/'calls').glob('*.request.json')):
                request=read(request_path)
                match=re.search(r'Return one `ProposalDraftBatch([1-4])`',request['contents'])
                local_correction = '# Local Structured Output Correction' in request['contents']
                if match is not None:
                    last_writer_batch = int(match.group(1))
                response_path=request_path.with_name(request_path.name.replace('.request.json','.response.json'))
                if not response_path.exists() or (match is None and not (local_correction and last_writer_batch)):
                    continue
                number=int(match.group(1)) if match else last_writer_batch
                response=read(response_path)
                raw=''.join(p.get('text','') for p in response['candidates'][0]['content']['parts'] if not p.get('thought'))
                attempt={'call':request_path.name.split('.')[0],'batch':number}
                schema_spec=request.get('config',{}).get('response_json_schema') or request.get('config',{}).get('response_schema') or {}
                if (str(schema_spec.get('title','')).startswith('LocalRepair_')
                        or local_correction):
                    attempt.update(kind='local_section_patch',quality_valid=None,
                                   validation_note='Partial correction: do not validate as a full batch. Merged checkpoints determine acceptance.')
                    detail['raw_writer_attempts'].append(attempt)
                    continue
                try:
                    from workflow.structured_repair import canonical_payload
                    batch_schema=PROPOSAL_DRAFT_BATCH_MODELS[number-1]
                    candidate=batch_schema.model_validate(canonical_payload(raw,batch_schema))
                    attempt['schema_valid']=True
                    if not unvalidated_lines and not final:
                        unvalidated_lines=['# B: Unvalidated Partial Writer Output','',
                            '> This excerpt contains only the persisted raw sections. It is not a complete business plan, '
                            'did not pass final citation review, and did not enter Critic or Revision.','']
                        for key in type(candidate).model_fields:
                            section=getattr(candidate,key)
                            if hasattr(section,'content'):
                                unvalidated_lines.extend(['## '+section.title,'',section.content,''])
                    validate_product_batch(candidate,language=language,allowed=allowed)
                    attempt['quality_valid']=True
                    attempt['quality_scope']='Language and citation shape only; not full evidence provenance or financial acceptance. Consult checkpoints/failure.'
                except ValueError as exc:
                    attempt['validation_error']=str(exc)
                    attempt.setdefault('schema_valid',False)
                    attempt['quality_valid']=False
                detail['raw_writer_attempts'].append(attempt)
            detail['rejections']=[read(path) for path in sorted((arm_dir/'rejections').glob('*.json'))]
        metrics['arms'][arm]=detail
    metrics['response_token_sum']=sum(a['usage'].get('total_token_count',0) for a in metrics['arms'].values())
    metrics['response_tokens_match_ledger']=metrics['response_token_sum']==results['accounting']['total_tokens']
    if before != inventory_files(directory):
        raise ValueError('Experiment changed during inspection')
    output.mkdir(parents=True)
    save(output/'METRICS.json',metrics)
    save(output/'historical_files.sha256.json',before)
    if unvalidated_lines:
        (output/'B_UNVALIDATED_DRAFT.md').write_text('\n'.join(unvalidated_lines)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(output),'statuses':{k:v['status'] for k,v in metrics['arms'].items()},
                      'total_tokens':metrics['response_token_sum'],'B_sections':metrics['arms'].get('B',{}).get('completed_sections')},ensure_ascii=False))


def inventory_files(directory):
    return {p.relative_to(directory).as_posix():sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    inspect(args.directory.resolve(),args.output.resolve())
