"""Read-only post-run reconstruction of accepted canonical outputs from raw selections."""
from copy import deepcopy
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
from schemas.evidence import canonical_hash
from workflow.contract_context import ContractContext
from workflow.grounding import validate_grounding
from workflow.generation_batches import CONTRACT_BATCH_MODELS
from workflow.contract_context import ROLE_SCHEMAS

def at(value,path):
    for key in path: value=value[key]
    return value

def audit(directory):
    ctx=ContractContext.from_case(ROOT/'runtime/docs/final_sprint/s0-v1','ai_education',condition='D')
    sources={s.source_id:s for s in ctx.packet.sources}
    chunks={c.chunk_id:c for c in ctx.packet.chunks}
    tasks=[]
    for file in directory.rglob('events.jsonl'):
        latest={}
        for line in file.read_text(encoding='utf-8').splitlines():
            event=json.loads(line)
            if event['kind']=='logical_task': latest[event['payload']['logical_task_id']]=event['payload']
        for task in latest.values():
            if task.get('protocol')!='body-then-grounding-v1': continue
            row=dict(phase=str(file.parent.relative_to(directory)),logical_task_id=task['logical_task_id'],
                     completed=task['completed'],first_output_passed=task['first_output_passed'])
            body=task.get('frozen_draft')
            if body is None:
                row['status']='no_accepted_body'
                tasks.append(row)
                continue
            catalog=task['selection_catalog']
            assert canonical_hash(body)==catalog['body_sha256']
            assert catalog['packet_sha256']==ctx.packet_sha256
            body_attempt=next(a for a in reversed(task['attempts']) if a['generation_stage']=='body' and a['passed'])
            assert json.loads(body_attempt['raw_output'])==body
            for span in catalog['body_spans'].values():
                text=at(body,span['path'])
                assert 0<=span['start']<span['end']<=len(text)
                assert text[span['start']:span['end']]==span['text']
            for anchor in catalog['evidence_spans'].values():
                chunk=chunks[anchor['chunk_id']]
                assert chunk.source_id==anchor['source_id']
                assert sources[anchor['source_id']].txt_sha256==anchor['snapshot_sha256']
                assert chunk.line_start<=anchor['line_start']<=anchor['line_end']<=chunk.line_end
                lines='\n'.join(chunk.text.splitlines()[anchor['line_start']-chunk.line_start:anchor['line_end']-chunk.line_start+1])
                assert anchor['quote'] in lines
            row['body_and_catalog_verified']=True
            if task['completed']:
                selected=next(a for a in reversed(task['attempts']) if a['generation_stage']=='grounding' and a['passed'])
                selections=json.loads(selected['raw_output'])
                assembled=deepcopy(body)
                mapping=task['assembly_mapping']
                count=0
                for group,info in catalog['groups'].items():
                    value=selections[group]
                    parent=at(assembled,info['path'][:-1])
                    claims=[]
                    for index,selection in enumerate(value['claims']):
                        c=deepcopy(selection)
                        b=c.pop('body_span_id'); es=c.pop('evidence_span_ids')
                        assert b in info['body_span_ids'] and len(es)==len(set(es))
                        anchors=[catalog['evidence_spans'][e] for e in es]
                        c.update(content_anchor=catalog['body_spans'][b]['text'],source_anchors=anchors,
                                 source_ids=list(dict.fromkeys(a['source_id'] for a in anchors)))
                        claims.append(c)
                        expected=dict(claim_path=info['path']+[index],body_span_id=b,body_span=catalog['body_spans'][b],
                                      evidence_span_ids=es,source_anchors=anchors)
                        assert mapping[count]==expected
                        count+=1
                    parent[info['path'][-1]]=claims
                    for key,item in value.items():
                        if key!='claims': parent[key]=item
                    if 'content' in parent:
                        parent['source_ids']=list(dict.fromkeys(s for c in claims for s in c['source_ids']))
                assert count==len(mapping)
                schema=CONTRACT_BATCH_MODELS[task['batch_number']-1] if task['batch_number'] else ROLE_SCHEMAS[task['role']]
                canonical=schema.model_validate(assembled)
                assert canonical_hash(canonical.model_dump(mode='json'))==task['assembled_sha256']
                validate_grounding(canonical,ctx.packet,version=task['artifact_version'])
                if hasattr(canonical,'financial_values'): ctx.finance.validate(canonical.financial_values)
                if hasattr(canonical,'financial_assumptions'): ctx.finance.validate(canonical.financial_assumptions.financial_values)
                row.update(status='raw_selections_reconstruct_exact_canonical',claims=count)
            else:
                row['status']='body_only_or_failed_selections_not_complete'
            tasks.append(row)
    return dict(status='passed',tasks=tasks,model_calls=0,
                expanded_text_is_not_model_token_usage=True,human_semantic_support='not_assessed')

if __name__=='__main__':
    directory=ROOT/'run_01/probe'
    if not (directory/'result.json').exists(): raise RuntimeError('Wait for completed trial')
    result=audit(directory)
    output=ROOT/'run_01/audit/assembly_audit.json'
    output.parent.mkdir(exist_ok=True)
    with output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))
