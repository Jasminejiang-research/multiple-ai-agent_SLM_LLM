# AI 教育 SLM 四小时能力测试交接

2026-09-07，Europe/Berlin。**真实测试已结束，未产出完整计划书。** 本次独立完整 D 尝试在 Research 节点首轮与一次结构修复均失败后停止。耗时 **2121.203 秒（35 分 21 秒）**，没有触发 4 小时截止，也没有耗尽请求或总 token 预算。

## 授权和执行范围

用户明确确认：仅本次 AI 教育 SLM 测试，单次输出上限 8192 tokens，最多 36 次请求，累计 500000 tokens，各节点共享 14400 秒总时限。授权记录在 authorization.json；此前 pending 记录完整保存在 authorization.pending.json。

- 模型：Granite 4.0 H Micro Q4_K_M，别名 granite-h-micro-32k；Ollama 0.33.2。
- 模型 digest：eec81a822241037c5d8e47a870b3d26423bfa1b010e02fcdf1b5f9f2de5c3b2b。
- CPU-only，num_gpu=0；实测加载上下文 32768，模型 VRAM 为 0。
- 输入为 S0 冻结 AI 教育 brief 与 evidence packet；执行固定源副本内的完整 D 图，真实上游生成，mock 为 false。
- 本次为非正式能力测试，formal_eligible=false。公共 A–D 配置保持原值；正式实验 0/8，Gemini 调用 0。

## 实际结果

| 请求 | 输入 tokens | 输出 tokens | 请求耗时 | 原始响应 | 契约结果 |
| --- | ---: | ---: | ---: | --- | --- |
| Research 首轮 | 3739 | 8192 | 1076.968 秒 | HTTP 200，done=true，done_reason=length | invalid_output；provider output truncated |
| Research 唯一结构修复 | 3780 | 8192 | 1033.219 秒 | HTTP 200，done=true，done_reason=length | invalid_output；provider output truncated |

合计 **2 次物理请求、7519 输入 tokens、16384 输出 tokens、23903 总 tokens**。剩余 34 次请求和 476097 tokens；transport retry=0，structure repair=1，semantic revision=0。

停止节点：research.generate。Research 没有有效产物，ComponentCritic、Strategy、Finance、Writer 与 final Critic 未执行；first_valid_plan_seconds=null、terminal_contract_state=not_checked、scorable_artifact_ref=null，运行目录内 proposal.md 数量为 0。完整 D 未通过。

CLI 报告模型测试退出码 2；外层执行工具报告退出码 1。应以 result.json 中的 failed 和原始日志为依据，不能当作启动失败或四小时超时。

## 新定位的问题

两次请求都陷入第一个 claim 的 financial_value_ids 数组重复，直到用尽单次输出上限。首轮原始文本 38449 字符，其中 average_paying_users 与 months 各出现 527 次；修复轮 39435 字符，这两个值各出现 306 次。两份数组都没有闭合，JSON 无法解析。

这次 CPU 模型调用及输入传输成功：两次输入 tokenizer 与 Ollama 计数差均为 0，HTTP 200，done=true。本次未复现先前 done=false 的混合 CPU/GPU 解码错误。当前直接阻塞是模型重复生成与截断，增加总运行时间本身没有解决它。

代码线索：runtime/schemas/evidence.py 中 financial_value_ids 是没有长度或唯一性约束的 list[str]；runtime/workflow/contract_generation.py 的一次修复使用通用的截断错误反馈。它们是下一步精准诊断入口，尚不能据此把底层采样、语法约束或模型训练原因断言为已确定。

附带发现：两份未闭合原文均写入 source_recency=2026，第二份还写入 source_quality=2，而共享契约要求这些归一化分数在 0–1 内。这些是原文可见的额外不一致；本次正式失败判定在截断检查时已发生，尚未进入完整对象的后续验证。不能把原文简单删重、补括号后认作有效计划书。

## 验证和保留

- 准备阶段离线专项：60 passed in 4.32s；本次没有为得到成功结论而修改共享 prompt、schema、provider、模型或输入材料。
- 完成后审计：固定运行副本 182 个文件 hash 全部匹配；准备时目标仓库的 180 个原始源/输入文件 hash 全部匹配。
- 公共 CPU 配置 SHA256 前后一致：4e8bec9bd8f951c07268b2cedf78858e14194bb20168bba2bb197576ce8ae63f。
- 293 个资源样本，保护门 passed；最低可用 RAM 3783307264 字节（约 3.52 GiB），最大 pagefile 增量 19922944 字节（19 MiB），GPU 峰值 0。
- 本次拥有的 Ollama 进程树已停止。完成后独立核验：Ollama/llama-server 进程 0、11434 监听 0、活动 lease 0。OwnedOllama.stop 本身不负责释放请求 lease，因此最终状态以独立核验为准。
- 已有未提交修改和历史运行数据保留，未提交 git。S5 准备记录在总状态中保留；没有启动正式实验或后续工作包。

## 证据与入口

- 结果：run_01/probe/result.json。
- 工作流、原始 usage、结构校验与路由：run_01/probe/workflow/events.jsonl。
- 模型身份、授权、CPU/内存/分页文件与退出记录：run_01/probe/events.jsonl。
- 便于阅读的审计摘要：run_01/audit/audit_summary.json。
- 两次原始输出副本：run_01/audit/research_attempt_1.raw.txt、research_attempt_2.raw.txt；对应 native_response.json 保留 Ollama 响应内容。
- 关闭证明：run_01/audit/post_run_process_proof.json。
- 固定代码/输入：runtime/、runtime_source.zip、runtime_manifest.json；授权：authorization.json；启动：Invoke-CapabilityTrial.ps1。
- 原 S5 状态与运行中状态分别保存在 PREVIOUS_STATUS_AT_START.md、PREVIOUS_STATUS_RUNNING.md。

下一入口仍是 **S3 的 Research 结构输出问题**：检查财务引用数组重复及归一化分数字段的约束表达，在保留实验可比性的前提下提出并验证精准修复，再继续完整 D 验证。本轮没有通过缩减契约、人工补产物或增加修复次数绕过失败。S5 正式执行门仍按其原依赖要求保持锁定。
