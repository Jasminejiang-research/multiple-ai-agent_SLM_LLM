# AI Agent 评价指标规范：A/B 产品级报告版

> 版本：v2.1-product-ab-reporting｜修订日期：2026-09-13  
> 本文件以当前论文大纲和已保存的产品级运行记录为准，报告范围仅包括 Conditions A and B、两个 case 和四个已选定执行。  
> v2.0-fast-generation 及其冻结 hash 作为原始设计与复现历史保留；旧的 `@ai_agent_evaluation_metrics_spec.md` 同样仅作历史记录。

# 1. 实验比较框架【当前报告范围】

| 条件 | 架构 | 模型 | 控制方式 | Selected executions |
| ---- | ---- | ---- | ---- | ---- |
| A | Single Agent | Gemini 2.5 Flash | 统一终端检查 | 2 |
| B | Multi-Agent | Gemini 2.5 Flash | 仅最终 Critic，检查失败才修订 | 2 |

两组执行相同的两个 case，每个 `case × condition` 选定一次执行，共 **4 个报告内执行**。预检、能力测试、调试调用和报告范围外的配置不进入结果分母。

由此分别衡量：

- B − A：Gemini 下 Single/Multi 的架构差异。

该比较发生在完整执行路径层面。A 与 B 同时在编排、提示、schema、检索和中间 artifact 上存在差异，因此结果不能被解释为 agent 数量的孤立因果效应。B 使用最终 Critic；两个已记录的 B 执行均进入 Revision，且每个执行者最多使用一次契约纠正机会。

实验单位是 `case_id`，科学样本量为 **n = 2 cases**，结果定位为两案例工程验证。四个执行不代表四个独立样本；每个 cell 仅运行一次，无法估计 cell 内运行方差。

# 2. Tier 0：实验结果是否有效【v2.1 当前要求】

Tier 0 使用以下四项检查：

* **同一实验输入**：同一完整商业 brief、冻结证据包和财务输入在 case 级归档；每个适用角色接收由同一确定性规则生成的角色视图。角色视图可以裁剪重复字段，但同一角色的可用事实集合不得按模型或可比条件改变。
* **同一语义目标**：A/B 生成同一十三章节商业计划，使用统一的事实／假设标注原则、财务引用规则和终端产品检查；条件特有的 prompt、wire schema 和角色视图必须保留原始记录。
* **同一运行规则**：相同工具权限、适用角色的输出上限、结构修复机会、语义修订机会和 60 分钟 run 硬限；角色提示词在执行前固定。
* **完整记录**：记录模型、配置、调用、超时、失败、确定性修复、结构 repair、语义 Revision、prompt/schema 负荷和全部中间 artifact。

以下差异属于被比较路径的一部分：A 为 Single Agent；B 为包含检索、角色分解、分批 Writer、final Critic 和 Revision 的 Multi-Agent 路径。对比结果归属于完整路径，不进一步归因于其中任一单独组件。

# 3. Tier 1：两个主要结果指标【v2.1】

**3.1 Academic Quality Score**

| 维度                 | 权重 |
| -------------------- | ---- |
| 事实与引用正确性     | 25%  |
| 推理与跨章节一致性   | 20%  |
| 指令遵循与结构完整性 | 15%  |
| 商业逻辑与领域合理性 | 15%  |
| 不确定性与置信度校准 | 15%  |
| 表达清晰度与可追溯性 | 10%  |


**3.2 High-impact Unsupported Claim Rate**

# 4. Tier 2：可靠性、速度与资源指标【v2.1】

| 指标 | 当前定义 | 处理规则 |
|---|---|---|
| **Completion rate** | 在 60 分钟共同硬限内完成该条件规定的全部角色、Critic/路由、统一终端检查并生成 canonical 输出的 selected executions / 全部 selected executions | 超时、API、Schema、模型和资源失败均保留在分母 |
| **Requests / tokens / retries** | 所有实际调用，包含失败、Critic、结构 repair 和语义 Revision | 按 provider、角色、目的和成功状态分项 |
| **Prompt / schema 负荷** | 每次调用的指令字符数、完整 prompt 字符数、provider 实际输入 tokens、wire schema UTF-8 字节数 | 用于检验加速机制是否真正减少隐性输入 |
| **阶段耗时** | prefill、generation、校验、确定性展开、Critic、Revision、导出及清理耗时 | 缺失采样与零耗时分开标记 |

统一终端检查要求输出可解析、必需章节完整、引用标识符可解析、财务引用符合冻结输入与公式规则，并保留事实、假设和无支持论断的显式状态。人工核验后来判定“已有 ID 但语义上仍无充分支持”的 claim 进入 Tier 1/Tier 3 指标，不追溯改写自动完成状态。Critic 发现的问题如果未在 Revision 后再次接受语义 Critic 检查，必须保持“未复核”状态，不能因结构化输出成功而宣称已经解决。

# 5. Tier 3：Confidence 指标【当前定义】

**Claim grounding rate** = 有来源支撑的 claim / 总 claim

**Assumption transparency** = 正确标注为 assumption 的 claim / 实际无支撑的 claim

（**Assumption transparency** 衡量“诚实度”而非“正确性”：它区分无支撑论断本身与系统是否明确承认该论断缺乏支持。）

# 6. 单个 Agent 的表现指标

本节用于诊断各角色的执行可靠性与资源消耗。最终内容的事实正确性、推理质量、商业合理性和表达质量，统一由 Tier 1 评价，不再为每个 Agent 的中间输出设置独立人工评分。

**6.1 核心指标：首次输出契约通过率**

$$
\text{首次输出契约通过率}
=
\frac{\text{首次提交即通过预设自动检查的逻辑任务数}}
{\text{已触发的逻辑任务总数}}
$$

“输出契约”指执行前固定、可以由程序明确判断的要求，例如：

* 通用检查：输出可解析、必需字段齐全、字段类型合法。
* Research / RAG：引用的 `source_id` 存在于冻结证据包中，来源符合 allowlist。
* Finance：按照预设公式与容差复算数值，检查结构化单位、币种和期间字段。
* Writer / Export：必需章节齐全、引用编号可以解析、导出结构符合要求。

这些检查合并为一次契约判定；失败时保留具体错误类型，不再为每个检查项单独建立主要指标。

计算规则：

* 一个逻辑任务及其重试视为同一个任务，重试不增加分母。
* 首次提交失败、超时或没有输出，均记为首次未通过；后续修复成功不能回改首次结果。
* 按工作流规则未触发的角色记为 `not_applicable`。
* 契约及检查规则在执行前固定，同一角色在可比条件下使用相同规则。

**该指标衡量可检查要求的符合程度。** 引用编号有效不代表来源支持论断；Critic 的输出格式合规也不代表其判断正确。不同角色承担不同任务，因此不能仅凭契约通过率进行能力排名。

**6.2 资源消耗：复用 Tier 2，按角色展示**

将 Tier 2 已记录的 **token 数、请求数和重试数**按 Agent 角色汇总，用于定位主要资源消耗和反复重试的位置。

统计包含失败尝试和修复调用，不只统计最终成功的调用。无需为角色重新建立资源评分，也不将资源消耗与质量合成为总分。

---

# 7. Multi-Agent 协作指标

协作是否改善最终结果，直接使用第 1 节已有的实验对照，并复用：

* Tier 1：Academic Quality Score、High-impact Unsupported Claim Rate。
* Tier 2：Completion rate、elapsed time、prompt/schema、token、request 与 retry 记录。

不再另设一套人工“协作质量评分”。本节仅保留以下三项自动过程诊断。

| 指标                            | 定义                                                                   | 用途                           |
| ------------------------------- | ---------------------------------------------------------------------- | ------------------------------ |
| **交接成功率**            | 在规定预算内完成的有效逻辑交接数 / 应执行的逻辑交接总数                | 判断上游产物是否正确交付给下游 |
| **调度与审查 token 占比** | Supervisor 与 Critic 模型调用消耗的 token / 全流程模型调用消耗的 token | 展示调度和审查占用的资源比例   |
| **Revision token 占比** | Revision 模型调用消耗的 token / 全流程模型调用消耗的 token | 单独展示修订阶段的资源比例，不与调度与审查指标合并 |

**交接成功率的计算规则**

有效交接要求：指定下游收到正确的上游产物及版本，并且其执行所需的依赖已经满足。第 6 节检查产物自身是否符合契约，本指标检查产物之间的传递和依赖关系。

应执行的交接清单由预设工作流和分支规则确定，不能仅以日志中已经成功发生的交接作为分母：

* 应发生但因上游失败而未完成的交接，记为未成功。
* 按规则跳过的分支，不计入应执行交接。
* 每条逻辑交接计一次，重传不增加分母。
* 缺少必要日志时标记缺失，不能推定交接成功。

该指标检查结构化交接，不判断下游是否充分理解或利用了上游内容。

**调度与审查及 Revision token 占比的计算规则**

每次模型调用按照预先定义的职责唯一归类，包含其实际输入、输出及重试消耗。调度与审查 token 占比只包含 Supervisor 与 Critic；修订调用归入 Revision 并通过 Revision token 占比单独报告。交接文本已进入下游输入 token 时，不再额外增加一笔“handoff token”。本研究的 Supervisor 为确定性控制节点且不发起模型调用，因此已记录的调度与审查 token 占比实际仅反映 Critic 消耗。

两个比例均只描述资源构成，不具有“越低越好”的单一方向，必须与最终质量、完成率和总 token 联合解释。在两个已选定 B 执行中，正式调度与审查 token 占比为 **57,383 / 689,026 = 8.33%**，Revision token 占比为 **271,380 / 689,026 = 39.39%**。二者不得合并为论文中的正式指标。

Single-Agent 条件的协作专属指标记为 `not_applicable`。预算上限、修订次数和终止规则是否得到遵守，复用 Tier 0 的规则检查与已有日志，不再增加协作评分。

---

# 8. 人工与自动评价的边界

人工评价集中于最终输出，不对每个 Agent 的中间输出另行评分。人工评分和 claim ledger 的记录保存在 `@final paper/evaluation_by_human_being/`；只有能够映射到本规范第 11.6 节四个 selected executions 的评价结果才能进入论文统计。

| 评价内容                                      | 方式         | 人工具体负责什么                                          |
| --------------------------------------------- | ------------ | --------------------------------------------------------- |
| 六维 Academic Quality Score                   | 人工         | 按统一 rubric 对最终输出评分                              |
| High-impact Unsupported Claim Rate            | 人工＋自动化 | 判断 claim 是否属于高影响、是否得到充分支持；程序计算比例 |
| Claim grounding rate                          | 人工＋自动化 | 判断 claim 是否得到来源支持；程序计算比例                 |
| Assumption transparency                       | 人工＋自动化 | 判断无支撑 claim 是否正确标注为 assumption；程序计算比例  |
| 首次输出契约通过率、交接成功率                | 自动化       | 无逐项人工评分                                            |
| 完成率、elapsed time、token、请求、重试及角色资源汇总 | 自动化       | 无逐项人工评分                                            |
| 调度与审查 token 占比、Revision token 占比    | 自动化       | 无逐项人工评分                                            |
| 版本、输入一致性、路由、修订次数和预算检查    | 自动化       | 无逐项人工评分                                            |
| 第 9 节的统计计算                             | 自动化       | 无新增人工评分                                            |

**Claim 核验统一记录一次，供 Tier 1 和 Tier 3 共用。** 不为三个 claim 指标分别进行三轮审核，也不另做各 Agent 中间输出的 claim 审计。

取消以下独立人工任务：是否可用判定、完整的问题严重性分级、Critic TP/FP/FN、Revision 修复与新增缺陷核验、人工编辑计时、成对偏好评分。高影响 claim 的识别继续保留，因为现有主要指标需要它。

LLM/Codex Judge 可以辅助提取待审核 claim，或用于可选的敏感性分析；其判断不能直接充当事实支持性或最终质量的真值。

---

# 9. 统计报告方式

独立分析单位为 `case_id`，科学样本量为 **n = 2 cases**。每个 cell 只有一次 selected execution；不存在可用于估计运行方差的重复运行。

沿用第 1 节的预设比较，每项比较统一报告：

* 每个 case 的双方原始值及失败、缺失状态。
* 完整配对数量和逐 case 配对差值。
* **平均配对差值作为主要效应量**，中位数差值及差值的 IQR 作为补充。
* 改善、持平和恶化的 case 数，注明实际配对分母。

比例指标先在每个 case 内计算，再对适用 case 等权平均；保留各 case 的分子、分母及有效 case 数。

失败和缺失按以下方式处理：

* 没有可评分输出时，质量分记为缺失，不能填 0；同时报告全部 selected executions 的完成率。
* 未完成的运行不将 3600 秒硬限当作成功耗时参与均值，失败状态与实耗资源仍保留。
* token、请求和重试等资源统计包含失败尝试的实际消耗。
* 分母为 0、运行失败和漏采集分别标记，不能混为同一种缺失。

**置信区间和显著性检验均为可选的探索性补充。** 如使用 Bootstrap，应以整个 case 为重采样单位，保留配对结构；如进行检验，应预先指定一种适用的配对检验，对同一检验族进行 Holm 校正，不根据结果挑选方法。

正文集中展示条件汇总表和配对比较表，逐 case 明细及过程诊断放入附表。结论首先限定于本次两个 case；不把“不显著”解释为等效或非劣。

---

# 10. 工程解释与报告规则

工程决策复用 Tier 1–3 和第 6–7 节的结果，不新增中间输出人工标注。方案选择考虑最终质量、完成率与资源消耗；运行限制由自动日志检查。

| 决策                                   | 当前依据或报告规则                                                                                                                                                                                |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Condition B 的 Critic/Revision 是否按记录执行** | 两个 B 执行都完成 final Critic 并进入 Revision。Berlin 与 MBA 的 Revision 各产生一次契约纠正重试。是否存在 correction event 只表示该阶段自身发生过重试，不能作为 Revision gate 是否启动的指标。 |
| **是否接受 Confidence 改造**     | 根据 Claim grounding rate、Assumption transparency 的变化，以及高影响无支撑 claim 率判断。删除“过度保守率下降 ≥25%”，因为该指标已不在新版 Tier 3 中；不另设替代性的任意百分比门槛。                |
| **论文如何表达优势**             | 默认明确表述“在本次测试中质量更高”“token 消耗更少”等具体结果。预先设定最小实际差异，并不自动足以支持总体性的`outperforms`；表述范围应与证据相匹配。                                             |

Token、时间与完成率分别报告，不合成为单一效率分数。

每项比较应报告两个 case 的完整配对情况；缺少配对时须明确标注，同时报告失败，不能用剩余成功 case 代替完整比较。

每项 B−A 比较报告两个 case 的完整配对、原始值和逐 case 差异；结构 repair 与语义 Revision 分开计数。

---

# 11. A/B 紧凑生成与审查记录

## 11.1 当前报告设计

* 报告 A/B、两个 case、四个已选定执行和 B−A 的逐 case 配对比较。
* A 保持 Single Agent；B 使用 Research、Strategy、Finance、Writer、final Critic 和 Revision 路径。
* Tier 1 权重、一次性 claim 核验和统计方法保持不变。
* 每个执行者最多一次契约纠正机会；Revision 后没有第二轮语义 Critic。结构 repair／correction retry 与正常 Revision 阶段分开计数。

## 11.2 指令、wire schema 与 canonical 输出

* 每次调用的公共 system 指令与当前角色/任务指令合计不超过 **500 个 Unicode 字符**。冻结 brief、角色视图、证据片段、上游交接和 wire schema 不计入该 500 字符，但必须分别记录完整字符数与 tokens。
* 模型只生成无描述、少嵌套的轻量 JSON wire object；不使用 YAML。字段保持简短且可读，由确定性代码无损展开为既有 canonical Pydantic 契约。
* 适用调用使用保存的规范化 prompt、角色视图、字段语义和 wire schema，并执行本地校验。
* 当前“正文调用＋声明/grounding 调用”改为一次紧凑生成：正文同时携带冻结短证据 ID。代码根据预先冻结的映射补齐 `source_id`、chunk、quote/line、snapshot hash、claim lineage 和 canonical 字段；代码不得创造模型未选择的事实支持。

## 11.3 确定性角色视图与交接

* 完整 brief、证据包、上游 artifact 和所有原始响应继续不可变归档。
* 进入模型的角色视图由版本化确定性规则生成。下游交接只含当前角色必需的 claim ID、单句结论、claim type/status、短证据 ID、财务 ID、置信度候选和未解决问题；不得携带历史对话、旧修复文本或重复完整元数据。
* 不增加模型摘要 Agent。裁剪规则、证据路由和胶囊生成规则必须保存版本或 hash。
* 短引用使用 `[E01]` 一类 case 内稳定 ID。每个业务角色仍对自己提出的事实选择证据；Writer 继承这些映射，不能重新发明或替换引用。

## 11.4 Critic、Revision 与实际记录字段

论文只报告 Critic 原始文件中实际存在的 `overall_score`、issue list、severity distribution 和 `must_fix_before_export` 条目：

| Case | Overall score | Issues | Severity distribution | Must-fix |
|---|---:|---:|---|---:|
| Berlin | 3.0 | 12 | 4 critical, 4 high, 4 medium | 6 |
| MBA | 4.0 | 7 | 4 high, 3 medium | 4 |

两个 B 执行均完成 final Critic 并进入 Revision，且两次 Revision 各记录一次契约纠正重试。两者在 Revision 后都没有第二次语义 Critic 调用，因此 pre-revision issue register、Revision 的 applied-critique summaries 与 recorded unresolved issues 必须分别保存；不得把未重新核验的问题写成已解决。

允许的机械修复仅包括提取唯一完整 JSON object、删除 schema 外字段和冻结别名／枚举的无歧义归一化；每次修改保存 diff。代码不得补写论断、引用、数字或把 unsupported 改为 supported。

## 11.5 工程预算

以下数值作为适用调用的工程设计目标；实际 provider token 数和完整 prompt 负荷另行记录：

| 调用 | 目标输入上限 | 输出上限 | 目标墙钟时间 |
|---|---:|---:|---:|
| Research | 2,500 tokens | 450 tokens | 4 分钟 |
| Strategy | 2,600 | 500 | 4 分钟 |
| Finance | 3,000 | 600 | 5 分钟 |
| Writer / Single Agent | 6,500 | 1,800 | 7 分钟 |
| Final Critic | 3,500 | 250 | 2.5 分钟 |
| 单次语义 patch | 1,800 | 300 | 最多 3 分钟 |

60 分钟为 A/B 共同 run 硬停止。达到时间或预算硬门后保存已有 artifact 和失败状态，不延长、重置或用后续成功覆盖该次执行。

## 11.6 记录边界与解释

论文结果只使用以下四个 selected executions：Berlin A/B 来自 `berlin-restaurant-waste-product-ab-v1-20260912`；MBA A 来自 `mba-ai-tutor-us-product-ab-v1-20260913/A`，MBA B 来自 `mba-ai-tutor-us-product-b-v2-20260913/B`。MBA 的 `mba-ai-tutor-a-separated-v1-20260912` 与 `mba-ai-tutor-b-separated-v1-20260912` 仅为上述最终产物的展示副本。两个 case 均以逐 case 的 B−A 差异为分析单位；selected records 使用同一 98-file code-inventory hash，且同一 case 内的 canonical input hash 一致。预检、能力测试、调试调用和其他记录不进入正文统计。
