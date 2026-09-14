> 最终状态：本字段别名试验未通过真实 Research，已经撤回。活动代码恢复为 v2 的引用/诊断修复；最终结果见 HANDOFF.md 和 restore_receipt.json。

# S3 精准修复 v3：消除正文锚字段命名歧义

本包接续同一用户授权的 S3 修复。此前修复的财务闭集、数组长度、本地去重拒绝、0–1 评分、冻结来源闭集、多错误反馈均保留。完整业务结果以 HANDOFF.md 与 run_01/probe/result.json 为准。

此前真实响应反复把 content_anchor 填成 source quote、target_customer 或 differentiation_mba，虽然已有正文示例仍未纠正。本次检验“字段名被理解为标识符/来源锚”的假设，不声称这是模型内部唯一原因。

- `schemas/evidence.py`：生成 schema 使用 `verbatim_parent_text`，Pydantic validation/serialization alias 映射到原 `content_anchor`。正常 canonical model_dump 与导出字段仍为 content_anchor；输入两种名称兼容，但同一对象同时提供两者仍受 extra=forbid 拒绝。映射不改写字符串。
- `workflow/contract_generation.py` 与 `workflow/grounding_generation.py`：提示模型先写父正文，再逐字摘取短语；明确不能填 ID、topic 或来源摘录。反馈使用生成端别名并继续给出准确父正文位置。逻辑任务原始诊断输出使用 by_alias=True；provider 原始响应仍完整留存。
- `schemas/contract_outputs.py`：共享契约版本为 proposal-grounding-v4-parent-text-wire-alias；prompt 为 grounded-generation-v4-verbatim-parent-text。内部必填字段、四批写作、业务路由、校验、模型、温度及次数规则未变，A–D 一致。
- 新增 `tests/test_parent_text_alias.py`：验证映射前后 canonical 数据完全一致、产物可按原完整契约验收、双字段歧义被拒绝、错误摘录仍失败。Gemini transport 兼容和四条件共享回归包含于完整 suite，未调用 Gemini。

实际验证：完整 **676 passed / 25 deselected / 3 subtests passed，125.84 秒**；累计预算和原生别名探针运行器 **8 passed，6.07 秒**；目标安装后 **23 passed，1.48 秒**。详见 validation/。本版首次完整回归即通过；前两版初始失败日志仍在各自目录。

原生探针只验证字段传输、精确值映射和长度，不能代替真实 Research。模型即使返回合法 JSON，也必须通过正文锚/来源逐字验证与其他全部契约，才能运行完整 D。

继承累计 8 请求、53872 tokens、3584.796 秒后，本版起始余额为 28 请求、446128 tokens、10815.204 秒。预算仍为用户原批准的累计 4 小时、36 请求、500000 tokens，单次输出 8192；没有新实验额度。各次模型运行均独立留档、串行执行并核验服务清理。

本版安装 5 文件，三版合计涉及 14 个不同源码/测试文件；每次 before/ 保留之前的未提交版本。运行副本 254 文件，archive SHA256：158b6aa920eb7803e26ff1c5c789f1fd726dd6d8ee703757995d40426d709571。没有覆盖旧运行、提交 Git、启动正式八槽实验或自动执行下一工作包。
