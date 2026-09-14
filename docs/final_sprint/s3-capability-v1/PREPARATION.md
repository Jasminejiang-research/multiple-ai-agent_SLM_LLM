# 最新结果：本次真实测试已结束

用户已补充确认全部独立参数。AI 教育完整 D 尝试耗时 35 分 21 秒，Research 首轮及一次结构修复均因 financial_value_ids 重复、8192 输出截断而失败，完整计划书未生成。实际调用 2 次，总 tokens 23903；服务已关闭。详情见同目录 HANDOFF.md 与 run_01/audit/audit_summary.json。以下为授权前的准备记录原文，保留作历史审计。

---
# AI 教育 SLM 四小时能力测试：准备记录

记录日期：2026-09-07。状态：prepared / awaiting additional budget authorization。

用户已批准本次 AI 教育 SLM 计划书测试的总时限为 4 小时。真实模型调用尚未开始，尚无本次计划书或实测生成耗时。

此前用户明确要求改变实验、模型或预算范围须确认。因此已提交一项补充确认：仅本次非正式 SLM 测试，单次输出上限 8192 tokens，最多 36 次请求、500000 总 tokens，节点和请求共享剩余 14400 秒。原公共配置仍为 1024 输出、18 请求、160000 总 tokens、1200 秒节点/请求及 5400 秒整次时限。authorization.json 中 approved=false 表示尚未得到补充答复，不能启动模型。

本次独立配置不等于批准公共 A–D 8192 方案，不构成 S5 正式运行；正式实验仍为 0/8。Gemini 不调用。模型仍是 Granite H Micro Q4_K_M，CPU 卸载层数 0，32768 上下文；既有内存和 pagefile 停止门保留。

## 已完成准备

- 读取冲刺计划、两份权威设计与 S4 最新状态，检查现有实现、虚拟环境和本机资源。
- 从目标仓库复制固定代码及 S0 案例输入，排除 .env、.git、.venv 和历史运行数据；清单见 runtime_manifest.json，源代码归档见 runtime_source.zip。
- 新增 slm/capability_trial.py 及专项测试，复用真实完整 D 图与共享端点 lease。源副本放在 runtime/；没有替换目标仓库的公共模型配置或共享工作流。
- 每个请求进行输入加输出的上下文容量校验；真实输出不足或校验失败不得静默缩减、伪造或改为 mock。保留原始请求、响应、usage、失败及资源证据。
- 4 小时计时覆盖初始化后的整条生成流程，节点/批次不重置时间，截止时取消并停止本次拥有的 Ollama 进程。
- 完整 Writer 契约产物与完整 D 流程是否成功分开记录；生成成功不代表人工质量/Gold 审核通过。
- 已告知并行 S5 任务使用隔离副本，避开公共模型/工作流修改和真实 SLM 运行期间的重型测试。

## 已实际执行的验证

在准备副本 runtime/ 内，使用目标仓库现有 Python 3.12.10 虚拟环境运行：

```powershell
C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/.venv/Scripts/python.exe -B -m pytest slm/tests/test_capability_trial.py slm/tests/test_granite_s3.py -q -p no:cacheprovider
```

实际结果：60 passed in 4.32s，退出码 0。包括 12 项新增专项及 48 项已有 Granite 专项。该结果为离线工程验证，真实模型调用数为 0。

启动器 PowerShell 语法检查：0 个错误。实际运行 -CheckOnly：因 authorization.json 的 approved=false 返回退出码 1（预期结果，Explicit trial authorization is missing）；在模型服务启动及创建 run_01 前停止。这是授权门验证，不是模型失败。

启动前资源检查：可用 RAM 6949777408 字节（约 6.47 GiB），pagefile CurrentUsage 468713472 字节；Ollama/llama-server 进程及 11434 监听均为 0。资源会随并行任务变化，实际启动时还需重新检查。

## 后续入口

补充授权到达后，将原授权记录另存保留，再记录用户实际答复及批准范围。禁止把时间流逝、预选项或其他任务的回复视作用户批准。

```powershell
./Invoke-CapabilityTrial.ps1 -SharedRepo C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM -RunName run_01 -CheckOnly
./Invoke-CapabilityTrial.ps1 -SharedRepo C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM -RunName run_01
```

启动器先校验固定副本 hash 和授权；通过前不启动模型服务。结果拟存 run_01/probe/result.json，完整流程证据位于 run_01/probe/workflow/。每次运行必须使用新目录，历史数据不覆盖。

当前阻塞仅为上述补充参数确认；没有本次真实生成成功结论。公共预算、正式预检与 S5 冻结状态继续以各自交接记录为准。
