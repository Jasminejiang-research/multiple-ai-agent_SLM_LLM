<!-- s3-research-20m-v1 actual-result -->
# 最新 S3：Research≤20分钟组件实测结果

结果：failed；Research生成组件通过=False，产物保存=False。含清理总耗时13分36.73秒，生成/校验13分34.73秒，共享上限1200秒。仅Research正文、声明、一次结构修复及严格校验；Critic/语义修订/完整D/完整计划书均未执行或产出。

本次3请求、24572已知tokens、24572预算扣记；未知用量调用0。原90分钟池累计5请求/115489预算tokens/4401.422秒，剩31请求/384511预算tokens/998.578秒。全历史另计21请求/412058预算tokens/14594.905秒；旧85923未知预留保留，未退款。

代码：三类各1发现，每条1声明，最多1条额外证据缺口；Finance负责财务计算。Research父节点含Critic/修订共享1200秒，正文640、声明2304输出上限，服从更低原配置。完整13章节/财务明细/来源校验保留。最终离线824通过（613+211），最终增量安装53通过、前阶段安装83通过、运行器27通过；审计记录完整性passed，272源码和3279历史文件逐哈希核验。服务停止及资源结果见原始result。

质量边界：正文NCES年份/分母已正确，但仍有未经证实的MBA增长、需求与市场空白推断，customer rationale恰在160字符处以“if”结束。这是语义残句，不能以结构成功宣称内容质量通过。首轮声明自然结束但一条假设状态标签错误，触发唯一结构修复；详细结果和原文均保留。

交接：docs/final_sprint/s3-research-20m-v1/HANDOFF.md。下一入口是Research含Critic/修订的质量与父节点时间验证，再评估完整D；此次实测仅证明生成组件结果。正式S5须重新冻结grounded-generation-v8-brief-research，不能混合旧版本。未自动重启完整D、调用Gemini或下一包。

---

## Physical model requests

| Stage | Input tokens | Output tokens | Seconds | Finish reason |
|---|---:|---:|---:|---|
| 1. body/generate | 4255 | 385 | 170.5 | stop |
| 2. grounding/generate | 8522 | 1330 | 351.875 | stop |
| 3. grounding/structure_repair | 8708 | 1372 | 289.125 | stop |

The physical HTTP success flag is distinct from a complete logical contract passing. The first grounding response returned naturally but failed its assumption/evidence-status cross-field rule. No response was silently truncated or changed by code. The final artifact, if present, is assembled from the exact frozen body and model-selected references.

## Evidence paths

- `run_01/probe/result.json`, `events.jsonl`, `artifact.json` and `Research.md` when produced.
- `run_01/audit/*.raw.txt` and `*.usage.json`: exact recorded responses and usage.
- `validation/research_probe_integrity.json`: record integrity, exact reconstruction and budget audit.
- `validation/research_body_quality.md`: source-backed quality limitations, separate from schema checks.
- `runtime_source.zip`, latest `runtime_manifest.json`, `change_manifest.json`, `before/`, `pre_probe_amendment/`: current source and all changed earlier versions.
- `validation/full_amended.log` (613), `slm_amended.log` (211), `installed_amended.log` (53), `installed_final.log` (83), `runner_installed.log` (27).

Recorded server stop: `owned_process_tree_terminated`. Power cleanup: `released`. Resource status: `passed`. The 20-minute production parent limit includes its Critic/revision in code, but this real component test does not measure those phases. No assertion of a complete plan within 90 minutes is made.
