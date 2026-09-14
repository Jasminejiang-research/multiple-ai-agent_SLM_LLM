# S2：角色审查、条件修订、共同预算与追踪

日期：2026-09-06。仅S2；未执行S3、未启动模型/正式实验。依据桌面sprint_plan_、两份权威设计、S0 INTERFACES及S1 HANDOFF。初始状态完整存于S1_STATUS_ARCHIVE.md。路径相对于 `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`。

## 实际实现

- `schemas/review.py`、`agents/component_critic.py`：Research/Strategy/Finance/final固定评分项，严格整数0–4，拒绝缺项、重复、未知项、越界和旧overall_score输入。代码计算mean及mean×2.5，must_fix从high/critical issues派生；它不是人工Academic Quality Score或Critic有效性指标。
- gate固定 `overall_score < 7.0 OR any high/critical issue`，不先四舍五入；critical为blocking。B仅final，C/D四处审查，A无LLM Critic。失败只修订一次，无回到Critic的边。
- `workflow/review_graph.py`：显式LangGraph生成、Critic、gate、条件revision、effective节点。initial、critique、revision、effective分别保存，生成依赖只使用effective版本。Writer初稿/修订均为相同完整13章、四批；不增加Supervisor调用或动态角色。
- `workflow/contract_generation.py`新增显式attempt_scope与首次物理尝试标志；S1调用接口仍兼容。首次API失败而传输重试成功也不能改成首次契约通过。一个逻辑任务及其传输重试/结构repair共用ID和唯一repair额度。
- 修订后issues仍为unverified_after_revision。high/critical限制传到effective claims和Confidence；上游重大问题不会因final Critic通过而清除。无claim定位的重大问题限制整个产物。critical持续blocking/needs_human_review。完整内部导出照常保留；external_ready=false，未执行人工核验。

版本：workflow=`multi-agent-review-gates-v2`（B/C/D）或`single-agent-common-contract-v1`（A），review=`component-review-v1-s2`，config=`review-run-v1-s2`，event=`review-events-v1-s2`。生成prompt/schema保留S1版本。Legacy `multi-agent-rag-v1`及旧factory行为不变。

## 共同入口

`workflow.review_graph.build_review_workflow(context, config=..., provider=..., output_dir=..., ...)`返回ReviewWorkflow，`.run()`只能执行一次，输出目录必须不存在。`workflow/multi_agent_graph.py`也显式导出新factory。context为S1 ContractContext；config为ReviewRunConfig。

max_requests、max_total_tokens、max_output_tokens、max_prompt_chars、request_seconds全部必填，**不提供生产默认预算**。固定temperature=0、context_tokens=32768；node_seconds≤1200、run_seconds≤5400；请求等待≤min(request_seconds,父节点剩余,run剩余)。transport_retries显式0或1、默认0，SDK自身重试禁用。不能套用旧18请求/pruned默认值。

S2入口暂时拒绝run_kind=formal，避免绕过尚未实现的S4/S5协议、计划行、模型和输入审核门。S3使用preflight/smoke/warmup等非正式类型。S4必须接入真实冻结检查后开放正式入口，不能简单删除拒绝条件就跑八次。

`workflow/review_providers.py:GeminiPhysicalProvider`实现单次SDK调用：剩余毫秒timeout、HttpRetryOptions(attempts=1)、共同schema/temperature/output cap；保留原始usage，output_tokens为可见candidates，total保留provider含thinking的总数，不能再次累加thinking。已验证本地安装SDK参数与合成响应；真实Gemini调用0。

## S3 Granite注入接口

`workflow/review_runtime.py:PhysicalRequest`包含完整prompt、Pydantic schema、system_instruction、temperature、max_output_tokens、timeout_seconds。provider公开provider='local'、model_exact_id，并实现 `invoke(request) -> PhysicalResponse`：

- 一次invoke只能发起一次物理请求；SDK/HTTP自动重试必须禁用。接收共同完整schema/输出上限，不在adapter内二次分批、裁剪、降级或换模型。
- PhysicalResponse返回原始text、usage_raw、可空prompt/output/total_tokens及finish_reason。缺usage填None；provider已含reasoning的total不能重复相加。length/MAX_TOKENS进入该任务唯一结构repair机会。
- API失败用ProviderFailure（仅错误类型，无密钥/请求头）；request_finished仅在确认请求终止时设True，明确允许的已结束失败才可retry。超时可抛TimeoutError，取消由controller的Event处理。
- `slm.factories.build_slm_review_workflow`是D的显式包装，调用同一个完整共同图。旧SLMClient/pruned adapters没有此物理接口，不能冒充Granite接入。
- 必须注入LocalRequestLease。所有进程/模型对同一**规范化服务端endpoint**共用相同lease目录及key；不能每run另建目录，或把同一地址用不同写法分开。
- lease排他创建并fsync，只有确认请求结束才移除自有marker。超时、取消、中断/未知失败保留marker，新实例及新run被挡住；迟到后台结果不修改已终止run。S3须查明服务端已停止/空闲（必要时停止服务并验证），留下reconciliation证据，再显式移除对应marker。S2不提供自动过期解锁；客户端线程已返回不能代替服务端idle证据。

S3仍须接入真实Granite4.0 H Micro Q4_K_M、验证实际32768 context、单模型加载、服务端取消/idle、RAM/VRAM/pagefile和20/90分钟门。本包没有加载Ollama、下载模型或证明D可行。

## 预算与故障

一个BoundedClient持有一个现有RunBudget。Research/Strategy/Finance各自生成+Critic+revision+repair共用父scope；Writer四批+final Critic+修订四批共用Writer；A四批只有Single父scope。只有下一父节点才换node时钟，run时钟不重置。取消Event/KeyboardInterrupt、超时、预算/API/契约失败均终止并记录status/failure。

token预占使用prompt+system+schema的UTF-8 bytes数加公共output cap，属于**保守预算估计，不是token测量**。有total usage后按实际total扣账；没有total时保留估计（至少覆盖已知部分）。实际usage超限如实记录并停止。S3须校准共同配置，不得只放宽D；本包没有冻结新的请求/token上限。

snapshot的charged_total_tokens为扣账；actual_*_tokens_known为已知部分；usage_missing_calls表示不完整。reserve失败写blocked_task，不新增实际attempt。transport_retry_count只数实际发起重试；structure_repair_request_count和revision_request_count单列，两者在revision repair时有交集，不能直接相加当请求数。资源统计按唯一attempt聚合。

SQLite RunRecord.token_usage记录实际值，存在缺usage请求时总字段为null并给原因，已知部分/预算放s2_budget；不把缺失填0。约50元消费约束不变，生产费用/遥测/正式调度尚待S3–S5，没有充值或查询额度。

## 持久化与交接分母

Pydantic事件schema见 `schemas/review_events.py`，JSON Schema见 `mock_audit/schemas.json`。每run有events.jsonl、result.json，成功终端有internal_export/。失败/部分输出仍在artifact、physical raw_output与logical_task事件；后续失败不抹掉已完整生成的可评分初稿引用。

- EventJournal逐条追加、flush、fsync；可选session_factory同步使用原SQLite NodeOutput JSON、AgentOutput JSON、ErrorRecord/RunRecord，无迁移。请求开始事件先持久化再dispatch。event_id去重，attempt_id配对开始/结束。
- call包含run/logical_task/attempt/父scope/batch/role/purpose/task_purpose、精确model/config、prompt/schema/evidence hash、输入/输出ref、时间、状态、raw_output与usage。修订职责固定Revision，修订中的repair保留task_purpose=revision。
- call.status=succeeded仅表示收到并解析provider JSON/schema，完整确定性契约还需contract_check/logical_task。首次契约使用最新logical_task.first_output_passed（含first_physical_attempt_passed），不能只看最后成功响应。资源按物理calls统计。
- replay_events按event_id去重、attempt_id归并；未结束dispatching转interrupted_unknown。末尾半行标truncated_tail，中间损坏不吞掉。automatic_resume_allowed=false，S4必须对账，不能把unknown当从未调用重放。
- HandoffLedger在首调用前建packet/brief→各节点、R→S/F/W、S→F/W、F→W、initial→Critic、Critic→gate、gate→effective、最终effective→terminal。Writer.initial是提交final Critic的完整、已确定性验证v1；final gate后才发布Writer.effective。
- revision支路只在gate明确触发后加入initial、feedback、packet/brief、所有上游、gate及revision→effective；未知gate保持branch_inventory=unknown。artifact ref校验ID/版本/hash，每个依赖分别计。上游失败后必需边变missing并保留，不能从成功日志倒推分母；A协作指标not_applicable。
- route事件/route_trace含节点、规则、gate、issues、预算和结果。标记effective的语义状态不覆盖initial/revision存档。

## 已执行验证

Python3.12.10、现有依赖pip check通过，无安装/更新。目标项目启动基线451 passed、25 deselected、3 subtests，60.08s。初轮专项87 passed（26.08s），补充SQLite/SDK/adapter专项95 passed（32.94s）。最终安装前专项97 passed（35.01s），含物理线程冻结证据隔离；最终源码整合及S0/S1兼容验证以validation_results.txt、installation_receipt.json为准。

`evaluation.s2`已生成七条**合成debug路径，不是8个planned rows**，全部complete、预期handoff全部succeeded：

| 条件 | 所有gate通过：合成请求数 | 所有适用gate critical后各修订一次：合成请求数 |
|---|---:|---:|
| A | 4 | 不适用 |
| B | 8 | 12 |
| C | 11 | 18 |
| D | 11 | 18 |

它们是无repair/transport retry时的路径数，**不是可用生产预算**。专项还覆盖失败、repair、耗尽、共享时间、取消、污染、版本/Confidence、未知请求和SQLite。没有模型质量分、人工Gold、真实推理速度或内存观测。

已实现的命令（目标项目目录，审计output-dir必须不存在）：

```powershell
& '.venv/Scripts/python.exe' -B -m pytest -q tests/test_s2_review.py slm/tests/test_s2_contract_adapters.py -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m pytest -q tests slm/tests -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m evaluation.s2 --output-dir data/s2-mock-new
& '.venv/Scripts/python.exe' -B -m evaluation.s1
& '.venv/Scripts/python.exe' -B -m evaluation.s0
& '.venv/Scripts/python.exe' -B -m evaluation.s0 --require-frozen
# 最后一条预期退出2：正式冻结尚未完成。
```

## 保留项与下一包

安装逐文件检查before/after SHA-256，拒绝覆盖启动后并行修改。原S0/S1记录、已有未提交代码、12份历史数据均保留；清单见change_manifest.json，实际校验见installation_receipt.json。未commit、迁移数据库或重写前端。

S2工程边界无需要改变模型、实验或预算范围的冲突。正式依赖仍是两case完整brief/packet批准、公共预算预检冻结、真实D可行性、S4运行器/指标/原UI及S5人工审核。S2的新SQLite版本由S4接入展示，缺usage不可转0。

仅用户要求时执行S3：先读status、本HANDOFF、桌面S3要求；从 `slm/factories.py:build_slm_review_workflow`、`workflow/review_runtime.py`、`workflow/review_config.py`开始。维持H Micro Q4_K_M、32768、共同schema/4批/一次repair/一次revision和20/90分钟硬限。若需换模型、裁剪D或扩大预算范围，保留失败证据后停止确认，不自动进入S4。

