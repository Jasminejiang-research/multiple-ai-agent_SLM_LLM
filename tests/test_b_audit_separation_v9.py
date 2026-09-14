"""B formal plan excludes audit transport while Appendix and audit lineage survive."""
import json
from pathlib import Path

from test_multi_agent_graph import _proposal
from workflow.nodes import export_node
from workflow.product_acceptance import product_node


def marked_proposal():
    proposal=_proposal()
    proposal.executive_summary.content += (' Evidence marker [web-fixture-1]. '
        '**[NEEDS_VALIDATION]** {{fin:missing.revenue}}')
    proposal.executive_summary.confidence='low'
    proposal.executive_summary.source_ids=['web-fixture-1']
    proposal.executive_summary.key_claims[0].evidence_status='unsupported'
    proposal.executive_summary.key_claims[0].source_ids=[]
    proposal.appendix.content='KEEP APPENDIX BUSINESS CONTENT. Reference [source_fixture_2]. **[UNSUPPORTED]**'
    proposal.appendix.confidence='low'
    proposal.appendix.source_ids=['source_fixture_2']
    return proposal


def audit_payload(markdown):
    return json.loads(markdown.split('```json\n',1)[1].rsplit('\n```',1)[0])


def test_b_export_writes_clean_plan_and_structured_audit_without_losing_appendix(tmp_path):
    proposal=marked_proposal()
    acceptance={'policy':'product-per-agent-one-correction-v1','corrections_allowed_per_agent':1,
        'corrections':{'writer':1},'correction_events':[],
        'unresolved_issues':[{'stage':'writer','message':'Synthetic audit-only issue.'}],
        'status':'accepted_with_issues'}
    state={'proposal_draft':proposal.model_dump(),'user_brief':{},
        'run_id':'audit_separation','product_acceptance':acceptance,
        'web_sources':[{'source_id':'web-fixture-1','title':'Fixture','url':'https://example.test'}],
        'evidence_chunks':[{'source_id':'source_fixture_2','content':'Fixture','score':0.8,
            'metadata':{'file_name':'fixture.md','chunk_index':2}}]}
    result=product_node('export',lambda value:export_node(value,output_dir=tmp_path))(state)
    plan=result['final_markdown']; audit=result['audit_markdown']
    for marker in ('Formal Output and Unresolved Issues','accepted_with_issues','Synthetic audit-only issue',
            '**Confidence:**','[NEEDS_VALIDATION]','[UNSUPPORTED]','**Source IDs:**',
            'web-fixture-1','source_fixture_2','{{fin:'):
        assert marker not in plan
    assert '## Appendix' in plan and 'KEEP APPENDIX BUSINESS CONTENT.' in plan
    payload=audit_payload(audit)
    assert payload['acceptance']['status']=='accepted_with_issues'
    assert payload['acceptance']['unresolved_issues'][0]['message']=='Synthetic audit-only issue.'
    assert len(payload['sections'])==13
    assert payload['sections'][-1]['field']=='appendix'
    assert payload['sections'][-1]['source_ids']==['source_fixture_2']
    assert {item['source_id'] for item in payload['source_registry']}=={'web-fixture-1','source_fixture_2'}
    assert Path(result['output_path']).is_file() and Path(result['audit_path']).is_file()
    assert Path(result['output_path']) != Path(result['audit_path'])


def test_formal_renderer_always_keeps_all_thirteen_sections():
    from workflow.product_audit import render_formal_b_proposal
    plan=render_formal_b_proposal(marked_proposal())
    assert plan.count('\n## ')==13
    assert '\n## Appendix\n' in plan
