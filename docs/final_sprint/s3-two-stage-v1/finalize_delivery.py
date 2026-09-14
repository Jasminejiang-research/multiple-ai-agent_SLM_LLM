from pathlib import Path
from datetime import datetime,timezone
import hashlib,json

ROOT=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
def load(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
result=load(ROOT/'run_01/probe/result.json')
assembly=load(ROOT/'run_01/audit/assembly_audit.json')
cleanup=load(ROOT/'run_01/audit/external_cleanup.json')
changes=load(ROOT/'change_manifest.json')['changes']
sources=load(ROOT/'runtime_manifest.json')['files']
history=load(ROOT/'history_inventory.json')
checks=dict(runtime_files=len(sources),changed_files=len(changes),historical_files=len(history),
    installed_mismatches=[r['path'] for r in sources if digest(REPO/r['path'])!=r['sha256']],
    snapshot_mismatches=[r['path'] for r in sources if digest(ROOT/'runtime'/r['path'])!=r['sha256']],
    backup_mismatches=[r['path'] for r in changes if r['before_sha256'] and digest(ROOT/'before'/r['path'])!=r['before_sha256']],
    historical_mismatches=[r['path'] for r in history if not (REPO/r['path']).exists() or digest(REPO/r['path'])!=r['sha256']],
    external_dependency_mismatches=[r['path'] for r in load(ROOT/'external_dependencies.json') if digest(Path(r['path']))!=r['sha256']])
assert not any(value for key,value in checks.items() if key.endswith('mismatches')),checks
carry=load(ROOT/'budget_carryover.json')
assert digest(Path(carry['result_path']))==carry['sha256']
budget=result['budget']
phase_budgets=[phase['budget'] for phase in result['phases'].values() if 'budget' in phase]
known_tokens=sum(p['actual_total_tokens_known'] for p in phase_budgets)
unknown_calls=sum(p['usage_missing_calls'] for p in phase_budgets)
retained_tokens=budget['this_run_charged_total_tokens']-known_tokens
remaining=dict(requests=36-budget['cumulative_request_count'],tokens=500000-budget['cumulative_charged_total_tokens'],
               seconds=14400-budget['cumulative_elapsed_seconds'])
manifest=dict(finalized_at_utc=datetime.now(timezone.utc).isoformat(),checks=checks,assembly_audit=assembly['status'],
    budget=budget,remaining=remaining,result_sha256=digest(ROOT/'run_01/probe/result.json'),
    runtime_archive_sha256=digest(ROOT/'runtime_source.zip'),public_budget_changed=False,cleanup=cleanup,
    complete_proposal_produced=result['complete_proposal_produced'],workflow_status=result['status'],
    this_run_measured_tokens=known_tokens,usage_missing_calls=unknown_calls,retained_unknown_usage_charge=retained_tokens)
with (ROOT/'final_manifest.json').open('x',encoding='utf-8') as stream: json.dump(manifest,stream,indent=2)
tasks=[]
for path in (ROOT/'run_01/probe').rglob('events.jsonl'):
    latest={}
    for line in path.read_text(encoding='utf-8').splitlines():
        row=json.loads(line)
        if row['kind']=='logical_task': latest[row['payload']['logical_task_id']]=row['payload']
    tasks.extend(latest.values())
errors=[dict(task=t['logical_task_id'],stage=t['attempts'][-1].get('generation_stage'),error=t['attempts'][-1]['error'])
        for t in tasks if t.get('attempts') and not t.get('completed') and t['attempts'][-1].get('error')]
research=result['phases'].get('research_probe',{})
full=result['phases'].get('full_d',{})
outcome='已生成完整 canonical 计划书' if result['complete_proposal_produced'] else '尚未生成完整计划书'
handoff=f'''# A–D 两阶段生成交接

更新时间：{manifest['finalized_at_utc']}。用户已批准该方案；代码已实施并安装，真实验证已结束。**{outcome}**。Research状态={research.get('status')}；完整D状态={full.get('status')}；总测试状态={result['status']}。

## 完成内容

- 统一 A–D 的两阶段生成：先正文及完整财务值，后声明和原文片段选择，最后严格 canonical 组装与校验。原13章节、四批写作、来源、财务、lineage和人工Gold要求保留。
- 两个阶段共用原节点时间、请求/token预算及一次结构修复。Critic保持单阶段，条件Revision数量不变；正常A/B/C/D请求数8/15/18/18。
- 所有真实调用和阶段单独记账；正文草稿不会提前算作完整契约通过；展开的摘录不冒充模型输出token。完整候选目录、原始选择和展开映射落盘。
- 16个文件改动、其中3个新增；256文件冻结快照。13个既有文件的安装前版本保存在before/。2254个旧sprint与data文件hash全部保持，公共CPU配置hash保持，未commit。

## 实际验证

- 完整离线回归：702 passed、25 deselected、3 subtests passed，172.06秒（validation/full_final.log）。
- 安装后两阶段与本地适配专项：30 passed，7.40秒（validation/installed.log）。累计预算运行器：7 passed，3.20秒（validation/runner.log）。现有依赖pip check通过，未安装或升级依赖。
- 两个案例的合成18请求演练中，AI教育最大输入19324tokens/74640字符，智能戒指21205tokens/88979字符；加8192输出后均在32K内。原始过长目录问题与修正后的演练均保留，合成结果不是模型能力证据。
- 真实本轮新增 {budget['this_run_request_count']} 请求、用时{budget['this_run_elapsed_seconds']:.3f}秒。HTTP请求={result['http_requests']}。已知实测用量={known_tokens}tokens；{unknown_calls}次请求用量未知，保留{retained_tokens}tokens预留扣记。本轮预算扣记合计{budget['this_run_charged_total_tokens']}tokens，不能当作实际生成量。累计{budget['cumulative_request_count']}请求、预算扣记{budget['cumulative_charged_total_tokens']}tokens、{budget['cumulative_elapsed_seconds']:.3f}秒。
- 原额度剩余{remaining['requests']}请求、{remaining['tokens']}tokens、{remaining['seconds']:.3f}秒。后续必须承接本包run_01/probe/result.json，不能复用较早启动额度。
- 实际模型保持Granite H Micro原digest/Ollama0.33.2/CPU/32K/温度0。资源状态={result.get('resources',{}).get('status')}，截止触发={result['deadline_fired']}；结束后的进程/端口/lease核验见run_01/audit/external_cleanup.json。
- 独立审计={assembly['status']}；本次仅有正文和候选目录可供核验，均通过。尚无通过第二阶段的真实输出，因此真实canonical展开仍未验证。审计脚本已在7个合成逻辑单元上独立重建成功，不代替模型能力或人工Gold判断。

## 当前阻塞与入口

本次直接停止原因是Windows页文件占用采集（Get-CimInstance Win32_PageFileUsage）的8秒超时，触发原required_resource_telemetry_missing门。Research正文941输出tokens、230.172秒自然stop并通过；引用选择请求在输入处理期间取消。最低可用RAM为2010853376bytes（约1.87GiB），未取得持续60秒低RAM触发证据；不能将采样超时简单归因为模型能力或内存不足。未触发4小时截止、未收到第二阶段完整响应。模型服务关闭后页文件采样恢复，见RESOURCE_STOP.md。

当前应先解决高负载下页文件采样可靠性并复核资源余量，再按保留状态和剩余额度安排恢复验证；不跳过原资源门、不把本次中断当作引用生成通过或失败的证据。第二阶段未知请求已确认终止并归档lease，原始用量未知状态及预留扣记保持。

本轮错误记录（为空表示未记录失败逻辑任务）：

```json
{json.dumps(errors,ensure_ascii=False,indent=2)}
```

完整计划书目录：{result.get('proposal_directory','无')}。对外ready状态不由本次结构校验自动批准。

下一入口：以真实Research/完整D结果定位未通过门；若本次完整D通过，供后续正式预检依赖审查使用，但不等于正式八槽运行已批准。S5仍需原两case输入批准、Gemini额度与smoke、公共预算和新共享协议代码冻结、正式启动授权及后续人工评审。没有自动执行下一工作包、没有调用Gemini或正式实验。

## 文件入口

- 实现：workflow/two_stage_generation.py、workflow/contract_generation.py、workflow/review_runtime.py；版本和事件契约在schemas/及workflow/review_config.py；组件入口slm/granite_preflight.py。
- 本包IMPLEMENTATION.md、authorization.json、change_manifest.json、install_receipt.json、final_manifest.json。
- 真实阶段/请求/原始响应：run_01/probe/各阶段events.jsonl，run_01/audit/；完整总结果run_01/probe/result.json。
- 保留：before/、runtime/、runtime_source.zip、history_inventory.json、全部validation初轮失败与最终通过日志。
'''
(ROOT/'HANDOFF.md').write_text(handoff,encoding='utf-8')
status=REPO/'docs/final_sprint_status.md'
old=status.read_bytes()
with (ROOT/'STATUS_BEFORE_FINAL.md').open('xb') as stream: stream.write(old)
header=f'''<!-- s3-two-stage-v1 final -->
# 最新 S3：两阶段方案已实施，真实验证已结束

2026-09-07。用户已明确批准统一A–D两阶段生成。代码已安装，**{outcome}**。Research={research.get('status')}，完整D={full.get('status')}。最终交接：docs/final_sprint/s3-two-stage-v1/HANDOFF.md。

共享contract=proposal-grounding-v5-two-stage，prompt=grounded-generation-v5-two-stage。先锁定正文/财务值，后生成声明和精确片段选择；原完整校验保留，两个阶段只共享一次结构修复，正常A/B/C/D=8/15/18/18请求。

完整回归702 passed/25 deselected/3 subtests passed，172.06秒；安装后30 passed，7.40秒。16文件变更，256文件快照、13个before备份及2254历史文件均校验通过。正式公共预算不变。

本轮真实{budget['this_run_request_count']}请求/{budget['this_run_elapsed_seconds']:.3f}秒；已知实测{known_tokens}tokens，另{unknown_calls}次用量未知，保留{retained_tokens}tokens预留，本轮预算扣记{budget['this_run_charged_total_tokens']}tokens。原4小时额度累计{budget['cumulative_request_count']}请求/预算扣记{budget['cumulative_charged_total_tokens']}tokens/{budget['cumulative_elapsed_seconds']:.3f}秒。剩余{remaining['requests']}请求/{remaining['tokens']}tokens/{remaining['seconds']:.3f}秒；后续承接本包run_01/probe/result.json，不重置。

Research正文941输出tokens、230.172秒通过；第二阶段在输入处理时因页文件采集8秒超时触发资源门而取消，不能判断其引用是否会合格。完整D未运行。最低RAM约1.87GiB；服务已关闭，进程/端口/活动lease均为0，未知请求lease已原样归档。下一入口是S3资源采样可靠性与两阶段Research恢复验证，不能直接声明两阶段/完整D验收通过。

真实阻塞、来源/正文展开审计、结束后资源与进程核验见本包HANDOFF.md和run_01/audit/。Gemini调用0，正式实验0/8，未启动S5正式运行。新的共享协议须在正式预检后重新冻结；旧单阶段产物不混入新协议比较。

---
<!-- s3-two-stage-v1 prior records -->

'''
status.write_bytes(header.encode('utf-8')+old)
print(json.dumps(dict(outcome=outcome,checks=checks,remaining=remaining,errors=errors,handoff=str(ROOT/'HANDOFF.md')),ensure_ascii=False,indent=2))
