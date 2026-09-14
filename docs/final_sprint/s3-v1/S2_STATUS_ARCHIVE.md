# Final sprint 执行交接

更新时间：2026-09-06。当前工作包：**S2**。状态：**complete（工程实现与离线验证）**。S0/S1：complete；S3–S5：not_started。未执行下一包，未启动正式实验。S1原始状态完整保存在 `docs/final_sprint/s2-v1/S1_STATUS_ARCHIVE.md`；S0/S1协议、快照及历史记录保留。

## S2实际完成

- ComponentCritiqueReport覆盖Research/Strategy/Finance/final固定评分项，严格整数0–4，代码计算mean×2.5。gate固定overall<7或high/critical；不信任旧自报总分。
- 独立版本LangGraph：A无Critic，B仅final，C/D角色级与final Critic。通过跳过，失败最多一次定向revision；无第二轮语义审查、Supervisor调用或动态角色。
- initial/critique/revision/effective分别保存，下游校验正确ID/版本/hash。修订后high/critical保留unverified_after_revision，critical持续blocking/needs_human_review，Confidence限制传到最终产物。完整13章内部导出保留，external_ready=false。
- 共同RunBudget及父节点/run时钟覆盖所有batch、Critic、repair、revision。请求/token耗尽、超时、取消、API失败明确终止并落盘；缺usage保留null和原因，预算扣账与实测usage分开。
- 物理请求开始先fsync/可选SQLite commit再dispatch；传输重试与结构repair分开记录，同一逻辑task不变。首次请求失败后重试成功仍保持首次未通过；修订及其中的repair归Revision。
- 原SQLite JSON字段+追加JSONL保存调用、原始输出、usage、route和预期handoff。必需交接提前建账，上游失败后的missing边保留，未知分支不猜通过；中断请求为interrupted_unknown，禁止自动重发。
- 本地endpoint排他lease阻止超时/取消/未知请求后的新实例重叠调用；Granite通过显式物理provider接口注入共同完整D图，旧SLM裁剪/隐式重试入口不混入。

## 代码与交接

所有路径相对于 `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`。

| 内容 | 路径 |
|---|---|
| API、预算/语义边界、事件口径与S3要求 | `docs/final_sprint/s2-v1/HANDOFF.md` |
| 评分与事件schema | `schemas/review.py`、`schemas/review_events.py` |
| Role-aware Critic | `agents/component_critic.py` |
| A/B/C/D图、有效版本与交接 | `workflow/review_graph.py`、`workflow/review_handoffs.py` |
| 共同配置、物理调用/预算、持久化 | `workflow/review_config.py`、`workflow/review_runtime.py`、`workflow/review_events.py` |
| Gemini单次SDK调用、Granite注入 | `workflow/review_providers.py`、`slm/factories.py` |
| S1共同生成attempt钩子 | `workflow/contract_generation.py` |
| 合成审计与完整路由记录 | `evaluation/s2.py`、`docs/final_sprint/s2-v1/mock_audit/` |
| 新增专项 | `tests/test_s2_review.py`、`slm/tests/test_s2_contract_adapters.py` |
| 最终验证与安装/保留校验 | `docs/final_sprint/s2-v1/validation_results.txt`、`installation_receipt.json`、`change_manifest.json` |

workflow版本multi-agent-review-gates-v2 / single-agent-common-contract-v1；config为review-run-v1-s2；event为review-events-v1-s2。Legacy multi-agent-rag-v1和旧数据保留。无数据库迁移、commit、前端重写或生产模型/预算配置变更。

## 实际验证与限制

- Python3.12.10，pip check通过，未安装/升级依赖。目标项目启动基线451 passed、25 deselected、3 subtests，60.08s。
- 初轮专项87 passed（26.08s）；补充SDK/SQLite/注入专项95 passed（32.94s）；整合547 passed、25 deselected、3 subtests（93.11s）。其后补充物理线程冻结证据隔离检查，最终安装前专项97 passed（35.01s）；安装后最终专项/整合与S0/S1审计原始结果以validation_results.txt和installation_receipt.json为准。
- 七条合成debug路径：A通过4请求；B通过8/全修订12；C通过11/全修订18；D通过11/全修订18。全部完成且预期handoff全部通过；critical修订后仍blocking。这是mock路径数，不是生产预算或模型质量/可行性证据。
- 本包真实Gemini/Granite生成、真实preflight/smoke/warmup、正式runs和实际消费均0；正式计划仍0/8。没有人工评分/Gold真值，未查询额度、充值或加载模型。
- 公共请求/token/输出上限仍待预检冻结；UTF-8保守预算估计不可冒充实测token。父节点≤1200秒、run≤5400秒，所有batch与修订共享父预算。
- S2入口拒绝formal，等待S4/S5接入计划行及完整输入/模型/配置冻结门。两case完整brief/packet仍pending；S0旧快照不原地更改。
- 无需要改变实验/模型/预算范围的重大冲突。正式依赖仍是case批准、Granite真实context/资源/速度与完整D smoke、公共预算冻结、S4运行器/指标/原UI及S5人工审核。Gemini约50元消费约束与“先不调查额度”的既有指示保留。

## 下一包：S3（仅用户明确要求时）

必读桌面sprint_plan_、两份权威设计、本状态和S2 HANDOFF。入口为slm/factories.py:build_slm_review_workflow及workflow/review_runtime.py的PhysicalRequest/PhysicalResponse/LocalRequestLease；接入真实Granite4.0 H Micro Q4_K_M，32768 context，完整C/D相同审查与修订，单并发/服务端idle确认、RAM/VRAM/pagefile及20/90分钟门。D不通过时保留证据并确认范围，不自动换模型、裁剪或进入S4。

可复用离线命令（目标项目目录，output-dir必须尚不存在）：

```powershell
& '.venv/Scripts/python.exe' -B -m pytest -q tests/test_s2_review.py slm/tests/test_s2_contract_adapters.py -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m pytest -q tests slm/tests -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m evaluation.s2 --output-dir data/s2-mock-new
& '.venv/Scripts/python.exe' -B -m evaluation.s1
& '.venv/Scripts/python.exe' -B -m evaluation.s0 --require-frozen
# 最后一条预期退出2（正式冻结尚未完成）。
```

