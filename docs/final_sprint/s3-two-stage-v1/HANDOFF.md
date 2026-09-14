# A–D 两阶段生成交接

更新时间：2026-09-07T09:45:55.792327+00:00。用户已批准该方案；代码已实施并安装，真实验证已结束。**尚未生成完整计划书**。Research状态=failed；完整D状态=not_run；总测试状态=resource_stopped。

## 完成内容

- 统一 A–D 的两阶段生成：先正文及完整财务值，后声明和原文片段选择，最后严格 canonical 组装与校验。原13章节、四批写作、来源、财务、lineage和人工Gold要求保留。
- 两个阶段共用原节点时间、请求/token预算及一次结构修复。Critic保持单阶段，条件Revision数量不变；正常A/B/C/D请求数8/15/18/18。
- 所有真实调用和阶段单独记账；正文草稿不会提前算作完整契约通过；展开的摘录不冒充模型输出token。完整候选目录、原始选择和展开映射落盘。
- 16个文件改动、其中3个新增；256文件冻结快照。13个既有文件的安装前版本保存在before/。2254个旧sprint与data文件hash全部保持，公共CPU配置hash保持，未commit。

## 实际验证

- 完整离线回归：702 passed、25 deselected、3 subtests passed，172.06秒（validation/full_final.log）。
- 安装后两阶段与本地适配专项：30 passed，7.40秒（validation/installed.log）。累计预算运行器：7 passed，3.20秒（validation/runner.log）。现有依赖pip check通过，未安装或升级依赖。
- 两个案例的合成18请求演练中，AI教育最大输入19324tokens/74640字符，智能戒指21205tokens/88979字符；加8192输出后均在32K内。原始过长目录问题与修正后的演练均保留，合成结果不是模型能力证据。
- 真实本轮新增 2 请求、用时300.640秒。HTTP请求=2。已知实测用量=5294tokens；1次请求用量未知，保留114777tokens预留扣记。本轮预算扣记合计120071tokens，不能当作实际生成量。累计13请求、预算扣记191323tokens、4788.311秒。
- 原额度剩余23请求、308677tokens、9611.689秒。后续必须承接本包run_01/probe/result.json，不能复用较早启动额度。
- 实际模型保持Granite H Micro原digest/Ollama0.33.2/CPU/32K/温度0。资源状态=failed，截止触发=False；结束后的进程/端口/lease核验见run_01/audit/external_cleanup.json。
- 独立审计=passed；本次仅有正文和候选目录可供核验，均通过。尚无通过第二阶段的真实输出，因此真实canonical展开仍未验证。审计脚本已在7个合成逻辑单元上独立重建成功，不代替模型能力或人工Gold判断。

## 当前阻塞与入口

本次直接停止原因是Windows页文件占用采集（Get-CimInstance Win32_PageFileUsage）的8秒超时，触发原required_resource_telemetry_missing门。Research正文941输出tokens、230.172秒自然stop并通过；引用选择请求在输入处理期间取消。最低可用RAM为2010853376bytes（约1.87GiB），未取得持续60秒低RAM触发证据；不能将采样超时简单归因为模型能力或内存不足。未触发4小时截止、未收到第二阶段完整响应。模型服务关闭后页文件采样恢复，见RESOURCE_STOP.md。

当前应先解决高负载下页文件采样可靠性并复核资源余量，再按保留状态和剩余额度安排恢复验证；不跳过原资源门、不把本次中断当作引用生成通过或失败的证据。第二阶段未知请求已确认终止并归档lease，原始用量未知状态及预留扣记保持。

本轮错误记录（为空表示未记录失败逻辑任务）：

```json
[
  {
    "task": "research.v1",
    "stage": "grounding",
    "error": "run cancellation requested"
  }
]
```

完整计划书目录：无。对外ready状态不由本次结构校验自动批准。

下一入口：以真实Research/完整D结果定位未通过门；若本次完整D通过，供后续正式预检依赖审查使用，但不等于正式八槽运行已批准。S5仍需原两case输入批准、Gemini额度与smoke、公共预算和新共享协议代码冻结、正式启动授权及后续人工评审。没有自动执行下一工作包、没有调用Gemini或正式实验。

## 文件入口

- 实现：workflow/two_stage_generation.py、workflow/contract_generation.py、workflow/review_runtime.py；版本和事件契约在schemas/及workflow/review_config.py；组件入口slm/granite_preflight.py。
- 本包IMPLEMENTATION.md、authorization.json、change_manifest.json、install_receipt.json、final_manifest.json。
- 真实阶段/请求/原始响应：run_01/probe/各阶段events.jsonl，run_01/audit/；完整总结果run_01/probe/result.json。
- 保留：before/、runtime/、runtime_source.zip、history_inventory.json、全部validation初轮失败与最终通过日志。
