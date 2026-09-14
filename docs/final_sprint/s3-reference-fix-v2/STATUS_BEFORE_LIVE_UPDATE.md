<!-- s3-reference-fix-v1 current -->
# 最新 S3 财务引用修复：代码已安装，真实验证进行中

更新时间：2026-09-07T07:52:34.102759+00:00（UTC）。用户已批准按财务引用约束、评分规则和诊断反馈建议修复代码。9 个源码/测试文件已安装；6 个既有文件的原始未提交版本保存在本包 before/。共享契约升级为 proposal-grounding-v2-reference-bounds，共享提示词为 grounded-generation-v2-bounded-references；正式 A–D 模型、预算和实验范围未调整。

- 财务引用生成 schema 使用本 case 的封闭 ID 集、maxItems、uniqueItems；代码严格拒绝重复/未知引用，不自动删除生成内容。评分明确为 0–1，未知 recency 为 null；结构修复反馈包含具体路径、重复数量、片段与合法示例。保留一次结构修复和现有完整验证门。
- 离线完整回归 **667 passed / 25 deselected / 3 subtests passed，115.87 秒**；恢复运行器 **6 passed，2.26 秒**；目标仓库安装后专项 **14 passed，1.29 秒**。
- 真实原生约束探针已通过长度门：要求输出 100 项而 schema 限 2 项，实际 2 项、自然 stop；仅 1 个不同 ID，证明本机 uniqueItems 不能单独保证唯一性，代码层的重复拒绝仍是必要保障。
- 正在使用冻结 AI 教育输入、相同 Granite CPU 32K 模型单测 Research。仅 Research 自然结束并通过全部契约校验后，运行器才启动新鲜完整 D。当前尚不能宣称完整计划书成功。
- 保守计入上次失败测试的 2121.203 秒、2 次请求和 23903 tokens；本次恢复起始余额 12278.797 秒、34 次请求、476097 tokens。原生探针、Research 和完整 D 共用余额及截止时钟。单次计划书输出上限仍 8192。

报告目录：docs/final_sprint/s3-reference-fix-v1/。真实事件：run_01/probe/events.jsonl 及各 phase 子目录；最终结果在运行结束后写入 run_01/probe/result.json。不可将本次非正式能力验证当作正式 D 预检/八槽实验批准。S5 准备与其余正式运行依赖保持下列历史记录，未执行下一工作包。

---
<!-- s3-reference-fix-v1 history -->

# 最新独立 SLM 能力测试：已结束，未产出计划书

2026-09-07（Europe/Berlin）。用户已明确确认仅本次 AI 教育 SLM 测试采用 8192 单次输出、36 次请求、500000 总 tokens、各节点共享 14400 秒总时限。真实完整 D 尝试已执行，耗时 **35 分 21 秒**；Research 首轮及唯一一次结构修复都陷入 financial_value_ids 数组重复，输出 8192 tokens 后被截断，未通过契约校验。**完整计划书未生成，完整 D 验收未通过。**

实际模型请求 **2 次**，输入 7519 / 输出 16384 / 总计 23903 tokens。两次均 HTTP 200、done=true，输入 token 计数差 0；未复现旧混合 CPU/GPU 解码错误。流程因 Research 契约失败终止；未触发 4 小时截止，预算未耗尽。后续 Critic/Strategy/Finance/Writer 未执行。

模型服务已关闭，完成后核验进程/监听/活动 lease 均为 0。资源保护门 passed，最低可用 RAM 约 3.52 GiB。固定运行副本 182 文件及原始源/输入 180 文件 hash 全匹配；公共 A–D 配置未变，正式实验 0/8，Gemini 调用 0。

交接：**docs/final_sprint/s3-capability-v1/HANDOFF.md**；结果：同目录 **run_01/probe/result.json**；审计与原始响应：**run_01/audit/**。下一入口为 S3 Research 数组重复及字段约束问题的精准修复，再继续完整 D。以下 S5 准备交接原文按原时点保留，其中独立 SLM 授权和执行状态已由上述最新记录取代；S5 正式运行的其他依赖保持原状。

---
# Final sprint 最新 S5 准备记录

末次并行记录核对：已读取 docs/final_sprint/s3-capability-v1/PREPARATION.md。其状态为 prepared / awaiting additional budget authorization；仅4小时总时限已批准，8192输出、36请求、500000总tokens及节点时限补充授权尚待答复，authorization.json为approved=false。60项离线测试通过；真实模型调用0，Ollama未启动。该独立测试不等于公共A–D方案批准或完整D正式验收。

2026-09-07（Europe/Berlin）。**S5准备完成/待满足正式运行条件**；S5整体未完成。本任务真实Gemini/SLM调用0，正式启动0，八个正式槽位均未运行，未代填人工评分。

- 优先复用 S4 运行器、匿名包、Gold、指标/配对统计/图表；只新增 `evaluation/s5.py`、`s5_preparation.py`、`s5_review.py`、`s5_export.py` 和 `tests/test_s5_preparation.py`。没有修改模型、公共预算、prompt、schema、provider或共享执行逻辑。
- 完成只读依赖检查、输入校验、含未提交文件的实际复现快照、严格人工CSV校验/新版本导入、S5目录导出。依赖检查与 pip check通过，原UTF-16 requirements保持不动；密钥只查是否存在。新增入口不能启动模型或冻结配置。
- 最终 **28 passed，8.22秒**；10条离线CLI符合预期，check-inputs退出2正确阻止正式运行；207文件准备快照校验通过，570个已存源文件和S0–S4历史文件未变。未运行重负载/整合回归，未重跑S4合成工作流。真实人工字段仍空。
- 独立交接：`docs/final_sprint/s5-prep-v1/HANDOFF.md`。有效快照：同目录 `reproduction_preparation_final/`，明确 `preparation_only_not_frozen`。日志、安装/保留核验、八槽位dry_run与纯synthetic材料均在该目录，合成数据禁止进入正式结果。
- 并行SLM任务协调信息是准备独立非正式AI教育完整计划书测试，后续以其 `s3-capability-v1/` 及最新明确授权/交接为准；本任务不判定其已通过。8192是否批准以最新明确用户记录为准，本任务未新增/应用预算；旧S4“暂缓/未经批准”文字作为历史保留，不能替代并行任务的新授权。
- 正式阻塞：两case完整输入批准、D完整预检通过或失败/未运行处置获批且落实、Gemini额度/消费与A/B/C匹配smoke、公共配置/代码冻结、预检结束后的必要整合回归、用户明确启动。当前S4 runner只支持完整D go路线；若选择失败/未运行处理，需待明确决定后补齐相应共享门禁，不能绕过。
- 下一入口：先读独立S5交接及最新并行记录，用 `evaluation.s5 check-inputs --experiment <正式目录>` 复核；条件齐备且用户明确启动后，仍由 `evaluation.s4 execute --experiment <正式目录>` 正式执行。人工返回后只 import-review/校验/export复算，不再调用模型。

以下为合并时重新读取并完整保留的既有交接；上面的S5准备状态更新不覆盖其他任务的授权与运行事实。

---

# Final sprint 执行交接

更新时间：2026-09-07（Europe/Berlin）。当前工作包：**S4 工程与离线验证**。状态：**complete（仅本次授权的工程/离线范围）**。S0–S2 已完成；S3 CPU 规避修复仍有效，但完整 D 验收未通过。**公共预算与 D 预检继续暂缓；S5 未启动，正式实验 0/8，本轮真实模型调用 0。**

## 最新完成与验收

- 八槽位运行器、固定种子分块顺序、追加落盘、预算停止、恢复与不确定请求处理已实现。成功/失败行均不自动重跑；正式执行门保持锁定。
- 执行状态、终端检查、可评分最终稿、人工处理状态分开。首次完整契约时间与 Export 确定性任务有独立记录；已有可评分失败稿可以内部导出。
- run/node/role/attempt/handoff、原始 provider usage、visible/thinking/total、失败调用、重试/repair/Revision 与 RAM/VRAM/pagefile 分项汇总。未触发、漏采、零分母和失败有不同状态。
- 匿名六维评分与共享 Gold Ledger、正文/声明/财务明细候选定位、覆盖确认和严格导入已实现。8 份可评分时约 2 份隐藏复评，仅增加评分副本；Gold 只核验一次 canonical 输出。人工字段保持待填。
- B−A、C−B、C−D 的逐 case 原值、配对差、均值/中位数/IQR、改善计数、等权比例与图表脚本可复算。无人工结论时不产生伪质量或 claim 结果。
- 原 Streamlit 新增只读 S4 Experiment Review，展示 Gemini 优化路径和新增节点；旧产品/历史兼容，D 继续 CLI。没有开发新前端或迁移 DB。

## 实际验证

- 现有基线：**596 passed、25 deselected、3 subtests passed，87.57 秒**。
- 修复后完整整合回归：**623 passed、25 deselected、3 subtests passed，122.84 秒**。
- 补充 Streamlit 新节点/待审提示/离线图表实际渲染：**1 passed，9.02 秒**。
- CLI 验收：8 个正式槽位全部 not_run；另外 8 条 synthetic 流程完成，共 86 次 mock attempt；实际模型调用为 0。所有质量与 Gold 人工结论为空。安装后最终目标复核 **82 passed，22.26 秒**，见本包 installed_validation_final.txt。
- 最终状态统计专项 **28 passed，16.52 秒**：未运行零资源和部分采样不能成为完整配对；原始值保留，完成率分母不变。当前派生导出以 dry_export_final/、synthetic_export_final/ 为准，旧导出保留作审计。
- 初轮测试失败与修复、一次 pytest 临时目录入口错误都保留在 validation/；完整命令、退出码与输出 hash 在 offline_audit.json。未安装/升级依赖，图表复用现有 Altair。

## 路径与保留

主交接：`docs/final_sprint/s4-v1/HANDOFF.md`；证据索引：同目录 `EVIDENCE_MAP.md`。

实现：`evaluation/s4*.py`，以及 `app.py`、`workflow/review_graph.py`、`workflow/review_runtime.py`。修正 `evaluation/s2_fixtures.py` 的跨 case 测试 ID；`slm/tests/test_isolation.py` 只对 S4 实验适配层列出精确边界，并实测旧产品不加载 SLM。新增 `tests/test_s4_evaluation.py`。

材料：本包 `dry_run/`、`review_templates/`、`synthetic_rehearsal/`、`synthetic_blind_pack/`、`synthetic_export_final/`。所有 synthetic 内容均为工程证据，不能用于论文模型结果。隐藏映射在评分包 private/，评分者只接收 reviewer/。

版本/安装：`final_version_manifest.json`、`code_install_receipt.json`、`amendments/statistic_states/receipt.json`、`before/`、`before_inventory.json`、`preservation_audit.json`。前次完整状态保存在 `PREVIOUS_S3_STATUS.md`。已有未提交修改与历史 S0/S1/S2/S3 数据保留，未 commit。

## 当前阻塞及下一入口

1. **公共预算暂缓**：CPU v2 仍是 1024 输出、18 请求、160000 总 token、90000 字符、32768 context、1200/5400 秒。Finance 明细 1919/2552 tokens 的 S3 测量仍是未解决问题；8192 公共候选未经批准，没有应用。
2. **完整 D 预检暂缓**：S3 只有真实 31K CPU 规避与 warmup 证据；Research/ComponentCritic/Finance/Writer 业务组件与完整 D smoke 未运行，SLM 仍无真实完整计划书。
3. 两 case 完整 brief/财务情景/证据批准、Gemini 可执行额度与消费记录、各条件 smoke、最终代码/配置冻结尚未齐备；当前 check-freeze 必须阻止正式执行。
4. 六维评分、隐藏复评与全部决策关键声明 Gold 审计待真实输出后由人工完成；没有把预留 1 小时当完成证据。

下一编号工作包为 **S5**，本轮不自动进入。用户恢复公共预算/D工作时先继续 S3，读取 `s3-fix-v1/BUDGET_PROPOSAL.md`、`s3-fix-v1/HANDOFF.md`；待依赖满足后由用户要求 S5。S5 同时读取本包 HANDOFF、S0 协议/rubric 和 `evaluation/s4_runner.py` 的正式门禁。不能用 mock、warmup 或节点探针替代完整 D。

已验证的只读入口（在目标仓库使用现有 .venv/Scripts/python.exe）：

```powershell
./.venv/Scripts/python.exe -B -m evaluation.s4 status --experiment docs/final_sprint/s4-v1/dry_run
./.venv/Scripts/python.exe -B -m evaluation.s4 check-freeze --experiment docs/final_sprint/s4-v1/dry_run
```

第二条当前预期退出 2，这是正确的依赖锁状态。更多实际命令及 raw→CSV→图表/评分包路径见 HANDOFF。没有向桌面正式结果目录创建占位论文/PPT或结果。
