> 最终状态更新：v3 别名试验没有改善验收，已恢复并保留本 v2 实现；最终总交接见 ../s3-reference-fix-v3/HANDOFF.md。下文保留本轮完成时的历史记录。

# S3 财务引用与锚修复 v2 交接

2026-09-07。本版代码已安装，真实 Research 复测结束；完整计划书未生成。继续验证同一 S3 修复中的生成端字段别名，后续见 s3-reference-fix-v3；未自动执行下一编号工作包。

本版补齐正文锚和冻结来源说明、来源 ID/chunk/hash 闭集及多问题反馈，保留 v1 的财务长度与唯一性校验、0–1 评分规则。实现与初始测试失败记录见 IMPLEMENTATION.md。

实际离线结果：完整 **673 passed / 25 deselected / 3 subtests passed，120.30 秒**；运行器 **7 passed，2.86 秒**；目标安装后 **20 passed，1.54 秒**。

真实运行 **753.672 秒（12 分 34 秒）**，3 次请求，共 **16008 tokens**：

| 请求 | 输入 / 输出 tokens | 结束 | 实际结果 |
| --- | --- | --- | --- |
| 原生数组探针 | 53 / 22 | stop | 长度上限生效，uniqueItems 仍需本地保障 |
| Research 首轮 | 5369 / 2178 | stop | 财务引用/评分未检出问题；客户设定错误标为 sourced_fact，JSON schema 拒绝；另有 4 处正文锚错误 |
| 唯一结构修复 | 5904 / 2482 | stop | JSON schema、引用、评分通过；正文锚仍错，完整契约拒绝 |

修复轮仍有 4 处 content_anchor 未出现在父正文；还可观察到 2 处引文没有逐字匹配所填冻结行号。来源 ID/chunk/hash 未再检出此前的虚构与错误配对，但该结果不代表证据实际支持相应语义，人工 Gold 仍未执行。完整 D 为 not_run，没有下游真实业务调用或计划书。

累计包含最初失败与 v1：**8 请求、53872 tokens、3584.796 秒（59 分 45 秒）**。后续起始余额 **28 请求、446128 tokens、10815.204 秒（约 3 小时）**。没有重置 4 小时、36 请求、500000 tokens 授权，也没有提高单次 8192 上限。

资源保护 passed，最低可用 RAM 4061503488 字节，pagefile 最大增量 8388608 字节；未触发 deadline。模型服务已关闭，外部核验进程/监听/活动 lease 均为 0。公共 A–D 配置 hash 未变，Gemini 调用 0，正式实验 0/8。

证据：run_01/probe/result.json、run_01/audit/audit_summary.json、external_cleanup.json、各次原始 raw.txt 和 usage.json。253 个已安装源/输入、253 个运行副本及 before/ 的 8 份安装前文件均 hash 匹配；上一结果 hash 未变。历史和未提交修改已保留。

下一入口：s3-reference-fix-v3 的生成端 verbatim_parent_text 别名验证；内部仍保存原 content_anchor，文字不补写，验收条件和业务调用结构保持原样。只有完整 Research 通过才启动 D。S5 正式运行仍待原条件与明确启动授权。
