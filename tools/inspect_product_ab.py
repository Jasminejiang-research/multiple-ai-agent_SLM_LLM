"""Offline recovery/diagnostics only; never calls an LLM or search provider."""
import json
from pathlib import Path
import re
import sys

from run_product_ab import bootstrap, read, save


def main():
    directory = Path(sys.argv[1]).resolve()
    manifest = read(directory/'manifest.json')
    bootstrap(Path(manifest['source']))
    from agents.writer import build_writer_prompt, build_writer_batch_prompt
    from schemas.agent_outputs import WriterInput
    from workflow.generation_batches import PROPOSAL_SECTION_BATCHES, PROPOSAL_DRAFT_BATCH_MODELS
    from workflow.gemini_schema import relaxed_response_schema
    from workflow.llm_client import LLMClient
    from google.genai import types
    results = read(directory/'results.json')
    state = read(directory/'B/state.json')
    partial = {}
    for number, batch_model in zip(('006','007'), PROPOSAL_DRAFT_BATCH_MODELS):
        response = read(directory/'B/calls'/f'{number}.response.json')
        raw = ''.join(part.get('text','') for part in response['candidates'][0]['content']['parts'] if not part.get('thought'))
        partial.update(batch_model.model_validate_json(raw).model_dump(mode='json'))
    save(directory/'B/partial_proposal.json', partial)
    lines = ['# B：未完成计划书（原始已生成章节）', '',
             '> 仅恢复 Writer 前两批的 7 个章节；尚未完成合并、引用检查、Critic 或修订。不是最终计划书，不可对外使用。正文保持原始语言与内容，不作修补。', '']
    sections = {}
    for name, section in partial.items():
        if not isinstance(section, dict):
            continue
        sections[name] = dict(characters=len(section['content']), confidence=section['confidence'],
                             claims=len(section['key_claims']))
        lines.extend(['## '+section['title'], '', section['content'], ''])
    lines.extend(['## 检索来源映射（仅提供追溯，不代表证据有效）',''])
    for source in state['web_sources']:
        lines.append(f"- `{source['source_id']}` — [{source['title']}]({source['url']})")
    (directory/'B/partial_proposal.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    writer_input = WriterInput.model_validate({k:state[k] for k in (
        'research_analysis','strategy_analysis','finance_assumptions','web_sources','evidence_chunks',
        'evidence_mode','low_confidence_required','evidence_was_budget_limited')})
    batch_model = PROPOSAL_DRAFT_BATCH_MODELS[2]
    prompt = build_writer_batch_prompt(build_writer_prompt(writer_input), batch_number=3,
             section_fields=PROPOSAL_SECTION_BATCHES[2], schema_name=batch_model.__name__, include_title=False)
    prompt = LLMClient._constrained_prompt(prompt,batch_model)
    config = types.GenerateContentConfig(system_instruction=None, response_mime_type='application/json',
        response_schema=relaxed_response_schema(batch_model),temperature=0.2,max_output_tokens=16384)
    config_data = config.model_dump(mode='json',exclude_none=True)
    input_bound = len(json.dumps({'contents':prompt,'config':config_data},ensure_ascii=False).encode('utf-8'))+4096
    output_bound = config_data['max_output_tokens']+32768
    actual = results['accounting']
    diagnostic = dict(classification='offline_exact_reconstruction_of_blocked_batch_3_not_a_provider_request',
        prompt_characters=len(prompt), harness_input_byte_bound=input_bound,
        harness_output_and_thinking_bound=output_bound, actual_tokens_before_block=actual['total_tokens'],
        projected_tokens=actual['total_tokens']+input_bound+output_bound,
        configured_token_limit=manifest['limits']['total_tokens'],
        actual_llm_cost_before_block=actual['llm_cost_usd'],
        projected_cost=actual['llm_cost_usd']+(input_bound*0.30+output_bound*2.50)/1e6,
        configured_llm_cost_limit=manifest['limits']['llm_cost_usd'],
        request_count_before_block=actual['llm_requests'],
        configured_request_limit=manifest['limits']['llm_requests'])
    save(directory/'budget_diagnosis.json',diagnostic)
    allowed = {s['source_id'] for s in state['web_sources']} | {s['source_id'] for s in state['evidence_chunks']}
    references = {sid for section in partial.values() if isinstance(section,dict)
                  for sid in section['source_ids']}
    metrics = dict(B_partial_sections=sections, B_unknown_partial_source_ids=sorted(references-allowed),
        B_rag_documents=[c['metadata'].get('file_name') for c in state['evidence_chunks']],
        B_web_results=len(state['web_sources']),
        B_missing_publication_dates=sum(s.get('published_date') is None for s in state['web_sources']),
        A_markdown_characters=len((directory/'A/proposal.md').read_text(encoding='utf-8')),
        A_h2_sections=len(re.findall(r'^## ', (directory/'A/proposal.md').read_text(encoding='utf-8'),re.M)),
        B_completed_llm_requests=actual['llm_requests']-results['arms']['A']['accounting_after']['llm_requests'],
        B_total_tokens=actual['total_tokens']-results['arms']['A']['accounting_after']['total_tokens'],
        B_llm_cost_usd=actual['llm_cost_usd']-results['arms']['A']['accounting_after']['llm_cost_usd'])
    save(directory/'observed_metrics.json',metrics)
    print(json.dumps(dict(budget=diagnostic,metrics=metrics),ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
