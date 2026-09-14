from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-research-15m-v2'
status=REPO/'docs/final_sprint_status.md'
previous=(ROOT/'PREVIOUS_STATUS.md').read_bytes()
if status.read_bytes()!=previous: raise RuntimeError('Concurrent latest-status change')
note='''<!-- s3-research-15m-v2 installed -->
# 最新 S3：三声明Research继续验证

前次13分37秒组件失败（假设状态标签错误），已封存。现进一步简化为3核心声明，证据缺口进待核查list，增加短完整句目标和状态标签合法例子；精准修复反馈明确wire路径、当前值和期望值，不替模型改输出。

本次只Research生成组件，最多900秒，使用原90分钟池剩998.578秒/31请求/384511预算tokens；不新开预算。Research生产父节点仍含Critic/修订共享1200秒。完整计划书、Critic及正式实验均未执行；质量与结构通过分开记录。

验证以 docs/final_sprint/s3-research-15m-v2/validation/ 日志及run_01/probe/result.json为准。正式共享提示词为grounded-generation-v9-minimal-research，S5须重新冻结版本。全部旧记录与未提交版本保留。

---
'''
(REPORT/'HANDOFF.md').write_text(note+'\n'+(REPORT/'IMPLEMENTATION.md').read_text(encoding='utf-8'),encoding='utf-8')
status.write_bytes(note.encode('utf-8')+previous)
(REPORT/'STATUS_AT_PROBE_START.md').write_bytes(status.read_bytes())
shutil.copy2(__file__,REPORT/'record_start.py')
print('Research v2 pre-run status recorded without changing old history.')
