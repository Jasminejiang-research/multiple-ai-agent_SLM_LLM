# Multiple AI Agent 最终冲刺执行计划

> 版本：v1.0｜日期：2026-09-06  
> 执行模型：GPT 6 Astra，推理强度「极高」（由用户在 Codex 中选择）。  
> 工作方式：六个工作包，一轮完成一个包；同一包内自主完成实现、必要测试和交接，不拆成逐文件审批。  
> 本文件是执行分解，不代表代码、模型预检或实验已经完成。

## 0. 使用方式与权威来源

代码工作区：`C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`。

每轮先读本文件、下列两份最新设计，以及已存在的执行记录；随后只读本轮相关代码。若仓库内同名旧文档与桌面设计不同，以用户最新决策及这两份桌面文件为准，不用旧文档恢复已取消的条件。

- [评价指标规范](<C:/Users/JasmineJiang/Desktop/s4/hu-3.Intelligent System/@final presentation/@ai_agent_evaluation_metrics_spec.md>)
- [产品优化计划](<C:/Users/JasmineJiang/Desktop/s4/hu-3.Intelligent System/@final presentation/@multiple_ai_agent_optimization.md>)
- 执行记录：`C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint_status.md`，由 S0 新建，后续每轮更新。

本次仅在原产品基础上优化并准备实验与证据。论文/PPT制作安排在明天，保留其数据和证据接口，不在本冲刺中撰写论文、制作PPT或做语言润色。

### 每轮启动提示词

将下面的 `S0` 换成当前工作包编号即可：

```text
请读取：
C:/Users/JasmineJiang/Desktop/s4/hu-3.Intelligent System/@final presentation/sprint_plan_.md

使用两份权威设计和 docs/final_sprint_status.md 中的最新记录，
在 C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM 中执行工作包 S0。

先检查依赖与已有实现；完成本包实现、必要验证和交接记录，不自动执行下一包。
常规实现选择自行处理，保留已有未提交修改及历史运行数据。
发现重大冲突或需要改变实验/模型/预算范围时，停止并向我确认。
结束时报告完成项、实际测试结果、文件路径、剩余阻塞与下一包入口。
```

“继续”默认指继续当前未完成工作包；只有当前包已验收且用户要求下一包时，才进入下一包。不要自动启动全部八次正式实验。

## 1. 本轮不可改变的决策

| 条件 | 模型 | 工作流 | 正式运行数 |
|---|---|---|---:|
| A | Gemini 2.5 Flash | Single Agent，统一终端检查 | 2 |
| B | Gemini 2.5 Flash | Multi-Agent，仅最终 Critic，检查失败才修订 | 2 |
| C | Gemini 2.5 Flash | Multi-Agent，Research/Strategy/Finance角色级 Critic＋最终 Critic，检查失败才修订 | 2 |
| D | Granite 4.0 H Micro Q4_K_M，本地运行 | 与C相同的完整工作流、审查和条件修订 | 2 |

- 四组使用相同的两个case，每个 `case × condition` 正式执行一次，共8个planned runs：Gemini 6次、Granite 2次；独立样本量 `n=2`。
- 两个case的具体选题尚未确定。沿用优化计划§7.4候选，在S0准备并由用户确认完整brief与证据；不得默认为执行六个候选。
- 比较仅为 B−A、C−B、C−D。C−B评价“增加角色级审查与条件修订”的组合效果。
- 不设Granite Single组，不设固定修订组，不估计模型×架构交互，不验证已取消的3/100质量非劣或15% token节省门槛。
- 预检、smoke、warm-up和调试调用单独记录，不能计入8次正式运行，也不能以其成功输出替换正式失败。
- A–D共同使用冻结证据、输出契约、上下文/输出上限、分批规则、温度、一次结构修复机会及可比的run预算。相同配置不要求不同模型的实际token计数相等。
- 正式实验禁止实时补搜；保留原产品的受控Web/RAG功能，以模式隔离实现冻结实验。
- 每个适用角色及最终稿最多一次语义修订；结构repair单独计数。通过检查直接跳过修订。
- 全部质量权重、claim核验与统计公式沿用两份设计，不另造指标、综合总分或人工中间输出评分。

## 2. 工作包、依赖与工时

| 包 | 交付主题 | 依赖 | 工程主动工作粗估 |
|---|---|---|---:|
| S0 | 基线、协议、两个case与接口约定 | 无 | 30–45分钟 |
| S1 | 统一A–D契约、冻结证据与Confidence | S0的技术约定 | 60–90分钟 |
| S2 | 角色Critic、条件修订、预算和追踪 | S1 | 90–150分钟 |
| S3 | Granite完整工作流接入与可行性预检 | S1、S2 | 45–90分钟 |
| S4 | 八次实验运行器、指标、评分材料与产品展示 | S1–S3的接口；D失败时等待范围确认 | 60–90分钟 |
| S5 | 正式冻结、八次实验、人工审核与证据归档 | S0–S4全部适用验收通过 | 主要为运行与审核，不并入上方开发估计 |

S0–S4主动工程工作约5–8小时。资料检索冻结、下载、真实推理等待与人工审核另计；整体8–14小时仍是需预检校准的排期估计。用户已为人工审核预留1小时；不把时间预算当作已完成评分的证据。

下载和资料准备可在不影响当前包代码工作的条件下进行；Granite生成只允许单并发。不要在本地正式测时/测内存期间同时运行重型测试或另一个本地模型。代码修改按依赖推进，不让多轮同时改共享schema和workflow。

各包编号表示可独立验收的交付单元，不是硬性分钟截止。需要突破源文件的运行硬限或缩减研究范围时按§9停止确认，不能为赶工降低验收标准。

## 3. S0 — 基线、协议、两个case与接口约定

**目标：**形成可以指导后续实现的技术约定与可审阅输入，不开始正式实验。

**读取重点：**两份设计全文；现有 `app.py`、`workflow/multi_agent_graph.py`、`workflow/llm_client.py`、`workflow/run_budget.py`、`workflow/generation_batches.py`、`slm/config.py`、`slm/factories.py` 及相关测试。仓库代码路径均相对于本文件§0的代码工作区。

**一次完成：**

1. 检查Git状态、已有运行数据、Python解释器与依赖、Ollama/模型是否可用；只记录密钥是否配置，不输出密钥。运行现有基础测试，区分既有失败与本轮新增失败。解释器不可用时先明确原因，不直接删除重建用户环境。
2. 建立 `docs/final_sprint_status.md` 和一份版本化实验协议。协议明确A–D、两个case、8个planned rows、失败/缺失状态、质量与资源记录口径，冻结已有rubric和claim审计规则。
3. 从原候选准备两个case的完整brief、来源内容快照、allowlist、抓取时间与SHA-256清单，交用户核查；两个名称及输入未确认时标记pending，不进入正式实验。接口与合成fixture的实现不依赖最终选题。
4. 约定共同输出模型与分批入口、证据packet结构、review/gate结构、调用事件和交接事件接口。优先复用既有Pydantic、LangGraph、SQLite、预算器；不迁移数据库或重写前端。
5. 点名现有差距并纳入后续包：A目前使用旧 `BusinessProposal`；Gemini与SLM分批不同；当前图的final revision是固定边；默认请求预算不能直接视为新角色审查流程的可用预算。
6. 列出A–D最少调用与修订/repair分支的预算需求。优化计划中的18请求、1024输出token属于起始配置，不等于已通过真实预检。正式公共上限须在预检后冻结；不得只提高D或只裁剪D来制造可比结果。
7. 记录Gemini当前项目可用额度和免费/付费状态；约50元是实际消费约束，包含预检、重试和正式运行。若需开通付费，先形成金额与用途明确的请求；本包不自行充值。费用只用于运行控制，不新增论文成本/ROI指标。

**验收：**

- 基线测试结果、技术接口、预算待定项及case审核状态都有记录。
- 选题、输入、额度等未知项标明具体影响，不伪装为已冻结。
- S1可依据已完成技术约定开工；正式实验仍须等待两个case与最终配置全部冻结。

**交接：**现有修改清单、可靠Python入口、协议路径、case状态、公共接口与下一包需要读取的文件。

## 4. S1 — 统一契约、冻结证据与Confidence

**目标：**A–D比较使用同一输出要求和可追踪证据，消除先改架构再补公平性的返工。

**读取重点：**优化计划§3–4、§7.1；`schemas/proposal_schema.py`、`schemas/workflow.py`、`schemas/agent_outputs.py`、`agents/research.py`、`agents/writer.py`、`workflow/multi_agent_nodes.py`、`workflow/generation_batches.py`、`slm/factories.py`、`rag/`。

**一次完成：**

1. 为正式A组建立与Multi相同的13章输出契约、引用/claim字段和终端校验。A仍由单一生成角色完成；允许使用共同分批策略，但不引入Research/Strategy/Finance独立角色或LLM Critic。不以旧schema结果直接参加A/B比较。
2. 收敛Gemini与Granite的分批实现为共享契约与分组规则，保持完整13章，禁止只有SLM使用简化schema。原产品历史输出保持可加载，不强制把旧数据补成新结果。
3. 实验入口一次注入冻结packet，Research及下游在首次需要证据时就能读取。不能等Writer前的RAG节点才让Research获得本应共享的证据；禁止正式运行偷偷联网补搜。
4. 按优化计划§4.2贯通claim/source字段、版本和定位信息，覆盖Research→Strategy/Finance→Writer→Critic/Revision→Export。校验来源allowlist、引用可解析性和修订后的来源保留。
5. Finance区分用户输入、外部基准、计算结果、假设，按冻结公式、单位、币种、期间与容差做确定性复算。
6. 实现共享Confidence聚合：Web/RAG按同一证据规则处理；普通明确假设不再导致全局low；unsupported/high-impact、裁剪、冲突和未核实重大问题不得升为high；标签变化记录reason。
7. 区分模型提出的支持关系与人工Gold Ledger。存在source_id、URL或模型自报direct都不能作为事实支持已被人工核实的证据；代码只自动验证可确定的结构和约束。

**必要验证：**

- A–D相同packet hash、共同schema/分批规则；旧输出仍可读。
- Web-only、assumption、unsupported、partial/conflict、pruned及来源丢失/新造ID的代表性fixture。
- Finance复算与最终13章/引用契约；正式模式的联网路径确实被关闭。
- 首次不合规记录不能因后续repair而改成首次通过。

**交接：**统一契约和packet示例、变更文件、针对性测试结果、仍未解决的证据链风险。此阶段仅证明工程规则，不能宣称质量已改善。

## 5. S2 — 角色Critic、条件修订、预算和追踪

**目标：**B、C、D使用同一套受限控制机制，先打通Research一条完整路径，再在本包内覆盖Strategy、Finance和final gate。

**读取重点：**优化计划§5、§11；`agents/critic.py`、`workflow/multi_agent_graph.py`、`workflow/multi_agent_nodes.py`、`workflow/nodes.py`、`workflow/state.py`、`workflow/logging.py`、`workflow/run_budget.py`。

**一次完成：**

1. 新增角色感知的ComponentCritiqueReport与固定评分项；各项0–4，代码校验缺项/重复/越界并换算到0–10。Final Critic也提供明确、可验证的gate输入，不把不兼容的旧自报评分直接混用。
2. 固定gate为 `overall_score < 7.0 OR 存在high/critical issue`。路由由代码决定；不增加LLM Supervisor、不动态创建角色。
3. B仅final gate；C/D在Research、Strategy、Finance后各加role gate，Writer后加final gate。失败才触发一次定向语义修订；通过就跳过，不实现新的固定修订实验路径。
4. 保存初稿、critique、修订稿和有效版本，后续节点只接收正确的有效产物。修订后只做规定的结构/确定性校验，不引入第二轮语义Critic；重大语义问题保留 `unverified_after_revision`，critical保持需人工处理，不能因schema通过自动清除。
5. 区分结构repair与语义revision，按逻辑任务归并重试。每个角色/最终稿修订最多一次，所有batch、repair、revision计入所属节点和run的共同预算，不能通过分批重置计时。
6. 共用请求、token、节点墙钟与run墙钟预算；处理预算耗尽、超时、取消和API失败，使其落盘并正常终止。客户端停止等待后，不得无检查地叠加仍在服务端执行的本地请求。
7. 每次实际调用记录 `run_id / logical_task_id / attempt_id / role / purpose / model / usage / status`；角色修订记入Revision。保存route trace及预期交接清单，缺失的应执行交接不能从分母消失。
8. 历史Legacy路径仅作兼容，A/B/C/D配置和版本独立可复现。

**必要验证：**

覆盖Research、Strategy、Finance、final的pass/skip、fail/revise-once、预算耗尽和pending语义状态；覆盖分数换算、禁止第二次修订、错误来源、产物版本交接及失败调用计数。用mock E2E验证流程，不以mock结果冒充模型质量实验。

**交接：**B/C/D路由示例、事件schema、预算边界、测试结果及供Granite注入的统一adapter接口。

## 6. S3 — Granite完整接入与可行性预检

**目标：**D真正执行与C相同的完整角色审查；先确认本机能否承担，再投入正式运行。

**读取重点：**优化计划§6、§12；`slm/config.py`、`slm/client.py`、`slm/factories.py`、`slm/pipeline.py`、`slm/preflight_slm.py`、`slm/tests/` 及S1/S2公共接口。

**一次完成：**

1. 接入本地Granite 4.0 H Micro Q4_K_M及显式32768 context配置；单并发、最多一个加载模型。实测有效context，不把模型标称窗口当成本机可用窗口。
2. 配齐Research、Strategy、Finance、Writer、三个role Critics、final Critic和各适用Revision的Granite调用，禁止隐式回退Gemini或用final-only流程冒充D。
3. 复用S1共同schema/分批与S2控制器；适配结构化输出、一次repair和provider usage。记录量化、模型精确ID、配置版本及运行时版本。
4. 复测当前RAM/VRAM/pagefile基线，不使用设计文档的旧空闲内存数字当作当前事实。资源遥测从运行前覆盖到结束；不支持的项标记缺失及原因，不填0。
5. 用真实规模prompt分别测Research、ComponentCritiqueReport、Finance、Writer batch，并验证完整D smoke；记录prefill与generation的count/duration，分开解释长输入与生成耗时。
6. 执行原限制：单节点含repair/revision最多20分钟，完整Multi最多90分钟；空闲RAM低于2 GiB或pagefile实际使用较基线增加超过2 GiB并持续60秒时停止。不得以每个Writer batch重新获得20分钟延长预算。
7. 冻结前核对输出长度策略与公平性：A–D必须共用输出上限及可比预算规则。如果本地速度要求只对D动态缩短输出、删字段或裁剪证据，停止并说明与共同配置的冲突，不能暗中继续。
8. H 1B是设计中的备选，只有按用户确认的降级决定建立独立版本后才使用；不能替代H Micro已计划运行结果。

**验收与停止：**

- 有真实模型、完整D角色路径、结构/内存/时间门及共同配置的可查证记录。
- D不通过可行性门时保留记录，停止需要D成功的后续安排并请用户确认范围；不擅自增加Granite Single组或更换云平台。
- 预检费用、调用与输出明确标为非正式，不进入正式八次结果。

**交接：**可复用启动命令、有效配置、真实遥测、各门通过/失败原因、共同预算建议和D是否可以进入正式实验。

## 7. S4 — 实验运行器、指标、评分材料与产品展示

**目标：**把已有产品变成能自动运行、可靠留证、直接供次日写作使用的实验版本。

**读取重点：**指标规范§2、§6–10；优化计划§7–8、§10–13；`storage/`、`workflow/logging.py`、`workflow/llm_client.py`、`app.py` 和既有UI测试。

**一次完成：**

1. 建立实验运行器：预建恰好8行manifest，按case分块、块内固定随机种子排列A–D；支持进度查看、预算停止和安全恢复。已完成正式行不可自动重跑；中断后不确定是否已发出的请求不能当作从未执行。
2. 分开记录执行状态、终端契约是否通过、可评分输出是否存在及是否需要人工处理。源ID污染等按协议记失败；可评分失败输出和全部原始记录仍保留。内部实验导出不因外部发布审批而丢失。
3. 完成run/node/role/attempt事件采集、RAM/VRAM/pagefile峰值、请求/token/重试统计。Gemini保留provider原始usage，区分可见输出与thinking等已返回计数；不能把两者遗漏或重复计费。无usage的失败调用保留请求及缺失原因。
4. 实现首次契约通过率、预期交接成功率、调度与审查token占比、完成率、首次完整契约有效计划时间及角色资源汇总。未触发角色为not_applicable；失败、漏采集和零分母分开；不把timeout当成成功时间。
5. 匿名化全部可评分最终输出，去除模型/组别/run_id/资源身份信息，保留内容和引用；映射文件单独存放。保留原计划约20%隐藏复评，8份可评分时约2份，复评不产生新的模型运行。
6. 生成六维评分表及一份共用Claim–Evidence Gold Ledger。审计范围按优化计划§4.4的全部决策关键声明，保留原子化、去重、部分支持、正确假设和高影响判断规则；Codex只辅助提取和定位，人工结论字段保持待填。
7. 编写可复算的指标/统计和图表脚本：三项预设比较的逐case值、配对差值、均值、中位数、IQR及改善/持平/恶化数；比例先在case内计算再等权汇总。没有人工评分时不得生成伪质量结果。
8. 在原Streamlit中接入或明确展示Gemini优化路径与新增节点详情；保留旧runs兼容。D继续用CLI，共用记录可供查看；不开发新前端或专用SLM UI。
9. 形成论文问题1–14到代码、测试、日志、表图和限制的证据映射；仅生成材料和索引，不撰写论文/PPT。

**必要验证：**

- 合成数据可确定复算指标；覆盖失败、缺失、零分母、重复attempt和角色未触发。
- dry-run只生成8个正式槽位；resume不重复成功行，失败不可被覆盖。
- 匿名评分包不泄露身份；Gold Ledger字段可同时复算三个claim指标。
- 从原始事件到结果CSV/图表的追踪链可走通；Streamlit新旧详情验证通过。
- 本包结束前跑一次适当的整合回归；不为文案或低影响样式额外扩展测试。

**交接：**运行器与导出器的实际命令、dry-run清单、测试结果、匿名材料模板、证据目录与待用户完成的输入项。新命令必须实际实现并验证后记录，不能把建议接口写成已可运行命令。

## 8. S5 — 正式实验、人工审核与最终证据

**目标：**执行已经冻结的两个case、四组实验，并交付真实证据。用户要求执行S5即启动本包；不再逐run询问。

**进入条件：**两个case及证据已确认；S1/S2/S4测试通过；D预检通过或用户已明确批准失败/未运行处理；Gemini配额与消费预算可执行；代码、prompt、schema、模型、上下文、分批、修复规则与随机顺序全部冻结。

**一次完成：**

1. 生成复现清单：源设计hash、Git版本及必要的工作树快照、模型与量化、运行时、prompt/schema/evidence/config hash、随机种子与命令。不能只记commit而遗漏实际运行的未提交代码。
2. 如需重新校准，仅使用明确标识的非正式smoke；确认后锁定版本，随后运行8行正式manifest。按冻结顺序执行，本地单并发；所有实际失败保留。
3. 运行期间仅观察状态和资源，不改正式输入、prompt、评分规则或中途调模型。发现影响有效性的bug、超额或必须降级时停止，保留现场并向用户确认新版本/范围。
4. 导出全部适用的自动指标、匿名输出和Gold Ledger待核验材料，把人工审核交给用户；预留1小时，不替用户填写质量分和支持性真值。
5. 用户尚未交回评分时，将本包状态记为 `waiting_for_human_review`。模型运行完成不等于全部评价完成；后续再次执行S5只导入审核并复算，不能重跑模型。
6. 收到审核后校验必需字段，计算六维质量分与三个claim比例，生成B−A、C−B、C−D结果和相应图表。失败输出不填0，实际缺失保持缺失。
7. 对角色级Critic复用C−B质量、安全、完成率和开销判断；对条件修订只核验运行行为。结论限定于两案例工程验证，不报告取消的固定修订比较或交互效应。

**本轮证据目录：**

在设计文件所在的演示目录交付以下结果，并保留工作区内可复算的原始材料与脚本；不得覆盖其他既有实验版本：

```text
01_evaluation_protocol.md
02_frozen_cases_and_evidence_manifest.csv
03_run_manifest.csv
04_agent_and_system_metrics.csv
05_blind_evaluation.csv
06_claim_evidence_gold_ledger.csv
07_results_tables.md
08_figures/
09_failure_analysis.md
11_reproducibility_manifest.md
example_outputs/  # A/B/C/D实际有输出的案例，名称或索引映射到run_id
```

以上是S5的交付目标，当前写计划时不创建占位结果。若目录已有同名结果，使用新的experiment版本目录并更新索引，不覆盖历史。论文/PPT文件明天再制作。

**最终验收：**8个planned rows均有明确状态；全部实际调用与失败可查；每个结果能回溯到输入、版本和原始输出；人工未完成项明确列出；两份设计中的必要指标、限制和论文证据映射有对应材料。

## 9. 重大问题：停止并确认的边界

常规命名、函数组织、共享组件提取和兼容修复由执行Codex自行完成。以下问题会改变用户已确认范围，应立即停止相关操作，说明文件/代码依据、影响及建议，然后请用户确认：

- 需要改变A–D、两个case、模型、运行数、claim分母、质量权重或研究比较。
- Granite无法在现有内存/时间门内完成，或需要只对D改变输出/schema/证据/上下文规则。
- 两份设计出现不能由具体条款澄清的实质冲突，或共同预算无法容纳必需工作而需要改变协议。
- 需要超过约50元预算、开通未经确认的付费服务，或破坏已有数据/用户修改才能继续。
- 正式运行开始后发现影响实验有效性的bug，需要变更冻结代码或重跑受影响条件。
- 必须取消角色级审查、将D改为final-only、增加结构修复/语义修订次数，或降低来源/终端校验才能输出。

不能把正常测试失败、一次可修复schema错误、尚未人工填写评分表视作需要重新批准整个计划。审批等待与已批准范围分开记录；明确的用户选择优先于旧设计的降级建议。

## 10. 每包结束的交接格式

S0建立、后续各包更新 `docs/final_sprint_status.md`，至少包含：

| 字段 | 应记录内容 |
|---|---|
| 当前包与状态 | not_started / in_progress / complete / waiting_for_user / waiting_for_human_review |
| 完成范围 | 实际完成的功能和对应验收项 |
| 代码与版本 | 改动文件、工作树状态、协议/prompt/schema/config版本 |
| 验证 | 实际执行命令、通过/失败/未运行及原因；区分mock与真实模型 |
| 数据与调用 | artifact路径、run_id、正式/非正式标识、消耗及失败 |
| 决策与阻塞 | 已确认选择、待确认项、禁止自动继续的依赖 |
| 下一步入口 | 下一包编号、必须读取的文件、可复用的实际命令 |

轮末回复保持简短，以完成项、验证、阻塞和下一步为主。代码尚未完成、仅mock通过、D未通过预检或人工评分未返回时，都不能把整个冲刺标为完成。

