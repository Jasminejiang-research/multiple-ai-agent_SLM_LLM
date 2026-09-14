# Final sprint 执行交接

更新时间：2026-09-06。当前工作包：**S1**。状态：**complete（工程契约与离线验证）**。S0：complete；S2–S5：not_started。未执行下一包，未启动正式实验。S0原始交接完整保存在 `docs/final_sprint/s1-v1/S0_STATUS_ARCHIVE.md`，原S0协议/快照/计划槽位均保留。

## S1实际完成

- 新A入口由同一生成角色完成四批、完整13章输出，与B/C/D的Writer共用严格schema、4/3/3/3分组、枚举提示、一次结构repair及终端检查。旧BusinessProposal、旧claim枚举/字符串和旧run读取保持兼容；旧图拒绝formal_frozen误用。
- 冻结packet在Research第一次调用前注入，完整brief字段保留；检查预期hash、allowlist、文件SHA-256、chunk内容及行定位，所有下游和审查/修订输入沿用同一packet。冻结生成期间受控Web、Tavily、RAG检索/现场知识库入口被拦截；产品模式继续可用。
- 新claim保留来源、锚点、版本和父ID；检查来源丢失/新造ID、错误定位、引用不一致及来源无变化时的不当升级；Critic反馈有来源/claim ID边界，revision v1→v2仅一次。
- Finance按S0两case冻结公式、单位/币种/期间用Decimal复算，保留输入来源类别及计算血缘；Finance和最终财务章都必须包含完整场景结果。
- Confidence共享可解释聚合及变更reason；普通假设不再导致整节low。裁剪、冲突、关键事实缺证及未核实重大语义问题保留限制。模型提出的direct关系与独立人工Gold严格区分。
- 内部JSON/Markdown导出保留完整13章、财务表、claim/source定位、packet与brief；不覆盖既有导出。首次失败记录不会因repair成功而回写为首次通过。

## 文件、版本与验证

全部路径相对于目标项目 `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`。

| 内容 | 入口 |
|---|---|
| S1完整交接、API、边界与S2要求 | `docs/final_sprint/s1-v1/HANDOFF.md` |
| 共同输出/来源/财务schema | `schemas/contract_outputs.py`、`schemas/evidence.py`、`schemas/financial.py` |
| 冻结输入/产物/导出、共享生成与批处理 | `workflow/contract_context.py`、`workflow/contract_generation.py`、`workflow/generation_batches.py` |
| 来源与Confidence、财务复算、访问隔离 | `workflow/grounding.py`、`workflow/finance_contract.py`、`workflow/evidence_policy.py` |
| provider兼容与SLM接入缝 | `workflow/schema_contract.py`、`workflow/gemini_schema.py`、`slm/factories.py` |
| 可运行离线审计 | `evaluation/s1.py` |
| 契约与packet示例、复算参考 | `docs/final_sprint/s1-v1/examples/` |
| 最终测试原始结果与安装/保留校验 | `docs/final_sprint/s1-v1/validation_results.txt`、`installation_receipt.json`、`change_manifest.json` |
| 新增专项测试 | `tests/test_s1_contract.py`、`slm/tests/test_s1_contract_adapters.py` |

版本：schema `proposal-grounding-v1-s1`，prompt `grounded-generation-v1-s1`，finance `s0-case-formulas-v1`；生产模型/预算配置未改变。没有数据库迁移、commit、清理历史或新前端。启动时已有未提交S0材料、evaluation工具与test_s0_preparation.py均保留；安装前逐文件校验目标hash，防止覆盖并行修改。

实际基线：同一Python3.12.10，pip check通过；376 passed、25 deselected、3 subtests，51.32s。S1初始60项专项通过；一次整合发现新增测试跨SLM隔离边界，移回slm/tests后整合445 passed、25 deselected、3 subtests，61.90s。新增schema本地SDK兼容专项138 passed、9 deselected。最终安装后针对性/整合结果和S0/S1审计由validation_results.txt保存。全部为离线mock/确定性检查，不能证明模型质量改善或D可行。

## 数据、决策与剩余依赖

- 本包Gemini/Granite实际生成调用0，预检/smoke/warm-up0，正式runs启动0/8，消费/充值0。财务JSON为假设公式复算参考，没有候选模型输出、人工评分或Gold真值。
- 两case完整brief/证据仍pending；原 `CASE_REVIEW.md` 是审核入口。S0冻结材料不原地更改；S4/S5须建立新的正式冻结版本，不能以旧protocol.json仍写pending为理由修改旧快照。
- 公共请求/token/输出上限仍待预检冻结。S2须加真实attempt/handoff持久化、父节点/run时间预算及条件路由；S3须实测Granite H Micro Q4_K_M、32768 context、单并发与时间/内存门；S4接正式运行器和原Streamlit展示。
- 来源/quote/ID检查不判断语义支持，也不确认模型是否列全决策关键claim；自由文本数字是否正确解释数值表仍需Critic及最终人工审核。high仅是共享规则下的标签资格，不是人工已核实；Gold默认pending。
- 当前修订接口保留未核实major状态；完整high/critical gate及外部可用状态由S2接入。未实现S2整图，不把S1七次生成链冒充B/C/D。
- Gemini额度沿用S0用户“先不调查、预计充值足够”的指示；未新增查询，约50元消费约束不变。Ollama/Granite可行性没有新结论。
- 未发现需要改变实验、模型或预算范围的重大冲突。上述依赖不阻塞S1工程交付，但阻塞正式实验。

## 下一包：S2（仅用户明确要求时）

必读：桌面sprint_plan_、两份权威设计、本状态、S1 HANDOFF、S0 PROTOCOL/INTERFACES。代码从ContractContext/ContractGenerator/grounding和现有multi_agent_graph/multi_agent_nodes/run_budget/logging开始。实现固定role/final Critic契约及7.0/high/critical gate、失败才修订一次、有效版本交接、共享父预算及完整调用记录。不要使用旧固定revision图执行正式条件。

实际可复用命令（目标项目目录）：

```powershell
& '.venv/Scripts/python.exe' -B -m evaluation.s1
& '.venv/Scripts/python.exe' -B -m evaluation.s0
& '.venv/Scripts/python.exe' -B -m evaluation.s0 --require-frozen
# 当前预期退出2：尚未正式冻结。
& '.venv/Scripts/python.exe' -B -m pytest -q tests/test_s1_contract.py slm/tests/test_s1_contract_adapters.py -p no:cacheprovider
& '.venv/Scripts/python.exe' -B -m pytest -q tests slm/tests -p no:cacheprovider
```
