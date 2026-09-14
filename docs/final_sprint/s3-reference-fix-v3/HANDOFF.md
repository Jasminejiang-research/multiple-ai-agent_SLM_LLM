# S3 精准修复最终交接

2026-09-07。**代码修复已完成并保留；SLM 完整计划书仍未生成，Research 仍未通过完整契约，完整 D 未启动。** 最终保留的是 s3-reference-fix-v2 的实现；本目录 v3 字段别名试验未改善 Research 验收，已经撤回，试验源码、原文和日志完整保留。

## 最终保留的实现

- financial_value_ids/value_ids/input_ids 使用 case 的合法财务 ID 闭集、maxItems、uniqueItems，并由本地校验严格拒绝重复、未知 ID 与越界长度；不自动裁剪、去重或补写模型输出。
- 明确 source_quality/source_recency 的 0–1 范围，未知 recency 为 null；结构修复反馈给出具体路径、重复次数、有限原文和合法示例。
- 冻结 source/chunk/hash 闭集，区分正文锚与来源锚，诊断正文不匹配、虚构来源、错误 hash、行号和引文；保留原引用污染失败规则和一次结构修复限制。
- A–D 统一使用 `proposal-grounding-v3-frozen-reference-bounds` / `grounded-generation-v3-explicit-anchors`。原 canonical 字段 content_anchor 保持原名；未保留 verbatim_parent_text 别名。

最终涉及 13 个不同源码/测试文件。主要实现：workflow/generation_constraints.py、workflow/grounding_generation.py、workflow/contract_generation.py、schemas/evidence.py、schemas/contract_outputs.py。新增测试在 tests/test_generation_constraints.py、tests/test_grounding_generation.py、slm/tests/test_reference_bounds.py；现有 mock/type 分派的兼容修改见各版本 change_manifest.json。

## 实际测试

- **最终保留版本完整回归：673 passed / 25 deselected / 3 subtests passed，120.30 秒**（s3-reference-fix-v2/validation/full_regression_v4.log）。
- 最终版本运行器累计预算验证：7 passed，2.86 秒；初次安装后专项 20 passed，1.54 秒。
- **撤回别名后，253 个源/输入文件 hash 与完整回归通过的 v2 副本完全一致；再次专项 20 passed，1.43 秒**，本包 restore_receipt.json 与 validation/retained_version_tests.log。
- 未保留别名试验的离线结果同样如实留存：676 passed / 25 deselected / 3 subtests passed，125.84 秒；探针运行器 8 passed，6.07 秒；安装后 23 passed，1.48 秒。这些不能替代真实业务验收。
- v1/v2 初始失败与 fixture/类型判断修复均保留在各 validation/ 中，没有隐藏失败或修改测试绕过业务规则。

## 三轮真实验证

每轮先原生探针，再真实 Research 首轮及最多一次结构修复。均未通过 Research，因此没有启动完整 D，也没有生成 proposal.md。

| 修复版本 | 模型调用 | tokens 总量 | 本轮耗时 | Research 输出 tokens（首轮 / 修复） | 结论 |
| --- | ---: | ---: | ---: | --- | --- |
| v1 财务引用约束 | 3 | 13961 | 709.921 秒 | 2533 / 2222 | 自然 stop；修复后引用和评分通过，正文锚失败 |
| v2 来源/锚反馈 | 3 | 16008 | 753.672 秒 | 2178 / 2482 | 自然 stop；修复后 JSON schema 通过，4 处正文锚、2 处引文不匹配 |
| v3 字段别名试验 | 3 | 17380 | 902.875 秒 | 3132 / 2536 | 自然 stop；修复后 JSON schema 通过，4 处正文摘录、4 处引文不匹配；别名撤回 |

原生探针证实此次长度约束生效；v1/v2 探针同时证明 uniqueItems 不能单独保证去重，所以代码层拒绝仍必要。v3 探针证明字段传输/解析可行，但业务结果没有改善。所有 Research 响应均自然结束，未再在 8192 处截断，也未复现旧混合 CPU/GPU 解码错误。

本次修复工作新增 **9 次模型调用、47349 tokens、2366.468 秒（39 分 26 秒）**。包含最初失败计划书试验，原四小时额度累计 **11 请求、71252 tokens、4487.671 秒（1 小时 14 分 48 秒）**；剩余 **25 请求、428748 tokens、9912.329 秒**。额度未耗尽，停止原因是业务契约失败，不能把剩余时间自动当作额外结构修复次数。各轮代码准备/离线测试时间不计入模型生成额度。

任何获批后续运行必须把本包 run_01/probe/result.json 的最新累计值作为 carryover，并核验其 hash；不能复用本包 budget_carryover.json 中启动前的旧余额记录。现有 run_01 是只读历史，启动脚本会拒绝覆盖它。

## 保留、清理与复现

- 正式公共配置 slm/configs/granite_preflight_cpu_v2.json SHA256 始终为 `4e8bec9bd8f951c07268b2cedf78858e14194bb20168bba2bb197576ce8ae63f`；实际模型仍 Granite H Micro Q4_K_M、CPU、32K，未改变温度、输入或模型范围。正式 A–D 输出预算仍未调整。
- 三轮资源保护均 passed。v3 最低可用 RAM 3714478080 字节；模型 GPU 使用 0，pagefile 最大增量 10485760 字节。未触发 deadline。
- 模型服务已关闭；本包 run_01/audit/external_cleanup.json 核验进程/11434 监听/活动 lease 均为 0。
- 各轮 before/、change_manifest.json、install_receipt.json 保留修改前的未提交版本；历史运行不覆盖，未提交 Git。v3 的单个新测试文件只从活动仓库撤回，完整内容仍在本包 runtime/ 和 archive 中。
- v3 恢复前 audit 验证 254 文件副本与已安装源码全匹配；随后 restore_receipt.json 验证恢复到 v2 的 253 文件全匹配。不得把 v3 运行副本误认为当前活动代码。最终保留版本的复现副本是 s3-reference-fix-v2/runtime/，对应 source archive SHA256 `9f84226395c2af55b3a58af660885f7d2e76d60cbaeab38bf98ab2f0fe91f612`。
- 原始证据：各版本 run_01/probe/result.json、events.jsonl、run_01/audit/ 中逐条 raw.txt/usage.json/audit_summary.json。恢复后状态以 restore_receipt.json 为准，不覆盖恢复前的试验审计。

## 剩余阻塞及下一入口

SLM 在当前单次完整结构生成方式下，仍会把来源问题/摘录/ID 当作正文锚，并改写引文；提示词和字段命名改动尚未解决这个跨字段对齐问题。代码现在正确拒绝这些结果，不能据此报告 Research 成功或完整计划书成功。

下一入口仍为 **S3 Research**。可审阅本包 NEXT_STEP_PROPOSAL.md 的“先正文、后声明/证据对齐”统一两阶段方案；它改变 A–D 调用结构与生成职责，按用户原要求需确认后才能实施。本轮未实施该方案，未更换模型、追加修复次数或增加预算。

S5 准备已完成的历史状态保留；正式 S5 仍待 D 门、输入审批、Gemini 条件、公共配置/代码冻结及明确启动等原依赖。正式实验仍 0/8，本次 Gemini 调用 0；没有自动执行下一编号工作包。

最终保留文件总清单与最早原始备份、三轮响应 hash 复核见 final_retained_manifest.json：13 文件改动（8 个既有文件、5 个新增文件），253 个源/输入文件及全部历史响应核验无差异。
