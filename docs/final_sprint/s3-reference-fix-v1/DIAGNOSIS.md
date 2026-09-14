# S3 财务引用重复问题：诊断与代码修复

本记录对应用户 2026-09-07 确认的精准修复。最终真实运行结论以本包 HANDOFF.md 和 run_01/probe/result.json 为准。旧数据保存在 s3-capability-v1，未修改。

## 已证实的故障

历史 Research 首轮与一次结构修复均正常收到 Ollama HTTP 200，但 finish reason 为 length，输出恰为 8192 tokens。不是 4 小时超时，也未复现旧 CPU/GPU 解码错误。

用新诊断器只读重放两份历史原文，实际定位到：

| 位置 | 首轮 | 结构修复 |
| --- | --- | --- |
| `$.market_trends[0].claims[0].financial_value_ids` | 已读 2110 项，average_paying_users / months 各重复 527 次 | 已读 2143 项，两 ID 各重复 306 次 |
| `$.market_trends[0].claims[0].source_recency` | 2026，违反 0–1/null | 同样为 2026 |
| `$.market_trends[0].claims[0].source_quality` | 未发现范围错误 | 2，违反 0–1 |

AI 教育 case 的合法财务候选集合只有 31 个 ID；`average_paying_users` 本身不是该 case 合法的完整 ID。此前引用数组没有依候选集合加生成端长度限制，反馈也未把截断 JSON 中的循环数组、具体路径与评分错误明确指出。现有数据能证明上述约束缺口和重复行为，不能证明模型内部退化的唯一底层原因。

## 已安装修复

- `workflow/generation_constraints.py`：从冻结 case 导出财务 ID 闭集；对 financial_value_ids / value_ids / input_ids 设置 enum、maxItems、uniqueItems；本地严格拒绝重复、未知 ID 和越界长度。不会通过裁剪、去重或补写内容伪造模型成功。
- `schemas/evidence.py`、`schemas/contract_outputs.py`：基础模型明确拒绝重复引用，并说明评分区间。共享契约版本为 `proposal-grounding-v2-reference-bounds`。
- `workflow/contract_generation.py`：共享 A–D 提示词解释只引用相关 ID、无关联填 []、评分为 0–1、未知时 recency=null；提供现有枚举与基数规则、精确引用和内容锚规则。结构修复现在包含错误路径、重复计数、少量原文、合法示例；仍只有一次结构修复。共享提示词版本为 `grounded-generation-v2-bounded-references`。
- `evaluation/s2_fixtures.py` 与已有 mock 测试使用 schema 继承关系识别 case-bound 子类，保持真实执行角色不变。新增 `tests/test_generation_constraints.py` 与 `slm/tests/test_reference_bounds.py`。

未修改正式模型、温度、公共预算、冻结输入、四批分段、结构修复/Revision 次数、共享完整验收条件。公共 A–D 后续运行必须共同采用本版本，并重新冻结实际代码与配置。

## 已完成验证

- 完整离线整合回归：**667 passed，25 deselected，3 subtests passed，115.87 秒**。
- 独立恢复运行器累计预算/阶段依赖测试：**6 passed，2.26 秒**。
- 目标仓库安装后新增专项：**14 passed，1.29 秒**。
- 首轮测试的 fixture 与隔离依赖失败没有隐藏：日志 `validation/full_regression_v1.log` 保留；修复缺失的旧 prompts/S4 synthetic 测试依赖和 case-bound 测试身份判断后，全套通过。没有用 synthetic 结果替代真实模型结果。
- 真实原生探针：schema 最多 2 项，提示要求 100 项，实际返回 2 项且自然 stop；但两个 ID 相同。因此证据只支持此次 native maxItems 生效，**不支持 native uniqueItems 可单独保证唯一性**。本地重复拒绝和详细反馈仍是必须的。

## 真实业务验证安排及保留

真实测试严格先 Research，通过全部契约且自然结束后才从真实输入重新执行完整 D。模型保持 Granite H Micro Q4_K_M、CPU、32768 context；正式 A–D 配置不变。沿用已批准的 8192 单次输出、36 请求、500000 总 tokens、4 小时累计时限，并扣除旧失败测试的 2 请求、23903 tokens、2121.203 秒。探针、Research 和完整 D 共用剩余预算。

本包 `before/` 保存 6 个既有文件的原始未提交版本；`change_manifest.json` 记录 9 个安装文件的前后 hash。运行使用 `runtime/` 固定副本、251 文件清单与 `runtime_source.zip`；原始输入/源文件清单和缺失 fixture 的补齐清单分别见 source_inventory.json 与 fixture_inventory.json。历史运行不覆盖，不提交 Git，不自动启动 S5 正式实验。
