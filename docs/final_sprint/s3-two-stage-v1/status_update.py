from pathlib import Path
from datetime import datetime,timezone
import hashlib,json

ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
status=REPO/'docs/final_sprint_status.md'
old=status.read_bytes()
backup=ROOT/'STATUS_BEFORE_LIVE_UPDATE.md'
if backup.exists(): raise RuntimeError('Preserve previous live status')
backup.write_bytes(old)
text='''<!-- s3-two-stage-v1 current -->
# 最新 S3：已批准两阶段生成，工程验证完成，真实测试启动

用户已明确批准统一 A–D 两阶段生成方案。实现及授权见 docs/final_sprint/s3-two-stage-v1/IMPLEMENTATION.md。
正文/完整财务值先生成并锁定，再生成声明和精确片段选择；最终按原完整 canonical 契约验收。A/B/C/D 正常调用数8/15/18/18；两个阶段共享一次结构修复，Critic与条件Revision规则不变。

离线测试与无模型演练证据见本包 validation/。真实测试承接最新累计11请求、71252tokens、4487.671秒，剩余25请求、428748tokens、9912.329秒，不重置。先真实Research通过后才运行完整D；启动不代表已成功生成计划书。

原未提交文件已备份；旧运行和正式公共预算不变，Gemini/正式实验/S5启动均未执行。结果以本包run_01/probe/result.json、HANDOFF.md及后续最新记录为准。

---
<!-- s3-two-stage-v1 history -->

'''
status.write_bytes(text.encode('utf-8')+old)
print(json.dumps(dict(updated_at_utc=datetime.now(timezone.utc).isoformat(),previous_sha256=hashlib.sha256(old).hexdigest())))
