# 权威rubric与claim审计规则（原文摘录）

版本 final-rubric-v1。来源及SHA-256见baseline.json；下文逐字摘自权威设计，不另造评分项。

### 3.2 两个主要结果指标与六维 Academic Quality rubric

| 层级 | 主指标 | 定义 |
|---|---|---|
| 学术质量 | Blinded Academic Quality Score，0–100 | 六维人工盲评加权分 |
| 安全护栏 | High-impact unsupported claim rate | 高影响但无直接证据或错误引用的 factual claim 比例 |

Academic Quality 使用以下固定维度、权重和 English anchors。章节齐全只影响结构维度，不能自动产生高总分；有充分理由的 `low` 不得因标签本身被扣分。

| ID / Dimension | Weight | Score 1 anchor | Score 3 anchor | Score 5 anchor |
|---|---:|---|---|---|
| AQ1 Factual and citation correctness | 25% | Decision-critical factual claims are frequently unsupported, contradicted, fabricated, or linked to mismatched citations. | Most decision-critical facts are verifiable, but one or more material support gaps or citation mismatches remain. | All audited decision-critical factual claims are directly supported by credible evidence or explicitly identified as unsupported. |
| AQ2 Reasoning and cross-section consistency | 20% | Core conclusions conflict with assumptions, evidence, calculations, or other sections; the reasoning chain breaks. | The plan is mostly coherent, but some evidence-to-recommendation links are implicit, incomplete, or weak. | Evidence, assumptions, calculations, recommendations, and cross-section dependencies form a coherent and explicit reasoning chain. |
| AQ3 Instruction adherence and structural completeness | 15% | A required section, field, or material instruction is missing or unusable. | The required structure is present, but some sections are generic, thin, or only formally complete. | Every required element is both contract-compliant and substantively developed for the case. |
| AQ4 Business logic and domain plausibility | 15% | Core commercial logic is infeasible, internally implausible, or materially detached from the domain. | The plan is broadly plausible but still requires material expert judgement or operational clarification. | The commercial logic is concrete, domain-appropriate, internally feasible, and translates into actionable decisions. |
| AQ5 Uncertainty and confidence calibration | 15% | Unsupported facts are presented with unjustified certainty, or mechanical labels obscure rather than communicate uncertainty. | Facts, assumptions, recommendations, and unknowns are usually distinguished, with some inconsistent labels or explanations. | Confidence labels and reasons consistently reflect the evidence state; justified low confidence is explicit and is not penalized. |
| AQ6 Clarity and traceability | 10% | The output is difficult to follow and material claims cannot be traced to evidence, assumptions, or upstream analysis. | The plan is generally readable and traceable, but some important links require inference. | The plan is concise, readable, and each material conclusion is readily traceable to its evidence, assumption, or calculation. |

**2/4分规则：** `2`表示在1与3锚点之间，问题仍明显但未达到1分严重度；`4`表示在3与5之间，已经较强但仍存在阻止5分的具体缺口。评审者必须记录缺口，不得仅因13章齐全而把AQ3评为4/5。

换算公式：

```text
Academic Score = 100 × Σ[w_d × (dimension_score_d − 1) / 4]
```

两个非正式评分示例仅用于校准评分者，不进入正式实验：

- **Example A — evidence-traceable launch plan:** `[AQ1..AQ6] = [5,4,5,4,5,4]`，总分 `83.75/100`。关键事实均可追溯，少量执行细节尚不足，因此AQ2/AQ4/AQ6为4而非5。
- **Example B — structurally complete but weakly grounded plan:** `[2,2,5,3,1,3]`，总分 `38.75/100`。13章齐全使AQ3为5，但无支撑市场事实、断裂推理和机械Confidence显著拉低总分。

所有可评分的A–D canonical最终输出都使用这一rubric。未产生可评分最终稿时，Academic Quality记为missing，并另行保留失败状态和实际资源消耗，不能填0或以补跑成功覆盖。


### 4.4 Confidence 评估指标

审计范围为每份可评分最终输出中的**全部决策关键声明**，覆盖市场、竞争、定价、财务、可行性、合规及其他会实质改变建议的判断。不能只审核模型主动列出的claims，也不能把结果表述为“全文所有声明”。

| 指标 | 冻结公式 |
|---|---|
| Claim Grounding Rate | 审计范围内得到充分来源支持的声明 / 审计范围内全部决策关键声明 |
| Assumption Transparency | 审计范围内正确标注为assumption的实际无支撑声明 / 审计范围内全部实际无支撑声明 |
| High-impact Unsupported Claim Rate | 审计范围内无充分支持的高影响事实声明 / 审计范围内全部高影响事实声明 |

三个指标共用一次人工核验与同一份Claim–Evidence Gold Ledger。分母为0时记`not_applicable`，每个case保留分子、分母、claim ID、证据、标签与理由。

为防止通过增加普通声明或滥贴`assumption`改善分数，正式运行前冻结以下规则：

1. **原子化：** 复合声明优先拆成可独立核验的最小语义单元；
2. **去重：** 同一输出内语义等价、证据义务相同的重复声明只计一次，并保留所有出现位置；不同condition的输出不能跨系统合并计数；
3. **部分支持：** 来源仅覆盖声明的一部分时，应先拆分；无法合理拆分则整条标为`partial_support`，不进入“充分支持”分子；
4. **正确假设：** 只有依赖未来选择、用户输入或明确建模前提且当前不可由外部事实直接验证的声明，才可标为assumption；可外部核验但缺证据的事实不能靠贴`assumption`标签转为透明；
5. **高影响：** 若声明错误会实质改变目标市场、竞争判断、定价、财务可行性、合规风险或主要行动建议，则标为high-impact。


## S0算术勘误（不改上方原文）

原文Example A的[5,4,5,4,5,4]写作83.75，但按两份权威文件一致的权重和公式应为88.75；Example B为38.75，正确。正式计算遵循冻结公式及权重，不能以示例笔误覆盖公式。这是可确定性复算的勘误，不改变实验范围、评分标准或权重。
