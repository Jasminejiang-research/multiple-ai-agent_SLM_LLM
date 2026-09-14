from pathlib import Path
from datetime import datetime, timezone
import shutil

ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-90m-fix-v1'
status=REPO/'docs/final_sprint_status.md'
prior=(REPORT/'PREVIOUS_STATUS.md').read_bytes()
if status.read_bytes()!=prior: raise RuntimeError('Concurrent status modification; do not overwrite')
header='''<!-- s3-90m-fix-v1 running -->
# 最新 S3：90分钟恢复修复已安装，真实验证准备启动

用户要求LLM、SLM各自每份完整计划书最多5400秒。本包修复Windows页文件原生采样、绑定身份的服务停止、共享两阶段prompt冗余及Writer预检一致性；完整13章/财务/grounding/lineage/Critic与一次结构修复保留。

261文件快照、10文件精确安装及旧版本备份完成。完整离线733 passed/25 deselected/3 subtests passed（196.77秒），安装后108 passed（7.72秒），预算运行器10 passed（2.02秒），pip check通过。正式公共预算及历史数据不变。

真实AI教育SLM测试承接13请求/预算扣记191323tokens/4788.311秒历史累计；本次最多5400秒、剩余23请求/308677tokens，单次8192。先真实Research通过后全新完整D，两者共享本次截止；不重置旧累计额度、不重发未知请求。当前尚未生成完整计划书，实际结果以docs/final_sprint/s3-90m-fix-v1/run_01/probe/result.json及HANDOFF.md为准。Gemini调用0，正式实验0/8；未启动S5正式运行。

---
<!-- s3-90m-fix-v1 previous records -->

'''
status.write_bytes(header.encode('utf-8')+prior)
(REPORT/'HANDOFF.md').write_text('# 真实验证准备启动\n\n修复、安装和离线验证见 IMPLEMENTATION.md；尚未宣称完整计划书成功。\n\n准备时间：'+datetime.now(timezone.utc).isoformat()+'\n',encoding='utf-8')
if ROOT != REPORT: shutil.copy2(__file__,REPORT/Path(__file__).name)
print('Recorded installed fixes and pending real 90-minute recovery.')
