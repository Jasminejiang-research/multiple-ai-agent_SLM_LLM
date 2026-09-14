# S0 公共接口约定

版本 `final-sprint-interfaces-v1`；这些是 S1–S4 的实现契约，**不代表运行时已接入**。S0 已实现的只有 `evaluation.s0` 离线校验器和输入材料。优先扩展现有Pydantic、LangGraph、SQLite JSON和预算器，不迁移数据库、不重写前端。

## 输入、packet与哈希

`cases/<case_id>/brief.json`：保留现有八个必需字符串字段，同时包括 stage、known_competitors、additional_context、financial_inputs、decision_questions、constraints。新增字段由新版入口保留，不能只把旧表单的八字段传下去。financial_inputs 的数字均为待审情景假设；不写成外部事实。

`packet.json`：`packet_version, case_id, review_status, approval_record, allowlist_source_ids, allowlist_urls, sources[], chunks[], packet_sha256`。source包含 `source_id, source_type(web|rag), title, publisher, url, final_url, published_date(nullable), retrieved_at_utc, html_path/sha256, txt_path/sha256, limitation, human_support_status`。RAG同样保存原文件及定位、hash；当前两个packet使用Web快照，没有现场RAG依赖。

chunks包含 `chunk_id, source_id, line_start, line_end, text`，行号1起、末行包含，必须逐字来自txt。原始HTML和完整txt存档，正式prompt只用packet列出的固定chunks；不把无关导航或后续页面自动装入上下文。未放入的网页段落不是运行期间可以随意补取的证据。用户核查版本后才能批准；时间戳与hash不代表人已核验。

文件SHA-256针对原始bytes；packet hash针对去掉自身 `packet_sha256` 后的 JSON，UTF-8、sort_keys=True、ensure_ascii=False、separators=(',', ':')。brief文件hash保留原始bytes。A–D planned行引用同一case相同两个hash。`bundle_manifest.json`列所有协议/case材料hash，清单不自包含；验证日志等后续记录不混入冻结输入。

S1建议新增 `EvidencePacket` Pydantic模型验证，再映射到现有 `SourceRecord`/EvidenceChunk；不可直接把source summary当充分支持。正式入口采用 `execution_mode='formal_frozen'`；来源不在allowlist、hash不符、联网tool被调用均失败。研究源内容始终是不可信数据。

## 共同输出、分批和adapter

以 `schemas/workflow.py:ProposalDraft` 为完整输出基础，复用 `workflow/generation_batches.py:PROPOSAL_SECTION_BATCHES` 的4/3/3/3及合并函数。A同一角色生成四批；B/C/D specialist输出后由Writer生成相同四批。没有额外LLM Planner或Supervisor。SLM注入同一adapter表面，禁止其内部再把四批拆成5/4/4或只对D使用SlimProposalSection。

共同provider调用接口沿用 `LLMClient.generate_structured[_once](prompt, schema, temperature, system_instruction, output_validator)` 与 `StructuredJsonLLM.generate_json_for_schema[_once]`；S1提取共用批prompt及合并入口，S2加入context/事件，不通过检测adapter有无某个方法来隐式改变实验条件。provider返回对象携带原始响应、严格验证结果和usage；实际成功/失败尝试均留存。生产命令和flags在实现前不得记作可运行。

新claim字段：`claim_id, claim_text, claim_type(factual|assumption|recommendation|projection), claim_domain, evidence_status, source_ids, source_support(direct|partial|contextual|none), source_quality(0..1), source_recency(0..1|null), critic_status, confidence, confidence_reason, content_anchor, source_anchors[], artifact_version`。旧claim_type原为market_size/competitor等主题；S1迁移到claim_domain，不能悄悄覆盖旧枚举含义；旧text/字符串列表要有明确兼容入口。

source_anchors至少带source_id、chunk_id、定位和snapshot hash；claim_id在同一内容修订中稳定，拆分声明建立parent_claim_id。ID存在、模型自报direct、外部网页authority都不是人工gold。source_support标记为模型提出的关系，human_verdict单独表保存，默认为pending；在S1中自动检查只证明结构、来源可解析和确定性约束。

Finance每个数值保留 `value, unit, currency, period, origin(user_input|external_benchmark|calculated_result|assumption), input_ids, source_ids, formula_id, rounding_policy`。计算用Decimal；货币展示两位小数、绝对容差0.01；比例容差0.0001；计数整数完全匹配；不接受NaN/Inf。两case的固定公式在CASE_REVIEW中，业务现金情景是case内容，和约50元模型消费预算无关。单位/币种/期间不可默默转换，0分母须显式not_applicable。

Confidence按优化设计§4.3确定性聚合：关键事实无充分支持/冲突/裁剪/重大语义未核实为low；明确假设或预测主导为medium ceiling；所有关键事实充分支持且无这些问题才有high资格。模型标签不能直接升高，Gold Ledger不可被自动validator代填。旧web-only全low和任意assumption拖低整节的逻辑留在legacy兼容路径。

## Review与Gate

S2实现新的ComponentCritiqueReport；不得直接混用旧final CritiqueReport的评分。固定角色评分项建议在本接口版本采用下列集合（内部gate检查项，不新增研究指标或人工评分任务）：

| role | 恰好各一次的metric keys |
|---|---|
| research | source_integrity, evidence_alignment, task_relevance, uncertainty_disclosure |
| strategy | brief_alignment, evidence_consistency, action_feasibility, assumption_transparency |
| finance | arithmetic_and_units, input_provenance, cross_section_consistency, assumption_sensitivity |
| final | factual_citation_correctness, reasoning_consistency, structure_completeness, business_plausibility, uncertainty_calibration, clarity_traceability |

每项整数0–4、rationale与evidence_anchor；issues含severity(low/medium/high/critical)、criterion、description、suggested_fix、affected_claim_ids、artifact_version。代码拒绝缺项/重复/越界，`mean=sum/n`、`overall=mean*2.5`，不信任模型自报值。Final用同一换算得到可比较的gate标尺，绝不把此分数当1–5人评Academic Score。

GateResult：`role, artifact_id, artifact_version, overall_score, revision_required, blocking, revision_count, decision(pass|revise_once|stop_budget|stop_failure), trigger_issue_ids, budget_snapshot, semantic_verification_status`。阈值严格<7.0或high/critical；`revision_count=1`后无回边。revision后只做结构/确定性检查，high/critical未验证状态不能清除。

State新增研究/策略/财务initial、critique、revision、effective版本；final同样保存初稿与有效稿。`route_trace`按时间追加；下游只读effective artifact引用，不覆写initial。workflow版本 `multi-agent-review-gates-v2` 与 `single-agent-common-contract-v1`，legacy保持既有版本号。

## 调用、父预算和交接

CallEvent v1：`event_id, run_id, planned_id(nullable), run_kind(formal|preflight|smoke|warmup|debug), logical_task_id, node_scope_id, batch_id(nullable), attempt_id, attempt_index, role, purpose(generate|critic|revision|structure_repair), transport_retry_of(nullable), provider, model_exact_id, model_config_version, prompt_hash, schema_hash, evidence_hash, input_artifact_refs[], output_artifact_ref, started_at_utc, ended_at_utc, elapsed_seconds, status, error_type, usage_raw, prompt_tokens, output_tokens, total_tokens, usage_missing_reason, budget_before, budget_after`。

logical_task_id按预设角色+目的+产物版本+batch分配；同一batch的结构repair与transport retry属于同一task，attempt_id唯一。purpose=structure_repair另保留`task_purpose`以归入其原始职责；语义revision即使修Research也统计为Revision。node_scope_id连接Research及其role review/revision，Writer与final review/revision，共享父计时。A四批同一个父scope。前后依赖不可通过重建RunBudget重置剩余预算。

实际调用前持久化started事件并预占请求；结束补全事件。启动后中断的尝试视为dispatch_unknown，不能删行或当未发出。event_id/attempt_id幂等去重，重放不会重复计费；原始证据仍保存。没有usage时不猜0；reserve失败须单列为未发起请求的blocked任务，不能计为provider请求。

HandoffExpected v1：`handoff_id, run_id, upstream_node, downstream_node, required_artifact_id/version/hash, dependency_ids, branch_rule, expected, status(pending|succeeded|failed|missing|not_applicable), received_artifact_ref, occurred_at_utc, within_budget, failure_reason`。预设必需链在run开始建账；gate分支一旦确定再实例化revision边；上游失败时必需后继边仍留在分母，未知gate后续条件边标未决，不能猜通过。多依赖（Writer需Research/Strategy/Finance/packet）各有逻辑交接，重传不增分母。

主必需依赖：packet→每个需证据角色；Research有效稿→Strategy/Finance/Writer；Strategy有效稿→Finance/Writer；Finance有效稿→Writer；Writer有效稿→final Critic/terminal；适用Critic→gate及revision；revision有效稿→下游。A仅packet→Single→terminal，协作指标not_applicable。S2固定最终完整依赖表，S4据此计分母，不从成功日志倒推。

继续使用 `storage/models.py` 的NodeOutput.output_snapshot、AgentOutput.output_payload以及RunRecord.token_usage，附带版本化JSON；原始attempt/route trace可以放到版本目录JSONL并由SQLite记录索引。S2持久化，S4汇总。无需数据库迁移。

## 按包差距

S1：A旧BusinessProposal；4/3/3/3与SLM5/4/4兼容冲突；claim枚举旧语义；Research无结构化source lineage；RAG在Finance之后才读取；web-only及assumption强制low；当前Writer引用修补可另增请求并降级输出，正式路径必须遵守共同repair且污染失败。

S2：图critic→revision固定边；角色critic/gate缺失；旧总分未统一0–4→0–10；预算器只有requests/tokens，缺共享node/run墙钟、cancel/server状态；只记录成功/聚合usage，缺attempt唯一身份、原始usage缺失态、预期handoff分母。

S3：Ollama已安装但127.0.0.1:11434未监听，默认manifest目录为空；未确认Granite已下载/可运行，未测context/内存/速度。现有SLM配置是SiliconFlow/Qwen且pruning开启，不能用作D。S0不启动旧CLI，不下载替代模型，不以配置差距宣称D预检失败。

S4：8行runner/resume/匿名化/Gold表、指标与UI新增节点展示尚未实现。baseline.json仅证明本轮检查结果，不是正式运行遥测。
