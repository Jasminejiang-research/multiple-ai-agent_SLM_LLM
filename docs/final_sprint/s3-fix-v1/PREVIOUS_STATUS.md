# Final sprint 执行交接

更新时间：2026-09-07（Europe/Berlin）。当前工作包：**S3**。状态：**工程实现已交付；真实预检 no_go，验收 blocked_pending_user_decision**。S0–S2 已完成；S4/S5 未启动，正式实验 0/8。不得把本次结果写为 S3 验收通过。

## 本包完成

- 已核对桌面 sprint_plan_、两份权威设计和 S2 最新交接，三份权威文件 hash 与 S0 一致。S2 原状态完整归档到 `docs/final_sprint/s3-v1/S2_STATUS_ARCHIVE.md`。
- 接入官方 Granite 4.0 H Micro Q4_K_M（3,191,396,096 参数），显式 32768 context / temperature=0。Ollama 0.33.2，专用单并发、最多一个加载模型；模型 alias/digest 与配置版本落盘。
- 原生 Ollama provider 注入 S2 完整 D 图：R/S/F/Writer、三个 role Critics、final Critic 和条件 revision 共用 S1 schema、13章、4/3/3/3 分批与一次 repair。无 Gemini 回退或 D 专用裁剪。
- 预检入口提供 warmup、长输入、四类组件和完整 D smoke 阶段；失败阶段会阻止依赖工作。父节点含 batch/critic/repair/revision <=1200 秒，完整 Multi <=5400 秒。
- Windows 实际 RAM/pagefile 与 GPU 遥测，缺值保留 null/原因；RAM<2 GiB 或 pagefile 实占增长>2 GiB 持续60秒取消并终止经过 PID/启动时间/监听端口验证的专用进程树。未知请求 lease 不自动释放。
- 实际模型文件、tokenizer、量化/版本证据、原始事件和失败输出均保留。既有未提交实现、S0–S2 记录与12份历史文件受 hash 校验保护；未 commit、未迁移数据库。

## 真实结果与阻塞

- 三个独立目录：前两次初始化失败均为0模型调用，Windows 单 PID 返回类型兼容修复后开始第3次真实预检。
- 本包真实调用 **2次**：warmup通过，42.484秒，输入332/输出9 tokens；prefill 21.797817秒，generation 0.850571秒。Granite模型精确digest为 `eec81a822241037c5d8e47a870b3d26423bfa1b010e02fcdf1b5f9f2de5c3b2b`。
- 长输入请求 **失败**，486.344秒；Ollama日志报 `Unexpected empty grammar stack after accepting piece: @ (31)`，HTTP 200但无正常completed response，provider记录 `OllamaMissingCompletion`。没有传输重试。
- 运行中 `/api/ps` 确认分配32768；服务器诊断日志 sampler记录31,331 text tokens、truncated=0。请求没有完整成功返回，最终API count/duration缺失，不能据此认定有效context与结构化输出门通过。保留的64890预算预留值不是实际token量。
- 四类组件 Research / ComponentCritiqueReport / Finance / Writer batch 和完整 D smoke 均 **not_run**（前置门失败），不是通过或mock替代结果。
- 87份资源样本：基线可用RAM约6.612 GiB，最小约4.148 GiB；峰值系统RAM使用约11.656 GiB、GPU约0.515 GiB；pagefile实际使用约0.513 GiB、增长0。已观察的资源/时间门通过，不能由此宣称完整D可行。
- 专用PID 28292进程树确认终止；未知请求的endpoint lease保留隔离，重测前须确认进程/端口停止并显式归档和协调该marker。不得自动续跑。
- Gemini调用0、正式runs 0/8，无费用/额度查询、充值或实验分组改变。两case brief/packet仍待批准；公共1024输出/18请求/160000总预算是未冻结候选，不能当作正式预算或通过结论。

## 测试与文件

修改前：548 passed、25 deselected、3 subtests（100.62秒）。S3专项最终38 passed（3.75秒）；安装前整合584 passed、25 deselected、3 subtests（92.60秒）。修复后目标仓库最终整合 **586 passed、25 deselected、3 subtests passed，91.96秒**，原始输出见 `final_validation.txt`。pip check通过；S0准备完整性通过，`--require-frozen`按预期退出2（尚未正式冻结）。未安装/升级Python依赖。

| 内容 | 相对目标仓库路径 |
|---|---|
| 详细交接、命令、失败解释与范围决策 | `docs/final_sprint/s3-v1/HANDOFF.md` |
| 最新真实结果 | `docs/final_sprint/s3-v1/real_preflight_03/result.json` |
| 遥测、manifest、每次调用 | `docs/final_sprint/s3-v1/real_preflight_03/` |
| Ollama诊断错误与访问日志 | `docs/final_sprint/s3-v1/setup_03/` |
| 审计与安装/修复/保留校验 | `docs/final_sprint/s3-v1/evidence_audit.json`、各receipt及change_manifest |
| 配置、provider、预检入口 | `slm/granite_config.py`、`slm/granite_provider.py`、`slm/granite_preflight.py` |
| 资源监控与专用服务生命周期 | `slm/resource_monitor.py`、`slm/owned_ollama.py`、`slm/start_granite.ps1` |
| 模型与候选配置 | `slm/Modelfile.granite-h-micro-32k`、`slm/configs/granite_preflight_v1.json` |
| 专项测试 | `slm/tests/test_granite_s3.py` |

## 停止点与下一包入口

按 sprint_plan_ §6 的“D不通过可行性门时保留记录，停止需要D成功的后续安排并请用户确认范围”停止。当前需用户决定：继续排查原 H Micro / 32K 的 Ollama解码问题并重新验证，或批准另一种D结果/范围处理。没有自动使用H 1B、换云、缩小D输入或增加预算。

下一包为 **S4**（仅用户明确要求且D处理范围已确认时）：读取 sprint_plan_ §7、本状态、S3 HANDOFF；接口是 `slm/factories.py:build_slm_review_workflow` 与 `workflow/review_runtime.py`。S4不得假设D已通过。当前未执行任何S4工作。
