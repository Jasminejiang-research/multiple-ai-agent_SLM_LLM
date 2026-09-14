# 最新 S3 精准修复：代码已交付，Research 仍阻塞

2026-09-07。**财务引用约束、评分规则和具体错误反馈已实现并验证；SLM 仍未生成完整计划书，完整 D 未启动。** 最终总交接为 docs/final_sprint/s3-reference-fix-v3/HANDOFF.md。

最终保留 s3-reference-fix-v2 的 13 文件改动：财务闭集/长度/严格唯一性校验、0–1 评分、来源 ID/chunk/hash 闭集、正文与来源锚说明及多问题反馈。共享 contract=proposal-grounding-v3-frozen-reference-bounds，prompt=grounded-generation-v3-explicit-anchors。v3 的 verbatim_parent_text 字段别名未改善真实验收，已撤回；活动字段仍为原 content_anchor，试验原始数据和代码完整保留。

最终保留版本完整回归：**673 passed / 25 deselected / 3 subtests passed，120.30 秒**。恢复后 253 文件 hash 与该完整回归副本全匹配，**专项 20 passed，1.43 秒**。所有原始未提交版本保存在各包 before/，历史运行未覆盖，未 commit。别名试验的 676/23 项测试仅属历史验证，不作为当前版本计数或真实模型成功证据。

三轮真实验证新增 **9 请求、47349 tokens、39 分 26 秒**；6 个 Research 响应均自然 stop，但每轮唯一结构修复后仍存在正文锚/引文不匹配，完整契约失败。因此后续完整 D 不运行。没有通过去重、补写、放宽校验或延长修复次数伪造成功。

原四小时额度累计 **11 请求、71252 tokens、4487.671 秒（1 小时 14 分 48 秒）**；剩余 **25 请求、428748 tokens、9912.329 秒（2 小时 45 分 12 秒）**。停止原因是业务失败，预算未耗尽。后续如获批，必须以 v3/run_01/probe/result.json 的最新累计值承接，不能复用较早启动记录重置。

模型服务已关闭；最后核验模型进程/11434 监听/活动 lease 均为 0。所有资源保护 passed，正式公共配置 hash 未变，实际 Granite CPU/32K、温度、输入及预算范围保持原样；正式实验 0/8、Gemini 调用 0。

下一入口仍为 **S3 Research**。本包 NEXT_STEP_PROPOSAL.md 给出待确认的统一 A–D 两阶段生成方案；它改变调用结构，按用户原要求须确认后实施，本轮未执行。S5 准备已完成的历史状态保留；正式运行仍待 D 门、输入批准、Gemini 条件、公共版本冻结和明确启动等原依赖，没有自动执行下一编号工作包。
