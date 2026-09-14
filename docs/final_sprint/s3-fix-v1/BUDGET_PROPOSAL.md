# 公共输出上限调整建议（未应用，等待用户确认）

2026-09-07。当前配置保持不变：max_output_tokens=1024。

使用项目已校验的官方 Granite tokenizer 对 S1 冻结财务契约进行离线测量：

| case | 必填结果行数 | 仅财务明细的紧凑 JSON tokens | 完整 Finance 工程示例 tokens |
|---|---:|---:|---:|
| ai_education | 21 | 1919 | 3104 |
| intelligent_ring | 27 | 2552 | 3857 |

行数来自 FinanceContract.expected_values()，并通过 FinanceContract.validate()。不包含输入行；不把 synthetic 示例当作真实模型输出。这是规范紧凑序列化的实测大小，不是对所有可能 JSON 编码的数学最小值证明。示例 Writer 第3批分别为3023/3770 tokens。当前1024起始值缺乏容纳完整契约的空间，不能以删字段处理。

建议仅另立公共候选版本，把 A–D 每次输出上限从1024改为8192，给完整字段、正文和模型格式化留出余量；正式配置仍须后续真实预检通过后冻结。

保持不变：H Micro Q4_K_M、32768 context、完整证据、13章、共同4/3/3/3分批、一次结构repair、max_requests=18、max_total_tokens=160000、max_prompt_chars=90000，以及节点1200秒、Multi5400秒、RAM/pagefile停止门。单次8192是上限，不要求生成满额；输入加输出必须仍满足context。其余预算可能独立阻塞，当前未证明这些值足以运行完整D。

本建议不授权Gemini调用、正式8次实验、模型切换、S4启动或绕过时间门。只在用户明确批准后实施公共候选变更和必要本地预检。

依据：用户要求“需要改变实验/模型/预算范围时，停止并向我确认”；sprint_plan_ §2/§6/§9要求公共预算、完整输出契约与确认范围变化。

测量明细：output_envelope_audit.json。
