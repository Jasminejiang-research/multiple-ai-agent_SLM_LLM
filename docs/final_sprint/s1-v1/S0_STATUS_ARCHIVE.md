# Final sprint 执行交接

更新时间：2026-09-06。当前工作包：**S0**。包状态：**complete（工程准备完成；case仍pending）**。S1–S5：not_started。未执行下一包，未启动正式实验。

## 已完成

- 全文读取两份桌面权威设计与sprint计划；比对仓库镜像逐字一致，记录SHA-256。
- 检查Git、依赖/解释器、旧实现、配置、运行数据与Ollama。开始工作树干净，分支codex/final-sprint、HEAD `4a256c060f39eb1ade754677e9897a94e923bb00`。无既有未提交修改可被覆盖。
- 建立版本化协议、原文rubric及claim审计规则、公共输出/packet/review/gate/调用/交接接口和预算推导。
- 从原候选准备AI education与intelligent ring完整待审brief、财务情景、6份官方HTML+文本快照、固定chunk行定位、allowlist、抓取时间及hash清单；case名称及完整内容尚未获用户确认。
- 建立恰好8个not_run计划槽位；实现离线材料/完整性校验器与未冻结拦截检查，不提供模型运行能力。

## 交付文件

所有路径相对于 `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`：

| 内容 | 文件 |
|---|---|
| S0协议 v1.0、待冻结配置与8行计划 | `docs/final_sprint/s0-v1/PROTOCOL.md`、`protocol.json`、`planned_runs.csv` |
| 公共接口 v1、分批/预算口径、各包差距 | `docs/final_sprint/s0-v1/INTERFACES.md` |
| 原文rubric和claim审计指南 | `docs/final_sprint/s0-v1/EVALUATION_RUBRIC.md` |
| 两case阅读入口 | `docs/final_sprint/s0-v1/CASE_REVIEW.md` |
| 完整brief/packet/审核状态/快照 | `docs/final_sprint/s0-v1/cases/ai_education/`、`cases/intelligent_ring/` |
| 来源/hash清单 | `docs/final_sprint/s0-v1/source_manifest.csv`、`source_capture.json`、`bundle_manifest.json` |
| 基线与历史保留证据 | `docs/final_sprint/s0-v1/BASELINE.md`、`baseline.json`、`legacy_history_readonly_inventory.json` |
| 实际验证记录 | `docs/final_sprint/s0-v1/validation_results.txt` |
| 已实现离线工具/测试 | `evaluation/__init__.py`、`evaluation/s0.py`、`tests/test_s0_preparation.py` |

仅新增以上S0材料和离线工具。生产app/agents/workflow/slm/schema/prompt、.env、SQLite和历史输出均未改；没有commit、迁移数据库或新前端。新增工具不是S1运行时契约实现。当前协议/接口为S0版本；生产prompt/schema/model config版本沿用基线，正式版本尚未冻结。

## 验证结果

- 目标 `.venv/Scripts/python.exe`：Python3.12.10；pip check通过。沙箱内WindowsApps访问失败已在同一解释器沙箱外排除，未重建环境。
- 实际基础回归：`-B -m pytest -q tests slm/tests -p no:cacheprovider` → **362 passed, 25 deselected, 3 subtests passed in 56.73s**。与旧基线一致，0失败；25项live排除，无真实模型调用。
- S0新增离线测试：**14 passed in 1.28s**（暂存材料验证）；安装后的复核见validation_results.txt。
- 离线包完整性验证：valid_preparation，errors=[]；case/hash/行定位/8行组合检查通过。要求正式冻结时因case审核、运行配置及后续验收pending而拒绝放行；此拒绝是预期结果。
- 6份官方网页均HTTP200，保存原始响应与提取文本，经过内容/固定片段检查；不是只保存URL或搜索摘要。
- 本包Gemini/Granite生成调用 **0**，正式runs **0/8启动**，预检/smoke/warm-up **0**，充值 **0**。无新增候选输出、人评质量分或Gold真值。

## 决策、待定项与阻塞

1. **case内容审核pending**：AI education保留美国成人MBA案例辅导；intelligent ring保留旧APPLE类别进入意图，明确为假设任务，不声称真实产品已发布。所有新增财务数字都是待审建模假设。请核查CASE_REVIEW及完整brief/packet；未确认前不能正式运行。
2. **Gemini额度按用户本轮指示不再调查**：用户暂无记录，记得曾充值、预计够用。标为user_reported_prior_top_up_unverified；免费/付费状态、余额、RPM/TPM/RPD未核实。约50元消费约束不变，不把API key存在或成本配置0当额度证据。此项不阻塞S0/S1；后续遇额度错误真实记账，需充值/超范围消费才确认。
3. **公共预算未冻结**：A/B/C/D最少4/8/11/11调用；全语义分支4/12/18/18；再一次结构repair上界8/24/36/36。18请求与1024输出仅预检起点，不能当已通过配置。现有Gemini实际51/600000与SLM18/300000不能直接沿用为共同上限。
4. **D可行性未知，留S3**：Ollama已安装但服务拒绝连接；默认模型manifest目录为空。未测Granite、有效32768 context、时间或内存；不是D正式失败。现有SLM指向SiliconFlow/Qwen且pruning开启，禁止将旧CLI输出当D；S0未启动它。
5. **实现差距按包移交**：S1统一A输出、分批、证据来源与Confidence；S2角色Critic/条件revision及时间/attempt/handoff；S3本地Granite；S4运行器/评价/展示。详见INTERFACES，不自动实施。
6. **原文算术勘误**：优化设计校准Example A分值[5,4,5,4,5,4]按固定权重/公式应88.75，原文83.75有笔误。保留原文并附勘误，公式/权重不改；是明确可复算问题，无需改变实验范围。Example B的38.75正确。
7. 提交绝对截止时间与人工评分实测耗时尚未提供；不假设重新拥有48小时。人工1小时是计划，S0不代填评分。

无妨碍S1合成fixture/接口工作的重大冲突。正式执行仍须两个case内容通过审核、后续包验收和公共配置冻结。后续如需换模型/缩D输出/改矩阵或突破时间/预算，按用户要求停止确认。

## 历史数据与恢复边界

目标仓库data仅.gitkeep，无历史DB/outputs；旧数据仍在原工作区 `C:/Users/JasmineJiang/Projects/multiple_ai_agent`，已只读登记hash。本包不复制/移动/删除历史数据；不要把目标仓库没有DB解释为历史数据损失。保留此前已提交的迁移基线与测试记录。后续在新目录建立版本，不覆盖S0快照；批准或更换case必须记录新版本和输入hash。

## 下一包入口：S1（仅用户要求时）

必读：桌面sprint_plan_及两份权威设计、本状态、S0的PROTOCOL/INTERFACES/CASE_REVIEW及baseline.json，然后读 `schemas/proposal_schema.py`、`schemas/workflow.py`、`schemas/agent_outputs.py`、`agents/research.py`、`agents/writer.py`、`workflow/multi_agent_nodes.py`、`workflow/generation_batches.py`、`slm/factories.py` 和 `rag/`。按已确认技术约定实现，不等待case选题即可使用合成fixture。

以下命令已实现；在目标项目目录运行，受限Codex沙箱可能仍需允许访问Windows Python：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& '.venv/Scripts/python.exe' -B -m pip check
& '.venv/Scripts/python.exe' -B -m evaluation.s0
& '.venv/Scripts/python.exe' -B -m evaluation.s0 --require-frozen
# 上一条在当前pending状态应返回2，禁止正式执行。
& '.venv/Scripts/python.exe' -B -m pytest -q tests/test_s0_preparation.py -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m pytest -q tests slm/tests -p no:cacheprovider
```

没有创建或宣称存在formal runner命令；该入口属于S4。本包结束不自动执行S1或八次实验。
