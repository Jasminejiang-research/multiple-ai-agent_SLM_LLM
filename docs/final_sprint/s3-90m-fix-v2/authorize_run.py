"""Record the user's explicit approval received after the installed handoff."""
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil

REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT = REPO/'docs/final_sprint/s3-90m-fix-v2'
path = REPORT/'authorization.json'
record = json.loads(path.read_text(encoding='utf-8'))
if record['approved'] or (REPORT/'run_01').exists():
    raise RuntimeError('Preserve prior authorization/run; do not replay')
shutil.copy2(path, REPORT/'authorization.pending.json')
record.update(approved=True, approved_at_utc=datetime.now(timezone.utc).isoformat(),
    user_confirmation='批准新的90分钟完整D复测',
    approved_question='一次新的独立90分钟完整D复测（AI教育、同一SLM、单次8192 tokens、最多36请求/50万tokens，旧消耗保留）',
    approval_source='Explicit user reply to the bounded validation proposal in the current task',
    old_consumption_preserved=True)
record.pop('reason_pending', None)
path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
status = REPO/'docs/final_sprint_status.md'
previous = status.read_bytes()
(REPORT/'PRE_RUN_STATUS.md').write_bytes(previous)
header = '''<!-- s3-90m-fix-v2 real-run authorized -->
# 最新 S3：用户已批准新的独立90分钟完整D复测

用户明确回复“批准新的90分钟完整D复测”。本次AI教育/同一Granite CPU，5400秒独立上限、8192输出、最多36请求/50万预算tokens；原16请求/296569预算tokens/10193.483秒独立保留。正式公共配置与Gemini未改动。

修复已完成782项完整回归、132项安装验证、26项运行器验证；真实新复测准备启动，尚未证明完整计划书成功。运行入口与记录位于 docs/final_sprint/s3-90m-fix-v2/；最终以run_01/probe/result.json及更新HANDOFF.md为准。未启动正式S5八槽。

---
<!-- s3-90m-fix-v2 preserved pre-run records -->

'''
status.write_bytes(header.encode('utf-8')+previous)
shutil.copy2(Path(__file__), REPORT/'authorize_run.py')
print('Explicit fresh 90-minute allowance recorded. No model calls yet.')
