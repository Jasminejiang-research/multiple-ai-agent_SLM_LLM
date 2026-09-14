# 两案例四条件实验协议

版本：`final-sprint-protocol-v1.0-s0`。性质：研究规则已按权威设计锁定；case 内容待用户核查，运行配置待 S1–S4 实现及预检，**尚未正式冻结，也未开始实验**。

## 权威与范围

来源为桌面 `sprint_plan_.md`、`@ai_agent_evaluation_metrics_spec.md`、`@multiple_ai_agent_optimization.md`。确切路径、SHA-256 和仓库镜像逐字一致性见 `baseline.json`。旧 `.cursorrules` 的 Phase 1 限制及仓库旧实验计划不改变用户已确认范围。优化设计 §6.4 的本地动态输出建议，按同文 §7.1 与更新的 sprint §1/§6 解读：正式 A–D 必须共用规则，不能只缩短 D；如仍需例外须用户确认。

| 条件 | 模型 | 工作流 | 正式槽位 |
|---|---|---|---:|
| A | Gemini 2.5 Flash | 单一生成角色，共同13章契约和确定性终端校验 | 2 |
| B | Gemini 2.5 Flash | Research→Strategy→Finance→Writer→final Critic；失败才修订一次 | 2 |
| C | Gemini 2.5 Flash | B 加三个角色 Critic 与相应条件修订 | 2 |
| D | Granite 4.0 H Micro Q4_K_M，本地 | 与 C 相同的完整工作流 | 2 |

两个 pending case 为 `ai_education`、`intelligent_ring`，来自原候选和现有样例；详见 `CASE_REVIEW.md`。每个 case×condition 一次，8 个 planned rows，6 次 Gemini、2 次 Granite；独立样本量 n=2。`planned_runs.csv` 是计划槽位，不是 S4 运行器；全部为 `not_run`，run_id 为空。正式随机顺序由 S4 按 case 分块、种子 `20260906` 生成并冻结；CSV 当前行号不是运行顺序。

仅比较 B−A、C−B、C−D；C−B 是角色审查与条件修订的组合效果。没有 Granite Single、固定修订对照、模型×架构交互、稳定性重复、3/100 非劣或 15% token 节省门槛。预检、调试、smoke、warm-up 单列，不替换失败正式行。

## 共同规则和冻结条件

- 相同完整 brief 与 evidence packet；首次 Research 前就注入 packet。正式模式关闭所有联网补搜与现场知识库读取，仅用固定 chunks；保留产品模式原有 Web/RAG 功能。
- 统一完整 13 章 `ProposalDraft` 契约、严格本地 Pydantic 校验和共同 4/3/3/3 分批；A 的分批全部由同一生成角色完成，无 specialist/LLM Critic。
- context 上限 32768，temperature=0；证据、输出上限、预算、批分组及 repair 规则 A–D 一致。1024 输出 token/请求仅为预检候选，非冻结值。不同 tokenizer 不要求实际 token 数相等。
- 不得直接使用旧 `BusinessProposal` 或 SLM pruned schema 作为正式输出；历史数据继续可读。
- 每个结构化逻辑任务最多一次结构 repair（一个 batch 是可审计子任务），重试不新增任务分母。全稿合并后的引用修补不得在既有 repair 之外再启动额外修补循环；确定性合并失败须显式失败并保留原文。S1/S2 必须把 batch 和节点父任务的关系写入事件。
- B 的 final、C/D 的 Research/Strategy/Finance/final 各最多一次语义 revision；每次 revision 产生新版本，其结构 repair 单列。gate = `overall_score < 7.0 OR any high/critical issue`。通过即跳过，revision 后不再次语义 Critic。
- 原 high/critical 问题 revision 后保留 `unverified_after_revision`；critical 继续需要人工处理。结构通过不证明语义已修复。内部证据留存不等待外部发布审批。
- 单节点所有 batches/repair/revision 共用最多1200秒，完整 Multi 最多5400秒；共同控制器以父节点剩余预算限制每次请求，不能按 batch 重置。空闲 RAM<2GiB 或 pagefile 实际使用比基线增加>2GiB，任一连续60秒即停止；S3 实测验证，不能用旧内存数代替。
- 正式执行前须全部冻结：case 内容/财务假设、证据/hash、代码及未提交差异、prompt、schema、provider/精确模型/量化/运行时、上下文、输出、共同请求/token/time 上限、repair/transport 策略与随机顺序。D 完整可行性、S1/S2/S4 验证通过。

## 预算推导（容量需求，不是新授权上限）

令 W=4 为 Writer/Single 完整分批数；Research/Strategy/Finance 各1次；final Critic 1次；三个 component Critics 共3次；Supervisor、RAG validator、gate、合并、export 均不调用 LLM。final revision 若需重写全部章节，最多 W 次。定向修订可更少，仍按同一分组规则。

| 条件 | 全部 gate 通过的最少调用 | 全部适用语义修订，无结构repair | 各逻辑任务均发生一次结构repair | 若每个实际尝试再有一次transport重试 |
|---|---:|---:|---:|---:|
| A | 4 | 4 | 8 | 16 |
| B | 8 | 12 | 24 | 48 |
| C | 11 | 18 | 36 | 72 |
| D | 11 | 18 | 36 | 72 |

一次 transport retry 与结构 repair 不同，表末仅为保留旧 Gemini HTTP503 重试时的容量上界，非必须启用；S2/S3 冻结共同重试策略，禁止不确认服务端终止就重发本地请求。D 当前18请求仅刚好容纳18次全语义分支，不能保证留有 repair。预算耗尽必须正常停止并记失败，不为获得成功而自行提高上限。

八次最少正式 provider 调用 = 2×(4+8+11+11)=68，其中 Gemini46、Granite22。全语义分支为104（Gemini68、Granite36）；再全结构repair为208（Gemini136、Granite72）。这不是8个独立模型请求，也不包含预检。

每次 prompt（含schema/system/证据）+预留输出≤32768；字符估算仅可保守预筛，S3 验证真实有效窗口。总 token 预算应结合实测输入及输出冻结，不能仅以请求数×1024代替。旧实际配置：Gemini51请求/600000 tokens；SLM18/300000、4096输出、90000字符、300秒、pruning开启，均不是新公共配置。代码默认值又是另一组，详见基线。

约50元为整个冲刺实际消费约束，含预检/重试/正式运行；不新增论文成本或ROI指标。用户本轮说明“暂无额度记录，记得曾充值，预计足够；先不要管额度”，S0 按此停止调查；付费状态、余额、RPM/TPM/RPD 保持未核实。没有把 API key 存在或成本配置0当作免费/余额证明。本包0模型调用、0充值。后续执行仍应记录实际消耗，可能超约束或需新充值时停止确认。

## 结果与失败口径

四个独立状态字段：`execution_status`、`terminal_contract_status`、`scorable_output_status`、`needs_human_review`。执行状态：not_run/running/succeeded/failed/cancelled/interrupted_unknown；契约：not_checked/passed/failed；可评分：not_available/available/pending_review。unknown 必須保留，不能写成0或成功。

failure_reason 至少支持 quota/api/transport/schema/citation_pollution/context_overflow/request_budget/token_budget/node_timeout/run_timeout/memory_guard/cancelled/infrastructure/telemetry_missing。source ID 新造或污染记失败；原文和可评分最终稿仍保存，不标 external ready。未产生可评分最终稿质量为 missing，不填0；有可评分失败稿也进入最终盲评。每个正式计划行不可被补跑覆盖；未知是否已发请求的中断行不允许无检查重放。

完成率 = 成功canonical输出 / 全部计划canonical runs（总分母8，每组2），成功须工作流正常完成及终端契约通过，外部发布审批另列。首次有效计划时间从run开始计至完整13章第一次通过自动终端契约；包含此前失败/修复时间。未通过时缺失，timeout不是成功用时。人工质量不参与这一时间的自动判定。

所有请求/usage/retry 包括失败、修订和修复。缺失 usage=null+reason，不填0；保留 Gemini 原始 prompt/candidates/total/thoughts/cached 等返回字段，不将总量与子项重复相加。provider 未返回的字段不能猜测。RAM、VRAM、pagefile 分列，缺遥测与未触发分别记录。

## 冻结的质量、claim与统计

人评 rubric 全文逐字摘录到 `EVALUATION_RUBRIC.md`，包含六维English anchors、2/4规则、两个校准示例，权重25/20/15/15/15/10%。`Academic Score=100×Σ[w×(score−1)/4]`；缺任一维时总分缺失，不重分配权重。Critic 自评分不是人评真值。S0复算发现原文Example A的[5,4,5,4,5,4]应为88.75而非83.75，原文保留并附勘误；两份文件的权重与公式一致，优先按公式，不改评价范围或标准。

claim审计沿用优化设计§4.4的全部决策关键声明：市场、竞争、定价、财务、可行性、合规及改变主要建议的判断；不局限模型列出的 key_claims。三个指标共用一次人工 Gold Ledger：充分支持/全部决策关键声明；正确标为assumption的实际无支撑声明/全部实际无支撑声明；无充分支持的高影响事实/全部高影响事实。分母0为not_applicable，失败和漏采集另记。

先原子化；同一输出内等价且证据义务相同者去重、保留全部位置，不跨condition去重；部分支持尽量拆分，不能拆则不计充分支持。可外部核验的缺证事实不能靠assumption标签变为正确假设。错误会改变核心市场/定价/财务/合规/行动者是高影响。模型支持关系、source_id/URL存在均不等于人工已核实。详见同文件原文摘录。

首次契约通过率 = 首次提交即通过的逻辑任务 / 已触发逻辑任务；所有批任务及其重试的身份提前固定，重试不增加分母；首次超时/无输出为未通过，修复不能回改。未触发角色not_applicable。交接成功率分母由冻结拓扑+实际分支确定，包含上游失败导致未完成的应执行边，跳过分支不计。协调与审查token占比只计Supervisor/Critic职责的实际消耗，Revision另归类；handoff文本已在输入中不得重复计费。A的协作指标not_applicable。

所有可评分canonical最终稿匿名盲评，隐藏约20%复评（8份可评分时约2份）；复评不产生模型运行。人工1小时是安排，不是完成证明。没有人工分数/Gold结论时不生成质量结果。

仅报告两case原值、失败/缺失、完整配对数、逐case差值、平均配对差值为主效应、中位差、差值IQR及改善/持平/恶化数量。IQR用线性分位数（q×(n−1)插值）并注明n。质量/完成率/grounding/transparency/契约/交接为较高较好；高影响无支持率及资源为较低较好；审查token占比无单向好坏。默认差值0为持平，不新增效应门槛。比例先case内算，再等权平均，保留分子/分母及有效case数；缺配对不补值。默认不做bootstrap/显著性检验/观察功效，不声称总体优越、等效或非劣。

## 验证和交接

`python -B -m evaluation.s0` 仅校验本准备包；`--require-frozen` 在存在pending时预期退出2，不是运行器。S1 从 `INTERFACES.md` 开工，case未确认不妨碍合成fixture和共同契约。只有用户要求下一包才继续。
