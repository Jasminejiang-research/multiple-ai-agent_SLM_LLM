# Research 简化与 20 分钟时限：只读实施审查

审查日期：2026-09-07。用户已允许简化 Research；本文件只提出实现与兼容性检查，不修改 runtime、历史结果或生成产物，不调用模型。采用根线程确定的较紧方案。最终 Writer 13 节、Finance 21 行、完整 brief/packet、模型、总请求/总 token 预算及既有 Critic 路由保持。

## 建议实施配置

使用一个共享的 `research-compact-v1` **生成约束层**，覆盖 B/C/D 的初始 Research 与其结构修复；canonical 仍能读取原始完整 Research 和历史运行。不要直接缩小所有角色共用的 `GroundedFinding`、`GroundedClaim`，也不要把旧产物静默转换成新简化产物。

| 项目 | 当前 Research | 本轮紧方案 |
|---|---|---|
| market_trends / customer_notes / competitor_assumptions | 每类 1–6 项 | 每类恰好 1 项 |
| 每个 finding 的 claims | 1–8 条 | 恰好 1 条原子核心声明 |
| unsupported_claims | 0–8 条 | 0–1 条；只容纳一个未被前三项表达的关键问题 |
| 单次 Research 声明出现数 | 理论最多 152；历史实际 17 | 最多 4 |
| analysis_summary | 无实质上限 | ≤280 字符 |
| finding / rationale | 无实质上限 | ≤240 / ≤160 字符 |
| claim_text / premise | 无实质上限 | ≤240 / ≤200 字符 |
| needs_human_review | 无实质上限 | 最多 3 项，每项 ≤140 字符 |
| 正文 / grounding 输出 token 上限 | 每阶段继承全局 8192 | `min(global_cap,640)` / `min(global_cap,2304)` |
| 时间 | 当前非正式试验节点可占满 90 分钟 | 两阶段与唯一结构修复共享一个 1200 秒截止时间 |
| claim 元数据、引用目录、canonical assembly | 完整 | 完整保留，不更换 selector wire |

字符上限使用实际字符串字符数，不是字节数或词数。提示必须明确这些是上限、不是填满目标；不通过截断字符串、删除已生成声明或补写金融表来“修复”。模型超过约束时只使用原有一次结构修复，仍受剩余时间约束。

建议同时给当前无界的 `topic` 加一个很小的界限（例如 64 字符），并令 `claim_domain` 使用短主题标签。否则长 topic/domain 仍能消耗大部分 640/2304 token。此举只控制 Research 文本长度，不应全局限制历史 claim ID 或下游字段。

## 保留什么信息才足以支持下游计划

Research 是三项核心研究发现与少量验证动作，不再承担完整计划的每条事实说明。下游仍接收未经裁剪的完整 brief、packet 和 Finance 合同。

1. **市场**：选一个与 MBA 服务判断直接有关的可证实事实或证据边界。若引用 NCES，保留年份、统计口径及“完成学位数不能直接推出 MBA 招生/TAM/付费需求”的限制，避免再次把单年 1.1m 误写成十年累计、或把硕士中的 business 比例套到所有 graduate degrees。
2. **客户**：选一个明确标注为假设的需求/付费意愿核心判断。US 成人 MBA 人群、英语、导师潜在机构购买者等原始条件仍在完整 brief；不必逐条复制成 Research 元数据对象，不可把 brief 设想说成外部验证事实。
3. **竞争**：选一个冻结材料支持的 Khanmigo 邻近竞争事实，或一个显式待验证的 MBA 差异化假设。不要在一条“原子声明”中同时堆叠功能、价格、学习效果、市场缺口等多个独立判断。
4. **验证动作**：最多三项可分别覆盖需求/付费访谈，MBA 差异化与学习效果测试，内容许可/数据权限前置检查。可在同一行动中列出相关检查，但不能据此宣称许可已经取得、隐私已经合规或学习提升已经证实。unsupported 的额外一条留给前三类确实无法承载的首要未解决问题。

`rationale` 只解释该核心声明的证据适用性、限制或与决策的关系，不能扩展出若干新的独立决策事实；`analysis_summary` 只概括已有条目。这一点必须同时进入正文提示与 Research Critic 的任务边界，否则模型会把被限制的声明转移到没有对应 claims 的自由文本里。

## 明确兼容风险与最小处理

### 1. 640 token 不是字符约束的数学保证

按所有字段填满字符上限，正文约 1900 字符，尚未计入三个 topic 与 JSON 字段名。英语普通短句通常可以较短地表达，但分词密度、数字与转义字符不同，合法长度字符串仍可能超过 640 tokens。必须把“短于上限”写进提示，例如 summary 一句、finding 一句、rationale 一个短解释；离线用冻结案例的完整示例验证 640 token 有余量。不能把 native schema 通过视为不会截断。

阶段上限要真正传到 **同一个 PhysicalRequest**，同步影响 Ollama/Gemini、上下文容量校验、日志和 reservation，不能只写在提示中。保留 global cap 作为外层上限；其他角色继续使用原配置。

### 2. 只有一次结构修复，不能重新分配 20 分钟

现有 `ContractGenerator.generate_task` 已让正文与 grounding 共享一次结构修复，应保留。截止时间应在 Research 首次正文请求前确定，后续阶段、重试和等待都取 `min(Research剩余时间,整份D剩余时间,request上限)`；不得为 grounding 或 repair 创建新的 1200 秒钟。

现有 `ReviewWorkflow` 的 Research 父节点还包含 Research Critic、条件语义修订与 effective 步骤。如果在父节点设置 1200 秒，它们也会共用该时限，这是保守且最容易保持既有控制流的做法。若实现只限制单次 Research 生成任务，必须分别记录 `research_generation_seconds` 与 `research_node_seconds`，不得把前者当成包含 Critic/语义修订的完整 Research 耗时；语义修订仍不能重置整份 D 的 90 分钟。不要为满足 20 分钟静默跳过 C/D 的 Research Critic 或修改 gate 阈值。

### 3. 紧数组约束与修订 lineage

新鲜运行初始 Research 最多四条，后续必须保留/显式关联其 ID、全部原锚点与不确定性。紧配置无法对一份已有十几条声明的旧 Research 直接做可保留全部 lineage 的修订，所以应从新的运行开始；旧运行只读保留。

“每项恰好一个原子声明”也减少了语义修订拆分声明的空间。如果 Critic 发现一项实际上混合多个独立结论，不能让代码删掉旧 ID 来适配。优先在初次正文阶段避免复合声明；必要修订在当前容量与 lineage 内完成，否则保留明确失败/待人工处理。不要以增加修复次数或放宽引用校验补救。

### 4. Critic 需要知道新的 Research 职责边界

四项 Research 指标和 gate 规则可以保持，但 Review 提示应知道这是“三项原子发现＋有限验证动作”的简化研究简报，最终 13 节与财务完整性由后续角色承担。不能单因未在 Research 重复整个 brief/financial ledger 就判遗漏；仍必须检查被选择的核心结论是否误导、缺关键限定条件、把假设当事实或隐去实质风险。B/C/D 应引用同一 Research profile/version；B 原本没有 Research Critic 的实验差异保持。

### 5. 不应删去看似固定的语义状态

本轮保留全部元数据是更小的风险。历史初始 Research 的 17 个 claim 实际都写了 `critic_status=unresolved`，并非 `not_reviewed`。把该字段省略后统一补 `not_reviewed` 会改变置信度及 lineage，不属于无损压缩。

`artifact_version`、`support_assessed_by`、初始无父声明时的 `parent_claim_id=null` 确实可以在未来的显式 wire 版本中由上下文补回；但本轮不需要这么做。confidence/reason 已参与确定性计算和历史变化记录，也不宜顺手删除。

## 三类方案比较

| 方案 | 收益 | 风险/建议 |
|---|---|---|
| 缩小 Research findings/claims 与自由文本边界 | 直接控制实质生成量，并减少下游重复输入；理论 152 条降至 4 条，历史 17 条规模降至最多 4 条 | 本轮首选；注意原子性、修订 lineage 与 Critic 职责 |
| selector 字段别名或固定元数据投影 | 减少字段名与固定值的解码；canonical 可保持完整 | 需要新 wire、prompt、污染检测、fixture、审计适配；根线程决定本轮不做，合理 |
| 单一 claim registry＋多处引用复用 | 同一合法声明跨多个父项时不再重复完整 metadata | 本轮每类只有一项，最多四条，复用收益很小；更复杂，且不能自动把同 ID 的不同意义合并。暂缓 |

历史 grounding：23 个 wire 字段/claim、17 个 claim 出现、66 个 evidence span 引用。原始服务计数 6055 tokens；官方 tokenizer 离线重编码 6000，等值紧凑 JSON 为 4801。两类计数相差 55，未归因。详见本目录 `grounding_minify_audit.json`、`GROUNDING_MINIFY_AUDIT.md`。

## 20 分钟的实际可行性口径

按根线程提供的近期约 5.4 tokens/s，640＋2304＋一次最坏 grounding repair 2304 共 5248 输出 tokens，**仅解码就约 972 秒（16.2 分钟）**，剩余约 228 秒用于输入处理、缓存恢复和其他开销。因此 1200 秒是明确的停止上限，不是成功承诺。

四条简短完整 claim 的通常输出应明显低于 2304 上限；不能把上限当作目标。阶段预算、精简内容与共享截止时间结合，比单纯提高总输出上限更有希望完成。实际是否成功必须以新的真实 Research 同时通过正文、grounding、完整合同/来源/lineage 校验及耗时记录为准。

## 最小验证清单

- B/C/D 相同 Research profile、数组与字符边界；A 的单角色生成保持原状。共有 final/finance 合同不变。
- 初始 Research 总声明数 ≤4；额外独立声明不得借 summary/rationale 逃逸。后者需真实输出/语义审查，结构测试不能证明。
- 超出边界拒绝而非裁剪；阶段输出上限分别为 640/2304 且不得大于全局 cap。
- 正文失败消耗唯一结构修复后，grounding 再失败不得二次修复；grounding repair 与先前正文共享 1200 秒。
- 使用假时钟验证剩余时间递减、跨阶段不重置、外层 90 分钟可提前终止；Critic/语义修订计时范围明确记录。
- 有合法引用、无证据假设、空 unsupported、含一个 unsupported、保留旧 ID 的紧配置修订各有离线覆盖；复杂旧版本 Research 不被强制按新上限重解释。
- 真实成功报告区分原始模型 token、assembly 展开文本与未知 usage；不把生成了正文称为 Research 或计划书完成。

## 审查来源

- 当前 stage：`schemas/contract_outputs.py`、`schemas/evidence.py`、`workflow/two_stage_generation.py`、`workflow/contract_generation.py`、`workflow/review_config.py`、`workflow/review_graph.py`、`agents/component_critic.py`。
- 冻结案例：目标仓库 `docs/final_sprint/s0-v1/cases/ai_education/brief.json`。
- 历史体积分布：目标仓库 `docs/final_sprint/s3-90m-fix-v1/run_01/audit/02_research_generate.raw.txt` 与 `.usage.json`；原始 response/log/tokenizer/hash 已保存在本目录 `grounding_minify_audit.json`。
- 本次仅额外对历史 raw 做了内存字段分布检查（0.57 秒）；未写回历史文件、未读活动大日志、未执行模型。
