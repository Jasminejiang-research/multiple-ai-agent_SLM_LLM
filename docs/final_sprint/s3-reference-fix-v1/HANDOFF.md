# S3 财务引用修复 v1 交接

2026-09-07。本版代码已安装；真实 Research 复测结束，完整计划书未生成。继续修复同一 S3 问题的内容锚/冻结来源规则，后续见 s3-reference-fix-v2；没有执行下一编号工作包。

已实现财务闭集和数组上限、本地拒绝重复、0–1 评分说明、包含具体路径及重复片段的唯一一次结构修复反馈。详见 DIAGNOSIS.md、change_manifest.json 和 before/。

实际离线验证：完整 **667 passed / 25 deselected / 3 subtests passed，115.87 秒**；运行器 **6 passed，2.26 秒**；目标安装后 **14 passed，1.29 秒**。初始失败日志均保留。

真实调用共 3 次，耗时 **709.921 秒（11 分 50 秒）**，共 **13961 tokens**：

| 请求 | 输入 / 输出 tokens | 结束 | 实际结论 |
| --- | --- | --- | --- |
| 原生数组探针 | 53 / 22 | stop | maxItems=2 生效，uniqueItems 未保证去重 |
| Research 首轮 | 4383 / 2533 | stop | 数组不再无限增长，所有评分合法，但两处引用仍重复，严格拒绝 |
| 唯一结构修复 | 4748 / 2222 | stop | 引用合法且无重复，评分/JSON schema 通过；完整契约因正文 content_anchor 不匹配失败 |

首轮数组长度为 31 / 29 / 2，前两项分别只有 28 个不同 ID。修复后的原始 JSON 还可观察到虚构的 `packet` 来源 ID 和来源摘录混入正文锚；业务校验未被放宽。完整 D 根据前置门保持 not_run，无 Critic/Strategy/Finance/Writer 真实业务调用，无计划书。

累计包含最初失败测试：**5 次请求、37864 tokens、2831.124 秒（47 分 11 秒）**。下一修复验证的余额为 **31 次请求、462136 tokens、11568.876 秒**。所有迭代沿用原 4 小时/36 请求/50 万 tokens 授权，没有重置额度。

资源保护 passed，最低可用 RAM 3956609024 字节，pagefile 最高增量 7340032 字节。所有请求自然结束，未触发 deadline，未复现 GPU 混合解码错误。服务已关闭；外部核验模型进程和 11434 监听均为 0，端点 lease 无文件。OwnedOllama 返回的 lease_released=false 表示该停止工具不擅自删除锁，外部核验确认请求自身已释放锁。

证据：run_01/probe/result.json、run_01/audit/audit_summary.json、run_01/audit/external_cleanup.json、逐条 raw.txt 和 usage.json、原始 events.jsonl。251 个已安装源/输入文件、251 个运行副本文件与 6 份原始修改备份均 hash 匹配，旧测试结果 hash 未变。正式公共配置 hash 未变，正式实验 0/8，Gemini 调用 0。

下一入口：s3-reference-fix-v2 的补充代码验证和同一预算下 Research 复测。只有通过完整 Research 才启动完整 D；S5 正式运行仍须满足原依赖和明确启动授权。
