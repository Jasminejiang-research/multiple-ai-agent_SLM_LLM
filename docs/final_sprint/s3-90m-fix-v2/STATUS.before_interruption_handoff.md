<!-- s3-90m-fix-v2 real-run authorized -->
# 最新 S3：用户已批准新的独立90分钟完整D复测

用户明确回复“批准新的90分钟完整D复测”。本次AI教育/同一Granite CPU，5400秒独立上限、8192输出、最多36请求/50万预算tokens；原16请求/296569预算tokens/10193.483秒独立保留。正式公共配置与Gemini未改动。

修复已完成782项完整回归、132项安装验证、26项运行器验证；真实新复测准备启动，尚未证明完整计划书成功。运行入口与记录位于 docs/final_sprint/s3-90m-fix-v2/；最终以run_01/probe/result.json及更新HANDOFF.md为准。未启动正式S5八槽。

---
<!-- s3-90m-fix-v2 preserved pre-run records -->

<!-- s3-90m-fix-v2 current -->
# 最新 S3：声明身份与待机修复已安装，真实完整D待复测

**完整计划书尚未生成；不能宣称90分钟达标。** 最新失败已定位：span-ID被误当声明ID导致跨语义碰撞；Windows三段睡眠合计49分49.45秒。旧页文件采样超时已修复，但旧资源passed仅代表观测点，40分钟空档不能认证连续资源门通过。真实原始记录保留。

15文件精准安装、268文件快照/安装hash一致、8个before备份、2943历史文件未变。完整回归 782 passed, 25 deselected, 3 subtests passed in 177.13s (0:02:57)；安装后 132 passed in 8.73s；运行器 26 passed in 3.35s。共享prompt=v7-claim-identity、canonical=v5，两阶段/完整13节/21行财务/grounding/lineage/Critic/修复次数均保留。

本包修复后真实调用0。此前本轮v1为3请求/5405.172秒含清理，Research正文通过、grounding身份冲突，完整D未启动。累计16请求/296569预算tokens/10193.483秒，原4小时余额4206.517秒。新独立90分钟完整D方案待用户确认，不清除历史消耗；明确方案与入口见 docs/final_sprint/s3-90m-fix-v2/NEXT_RUN_PROPOSAL.md。

详细交接：docs/final_sprint/s3-90m-fix-v2/HANDOFF.md。Gemini0、正式0/8，公共正式预算不变；新prompt需共同重冻，未自动进入下一工作包。

---
<!-- s3-90m-fix-v2 preserved previous records -->

<!-- s3-90m-fix-v1 final -->
# 最新 S3：90分钟恢复验证已结束

status=failed；完整计划书=尚未生成；Research=failed，完整D=not_run。真实3请求/5405.172秒。详细实际结论与阻塞见docs/final_sprint/s3-90m-fix-v1/HANDOFF.md和run_01/probe/result.json。

10文件修复已安装；完整离线733 passed/25 deselected/3 subtests passed、安装后108 passed、预算运行器10 passed。Windows原生页文件采样与绑定身份停机、无损两阶段prompt压缩、预检Writer一致性已实现。每份计划书5400秒独立截止；旧请求/token额度不重置。累计16请求/296569预算tokens/10193.483秒，后续只承接本包最新result，不使用旧余额。

prompt=v6-compact-two-stage，canonical仍v5；完整契约和正式公共配置不变。保留2623历史文件及before备份；Gemini调用0、正式实验0/8，未自动启动下一工作包。结构验收与人评质量分开，不能由局部Research通过推断完整D成功。

---
<!-- s3-90m-fix-v1 previous records -->

<!-- s3-90m-fix-v1 running -->
# 最新 S3：90分钟恢复修复已安装，真实验证准备启动

用户要求LLM、SLM各自每份完整计划书最多5400秒。本包修复Windows页文件原生采样、绑定身份的服务停止、共享两阶段prompt冗余及Writer预检一致性；完整13章/财务/grounding/lineage/Critic与一次结构修复保留。

261文件快照、10文件精确安装及旧版本备份完成。完整离线733 passed/25 deselected/3 subtests passed（196.77秒），安装后108 passed（7.72秒），预算运行器10 passed（2.02秒），pip check通过。正式公共预算及历史数据不变。

真实AI教育SLM测试承接13请求/预算扣记191323tokens/4788.311秒历史累计；本次最多5400秒、剩余23请求/308677tokens，单次8192。先真实Research通过后全新完整D，两者共享本次截止；不重置旧累计额度、不重发未知请求。当前尚未生成完整计划书，实际结果以docs/final_sprint/s3-90m-fix-v1/run_01/probe/result.json及HANDOFF.md为准。Gemini调用0，正式实验0/8；未启动S5正式运行。

---
<!-- s3-90m-fix-v1 previous records -->

<!-- s3-two-stage-v1 final -->
# 最新 S3：两阶段方案已实施，真实验证已结束

2026-09-07。用户已明确批准统一A–D两阶段生成。代码已安装，**尚未生成完整计划书**。Research=failed，完整D=not_run。最终交接：docs/final_sprint/s3-two-stage-v1/HANDOFF.md。

共享contract=proposal-grounding-v5-two-stage，prompt=grounded-generation-v5-two-stage。先锁定正文/财务值，后生成声明和精确片段选择；原完整校验保留，两个阶段只共享一次结构修复，正常A/B/C/D=8/15/18/18请求。

完整回归702 passed/25 deselected/3 subtests passed，172.06秒；安装后30 passed，7.40秒。16文件变更，256文件快照、13个before备份及2254历史文件均校验通过。正式公共预算不变。

本轮真实2请求/300.640秒；已知实测5294tokens，另1次用量未知，保留114777tokens预留，本轮预算扣记120071tokens。原4小时额度累计13请求/预算扣记191323tokens/4788.311秒。剩余23请求/308677tokens/9611.689秒；后续承接本包run_01/probe/result.json，不重置。

Research正文941输出tokens、230.172秒通过；第二阶段在输入处理时因页文件采集8秒超时触发资源门而取消，不能判断其引用是否会合格。完整D未运行。最低RAM约1.87GiB；服务已关闭，进程/端口/活动lease均为0，未知请求lease已原样归档。下一入口是S3资源采样可靠性与两阶段Research恢复验证，不能直接声明两阶段/完整D验收通过。

真实阻塞、来源/正文展开审计、结束后资源与进程核验见本包HANDOFF.md和run_01/audit/。Gemini调用0，正式实验0/8，未启动S5正式运行。新的共享协议须在正式预检后重新冻结；旧单阶段产物不混入新协议比较。

---
<!-- s3-two-stage-v1 prior records -->

<!-- s3-two-stage-v1 current -->
# 最新 S3：已批准两阶段生成，工程验证完成，真实测试启动

用户已明确批准统一 A–D 两阶段生成方案。实现及授权见 docs/final_sprint/s3-two-stage-v1/IMPLEMENTATION.md。
正文/完整财务值先生成并锁定，再生成声明和精确片段选择；最终按原完整 canonical 契约验收。A/B/C/D 正常调用数8/15/18/18；两个阶段共享一次结构修复，Critic与条件Revision规则不变。

离线测试与无模型演练证据见本包 validation/。真实测试承接最新累计11请求、71252tokens、4487.671秒，剩余25请求、428748tokens、9912.329秒，不重置。先真实Research通过后才运行完整D；启动不代表已成功生成计划书。

原未提交文件已备份；旧运行和正式公共预算不变，Gemini/正式实验/S5启动均未执行。结果以本包run_01/probe/result.json、HANDOFF.md及后续最新记录为准。

---
<!-- s3-two-stage-v1 history -->

<!-- s3-reference-fix-v3 current -->
# 最新 S3 精准修复：代码已交付，Research 仍阻塞

2026-09-07。**财务引用约束、评分规则和具体错误反馈已实现并验证；SLM 仍未生成完整计划书，完整 D 未启动。** 最终总交接为 docs/final_sprint/s3-reference-fix-v3/HANDOFF.md。

最终保留 s3-reference-fix-v2 的 13 文件改动：财务闭集/长度/严格唯一性校验、0–1 评分、来源 ID/chunk/hash 闭集、正文与来源锚说明及多问题反馈。共享 contract=proposal-grounding-v3-frozen-reference-bounds，prompt=grounded-generation-v3-explicit-anchors。v3 的 verbatim_parent_text 字段别名未改善真实验收，已撤回；活动字段仍为原 content_anchor，试验原始数据和代码完整保留。

最终保留版本完整回归：**673 passed / 25 deselected / 3 subtests passed，120.30 秒**。恢复后 253 文件 hash 与该完整回归副本全匹配，**专项 20 passed，1.43 秒**。所有原始未提交版本保存在各包 before/，历史运行未覆盖，未 commit。别名试验的 676/23 项测试仅属历史验证，不作为当前版本计数或真实模型成功证据。

三轮真实验证新增 **9 请求、47349 tokens、39 分 26 秒**；6 个 Research 响应均自然 stop，但每轮唯一结构修复后仍存在正文锚/引文不匹配，完整契约失败。因此后续完整 D 不运行。没有通过去重、补写、放宽校验或延长修复次数伪造成功。

原四小时额度累计 **11 请求、71252 tokens、4487.671 秒（1 小时 14 分 48 秒）**；剩余 **25 请求、428748 tokens、9912.329 秒（2 小时 45 分 12 秒）**。停止原因是业务失败，预算未耗尽。后续如获批，必须以 v3/run_01/probe/result.json 的最新累计值承接，不能复用较早启动记录重置。

模型服务已关闭；最后核验模型进程/11434 监听/活动 lease 均为 0。所有资源保护 passed，正式公共配置 hash 未变，实际 Granite CPU/32K、温度、输入及预算范围保持原样；正式实验 0/8、Gemini 调用 0。

下一入口仍为 **S3 Research**。本包 NEXT_STEP_PROPOSAL.md 给出待确认的统一 A–D 两阶段生成方案；它改变调用结构，按用户原要求须确认后实施，本轮未执行。S5 准备已完成的历史状态保留；正式运行仍待 D 门、输入批准、Gemini 条件、公共版本冻结和明确启动等原依赖，没有自动执行下一编号工作包。

---
<!-- s3-reference-fix-v3 history -->

<!-- s3-reference-fix-v2 current -->
# 最新 S3 精准修复：v3 共享契约已安装，真实 Research 复测进行中

2026-09-07。用户批准按财务引用、评分与错误反馈建议修复。第一轮修复已证实解决无限财务数组和评分越界：Research 2533 / 2222 输出 tokens 均自然 stop，唯一结构修复后引用合法无重复，但内容锚未指向本段正文，完整契约失败。第一轮最终记录见 s3-reference-fix-v1/HANDOFF.md；旧“进行中”文字按历史原样保留，以新结果为准。

已继续补齐同一问题的内容锚/来源规则：共享 prompt=grounded-generation-v3-explicit-anchors、contract=proposal-grounding-v3-frozen-reference-bounds。来源 ID、chunk ID、hash 使用冻结集合约束；正文锚必须匹配所属正文，不以 claim_text 或来源摘录代替；结构修复反馈同时诊断重复、评分、锚与来源错误。完整验证门、禁止引用污染规则及一次结构修复次数保持不变。

实际离线结果：**673 passed / 25 deselected / 3 subtests passed，120.30 秒**；累计预算运行器 **7 passed，2.86 秒**；目标安装后 **20 passed，1.54 秒**。13 个不同源码/测试文件经过两轮修复；各轮 before/ 保留安装前的未提交版本，原始运行数据不覆盖。

补充修复报告：docs/final_sprint/s3-reference-fix-v2/。运行使用 253 文件不可变副本，原生长度探针已通过，真实 AI 教育 Research 正在执行。仅自然结束且通过完整契约后启动全新完整 D，当前没有完整计划书成功证据。

不重置已批准额度：承接最初失败和第一轮修复的累计 **5 请求、37864 tokens、2831.124 秒**，本轮起始剩余 **31 请求、462136 tokens、11568.876 秒**。探针、Research 与完整 D 共用原 4 小时/36 请求/50 万 tokens 总限，单次输出 8192。正式公共 A–D 配置、实际模型、CPU 路径、温度、输入、实验范围未变；Gemini 调用 0、正式实验 0/8。

最终结果将在本轮结束后写入 s3-reference-fix-v2/run_01/probe/result.json 和 HANDOFF.md。S5 准备状态及正式运行阻塞仍按下方原交接；未执行下一编号工作包。

---
<!-- s3-reference-fix-v2 history -->

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
