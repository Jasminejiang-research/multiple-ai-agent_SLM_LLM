# S0 基线与实际验证

检查时间：2026-09-06（详细UTC见baseline.json）。目标工作区 `C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`；分支 `codex/final-sprint`；HEAD `4a256c060f39eb1ade754677e9897a94e923bb00`。开始时工作树干净，没有未提交修改；未自动commit、切分支或reset。

## 环境与测试

可靠入口：目标项目 `.venv/Scripts/python.exe`，Python 3.12.10。第一次在受限沙箱启动报告WindowsApps Python不可访问；经授权在沙箱外同一入口正常启动。不是虚拟环境损坏，不重建/删除环境。`pip check` 实际通过：No broken requirements found。关键依赖版本及完整旧freeze见baseline.json和上一层baseline-requirements.txt；本包没有安装、升级或卸载依赖。

实际重跑命令（目标仓库目录）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& '.venv/Scripts/python.exe' -B -m pytest -q tests slm/tests -p no:cacheprovider
```

结果：**362 passed, 25 deselected, 3 subtests passed in 56.73s**，exit 0。25项live测试按pytest.ini排除，没有调用真实Gemini API。与已迁移基线362/25/3一致，无既有测试失败。默认仅 `pytest -q` 的testpaths不含slm/tests，后续必须显式列出两目录。

S0新增离线材料校验与测试结果见 `validation_results.txt`；它们验证hash、allowlist、分母槽位与pending门，不能证明模型质量、Granite可行性或新工作流已经实现。

## 现有实现与配置

| 项目 | 本轮实际检查 |
|---|---|
| A入口 | app.generate_proposal直接生成旧BusinessProposal，temperature=0.4 |
| Multi图 | 固定specialist顺序，final critic→revision固定边；Supervisor不调用LLM |
| 共同批候选 | workflow/generation_batches.py已存在4/3/3/3完整13章 |
| SLM适配 | 存在5/4/4内部批和pruned schema；需核对实际被上游schema-specific接口调用的路径，不能仅凭chunked flag推断实际批次 |
| Gemini代码默认 | 8请求、120000 run tokens；请求输出16384、prompt120000字符；旧角色温度0.2/0.3 |
| Gemini实际.env | 51请求、600000 run tokens，不是新公共预算 |
| SLM代码默认 | SiliconFlow/Qwen2.5-7B、12请求、160000 tokens、8192输出、900秒 |
| SLM实际.env.slm | SiliconFlow/Qwen2.5-7B、18请求、300000 tokens、4096输出、90000字符、300秒、chunked=1、pruned=1 |
| 密钥 | GEMINI_API_KEY、GOOGLE_API_KEY、TAVILY_API_KEY、SLM_API_KEY配置项均非空；不验证有效性、不输出密钥 |
| 预算/usage | 已有RunBudget、ContextVar与成功响应聚合；缺共同墙钟和attempt/原始usage缺失语义 |
| SQLite | 复用既有JSON字段即可，不需要迁移 |

这些都是预期工程差距，不是改变已确认研究范围的理由。不得启动现有SLM CLI作为D；其当前模型/endpoint不是Granite。S0没有改.env、SLM配置、生产prompt/schema/图或前端。

## Ollama与数据保留

Ollama可执行文件已安装。沙箱内及沙箱外对127.0.0.1:11434的version/tags/ps请求都连接被拒；不是把沙箱网络错误当服务事实。默认 `~/.ollama/models/manifests` 存在但没有模型清单。未检查其他自定义模型目录，未确认Granite本机已下载；没有启动模型、生成、下载或卸载。版本API不可用，版本未知；S3负责启动配置和完整预检，S0不宣称D失败或已可行。

目标仓库运行目录检查：data仅.gitkeep，无app.db；outputs、slm/data、slm/outputs不存在。它是迁移后的代码工作区，不能声称历史运行数据丢失。原工作区 `C:/Users/JasmineJiang/Projects/multiple_ai_agent` 仍有app.db与旧Markdown；只读SHA-256清单见 `legacy_history_readonly_inventory.json`，未复制、改写或清除。当前新增文件仅S0交付，不修改原历史。

## Gemini用户决策

用户本轮原话：“暂无记录；你先不要管Gemini的额度，我记得我上次充值过一次，额度应该足够我们的实验次数。”因此不继续查询账户、余额或配额，不以密钥存在推断免费/付费状态；相关字段null并注明user_reported_prior_top_up_unverified。无需以此阻塞S0/S1工程工作。约50元仍是冲刺消费约束；S0零模型API调用、零充值。

查阅过的Google官方说明仅供以后需要时定位账户信息：[billing](https://ai.google.dev/gemini-api/docs/billing)、[rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)。公共页面不证明本项目实际额度；用户上述答复优先于继续查询的原准备计划。
