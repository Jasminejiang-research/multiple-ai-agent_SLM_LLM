from pathlib import Path

STAGE=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-reference-fix-v3'
status=REPO/'docs/final_sprint_status.md'
start='<!-- s3-reference-fix-v3 current -->'
end='<!-- s3-reference-fix-v3 history -->'
old=status.read_text(encoding='utf-8-sig')
if old.startswith(start):
    old=old.split(end,1)[1].lstrip('\n')
else:
    path=REPORT/'STATUS_BEFORE_LIVE_UPDATE.md'
    if not path.exists(): path.write_bytes(status.read_bytes())
current=(STAGE/'STATUS_CURRENT.md').read_text(encoding='utf-8')
status.write_text(start+'\n'+current+'\n---\n'+end+'\n\n'+old,encoding='utf-8')
print('Latest status updated; previous history preserved.')
