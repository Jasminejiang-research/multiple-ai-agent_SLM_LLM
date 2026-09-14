<!-- s3-research-20m-v1 installed -->
# 最新 S3：Research 精简已安装，准备20分钟组件实测

按用户最新要求，Research改为市场、客户、竞争各一条核心发现，每条一条声明，最多一条额外证据缺口；财务计算由Finance负责。完整计划13章节、财务明细、来源与继承校验保留。共享提示词更新为grounded-generation-v8-brief-research；正式实验需冻结新版本。

Research父节点正文、声明、结构修复、Critic、条件修订共享最多1200秒；正文输出最多640、声明最多2304 tokens，仍服从更低原配置上限。此次真实验证只执行Research生成组件及严格校验，不包含Critic或完整D；硬截止不等于保证有效产出。

已安装9文件，保留5原版本与全部历史。完整离线823 passed/25 deselected/3 subtests；安装83 passed，运行器27 passed。一次安装测试命令因文件路径拼写错误未收集测试，已更正并通过，日志保留。

此次使用原已批准90分钟池剩余34请求/409083预算tokens/1815.312秒，其中最多1200秒用于本组件；旧未知用量不退款，不重置全历史。实测尚未完成，结果以 docs/final_sprint/s3-research-20m-v1/run_01/probe/result.json 为准。

未自动重启完整D、调用Gemini、启动正式S5八槽或下一包。交接：docs/final_sprint/s3-research-20m-v1/HANDOFF.md。

---
<!-- preserved previous records -->


# Research simplification and 20-minute limit

The user confirmed manually interrupting the preceding complete-D trial and explicitly requested shorter Research output within 20 minutes. This package implements that scope. It retains the final proposal's 13 sections, complete financial values, strict grounding and lineage checks. No model, GPU configuration, source packet, Critic scoring metric or routing threshold is changed.

## Generation profile

Shared `research-brief-v1` applies to Research in B/C/D, including Gemini and Granite. A retains its Single final-proposal contract. The canonical reader stays `proposal-grounding-v5-two-stage` so historical artifacts remain readable. New generations use `grounded-generation-v8-brief-research`; formal comparisons must re-freeze this profile and not pool old versions.

- Exactly one market, one customer, and one competitor/substitute finding.
- Exactly one atomic core claim per finding; at most one additional unsupported claim: at most four claim objects in total.
- Character ceilings: summary 280, topic 60, finding 240, rationale 160, claim text 240, domain 48, premise 200. At most three human-review questions of 140 characters each.
- Research defers scenario calculations to Finance. `financial_value_ids` is required to be `[]`; native case bounds now preserve narrower profile limits instead of widening them.
- At most two evidence selections for a new Research claim, with all candidates still available. A larger inherited original anchor set remains representable; inherited evidence is never silently dropped.
- Claim ID/version/parent rules, exact source quotation assembly, the full canonical validator and one structural repair remain. Code rejects overlong outputs without truncating or silently pruning them.
- Research Critic assesses the three-theme brief scope, while retaining existing metrics, scoring and severity rules. Incorrect facts, arithmetic actually stated, unsupported claims and missing uncertainty still count as errors.

The profile is for fresh generation and revisions of fresh brief outputs. Do not reinterpret older large Research artifacts as new brief outputs or silently discard their claim lineage to force them into this profile.

## Time and token control

The **Research parent node** shares one `min(config.node_seconds, 1200)` clock across body, grounding, structural repair, Critic and conditional revision. It cannot restart at each phase. Other role clocks retain their original behavior. Logs expose the effective deadline.

Research physical output caps are `min(global_cap, 640)` for body and `min(global_cap, 2304)` for grounding/legacy single-stage. Repairs use their stage's same cap. Existing lower formal caps are never raised. Critic output caps remain as configured, but Critics still share the Research parent deadline.

A hard stop guarantees no continued inference beyond the allowed active run deadline; it does **not** guarantee a valid response will finish. Character ceilings are not token counts, and sleep/user interruption can delay wall-clock cleanup. Actual model completion is separately measured.

## Authorized real verification scope

One Research **generation component** test only: body + grounding + its existing single structure repair and full canonical/context verification. This component probe does not run Critic, semantic revision, Strategy, Finance, Writer or full D. Its measured generation time must not be described as the latency of the entire reviewed Research parent or a complete plan.

The user-authorized fresh 90-minute pool from the interrupted preceding run consumed 2 requests / 90,917 charged tokens / 3584.688 seconds. It retains 34 requests / 409,083 charged tokens / 1815.312 seconds. The new probe uses at most 1200 seconds **from that remainder**, without resetting the pool. Its source result hash and the parent authorization are recorded.

All-history consumption before this probe is separately 18 requests / 387,486 charged tokens / 13,778.171 seconds. Unknown requests retain their reservations; the preceding 85,923-token unknown reservation is not actual measured use or a refund.

## Verification and preservation

Complete offline regression: **823 passed, 25 deselected, 3 subtests passed in 168.14 seconds**. Target-installation and probe-runner results are recorded in `validation/` and `HANDOFF.md` after they finish. A passing offline or mock test is not model success.

`runtime_source.zip`, `runtime_manifest.json`, `change_manifest.json`, `before/` and `history_inventory.json` preserve exact sources, old uncommitted versions and historical data. No commit/reset, new package or formal experiment is started automatically.

Entry after installation: `Invoke-RecoveryTrial.ps1 -SharedRepo C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM`. It verifies frozen source and remaining allowance before starting the owned CPU service. Output is the unique `run_01/probe/` directory.

## Final pre-probe amendment

Before any real call, removed generic nonempty financial-reference examples from brief Research body, grounding and repair feedback. All three use the empty allowed set; normalized score guidance remains. The amendment's previous files and manifests are preserved in `pre_probe_amendment/`.

Final source verification: `tests/` **613 passed, 25 deselected, 3 subtests, 274.37s**; `slm/tests/` **211 passed, 25.31s**, totaling **824 passed** across the full offline suite. The default pytest testpaths omits slm/tests, so both directories were explicitly covered. Final installed amendment **53 passed, 6.38s**, prior installed profile/deadline checks **83 passed, 9.13s**, installed runner **27 passed, 2.35s**. No model call occurred during these tests.
