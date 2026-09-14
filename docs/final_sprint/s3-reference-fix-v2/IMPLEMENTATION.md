# S3 精准修复实现与验证记录

本包接续 s3-reference-fix-v1，同属用户批准的代码修复及 AI 教育 SLM 非正式能力测试。最终业务结果见 HANDOFF.md 与 run_01/probe/result.json。

## 实现

1. `workflow/generation_constraints.py` 从本 case 冻结财务候选导出合法 ID 枚举、长度上限和唯一性要求。本地严格拒绝重复与未知 ID，不裁剪或补写模型产物。AI 教育合法财务候选数为 31。财务基础 schema 的重复拒绝与 0–1 评分说明保留自 v1。
2. 同一生成 schema 还将 source_ids/source_id、chunk_id、snapshot_sha256 限定在本冻结证据集合内。各字段闭集约束不能单独保证来源/片段/hash 的正确配对；原有完整 grounding 校验继续核对配对、行号和逐字引文，引用污染仍是失败，不放宽为可忽略结果。
3. `workflow/grounding_generation.py` 明确区分正文锚与来源锚。content_anchor 必须出现在所属 finding/recommendation/assumption/rationale 或 section.content 中，claim_text/topic/来源摘录不算正文。提供现有冻结证据的逐字锚格式示例，只能在确实相关时采用；不新增证据，也不代替人工支持度审计。
4. 用户 brief 只定义输入假设，不能伪装成 packet/brief 来源 ID；无外部证据的输入假设保留 assumption 状态、前提及空来源引用。共享提示词仍要求只引用实际相关财务值，不把全部 ID 放进市场声明。
5. 唯一一次结构修复反馈能在 JSON schema 失败时一并诊断已经可读的正文锚/来源错误，避免等下一轮才暴露；记录具体路径、有限原文、父正文合法片段和冻结行号。原始响应不变，最多 10 条简短问题；截断 JSON 仍由 v1 前缀诊断器识别财务循环与评分越界。
6. mock provider 和测试使用 schema 继承关系识别角色，兼容 case-bound 子类；真实节点和路由未改。

共享版本：`proposal-grounding-v3-frozen-reference-bounds` / `grounded-generation-v3-explicit-anchors`。A–D 统一采用同一实现，case 间集合及 cache 独立。未变更模型、温度、公共预算、输入、四批生成、一次结构修复、一次条件 Revision、引用污染规则及完整契约验收门。正式实验需要重新冻结实际版本，本次不自动执行 S5。

## 实际离线验证

- 完整 suite：**673 passed，25 deselected，3 subtests passed，120.30 秒**，validation/full_regression_v4.log。
- 累计预算运行器：**7 passed，2.86 秒**，validation/trial_runner_tests.log。
- 目标安装后：**20 passed，1.54 秒**，validation/installed_tests.log。
- 历史真实响应重放：validation/prior_response_replay.json 记录 v1 两次响应 hash 和新反馈。首轮识别财务重复、正文锚和 hash/引文问题；修复轮还识别虚构 packet 来源。不是 synthetic 模型成功证据。
- 初始失败如实保留：anchor_focused.log 为 1 failed / 67 passed，失败来自 mock Critic 的 schema 身份判断；full_regression_v3.log 为 18 failed / 655 passed，均来自同一旧身份断言的参数组合。修正为继承判断后完整 suite 通过，没有改弱 Revision 路由断言或业务校验。

## 预算、运行和保留

v1 真实运行已消耗 3 请求、13961 tokens、709.921 秒；连同最初失败，累计 5 请求、37864 tokens、2831.124 秒。v2 从上述累计值继续，起始剩余 31 请求、462136 tokens、11568.876 秒；仍受原批准 4 小时/36 请求/500000 tokens 共同上限约束，单次计划书输出 8192。budget_carryover.json 验证上一结果的 SHA256，新增测试防止误用最新一轮耗时而重置累计余额。

运行器先原生长度探针，再真实 Research；只有自然结束且通过完整契约才运行从真实输入开始的全新完整 D。所有阶段共用剩余预算、总截止计时、全仓库端点 lease、CPU/32K 布置与资源保护。正式实验 0/8，Gemini 调用 0。

v2 安装 10 个新增或修改文件；与 v1 合计影响 13 个不同源码/测试文件。各轮 before/ 保留安装前版本，change_manifest.json 和 install_receipt.json 提供逐文件 hash。v2 固定 runtime/ 为 253 文件；runtime_source.zip SHA256 为 `9f84226395c2af55b3a58af660885f7d2e76d60cbaeab38bf98ab2f0fe91f612`。历史数据不覆盖，未提交 Git。
