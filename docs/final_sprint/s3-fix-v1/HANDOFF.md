# S3 解码故障审计与修复交接

2026-09-07（Europe/Berlin）。目标仓库：`C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`。

**混合CPU/GPU路径的长输入故障可复现；CPU-only对照成功，已安装相应规避修复。完整计划书仍未产出，S3整体验收未通过，等待公共输出预算确认。** 不得将ProbeAck成功写成完整D成功。S4/S5未启动，正式运行0/8。

## 定位证据

保持同一官方H Micro Q4_K_M、模型digest、Ollama 0.33.2、32768 context、完整ProbeAck schema、temperature=0、单并发及原时间/资源门。未升级运行时、下载模型或调用Gemini。

| 本轮真实调用 | 输入/输出tokens | 结果 |
|---|---|---|
| diagnostic_01_raw_short | 363 / 6 | 原raw路径短输入成功 |
| diagnostic_02_chat_long | 期望31344；失败无完整usage | 正确聊天模板仍在474.046秒后失败 |
| diagnostic_03_chat_4k | 4440 / 9 | 成功，49.938秒 |
| diagnostic_04_chat_long_cpu | 31344 / 17 | 1006.672秒成功，done=true，JSON契约通过 |
| installed_cpu_warmup | 332 / 9 | 安装后真实入口成功，12.438秒 |

原始S3与本轮chat长输入均报 `Unexpected empty grammar stack after accepting piece: @ (31)`。本轮捕获真实响应：HTTP200，`message.content="{\n"`，`done=false`。原provider拒绝不完整响应是正确行为，但此前未持久化这段原生响应。

evidence_audit.json严格比较diagnostic_02与04：**整个请求body仅相差options.num_gpu，省略（自动卸载）改为0（CPU）**；期望输入均为31344。自动路径日志显示4/41层卸载；CPU对照实际size_vram=0。故障定位到本机混合推理路径，尚不能据此指认某个CUDA/SSM算子或宣称修好了上游内核。

CPU对照：API prefill=1000.076508秒，generation=4.313709秒，load=2.1105818秒；17输出tokens的JSON含较多空白，经ProbeAck校验有效。141份资源样本，最少可用RAM=4357718016 bytes（约4.06 GiB），GPU峰值0、pagefile增长峰值0，资源门通过。期间曾运行8.08秒的43项离线专项测试和简短tokenizer测量，耗时仅作诊断观测，不当作独占机器性能基准。

## 改动

- granite_config.py：增加gpu_layers与context_probe_mode，历史v1文件保持原字节与原行为。
- 新增granite_preflight_cpu_v2.json：固定gpu_layers=0、聊天式context probe及新配置版本。模型/量化、32768 context、1024输出、18请求、160000总token、90000字符、1200/5400秒与资源门不变。
- granite_provider.py：CPU配置每次发送num_gpu=0；context计数采用官方纯文本system/user模板并核对真实API count。保留legacy_raw复现历史。保存原生HTTP状态、完整/部分JSON响应及具体错误；每次请求清空旧诊断。HTTP200错误对象或未完成响应不得算成功；无额外重试或隔离解除。
- granite_preflight.py：默认入口选CPU v2；context门要求实测size_vram=0；控制线程持久化原生诊断。业务D图、公共schema、13章、4/3/3/3分批与repair/revision规则不变。
- test_granite_s3.py：新增不完整响应回归、诊断持久化、CPU选项、预算不变、聊天计数及实际显存门测试。

## 验证与保留

- 初版日志专项43 passed，8.08秒。
- 最终暂存代码完整离线回归：**596 passed、25 deselected、3 subtests passed，93.73秒**，见staged_validation.txt。
- 安装后目标专项：**48 passed，4.16秒**，见installed_targeted_validation.txt。
- installed_request_replay.json：安装后完整31K请求与成功CPU真实请求逐字段完全一致；回放真实响应，tokenizer/API差值0。这是离线一致性验证，不是新真实调用或完整预检。
- 安装后真实warmup通过，原生诊断、CPU元数据与4份资源样本见installed_cpu_warmup/probe，资源门通过。
- 本轮真实调用5次、Gemini0、正式0。旧S3数据全部保留；未知旧lease按本次修复授权，在确认进程/端口停止后归档并核对SHA，见diagnostic_01和diagnostic_03的reconciliation.json。
- shutdown_audit.json确认Ollama/llama-server进程0、11434监听0、活跃lease0。stop()的lease_released=false表示关闭函数本身未操作lease，不代表成功请求后仍有活跃lease。
- code_install_receipt.json记录hash安装；before/保存四个修改源码的修复前字节；PREVIOUS_STATUS.md保存上一状态；preservation_audit.json记录最终保留核对。未commit、未清理历史或改变依赖。

## 剩余阻塞与入口

冻结财务契约要求教育21行、戒指27行结果。官方tokenizer测得**仅明细紧凑JSON就需1919/2552 tokens**，尚未含Finance解释等字段。1024起始上限缺乏容纳完整契约的空间。完整synthetic对象仅作大小示例，不能算真实或合格业务输出；测量并非任意JSON编码的数学最小值证明。详见output_envelope_audit.json。

按用户“改变预算范围前确认”及sprint_plan_ §6/§9，未增加预算、删字段或以Python/模板补成模型计划书。已提出另立A–D公共8192输出候选，其他预算和硬限不变，见BUDGET_PROPOSAL.md；截至交接未收到批准。更大上限仍需验证上下文、总token、请求与时间门，不保证完整D可行。

下一步属于**继续S3**：收到公共预算决定后更新明确版本，先跑真实Research/ComponentCritic/Finance/Writer组件，再按依赖门运行完整D smoke并保留全部响应。当前四组件与完整D均未运行，SLM尚未生成完整计划书。

仅复核已安装短请求的示例（目录必须使用新名字）：

```powershell
Set-Location -LiteralPath 'C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM'
./slm/start_granite.ps1 -OutputDirectory './docs/final_sprint/s3-fix-v1/new_check_server'
./.venv/Scripts/python.exe -B -m slm.granite_preflight --phase warmup --config './slm/configs/granite_preflight_cpu_v2.json' --output-dir './docs/final_sprint/s3-fix-v1/new_check' --server-owner './docs/final_sprint/s3-fix-v1/new_check_server/server_owner.json' --tokenizer './docs/final_sprint/s3-v1/setup/tokenizer.json' --tokenizer-provenance './docs/final_sprint/s3-v1/setup/tokenizer_provenance.json'
```

下一包仍是S4；仅用户明确要求且D验收或失败范围已确认后进入。接口仍是slm/factories.py:build_slm_review_workflow和workflow/review_runtime.py。本轮未执行S4。
