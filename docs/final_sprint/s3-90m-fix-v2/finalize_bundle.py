"""Close engineering handoff without starting or authorizing a model run."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import shutil

STAGE = Path(__file__).resolve().parent
REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
REPORT = REPO/'docs/final_sprint/s3-90m-fix-v2'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text(encoding='utf-8-sig'))

files = load(REPORT/'runtime_manifest.json')['files']
for entry in files:
    if sha(REPO/entry['path']) != entry['sha256'] or sha(REPORT/'runtime'/entry['path']) != entry['sha256']:
        raise RuntimeError('Installed/frozen source mismatch: '+entry['path'])
history = load(REPORT/'history_inventory.json')
for entry in history:
    if sha(REPO/entry['path']) != entry['sha256']:
        raise RuntimeError('Prior historical file changed: '+entry['path'])
for entry in load(REPORT/'external_dependencies.json'):
    if sha(Path(entry['path'])) != entry['sha256']:
        raise RuntimeError('Public budget/launcher changed')
full = (REPORT/'validation/full_final.log').read_text(encoding='utf-8-sig')
installed = (REPORT/'validation/installed.log').read_text(encoding='utf-8-sig')
helper = (REPORT/'validation/trial_runner_installed.log').read_text(encoding='utf-8-sig')
if '782 passed, 25 deselected, 3 subtests passed' not in full or 'failed' in installed or 'passed' not in installed or '26 passed' not in helper:
    raise RuntimeError('Expected successful validation logs')
lines = lambda text: next(line for line in reversed(text.splitlines()) if 'passed' in line)
receipt = dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
    full_regression=lines(full), installed_validation=lines(installed), helper_validation=lines(helper),
    installed_and_frozen_files_verified=len(files), historical_files_verified_unchanged=len(history),
    public_budget_unchanged=True, model_calls_after_v2_fix=0, formal_runs_started=0,
    complete_plan_demonstrated=False, next_run_authorization='pending')
(REPORT/'verification_receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')

handoff = f'''# S3 精准修复 v2 交接

**修复已安装；完整计划书仍未生成，90分钟达标尚未验证。**

实际定位了两个本轮阻塞：Research 将正文片段 ID 当成声明 ID，并跨不同语义复用；Windows 三段待机合计 **49分49.45秒**。旧注释中的页文件 CIM 采样超时已由 v1 原生采样修复，本轮没有缺失采样值，但长时间无采样使连续资源覆盖无法认证。旧 `resources=passed` 不能解释为全过程资源通过；原日志保留，复核见前包 `run_01/audit/RESOURCE_COVERAGE.md`。

## 已安装

15文件精确变更：声明 ID/父 ID/版本约束、带实际路径与字段差异的修复反馈、正确 nullable enum 提示、共享紧凑 JSON 与非冗余证据提示、运行期间防自动睡眠申请、遥测空档停止，以及公开 Granite 预检入口集成。8个旧版本已备份，268文件源快照已验证。

共享 prompt 为 `grounded-generation-v7-claim-identity`，canonical 仍 `proposal-grounding-v5-two-stage`。完整13节、21行财务、来源、正文锚、lineage、Critic与一次结构修复均保留；公共正式预算、模型、GPU配置不变。

## 实际验证

- 完整离线：{lines(full)}。
- 安装后专项：{lines(installed)}。
- 安装后运行器：{lines(helper)}（mock；无模型/Windows调用）。
- {len(history)}个历史文件逐一 hash 未变，268个当前/快照文件一致；原未提交修改及运行数据保留。
- v2 新模型调用0；此轮此前 v1 真实3请求，Research正文923 tokens/217.438秒通过；grounding6055 tokens/1240.266秒自然结束但声明身份冲突；唯一修复耗尽5400秒截止。总记录5405.172秒含清理，完整D未开始。
- 本包紧凑 JSON 的6000→4801 token差是**离线等值度量**，未证明真实提速或计划书成功。

## 剩余阻塞与下一入口

完整 D 是否能在90分钟完成仍未知。需对新版本做真实端到端验证；离线通过不代表模型行为通过。原Research还存在统计事实误读，人评/Gold与结构验收分开。

旧累计额度已用16请求/296569预算tokens/10193.483秒；剩20请求/203431预算tokens/**70分6.517秒**。未知用量保留预留，不退款，不重置。新独立90分钟复测授权目前 pending，启动器会在模型启动前阻断。具体可审批方案见 [NEXT_RUN_PROPOSAL.md](NEXT_RUN_PROPOSAL.md)：接电源、机盖保持打开，一次完整D最多5400秒、8192输出tokens、36请求/50万tokens；历史消耗独立保存。

用户确认后入口：`Invoke-RecoveryTrial.ps1 -SharedRepo C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`，输出唯一 `run_01/`。它使用完整D内部Research门，省去额外的重复Research预检；不跳过D中任何步骤。

Gemini真实调用0、正式实验0/8。没有自动启动S5正式八槽或下一工作包。正式A–D比较仍需共同预算决定及新prompt重新冻结，旧版本运行不能混入新比较。

依据、逐项变更和证据索引见 `IMPLEMENTATION.md`、`change_manifest.json`、`verification_receipt.json`、`validation/` 与前包真实 `run_01/probe/result.json`。完整计划书文件路径：**暂无**。
'''
(REPORT/'HANDOFF.md').write_text(handoff, encoding='utf-8')
status_path = REPO/'docs/final_sprint_status.md'
previous = (REPORT/'PREVIOUS_STATUS.md').read_bytes()
if status_path.read_bytes() != previous:
    raise RuntimeError('Latest status changed concurrently; preserve it and reconcile manually')
header = f'''<!-- s3-90m-fix-v2 current -->
# 最新 S3：声明身份与待机修复已安装，真实完整D待复测

**完整计划书尚未生成；不能宣称90分钟达标。** 最新失败已定位：span-ID被误当声明ID导致跨语义碰撞；Windows三段睡眠合计49分49.45秒。旧页文件采样超时已修复，但旧资源passed仅代表观测点，40分钟空档不能认证连续资源门通过。真实原始记录保留。

15文件精准安装、268文件快照/安装hash一致、8个before备份、{len(history)}历史文件未变。完整回归 {lines(full)}；安装后 {lines(installed)}；运行器 {lines(helper)}。共享prompt=v7-claim-identity、canonical=v5，两阶段/完整13节/21行财务/grounding/lineage/Critic/修复次数均保留。

本包修复后真实调用0。此前本轮v1为3请求/5405.172秒含清理，Research正文通过、grounding身份冲突，完整D未启动。累计16请求/296569预算tokens/10193.483秒，原4小时余额4206.517秒。新独立90分钟完整D方案待用户确认，不清除历史消耗；明确方案与入口见 docs/final_sprint/s3-90m-fix-v2/NEXT_RUN_PROPOSAL.md。

详细交接：docs/final_sprint/s3-90m-fix-v2/HANDOFF.md。Gemini0、正式0/8，公共正式预算不变；新prompt需共同重冻，未自动进入下一工作包。

---
<!-- s3-90m-fix-v2 preserved previous records -->

'''
status_path.write_bytes(header.encode('utf-8') + previous)
if STAGE != REPORT:
    shutil.copy2(Path(__file__), REPORT/'finalize_bundle.py')
print(json.dumps(receipt, indent=2))
