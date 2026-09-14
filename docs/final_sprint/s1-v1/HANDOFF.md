# S1：统一输出、冻结证据与 Confidence

状态：本包工程实现完成；真实模型和正式实验未运行。本文件对应 `proposal-grounding-v1-s1` / `grounded-generation-v1-s1` / `s0-case-formulas-v1`。两份桌面权威设计及S0协议的研究范围、模型、权重、case数和预算均未改变。

## 已实现接口

`workflow/contract_context.py:ContractContext.from_case(root, case_id, condition=..., execution_mode='fixture')` 是证据入口。完整brief和packet只加载一次，检查case/packet/brief hash、allowlist、源文件SHA-256、chunk文本和行号。每次交接返回独立副本，调用者不能通过修改上游字典改变后续证据。`formal_frozen` 还要求明确的case与packet批准记录；它不是S4正式运行器，S4仍须验证整份运行配置及S1–S3验收。

`workflow/contract_generation.py:ContractGenerator` 使用显式注入的 `generate_structured_once` 客户端、temperature=0和共享枚举提示。`generate(context, 'single')` 是新A输出入口：四批全部属于single角色，无Planner、specialist或LLM Critic。`research`、`strategy`、`finance`、`writer` 是S2可直接组合的节点能力，依赖顺序分别为无、Research、Research+Strategy、Research+Strategy+Finance。本包没有提供B/C/D整图运行命令，测试中的7次调用仅是S1生成链，不代表完整B/C/D。

所有完整提案使用 `schemas/contract_outputs.py:ContractProposal`，在既有ProposalDraft的13个章节字段上扩展严格来源、claim和财务契约。四批边界直接复用 `workflow/generation_batches.py:PROPOSAL_SECTION_BATCHES` 的4/3/3/3。Gemini与 `slm.factories.build_slm_contract_generator(client)` 返回完全相同的生成器；SLM新入口不构造默认Qwen、不使用SlimProposalSection、pruning或二次分批。模型和provider具体配置留S3显式注入。

旧BusinessProposal、旧ProposalDraft/字符串claims、既有app与旧SLM适配器保持兼容。旧claim_type的主题含义不改写；新claim_type为factual/assumption/recommendation/projection，主题单独放claim_domain。旧结果不能自动变成新实验结果。旧图收到 `execution_mode='formal_frozen'` 会在validator拒绝，避免误用旧固定revision流程。

## 来源与审查/修订交接

- 每个新claim保留ID、父ID、内容锚、source_ids、source_anchors、chunk/行号/quote/snapshot hash、证据状态、模型提出的支持关系、质量/时效、版本、影响/裁剪/冲突/未决语义标记及Confidence原因。
- `ContractContext.accept/validate` 检查引用与allowlist、确切定位及来源保留。保留同一claim时必须保留其ID或明确parent ID；直接重复相同文本而换ID会拒绝。事实不能改贴assumption以消除证据义务；无新锚点时，低支持事实不能升级。语义改写是否保持同一意义仍需审查，代码不判断语义等价。
- `review_input(artifact)` 交付同一packet及有效版本；`validate_review_feedback` 拒绝Critic/Revision新造source/chunk/affected_claim IDs。S2应先解析自己的ComponentCritiqueReport，再调用此来源边界；本包没有替代S2评分、gate或Critic。
- `generate(..., previous=artifact, version=2, revision_feedback=report, unresolved_major=True)` 是定向修订能力；revision反馈进入prompt。v1→v2仅一次，第二次语义修订在调用前拒绝。S2决定是否触发，传入未决high/critical状态并持久化有效版本；结构通过不能清除该状态。
- v1契约禁止修订静默删除原claim及其来源。拆分须使用parent_claim_id并保留血缘。若未来需要显式撤回错误claim，应增加有记录的撤回机制，不能直接删除历史。模型语义关联与事实支持性依然不是确定性可验证事项。

`ContractArtifact`保存角色、版本、brief/packet hash、JSON产物及Confidence变更，SHA-256覆盖完整信封。`export`仅接受完整13章，重新核验终端契约；在新目录保存proposal.json、proposal.md、packet.json、brief.json。Markdown包含13章、财务结果表和Appendix来源表；JSON保留完整claim与定位。目录已存在时拒绝覆盖。它是内部证据导出，不代表已通过人工审核或可对外发布。

## Confidence 与人工 Gold 的边界

按claim证据状态汇总：关键事实缺证、partial/contextual、冲突、裁剪、重大未核实语义问题为low；假设/预测主导为medium上限。实现用显式假设/预测数量不少于事实数量作为“主导”的确定性条件；没有事实的章节也不凭空升high。普通假设不会把其他已支持事实自动降low；Web/RAG按同一规则处理。来源结构完整、模型提出direct关系且无阻碍时仅获得规则层面的high资格。

**high标签不是人工核实。** source_support固定带 `support_assessed_by='model_proposed'`；有效产物与每次标签变更带 `proposed_support_structurally_checked_not_human_gold`。代码能核对定位、引用和结构，不能确认引文是否充分支持结论、是否遗漏关键限定或是否覆盖全部决策关键声明。`HumanSupportVerdict`是独立数据模型，默认pending；模型不能在claim中填写human_verdict。没有新造Gold真值或质量得分，也不宣称本包改善了模型质量。

## 财务复算

`FinanceContract`严格读取S0两case固定财务输入：保留user_input/external_benchmark/assumption的原始类别，当前两case实际全部为pending assumption；不能因出现在brief中便改称用户已确认事实。计算结果使用calculated_result、formula_id、input_ids、unit/currency/period/rounding，claim可通过financial_value_ids定位数值。Finance与最终financial_assumptions均须提交完整低/中/高场景结果，不能删减以绕过复算。

Decimal采用未舍入中间值；货币两位HALF_UP、容差0.01；比率容差0.0001；计数整数完全一致。拒绝NaN/Inf、布尔数字、单位/币种/期间/来源/公式/输入ID错误、缺项和重复项。盈亏平衡分母≤0明确not_applicable，不填0。基准验证：education中场景期末现金57000 USD、经营盈亏平衡500用户；ring中场景期末现金698576 USD、盈亏平衡3176台。这些是假设复算参考，不是模型实验输出。自由文本中所有数字是否都正确引用财务表仍属于语义审查/人工最终审核。

## 首次输出与repair

一个batch是一个逻辑任务；共同生成器最多调用一次结构repair，来源污染直接失败，无额外整稿引用修补循环。任务保存每次契约尝试及首次判定；repair成功不改写首次失败。timeout/provider错误不当结构repair处理；已触发ID不能再次调用以重置次数。整稿跨批冲突单独记terminal_checks失败，不额外调用模型。保留schema失败的原始文本；普通成功任务目前保存严格解析后的JSON，完整provider原始响应与物理transport attempt仍由S2补齐。

新入口复用现有provider请求/token预算与record_retry；没有创建新run预算或按batch重置。S2仍须加入共同父节点/整run墙钟、真实attempt事件、取消/服务端存活、持久化和expected handoff分母；现有Gemini HTTP503的内部transport retry仍按旧客户端行为，S2必须明确记录。S3负责本地单并发及32768有效context、输出长度和资源门。S1不把当前默认限制当作已冻结共同配置。

## 验证与材料

实际命令在目标仓库目录运行，WindowsApps解释器在受限Codex沙箱内可能需要工具权限：

```powershell
& '.venv/Scripts/python.exe' -B -m evaluation.s1
& '.venv/Scripts/python.exe' -B -m evaluation.s0
& '.venv/Scripts/python.exe' -B -m evaluation.s0 --require-frozen
# 上条当前应退出2：case、配置和后续包未冻结。
& '.venv/Scripts/python.exe' -B -m pytest -q tests/test_s1_contract.py slm/tests/test_s1_contract_adapters.py -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m pytest -q tests slm/tests -p no:cacheprovider
```

`evaluation.s1 --output-dir <新目录>`会生成离线审计、共同schema和原样S0 packet示例；现有目录拒绝覆盖。已生成示例在 `examples/`，packet内快照路径相对于S0根目录。`contract_audit.json`包含共同schema/batch哈希、case/brief/packet哈希及确定性财务参考值；无模型调用。

安装前基线376 passed/25 deselected/3 subtests；本包整合回归曾因测试跨SLM隔离边界失败，修复后445 passed/25 deselected/3 subtests。后续补充schema和审查反馈测试；**最终安装后结果以validation_results.txt为准**。Gemini/Granite真实调用0，正式run启动0/8。

## S2入口（仅用户要求时）

读本文件、最新final_sprint_status、S0 INTERFACES/PROTOCOL、两份桌面权威设计，然后读 `workflow/contract_context.py`、`contract_generation.py`、`grounding.py`、`generation_batches.py`、`schemas/contract_outputs.py`。在LangGraph中按B final-only与C/D role+final条件gate组合这些能力；保留原始和effective产物，用同一packet与版本、同一client、父预算和task_sink接入事件。不能用当前旧图宣称完整B/C/D，也不能启动八次正式实验。

仍待后续解决：case完整内容审批；S2门控/预算/持久事件；S3 Granite真实预检；S4运行器与盲评材料；最终公共配置冻结。新增provenance/完整财务表会增大prompt和输出，必须在S3按共同配置实测，不得只给D裁字段或提高预算。本包没有因此改变预算、模型或实验范围。
