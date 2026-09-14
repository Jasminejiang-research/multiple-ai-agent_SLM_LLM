from pathlib import Path
r=Path(__file__).parent/'runtime'
p=r/'tests/test_s2_review.py'
s=p.read_text(encoding='utf-8').replace('[("research", 2), ("strategy", 4), ("finance", 6), ("final", 11)]','[("research", 3), ("strategy", 6), ("finance", 9), ("final", 18)]')
s=s.replace('len(workflow.generator.tasks[0].attempts) == 1','len(workflow.generator.tasks[0].attempts) == 2')
s=s.replace('(2 if source_field == "source_ids" else 3)','(3 if source_field == "source_ids" else 4)')
s=s.replace('== ["revision", "structure_repair"]','== ["revision", "structure_repair", "revision"]')
s=s.replace('result["budget"]["revision_request_count"] == 2','result["budget"]["revision_request_count"] == 3')
s=s.replace('"multi-agent-review-gates-v2"','"multi-agent-review-gates-v3-two-stage"').replace('if e["kind"] == "call"]) == 24','if e["kind"] == "call"]) == 46').replace('run.token_usage["request_count"] == 12','run.token_usage["request_count"] == 23')
p.write_text(s,encoding='utf-8')
p=r/'tests/test_s1_contract.py'
s=p.read_text(encoding='utf-8')
s=s.replace('with pytest.raises(CitationPollutionError): generator.generate(context, "research")','with pytest.raises(CitationPollutionError):\n        generator.generate_task("synthetic direct-contract diagnostic", ContractResearchAnalysis, context=context,\n            role="research",version=1,logical_task_id="pollution",validator=lambda c:context.validate(c,version=1))')
s=s.replace('assert len(client.calls) == 5','assert len(client.calls) == 9')
s=s.replace('''        if issubclass(schema, CONTRACT_BATCH_MODELS[-1]):
            for key in PROPOSAL_SECTION_BATCHES[-1]:
                getattr(candidate, key).key_claims[0].source_quality = .1''','''        if getattr(schema, "__canonical_schema__", None) is CONTRACT_BATCH_MODELS[-1] and schema.__generation_stage__ == "grounding":
            for key in schema.model_fields:
                getattr(candidate, key).claims[0].source_quality = .1''')
s=s.replace('assert len(client.calls) == 4','assert len(client.calls) == 8')
s=s.replace('return schema.model_validate(component_payload(context, "research", version=2))','from evaluation.two_stage_fixtures import synthetic_stage_payload\n        return schema.model_validate(synthetic_stage_payload(schema,component_payload(context, "research", version=2)))')
p.write_text(s,encoding='utf-8')
p=r/'slm/granite_preflight.py'
s=p.read_text(encoding='utf-8')
start=s.index('return generator.generate_task(writer_probe_prompt')
print(s[start:start+700])
p=r/'slm/tests/test_granite_s3.py'
s=p.read_text(encoding='utf-8')
s=s.replace('from workflow.grounding_generation import grounding_reference_contract','from workflow.two_stage_generation import BODY_INSTRUCTION')
s=s.replace('writer_probe_prompt(context,(research,strategy,finance))+"\\n\\n"+','writer_probe_prompt(context,(research,strategy,finance))+"\\n\\n"+BODY_INSTRUCTION+"\\n\\n"+')
s=s.replace('financial_reference_contract(context.finance.value_ids)+"\\n\\n"+grounding_reference_contract(context.packet))','financial_reference_contract(context.finance.value_ids))')
p.write_text(s,encoding='utf-8')
