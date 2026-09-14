# 论文问题 1–14 的工程证据索引

本文件是材料索引，不是论文。所有 S4 样本均为 synthetic/offline，不能支撑模型质量结论。真实实验 0/8；S3 完整 D 仍待预检；人工结论未填。

| 问题 | 代码与规则 | 测试/日志/表图入口 | 当前限制 |
|---|---|---|---|
| 1 任务、价值、成功/失败 | S0 `PROTOCOL.md`；`schemas/contract_outputs.py`；`s4_runner.py:_result_state` | `dry_run/manifest.csv`；`test_terminal_export_failure_is_distinct_from_scorability` | 完成率不是商业可用性或内容质量 |
| 2 Agentic architecture | `workflow/review_graph.py`；`workflow/review_config.py` | S2 pass/skip/revise 测试；synthetic `route_trace.csv` | 预定义角色与代码选路，不是自由自治 Supervisor |
| 3 角色、通信 | `schemas/review_events.py`；`workflow/review_handoffs.py` | `logical_tasks.csv`、`handoffs.csv`、`role_metrics.csv` | 契约与交接只校验可确定规则，不代表语义理解 |
| 4 Framework | LangGraph/Pydantic；`storage/` 原 SQLite JSON；`app.py` | 原 storage/UI 回归；S4 `test_ui_sqlite_new_events_not_collapsed_and_legacy_unchanged` | 不做框架比较，不迁移 DB |
| 5 Prompt | `workflow/contract_generation.py`；`agents/component_critic.py` | attempts 的 prompt/schema hash；first-contract、repair 分项 | 无 prompt ablation，无中间输出人工能力排名 |
| 6 SLM 选择 | `slm/granite_provider.py`、CPU v2 配置 | S3 `diagnostic_04_chat_long_cpu`/`installed_cpu_warmup`；S3 tests | 仅 CPU 长输入/短确认成功，未产出真实完整 D 计划 |
| 7 Memory/context | 共同 32768、4/3/3/3、run/node 限额；`review_runtime.py` | S1/S2 分批/溢出/时钟测试；attempt hash/usage；S3 31K记录 | 公共输出预算未冻结；真实 context/输出/总预算可行性未确认 |
| 8 RAG/Web/证据可信度 | `evidence_policy.py`、`grounding.py`、`contract_context.py` | S1 冻结网络/来源测试；S0 snapshots；Gold 候选和 coverage | source_id/URL/模型 direct 不等于人工支持真值 |
| 9 Single-Agent | A 共同 13 章，无 specialist/LLM Critic | 合成 A 路径；原始 attempts；预设 B−A 表结构 | A 真实质量/时间/资源尚未测量 |
| 10.1 Multi 最终任务 | B/C/D 共同输出与有限修订；六维 rubric | `paired_cases.csv`/`paired_summary.csv`；审核后质量资源图入口 | 当前无人工质量与真实模型结论 |
| 10.2 协作层 | 预期交接清单；唯一职责 token 分类 | `handoffs.csv`、review-token share、角色图 | A 协作指标 N/A；占比无“越低越好”方向 |
| 10.3 协调失败 | `s4_runner.py` 恢复；`s4_metrics.py` 缺失/失败区分 | 中断、截断、预算、重复 attempt、失败交接 tests；failure CSV | 不确定请求不自动补跑；未返回 usage 不猜 0 |
| 10.4 公平比较 | 两 case×A–D、seed、freeze checks | `test_dry_run_exact_slots_no_calls_and_guard`；输入 hash；plan | 共同预算、case批准、各模型 smoke 尚待冻结 |
| 11 Ablation | 唯一 C−B：增加 role Critic 与条件修订的组合 | S2 routing tests；C−B case/summary 表 | 不分离 Critic/Revision 因果贡献，无固定修订对照 |
| 12 评价可靠性 | `s4_blind.py`；共享 Gold；`s4_statistics.py` | 匿名身份隔离、评分导入、三分母、重复/缺失 tests；private mapping | 单评审、n=2；隐藏复评不增加独立样本；不报告 inter-rater |
| 13 HITL | freeze批准；critical/unverified状态；内部导出与外部发布分开 | `needs_human_review`、gate/issue events；failed-scorable test | 人工审核与外部发布尚未完成，external_ready=False |
| 14 安全/复现 | allowlist、frozen scope、共享预算、slot claim、hash、版本与原始数据保留 | S1/S2/S3/S4 regressions；`provenance.json`；安装/保留审计 | 真实冻结前仍须明确工作树与配置；合成证据不替代实测 |

表/图脚本为 `evaluation/s4_export.py`，入口 `python -m evaluation.s4 export`。图包含逐 case 原始值、三项配对差值、各角色请求/token/首次契约指标；质量/claim/资源权衡图仅在相应人工字段和真实观测存在后生成。原设计 Example A 的算术笔误沿用 S0 勘误：按冻结公式为 88.75，不改变权重。
