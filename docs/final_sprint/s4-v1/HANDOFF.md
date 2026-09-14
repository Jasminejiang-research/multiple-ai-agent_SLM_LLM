# S4 工程与离线验证交接

2026-09-07（Europe/Berlin）。目标工作区：`C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`。

本轮按用户最新指令执行 S4 工程与离线验证，公共预算与 D 预检暂缓。旧 S3 交接中要求等待完整 D 的后续依赖，由本次指令明确限定为可继续离线工程；没有把 D 标为通过，也没有批准新预算。正式实验 **0/8**，本轮真实模型调用 **0**。

## 实际交付

- `evaluation/s4_runner.py`：两 case 分块、种子 20260906、块内 A–D 顺序固定、恰好八个槽位。正式 plan 与 synthetic rehearsal 分开。请求前 fsync 占用槽位；状态由追加日志恢复，CSV 只是投影。已结束的成功、失败、取消行不重跑。中断不确定行须明确核对并标失败，不能恢复成未运行；截断原日志与失效锁留档。
- 正式入口懒加载真实 provider。冻结门同时检查输入批准记录、两份设计及计划 hash、实际工作树代码/prompt/config、Python/SDK/framework 版本、共同预算、Gemini 配额/消费批准、A/B/C smoke、完整真实 D preflight 和执行授权。当前全部正式入口保持锁定。没有修改 1024/18/160000 等候选预算；S4 合成夹具沿用 S2 宽松测试额度，不能当作公共额度建议或输出长度可行性证据。
- `evaluation/s4_metrics.py`：从 run/node/role/logical-task/attempt/handoff 记录重算。原始 usage 留存，provider total 不重复加 thinking；visible output、已返回 thinking、已知 token 小计、未知 token 原因分别保留。失败实际请求计入，分批/repair/transport retry 不增加已有 logical task 分母。Revision 归入 Revision。
- `workflow/review_graph.py`：完整稿首次契约通过时间有独立事件；terminal/export 的检查状态与“存在可评分最终稿”分开。失败但已有最终稿仍可内部留存和评分，未完成 run 的成功时间保持缺失。补充 Export 的确定性逻辑任务。`review_runtime.py` 对每次物理调用保存 native diagnostic（包括失败/部分响应）。
- `evaluation/s4_resources.py`：运行前基线、周期与结束采样，RAM/VRAM/pagefile 分开汇总。D 复用 S3 的持续内存门；末尾资源失败也不能记为成功。云端硬件资源不可见，本机样本仅为 host 观测；缺项不填 0，部分覆盖单列。
- `evaluation/s4_blind.py`：只从实际存在的最终 artifact 生成匿名内容，包含原文、引用、Confidence、声明/前提及财务明细；身份映射单独放 `private/`。8 份可评分时产生 10 份评分副本，其中 2 份隐藏复评。无人工质量分或支持性结论被填写。
- 评分先于 Gold 阶段。为避免 Gold 条数泄露隐藏复评，唯一输出的候选 ledger 暂存 `private/`；所有匿名六维评分完成后，`gold-phase` 释放一份共用 ledger 和 coverage 表，仅核验八份 canonical 输出，不重复审计 claim、不新增模型运行。候选提取同时扫描章节正文、key claims、前提和财务行；仍须人工补漏、原子化、语义去重与全部决策关键声明覆盖确认。
- `evaluation/s4_statistics.py` / `s4_export.py`：固定六维权重和公式；仅 B−A、C−B、C−D；逐 case 原值/状态、完整配对数、差值均值/中位数/线性插值 IQR、改善/持平/恶化数。比例先按 case 再等权汇总。调度审查占比不设置改善方向。不填伪质量、CI 或显著性结果。
- 原 `app.py` 增加 `S4 Experiment Review` 只读入口，明确展示 Gemini A/B/C 和 D CLI 路径、节点/critic/gate/revision/初稿/有效稿、状态与资源。该模式禁用生成按钮；旧模式和 SQLite 历史详情保留。新事件按角色/attempt/artifact 展开，避免只剩最后一个 `s2.gate`。无新前端、无 SLM 专用 UI、无数据库迁移。
- S3 兼容：逐物理调用的 `physical_provider_diagnostic` 与已有阶段级 `native_provider_diagnostic` 分开。旧隔离测试仅为新增的 S4 实验运行器/资源适配层列出精确可导入模块，运行器的模型导入必须延迟到调用时；新增独立进程测试阻止所有 SLM 导入后仍能导入原 Gemini 产品与 S4 只读视图。其他代码仍禁止依赖 SLM。

## 可复用命令

以下 CLI 接口已在隔离副本实际执行；每条命令、退出码、日志 hash 见 `offline_audit.json` 及 `command_logs/`。安装后复核见 `installed_validation_final.txt`。WindowsApps Python 在沙箱内不可访问时，应使用同一个环境的经授权执行入口，不重建虚拟环境。

```powershell
Set-Location -LiteralPath 'C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM'
./.venv/Scripts/python.exe -B -m evaluation.s4 status --experiment docs/final_sprint/s4-v1/dry_run
./.venv/Scripts/python.exe -B -m evaluation.s4 check-freeze --experiment docs/final_sprint/s4-v1/dry_run
./.venv/Scripts/python.exe -B -m evaluation.s4 resume --experiment docs/final_sprint/s4-v1/dry_run
```

`check-freeze` 预期退出 **2** 并列出未满足依赖；这是通过了锁验证。`resume` 仅恢复记录，不调用模型。带 `--recover-dead-lock` 时必须通过本机进程已不存在的检查；活跃或无法确认的进程锁不会删除。`resolve-unknown --planned-id ... --note ...` 只将未知状态核对为失败，绝不重跑该槽位。

新离线材料目录须使用未存在的名称，避免覆盖已留证的输出：

```powershell
./.venv/Scripts/python.exe -B -m evaluation.s4 dry-run --output-dir <新的正式计划目录>
./.venv/Scripts/python.exe -B -m evaluation.s4 rehearsal --output-dir <新的纯合成目录>
./.venv/Scripts/python.exe -B -m evaluation.s4 export --experiment <实验目录> --output-dir <新的导出目录>
./.venv/Scripts/python.exe -B -m evaluation.s4 blind-pack --experiment <实验目录> --output-dir <新的评分包目录>
./.venv/Scripts/python.exe -B -m evaluation.s4 gold-phase --pack <已完成匿名评分的包目录>
./.venv/Scripts/python.exe -B -m evaluation.s4 export --experiment <实验目录> --human-pack <评分包目录> --output-dir <新的审核后导出目录>
```

`execute --experiment ...` 已实现并实际验证当前退出 2、不会构造模型。正式执行须在 S5 授权和所有适用冻结门满足后进行，本轮没有调用可通过门禁的 execute。真实 Gemini/Granite 完整调度仅有工程和 mock 验证，仍需 S5 前的真实 smoke/预检，不能写成已实测通过。

复现整个本包 CLI 工程验收：

```powershell
./.venv/Scripts/python.exe -B -m evaluation.s4_audit --output-dir <新的S4离线审计目录>
./.venv/Scripts/python.exe -B -m pytest -q tests slm/tests -p no:cacheprovider
./.venv/Scripts/python.exe -m streamlit run app.py
```

## 证据位置

| 路径 | 内容与边界 |
|---|---|
| `dry_run/plan.json`, `manifest.csv`, `freeze.json` | 八个未执行的正式槽位、公共预算/D pending 状态 |
| `dry_export_final/` | 未运行状态的可复算导出，不是实验结果 |
| `review_templates/reviewer/` | 评分表头、rubric、审计指南；无候选模型输出 |
| `synthetic_rehearsal/runs/` | 八条合成工程流程的原始 events、result、internal_export；绝非正式/预检模型输出 |
| `synthetic_blind_pack/reviewer/` | 10 份匿名合成评分副本及空白评分表 |
| `synthetic_blind_pack/private/` | 独立身份映射、8 份 canonical 的 Gold 候选、覆盖确认表；不交给盲评分者 |
| `synthetic_export_final/` | CSV、配对表、角色分项、原始事件溯源 hash、Altair/Vega-Lite 图表 |
| `offline_audit.json`, `command_logs/` | 已执行 CLI、返回值、mock/正式隔离检查 |
| `validation_summary.json`, `validation/` | 完整实际测试结果，含修复前失败与测试入口错误记录 |
| `EVIDENCE_MAP.md` | 论文问题 1–14 到代码/测试/证据/限制的映射 |
| `code_install_receipt.json`, `preservation_audit.json`, `before/` | 安装 hash、旧文件备份、历史数据与其他既有修改核对 |

图表复用已安装 Altair 6.2.1；未安装/升级依赖。`.vl.json` 是离线图表规范，可在原 Streamlit 的实验视图显示；独立 HTML 预览需要 renderer CDN。无人工评分时不生成 Academic Quality 或 claim 指标图。RAM/GPU/pagefile 合成值、15-token mock 调用计数等只检验算法，不是硬件或模型实测。

## 剩余阻塞与下一包

1. 公共输出预算继续暂缓。S3 记录的 Finance 21/27 行 JSON 测量为 1919/2552 tokens，1024 起始上限问题未解决；8192 候选未经批准，所有原配置保留。
2. S3 CPU 长输入规避和 warmup 成功仍有效，但真实 Research/ComponentCritic/Finance/Writer 四组件和完整 D smoke 没有执行，S3 不可整体验收。
3. 两 case 的完整 brief、财务情景与证据在当前 case 文件仍为 pending；Gemini 实际额度/消费与公共配置仍待确认和冻结。
4. 六维人工评分、约 20% 隐藏复评、全部决策关键声明的一次 Gold 审计尚未开始；预留 1 小时不等于完成记录。

下一编号包为 **S5**，但进入前须先解除以上依赖，并读取当前状态、S3 `BUDGET_PROPOSAL.md`/`HANDOFF.md`、本交接、S0 协议与 rubric、`freeze.json` 门禁。用户恢复公共预算/D工作时先继续 S3；不得直接把本包合成结果或既有 warmup 当完整 D 通过。没有启动下一包，没有生成论文/PPT，也没有向桌面 S5 结果目录写占位结果。

## 最终安装验收（2026-09-07）

完整离线整合：623 passed、25 deselected、3 subtests passed，122.84 秒；补充 UI 渲染 1 passed，9.02 秒。末次状态统计专项 28 passed，16.52 秒；目标目录最终 S4/UI/SLM 相关复核 **82 passed，22.26 秒**。

未运行槽位的原始零请求/零 token 保留，但不计入完整资源配对；部分内存峰值只作观测下界，不能当完整配对值。完成率仍保留全部计划行。当前有效派生材料为 `dry_export_final/` 和 `synthetic_export_final/`；早先导出保留作开发审计，不用于最终比较。

最终修复回执与旧源码在 `amendments/statistic_states/`；当前代码/运行时/材料 hash 在 `final_version_manifest.json`，验证汇总在 `final_validation.json`。原始 synthetic events、正式未运行计划、S0–S3材料及旧用户修改保持。正式0/8，真实模型调用0，预算/D/S5状态未改变。
