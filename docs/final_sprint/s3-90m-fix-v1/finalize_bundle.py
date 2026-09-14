"""Create factual post-run handoff after results and external cleanup proof exist."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil

REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-90m-fix-v1'
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
result=load(REPORT/'run_01/probe/result.json')
cleanup=load(REPORT/'run_01/audit/external_cleanup.json')
history=load(REPORT/'history_inventory.json')
mismatches=[r['path'] for r in history if not (REPO/r['path']).exists() or sha(REPO/r['path'])!=r['sha256']]
manifest=dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),result=result,
    historical_files_checked=len(history),historical_mismatches=mismatches,external_cleanup=cleanup,
    code_changes=load(REPORT/'change_manifest.json')['changes'],
    public_config_sha256=sha(REPO/'slm/configs/granite_preflight_cpu_v2.json'))
(REPORT/'final_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
if mismatches: raise RuntimeError('Historical files changed: '+str(mismatches))
budget=result['budget']; phases=result['phases']; resources=result.get('resources') or {}
research=phases.get('research_probe',{}); full=phases.get('full_d',{})
duration=result['elapsed_seconds']; produced=result['complete_proposal_produced']
lines=[
    '# 90分钟 SLM 恢复验证交接', '',
    f"实际结论：status={result['status']}；完整计划书={'已生成' if produced else '尚未生成'}。Research={research.get('status')}，完整D={full.get('status')}。",
    f"本次执行用时{duration:.3f}秒（{duration/60:.2f}分钟），硬截止5400秒。LLM与SLM每份计划书时钟独立，本包真实Gemini调用0、正式实验0/8。",
    '', '## 实现与验证', '',
    '10文件修复：原生页文件采样、精确进程身份及有界停机、共同两阶段prompt压缩、共享证据枚举、原声明证据索引、Writer预检入口统一。261文件源快照及原版本备份已保存；完整13章、财务精度、引用、lineage、Critic及修复次数规则保留。',
    '完整离线733 passed / 25 deselected / 3 subtests passed，196.77秒；安装后108 passed，7.72秒；预算运行器10 passed，2.02秒；pip check通过。',
    'prompt=grounded-generation-v6-compact-two-stage；canonical=proposal-grounding-v5-two-stage。旧prompt结果不混入新冻结协议。',
    '', '## 真实预算与资源', '',
    f"本次请求{budget['this_run_request_count']}，预算扣记{budget['this_run_charged_total_tokens']}tokens；累计{budget['cumulative_request_count']}请求/{budget['cumulative_charged_total_tokens']}预算tokens/{budget['cumulative_elapsed_seconds']:.3f}秒。预算扣记不等于已知实际tokens，未知用量的预留不回填为0。",
    f"资源门={resources.get('status')}，原因={resources.get('reason')}；最低空闲RAM={resources.get('min_available_ram_bytes')}bytes，页文件最大增长={resources.get('peak_pagefile_delta_bytes')}bytes。",
    f"历史{len(history)}文件hash均保留；服务停止与lease核验见run_01/audit/external_cleanup.json。",
    '', '## 文件与下一入口', '',
    '真实完整记录：run_01/probe/result.json；原始请求/返回：各phase events.jsonl及run_01/audit/；逐字展开独立复核：run_01/audit/assembly_audit.json。',
    f"完整计划书目录：{result.get('proposal_directory','无')}。", '',
    '尚未进行人评或Gold审计，结构通过不等于事实正确。已识别Research正文中的学位统计时间段与百分比分母误读；不能手工改入模型产物或当作已修复事实。',
    '下一入口按实际阻塞继续S3恢复/验收；没有自动运行S5正式八槽。正式比较仍需匹配公共预算/新prompt冻结及原S5依赖。', '',
]
(REPORT/'HANDOFF.md').write_text('\n'.join(lines),encoding='utf-8')
status=REPO/'docs/final_sprint_status.md'
old=status.read_bytes()
if not old.startswith(b'<!-- s3-90m-fix-v1 running -->'): raise RuntimeError('Concurrent status update; handoff saved but current status not overwritten')
header=f'''<!-- s3-90m-fix-v1 final -->
# 最新 S3：90分钟恢复验证已结束

status={result['status']}；完整计划书={'已生成' if produced else '尚未生成'}；Research={research.get('status')}，完整D={full.get('status')}。真实{budget['this_run_request_count']}请求/{duration:.3f}秒。详细实际结论与阻塞见docs/final_sprint/s3-90m-fix-v1/HANDOFF.md和run_01/probe/result.json。

10文件修复已安装；完整离线733 passed/25 deselected/3 subtests passed、安装后108 passed、预算运行器10 passed。Windows原生页文件采样与绑定身份停机、无损两阶段prompt压缩、预检Writer一致性已实现。每份计划书5400秒独立截止；旧请求/token额度不重置。累计{budget['cumulative_request_count']}请求/{budget['cumulative_charged_total_tokens']}预算tokens/{budget['cumulative_elapsed_seconds']:.3f}秒，后续只承接本包最新result，不使用旧余额。

prompt=v6-compact-two-stage，canonical仍v5；完整契约和正式公共配置不变。保留{len(history)}历史文件及before备份；Gemini调用0、正式实验0/8，未自动启动下一工作包。结构验收与人评质量分开，不能由局部Research通过推断完整D成功。

---
<!-- s3-90m-fix-v1 previous records -->

'''
status.write_bytes(header.encode('utf-8')+old)
source=Path(__file__).resolve()
if source.parent!=REPORT: shutil.copy2(source,REPORT/source.name)
print(json.dumps(dict(status=result['status'],complete_proposal_produced=produced,handoff=str(REPORT/'HANDOFF.md'),history_files_verified=len(history))))
