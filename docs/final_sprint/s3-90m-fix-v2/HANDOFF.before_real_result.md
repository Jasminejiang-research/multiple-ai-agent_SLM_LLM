# S3 精准修复 v2 交接

**修复已安装；完整计划书仍未生成，90分钟达标尚未验证。**

实际定位了两个本轮阻塞：Research 将正文片段 ID 当成声明 ID，并跨不同语义复用；Windows 三段待机合计 **49分49.45秒**。旧注释中的页文件 CIM 采样超时已由 v1 原生采样修复，本轮没有缺失采样值，但长时间无采样使连续资源覆盖无法认证。旧 `resources=passed` 不能解释为全过程资源通过；原日志保留，复核见前包 `run_01/audit/RESOURCE_COVERAGE.md`。

## 已安装

15文件精确变更：声明 ID/父 ID/版本约束、带实际路径与字段差异的修复反馈、正确 nullable enum 提示、共享紧凑 JSON 与非冗余证据提示、运行期间防自动睡眠申请、遥测空档停止，以及公开 Granite 预检入口集成。8个旧版本已备份，268文件源快照已验证。

共享 prompt 为 `grounded-generation-v7-claim-identity`，canonical 仍 `proposal-grounding-v5-two-stage`。完整13节、21行财务、来源、正文锚、lineage、Critic与一次结构修复均保留；公共正式预算、模型、GPU配置不变。

## 实际验证

- 完整离线：782 passed, 25 deselected, 3 subtests passed in 177.13s (0:02:57)。
- 安装后专项：132 passed in 8.73s。
- 安装后运行器：26 passed in 3.35s（mock；无模型/Windows调用）。
- 2943个历史文件逐一 hash 未变，268个当前/快照文件一致；原未提交修改及运行数据保留。
- v2 新模型调用0；此轮此前 v1 真实3请求，Research正文923 tokens/217.438秒通过；grounding6055 tokens/1240.266秒自然结束但声明身份冲突；唯一修复耗尽5400秒截止。总记录5405.172秒含清理，完整D未开始。
- 本包紧凑 JSON 的6000→4801 token差是**离线等值度量**，未证明真实提速或计划书成功。

## 剩余阻塞与下一入口

完整 D 是否能在90分钟完成仍未知。需对新版本做真实端到端验证；离线通过不代表模型行为通过。原Research还存在统计事实误读，人评/Gold与结构验收分开。

旧累计额度已用16请求/296569预算tokens/10193.483秒；剩20请求/203431预算tokens/**70分6.517秒**。未知用量保留预留，不退款，不重置。新独立90分钟复测授权目前 pending，启动器会在模型启动前阻断。具体可审批方案见 [NEXT_RUN_PROPOSAL.md](NEXT_RUN_PROPOSAL.md)：接电源、机盖保持打开，一次完整D最多5400秒、8192输出tokens、36请求/50万tokens；历史消耗独立保存。

用户确认后入口：`Invoke-RecoveryTrial.ps1 -SharedRepo C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`，输出唯一 `run_01/`。它使用完整D内部Research门，省去额外的重复Research预检；不跳过D中任何步骤。

Gemini真实调用0、正式实验0/8。没有自动启动S5正式八槽或下一工作包。正式A–D比较仍需共同预算决定及新prompt重新冻结，旧版本运行不能混入新比较。

依据、逐项变更和证据索引见 `IMPLEMENTATION.md`、`change_manifest.json`、`verification_receipt.json`、`validation/` 与前包真实 `run_01/probe/result.json`。完整计划书文件路径：**暂无**。
