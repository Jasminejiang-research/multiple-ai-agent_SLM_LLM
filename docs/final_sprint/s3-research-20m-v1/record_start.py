from pathlib import Path
import shutil

STAGE = Path(__file__).resolve().parent
REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT = REPO / 'docs/final_sprint/s3-research-20m-v1'
status = REPO / 'docs/final_sprint_status.md'
previous = (STAGE / 'PREVIOUS_STATUS.md').read_bytes()
if status.read_bytes() != previous:
    raise RuntimeError('Concurrent status change; merge before writing')
note = '''<!-- s3-research-20m-v1 installed -->
# 最新 S3：Research 精简已安装，准备20分钟组件实测

按用户最新要求，Research改为市场、客户、竞争各一条核心发现，每条一条声明，最多一条额外证据缺口；财务计算由Finance负责。完整计划13章节、财务明细、来源与继承校验保留。共享提示词更新为grounded-generation-v8-brief-research；正式实验需冻结新版本。

Research父节点正文、声明、结构修复、Critic、条件修订共享最多1200秒；正文输出最多640、声明最多2304 tokens，仍服从更低原配置上限。此次真实验证只执行Research生成组件及严格校验，不包含Critic或完整D；硬截止不等于保证有效产出。

已安装9文件，保留5原版本与全部历史。完整离线823 passed/25 deselected/3 subtests；安装83 passed，运行器27 passed。一次安装测试命令因文件路径拼写错误未收集测试，已更正并通过，日志保留。

此次使用原已批准90分钟池剩余34请求/409083预算tokens/1815.312秒，其中最多1200秒用于本组件；旧未知用量不退款，不重置全历史。实测尚未完成，结果以 docs/final_sprint/s3-research-20m-v1/run_01/probe/result.json 为准。

未自动重启完整D、调用Gemini、启动正式S5八槽或下一包。交接：docs/final_sprint/s3-research-20m-v1/HANDOFF.md。

---
<!-- preserved previous records -->

'''
(REPORT / 'HANDOFF.md').write_text(note + '\n' + (REPORT / 'IMPLEMENTATION.md').read_text(encoding='utf-8'), encoding='utf-8')
status.write_bytes(note.encode('utf-8') + previous)
(REPORT / 'STATUS_AT_PROBE_START.md').write_bytes(status.read_bytes())
shutil.copy2(__file__, REPORT / 'record_start.py')
print('Pre-run handoff and latest status recorded; historical status preserved.')
