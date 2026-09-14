# Final sprint 执行交接

更新时间：2026-09-07（Europe/Berlin）。当前工作包：**S3故障审计与修复**。状态：**CPU解码规避修复已安装并验证；完整D/计划书未完成，等待公共输出预算决定**。S0–S2已完成；S4/S5未启动，正式实验0/8。不可写为S3整体验收通过。

## 最新结果

- Ollama 0.33.2混合CPU/GPU路径：31344-token聊天输入失败，HTTP200仅返回`{\n`和done=false，日志报empty grammar stack。短raw与4440-token聊天可成功，单纯改模板无效。
- 同一模型/schema/31344-token请求，仅显式num_gpu=0后成功：输入31344/输出17，1006.672秒，done=true、JSON校验通过，实际显存占用0。底层具体故障算子未确定，已采用有实测支持的CPU规避方案。
- 新候选slm/configs/granite_preflight_cpu_v2.json固定CPU、32768 context及聊天计数。所有预算仍为原值：1024输出/18请求/160000总token/90000字符，节点1200秒、Multi5400秒。历史v1字节不变。
- 补全HTTP错误/部分响应留存、具体错误分类、每请求诊断重置；context预检要求实测size_vram=0。无隐式重试、换模型、Gemini回退、字段裁剪或预算增加。
- 安装后离线回放证明新provider的31K完整payload与成功CPU请求完全一致；这不是新真实调用。
- 安装后真实warmup通过：输入332/输出9，12.438秒。CPU长输入及warmup资源/时间门均通过。本轮真实调用5次、Gemini0；旧S3记录保留。
- 真实四类业务组件与完整D smoke尚未运行，**SLM尚未产出完整计划书**。

## 验证、文件与保留

最终完整离线回归（暂存副本）：**596 passed、25 deselected、3 subtests passed，93.73秒**；安装后目标专项：**48 passed，4.16秒**。没有安装/升级依赖或运行正式实验。

以下交接文件位于docs/final_sprint/s3-fix-v1/：

- HANDOFF.md：详细证据、限制、命令及下一入口。
- diagnostic_04_chat_long_cpu/probe/result.json：真实31K CPU对照成功。
- installed_cpu_warmup/probe/result.json：安装后真实入口。
- installed_request_replay.json、evidence_audit.json、preservation_audit.json、shutdown_audit.json：一致性、审计与保留校验。
- code_install_receipt.json：代码安装回执；before/：修复前源码；PREVIOUS_STATUS.md：上一状态。

修改slm/granite_provider.py、granite_preflight.py、granite_config.py、tests/test_granite_s3.py，新增CPU v2配置。模型服务及子进程已关闭，11434监听0、活跃lease0。旧未知lease在验证进程停止后按本次修复授权归档并核对SHA；历史数据与既有未提交修改保留，未commit。

## 当前停止点

两案例必填财务明细紧凑JSON实测分别为**1919/2552 tokens**（21/27行），超过当前1024起始上限，尚未含解释正文。它是规范序列化测量，不是任意编码最小值证明；synthetic示例不是模型结果。

按用户和sprint_plan_要求，预算范围变化须确认。已提出**另立A–D公共8192输出候选，保持其他预算/模型/完整契约/时间门不变**，见BUDGET_PROPOSAL.md和output_envelope_audit.json。尚未收到批准，配置未改为8192；其他预算/context/时间门仍需真实验证，不保证完整D成功。

下一步先继续S3：用户决定公共预算后，执行真实四组件与完整D smoke，按门保留失败并停止，不伪造计划书或提前认定验收。下一包S4尚未执行，仅在用户明确要求且D处理范围已确认后进入。接口仍为slm/factories.py:build_slm_review_workflow与workflow/review_runtime.py。
