# 90分钟 SLM 恢复：审计与实现

本包只恢复 AI 教育案例的非正式完整 D 能力测试。用户于2026-09-07要求诊断、定位和修复，并明确 LLM、SLM **各自**最多90分钟生成一份完整计划书。开发/离线测试时间另列；本次 SLM 从启动执行控制器起，包括 Research 前置验证及后续全新完整 D，共享5400秒，不按节点或batch重置。公共LLM运行配置原本也限制每个run最多5400秒，不合并两模型时钟。没有启动正式S5八槽实验或新增Gemini消费。

## 已定位

上一轮 Research 正文941输出tokens、230.172秒通过。引用阶段尚在处理输入时，页文件采样 PowerShell/CIM 子进程8秒超时，触发必需遥测缺失中止；当时空闲RAM约2.24GiB。不能将它记为引用生成失败，也不能将最低RAM约1.87GiB单点读数解释为持续60秒超限。

原采样每5秒启动PowerShell；替换为Windows原生 `EnumPageFilesW`，汇总 `TotalInUse × page size`。不以commit charge或已分配页文件大小代替实际占用。API失败仍按遥测缺失停止；RAM低于2GiB或页文件较基线增长超过2GiB持续60秒的门不变。

原两阶段system不一致、正文指令重复，且正文片段目录重复全文。现共享阶段无关system，完整输入前置；目录以原字符位置引用唯一正文，完整审计目录仍保存文本；native schema使用共享证据ID枚举。正文、证据、章节、财务精度、关键声明、Critic/revision与唯一结构修复全部保留。实际缓存是否命中由真实运行判断，不能据prompt布局推定。

预检Writer与完整生成共同使用 `build_generation_prompt`，避免预检测到另一套提示词。共享prompt版本升级为 `grounded-generation-v6-compact-two-stage`；完整canonical仍 `proposal-grounding-v5-two-stage`，wire仍 `body-then-grounding-v1`。新旧prompt产物不能混作同一冻结协议。

停止路径保留启动时commandline/监听PID核验，并绑定只读原生进程句柄、精确创建时间和可执行文件路径；独占写入owner旁证供独立cleanup核验。停止保留有界taskkill与退出确认。身份不明或退出未确认不释放lease。已有声明到已有证据候选的查找表只帮助模型保留来源，不自动替模型选证据或修复输出。

## 预算及范围

90分钟是本次新运行上限；旧36请求/500000tokens/14400秒累计授权不重置。起点继承上轮累计13请求、预算扣记191323tokens、4788.311秒，剩余23请求、308677tokens；其中旧114777tokens属于未知请求的保守保留额度，不能宣称为实测生成量。单次输出8192，CPU/Granite Q4_K_M/32K不变。授权与前次结果SHA见 `authorization.json`、`budget_carryover.json`。

Research严格通过并自然结束后才运行全新完整D；任何失败保留原始数据并显式报告。若90分钟内失败，不能延长、删Critic、降低完整契约或用fixture填充结果。正式公共预算未改，模型更换、实验或预算扩大仍需确认。

## 验证及交接

最终实际结果记录于 `HANDOFF.md` 和本包 `run_01/probe/result.json`。离线fixture只证明工程行为，不证明真实计划书质量或SLM成功。安装会逐文件检查旧hash，保留before备份、全量源快照及2623项旧运行/数据文件的hash记录。没有commit或覆盖历史运行。

完整离线回归：733 passed / 25 deselected / 3 subtests passed，196.77秒。预算运行器：10 passed，2.02秒。`pip check`：No broken requirements found。261个runtime文件冻结，10文件变更；安装后专项与真实测试结果单独记录。
