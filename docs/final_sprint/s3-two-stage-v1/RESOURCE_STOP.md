# 真实测试中断：Windows 页文件采集超时

2026-09-07。协议实现和离线验收通过；真实完整计划书尚未生成。

1. Research 正文请求成功：4353输入、941输出、5294总tokens，230.172秒，HTTP完成并自然stop；内部正文校验通过，冻结正文与候选目录已留存。
2. 第二阶段请求已发出，服务器日志显示正在处理输入；43.781秒后控制器取消，尚无完成响应。这里的43.781秒是控制器记账时间，服务器从请求取消到确认停止之间仍可能执行，不能据此推断完整请求耗时或tokens。
3. 直接触发项：required_resource_telemetry_missing。WindowsResourceProbe用8秒超时运行PowerShell的Get-CimInstance Win32_PageFileUsage；该样本返回TimeoutExpired，页文件占用缺失，原门按规则停止。
4. 原RAM规则为持续60秒低于2GiB；本次最低观测2010853376bytes（约1.87GiB），没有记录满足持续60秒门。缺失样本时可用RAM2404392960bytes（约2.24GiB）。最大已观测页文件增量4MiB，不能把缺失样本视作0或认定无压力。
5. 首次停止进程核验也超时，随后重试确认owned_process_tree_terminated。最终外部核验模型进程、11434监听、活动lease均0；原请求lease按run_id/attempt_id核对后移动至audit/terminated_unknown_request.lease.json，hash保持。没有重新发送请求。
6. 停止后同一CIM页文件查询恢复，观测当前占用366MiB。因此已证实的是高负载期间采样超时；内部Windows/WMI/调度瓶颈尚未唯一定位，不能据此声称模型引用生成失败、Ollama解码失败或持续RAM门超限。

预算：本轮2请求、300.640秒；只取得首请求5294实测tokens。第二次用量未知，保留原114777tokens预留，本轮预算扣记120071tokens。累计13请求/191323预算tokens/4788.311秒；剩余23请求/308677预算tokens/9611.689秒（约2小时40分12秒）。这些预留不是实际生成量，不予重置或擅自扣回。

恢复前入口：复核CPU推理时的系统余量与页文件采集可靠性；在同样采样含义和原资源门下验证采集方案。若需要降低资源保护标准、改变模型/上下文/预算或实验范围，应先形成具体方案并征求用户确认。第二阶段和完整D仍待真实验收；不自动开始S5正式实验。

证据：run_01/probe/events.jsonl的resource_stop/server_stop；research_probe/events.jsonl的物理调用和logical_task；run_01/server/server.stderr.log；run_01/probe/result.json；run_01/audit/assembly_audit.json和external_cleanup.json。
