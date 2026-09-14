"""Record actual Research component outcome without changing runtime or history."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil

STAGE=Path(__file__).resolve().parent
REPO=Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT=REPO/'docs/final_sprint/s3-research-20m-v1'
RUN=REPORT/'run_01/probe'
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def fmt(seconds): return f'{int(seconds//60)}分{seconds%60:.2f}秒'
result=load(RUN/'result.json')
audit_path=STAGE/'validation/research_probe_integrity.json'
audit=load(audit_path)
if audit['integrity_status']!='passed': raise RuntimeError('Resolve integrity audit failures before finalizing')
if result['research_probe_passed'] != audit['research_probe_verified']: raise RuntimeError('Outcome mismatch')
for entry in load(REPORT/'external_dependencies.json'):
    if sha(Path(entry['path']))!=entry['sha256']: raise RuntimeError('External dependency changed: '+entry['path'])
status=REPO/'docs/final_sprint_status.md'
prior=(REPORT/'STATUS_AT_PROBE_START.md').read_bytes()
if status.read_bytes()!=prior: raise RuntimeError('Concurrent latest-status change; merge required')
for name in ('audit_research_probe.py','research_probe_integrity.json','research_body_quality.md'):
    shutil.copy2(STAGE/'validation'/name,REPORT/'validation'/name)
calls={}
for line in (RUN/'events.jsonl').read_text(encoding='utf-8').splitlines():
    row=json.loads(line)
    if row['kind']=='call': calls[row['payload']['attempt_id']]=row['payload']
rows=[]
raw_dir=REPORT/'run_01/audit'
raw_dir.mkdir(exist_ok=False)
for i,call in enumerate(calls.values(),1):
    label=f'{i:02d}_{call["generation_stage"]}_{call["purpose"]}'
    if call.get('raw_output') is not None:
        (raw_dir/(label+'.raw.txt')).write_text(call['raw_output'],encoding='utf-8')
    if call.get('usage_raw') is not None:
        (raw_dir/(label+'.usage.json')).write_text(json.dumps(call['usage_raw'],ensure_ascii=False,indent=2),encoding='utf-8')
    rows.append(f'| {i}. {call["generation_stage"]}/{call["purpose"]} | {call.get("prompt_tokens")} | {call.get("output_tokens")} | {call.get("elapsed_seconds")} | {call.get("finish_reason")} |')
produced=result['research_artifact_produced']
passed=result['research_probe_passed']
if produced:
    artifact=load(RUN/'artifact.json')
    payload=artifact['payload']
    text=['# AI 教育 Research 组件产物','',
          '模型原始正文的便读导出。完整契约已校验；未执行 Critic，也不是完整计划书。内容质量问题见 validation/research_body_quality.md。','',
          payload['analysis_summary'],'']
    for key,title in (('market_trends','市场'),('customer_notes','客户'),('competitor_assumptions','竞争')):
        for finding in payload[key]:
            text += ['## '+title+'：'+finding['topic'],'',finding['finding'],'',finding['rationale'],'']
    text += ['## 待人工核查',''] + ['- '+question for question in payload['needs_human_review']]
    (RUN/'Research.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
pool=result['pool_cumulative']; history=result['all_history_cumulative']; remaining=result['pool_remaining']
used=result['this_probe']; usage=used['known_usage']
summary=f'''<!-- s3-research-20m-v1 actual-result -->
# 最新 S3：Research≤20分钟组件实测结果

结果：{result['status']}；Research生成组件通过={passed}，产物保存={produced}。含清理总耗时{fmt(result['elapsed_seconds'])}，生成/校验{fmt(result['inference_elapsed_seconds'])}，共享上限1200秒。仅Research正文、声明、一次结构修复及严格校验；Critic/语义修订/完整D/完整计划书均未执行或产出。

本次{used['request_count']}请求、{usage['actual_total_tokens_known']}已知tokens、{used['charged_total_tokens']}预算扣记；未知用量调用{usage['usage_missing_calls']}。原90分钟池累计{pool['request_count']}请求/{pool['charged_total_tokens']}预算tokens/{pool['elapsed_seconds']:.3f}秒，剩{remaining['request_count']}请求/{remaining['charged_total_tokens']}预算tokens/{remaining['elapsed_seconds']:.3f}秒。全历史另计{history['request_count']}请求/{history['charged_total_tokens']}预算tokens/{history['elapsed_seconds']:.3f}秒；旧85923未知预留保留，未退款。

代码：三类各1发现，每条1声明，最多1条额外证据缺口；Finance负责财务计算。Research父节点含Critic/修订共享1200秒，正文640、声明2304输出上限，服从更低原配置。完整13章节/财务明细/来源校验保留。最终离线824通过（613+211），最终增量安装53通过、前阶段安装83通过、运行器27通过；审计记录完整性passed，272源码和3279历史文件逐哈希核验。服务停止及资源结果见原始result。

质量边界：正文NCES年份/分母已正确，但仍有未经证实的MBA增长、需求与市场空白推断，customer rationale恰在160字符处以“if”结束。这是语义残句，不能以结构成功宣称内容质量通过。首轮声明自然结束但一条假设状态标签错误，触发唯一结构修复；详细结果和原文均保留。

交接：docs/final_sprint/s3-research-20m-v1/HANDOFF.md。下一入口是Research含Critic/修订的质量与父节点时间验证，再评估完整D；此次实测仅证明生成组件结果。正式S5须重新冻结grounded-generation-v8-brief-research，不能混合旧版本。未自动重启完整D、调用Gemini或下一包。

---
'''
shutil.copy2(REPORT/'HANDOFF.md',REPORT/'HANDOFF.before_real_result.md')
details='''
## Physical model requests

| Stage | Input tokens | Output tokens | Seconds | Finish reason |
|---|---:|---:|---:|---|
'''+ '\n'.join(rows)+f'''

The physical HTTP success flag is distinct from a complete logical contract passing. The first grounding response returned naturally but failed its assumption/evidence-status cross-field rule. No response was silently truncated or changed by code. The final artifact, if present, is assembled from the exact frozen body and model-selected references.

## Evidence paths

- `run_01/probe/result.json`, `events.jsonl`, `artifact.json` and `Research.md` when produced.
- `run_01/audit/*.raw.txt` and `*.usage.json`: exact recorded responses and usage.
- `validation/research_probe_integrity.json`: record integrity, exact reconstruction and budget audit.
- `validation/research_body_quality.md`: source-backed quality limitations, separate from schema checks.
- `runtime_source.zip`, latest `runtime_manifest.json`, `change_manifest.json`, `before/`, `pre_probe_amendment/`: current source and all changed earlier versions.
- `validation/full_amended.log` (613), `slm_amended.log` (211), `installed_amended.log` (53), `installed_final.log` (83), `runner_installed.log` (27).

Recorded server stop: `{result['server_stop']['status']}`. Power cleanup: `{result['power_cleanup']}`. Resource status: `{result['resources']['status']}`. The 20-minute production parent limit includes its Critic/revision in code, but this real component test does not measure those phases. No assertion of a complete plan within 90 minutes is made.
'''
(REPORT/'HANDOFF.md').write_text(summary+details,encoding='utf-8')
status.write_bytes(summary.encode('utf-8')+prior)
receipt=dict(finalized_at_utc=datetime.now(timezone.utc).isoformat(),result_sha256=sha(RUN/'result.json'),
    integrity_audit_sha256=sha(REPORT/'validation/research_probe_integrity.json'),
    research_artifact_produced=produced,research_probe_verified=passed,critic_verified=False,complete_d_verified=False,
    runtime_files_verified=272,old_history_files_verified=3279,public_config_changed=False,
    process_cleanup_status=result['server_stop']['status'],power_cleanup=result['power_cleanup'])
(REPORT/'final_run_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(__file__,REPORT/'finalize_probe.py')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
