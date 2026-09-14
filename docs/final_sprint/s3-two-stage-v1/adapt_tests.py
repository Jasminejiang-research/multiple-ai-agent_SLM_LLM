from pathlib import Path
root=Path(__file__).parent/'runtime'
p=root/'tests/test_s2_review.py'
s=p.read_text(encoding='utf-8').replace('[("A", 4, ()), ("B", 8, ("final",)),','[("A", 8, ()), ("B", 15, ("final",)),').replace('("C", 11,','("C", 18,').replace('("D", 11,','("D", 18,')
s=s.replace('(4 if role == "final" else 1)','(8 if role == "final" else 2)').replace('(12 if condition == "B" else 18)','(23 if condition == "B" else 32)')
p.write_text(s,encoding='utf-8')
p=root/'tests/test_s1_contract.py'
s=p.read_text(encoding='utf-8').replace('(4 if condition == "A" else 7)','(8 if condition == "A" else 14)')
start=s.index('    for (_, schema, _), base in zip(client.calls[-4:]')
end=s.index('    for prompt, _, kwargs in client.calls:',start)
s=s[:start]+'''    for index, (_, schema, _) in enumerate(client.calls[-8:]):
        assert schema.__canonical_schema__ is CONTRACT_BATCH_MODELS[index // 2]
        assert schema.__generation_stage__ == ("body" if index % 2 == 0 else "grounding")
''' + s[end:]
s=s.replace('== [False, True]','== [False, True, True]').replace('== ["generate", "structure_repair"]','== ["generate", "structure_repair", "generate"]')
s=s.replace('    assert len(client.calls) == 2\n\n\ndef test_only_one_repair','    assert len(client.calls) == 3\n\n\ndef test_only_one_repair')
p.write_text(s,encoding='utf-8')
p=root/'slm/tests/test_granite_s3.py'
s=p.read_text(encoding='utf-8').replace('len(providers[-1].calls)==11','len(providers[-1].calls)==18')
p.write_text(s,encoding='utf-8')
print('Updated normal-route expectations for the approved protocol.')
