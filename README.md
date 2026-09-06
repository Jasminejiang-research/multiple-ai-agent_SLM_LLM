# multiple-ai-agent_SLM_LLM

本仓库从既有 Multiple AI Agent 产品迁移，继续完成最终产品优化与实验。保留原提交历史，产品代码基线来自旧仓库已推送的 `fb085642bd76a0aa43ca0ef4a6d6547ae026aedc`，迁移本身只新增交接文档与验证材料。

## 最终冲刺入口

- [逐包执行计划：sprint_plan_.md](docs/final_sprint/sprint_plan_.md)
- [最新产品优化设计](docs/final_sprint/@multiple_ai_agent_optimization.md)
- [最新评价指标规范](docs/final_sprint/@ai_agent_evaluation_metrics_spec.md)

以上是 2026-09-06 桌面最新规划的同步快照；用户后续决策及冲刺计划所列权威来源优先。仓库其余早期设计文档保留作历史参考，不得据此恢复已经取消的实验条件。

当前方案为 A–D 四组，每组相同两个 case，共八次正式运行。Granite 使用角色级 Critic＋最终 Critic，检查失败才修订。迁移未执行 S0，也未启动正式实验；两个 case 的确认和真实模型预检仍属于后续工作包。

后续在新项目中读取本计划，执行一个指定工作包（首先 S0）；完成验收与交接后，再按用户要求进入下一包。`docs/final_sprint_status.md` 由 S0 新建。

## 迁移基线

| 项目 | 记录 |
|---|---|
| 日期 | 2026-09-06 |
| 来源仓库 | https://github.com/Jasminejiang-research/multiple_ai_agent |
| 来源提交 | `fb085642bd76a0aa43ca0ef4a6d6547ae026aedc` |
| 来源代码树 | `3ed0a594816a072e35c29d41ebb6fedd87308310` |
| 来源远端分支 | `master`、`codex/sprint-plan-slm`，迁移时均指向上述提交 |
| 新本地目录 | `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM` |
| 新远端 origin | https://github.com/Jasminejiang-research/multiple-ai-agent_SLM_LLM.git |
| 基线分支／标签 | `main`／`baseline-pre-final` |
| 后续开发分支 | `codex/final-sprint` |

使用 `git clone --no-hardlinks --single-branch --branch codex/sprint-plan-slm` 从旧本地目录创建独立副本，继承该分支完整祖先历史。只在新副本替换远端。旧目录、旧远端和旧仓库提交不作修改。

迁移基线提交在来源提交之上，只加入本 README 和 `docs/final_sprint/`。基线标签用于与后续优化比较；具体基线提交可用 `git rev-parse baseline-pre-final` 查询。

## 环境与验证

新目录已建立独立 `.venv`，使用 Python 3.12.10，依赖版本与迁移时旧环境一致。冻结列表见 [baseline-requirements.txt](docs/final_sprint/baseline-requirements.txt)。重建时使用 Python 3.12 创建虚拟环境，再安装该列表；无需依赖旧项目的 `.venv`。

```powershell
Set-Location "C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM"
& ".\.venv\Scripts\python.exe" -m pip check
& ".\.venv\Scripts\python.exe" -m pytest -q tests slm/tests
```

迁移验收在新目录独立环境中执行：

- `pip check`：`No broken requirements found.`
- 完整本地测试：`362 passed, 25 deselected, 3 subtests passed in 62.60s (0:01:02)`。
- `pytest.ini` 默认排除 `live`，25 项真实 API 测试未执行；通过结果不代表 Gemini 服务或本地 Granite 已完成预检。
- [原始测试输出](docs/final_sprint/baseline-test-results.txt)。

`.env` 与 `slm/.env.slm` 仅复制到本机新目录，并仍被 Git 忽略；配置沿用旧值，尚未按最终冲刺改为或验证 Granite 设置。虚拟环境、密钥、模型权重、缓存及历史运行输出均不进入此次 Git 提交。旧运行数据留在旧目录，不作为本次八次正式实验结果。
