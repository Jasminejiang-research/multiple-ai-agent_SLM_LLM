# 两个case待审材料

状态：**pending**。由Codex从优化计划§7.4候选及已有样例准备，尚未代表Jasmine批准名称、完整输入、财务假设或来源。仅批准case名称不足以批准这些材料。两case均用于相同A–D，共8个槽位。本文件是阅读入口；模型输入以各case的完整 `brief.json` 和 `packet.json` 为准。

## Case 1：AI education

名称：AI Tutor for MBA Students（假设性试点）。美国18岁以上MBA/商科研究生及申请者，英语商业案例推理教练；用户痛点、付费意愿和学习收益均是待验证假设。基础商业模式为个人订阅，院校许可作为后续选项，不计入基础收入。要求提出投资者可阅读的完整13章方案、差异化、分阶段行动、资金情景和有条件进入/不进入建议。

范围：前三个月发现需求/原型、随后三个月有限试点、之后仅在验证通过时扩展；不生成违反考试要求的代答，不默认取得课程材料授权或院校记录权限。财务表为launch后12个月的标准化经营情景，**不是按阶段预测的真实增长曲线**。NCES历史毕业人数不能当作当前MBA在校人数、可触达市场或收入预测。

| 财务输入（全部待审建模假设，USD） | 值 |
|---|---:|
| 期初现金 | 120000 |
| 个人月费/每用户月度可变成本 | 19 / 4 |
| 每月固定经营成本/营销 | 6000 / 1500 |
| 一次性启动支出 | 18000 |
| 12个月内平均付费用户：低/中/高 | 100 / 250 / 500 |

固定公式（S1用Decimal复算，S0不运行模型）：月收入=N×19；月可变成本=N×4；月贡献=N×(19−4)；月经营结果=月贡献−6000−1500；年情景现金变化=12×月经营结果−18000；期末现金=120000+年现金变化；经营盈亏平衡用户=ceil((6000+1500)/(19−4))。这是经营盈亏平衡，启动支出单列；分母≤0不能输出有限盈亏平衡人数。不是实验消费预算，也不把这些假设当用户已提供的事实。

待审输入：[brief.json](cases/ai_education/brief.json)、[packet.json](cases/ai_education/packet.json)。

| ID | 官方来源与用途 | 边界 |
|---|---|---|
| EDU-01 | [Khanmigo pricing](https://www.khanmigo.ai/pricing)：竞品价目及院校定价方式 | 相邻辅导产品；不能证明MBA需求或本产品付费意愿 |
| EDU-02 | [NCES Graduate Degree Fields](https://nces.ed.gov/programs/coe/indicator/ctb/graduate-degree-fields)：2024发布、2021–22历史学位数据 | business口径比MBA广，毕业数不是在校数；不是2026市场规模 |
| EDU-03 | [US Department of Education FERPA FAQ](https://studentprivacy.ed.gov/faq/what-ferpa)：教育记录及eligible student背景 | 有限FAQ，不是本产品的合规认定或完整法律清单 |

## Case 2：consumer hardware / intelligent ring

名称：Apple intelligent ring category-entry scenario（假设性类别进入研究）。沿用旧 APPLE intelligent ring 样例的意图，明确这是模拟管理咨询任务，不能写成Apple已公布的产品或内部计划。目标为美国成人智能手机用户，分析无屏幕wellness ring及可选订阅的差异化、资金情景和条件进入/不进入建议。

范围：12个月受限试点，发现需求→工程验证→有限用户试点→条件上市；不宣称已获得医疗有效性、FDA许可、现成系统整合或供应商报价。不假定品牌自动带来转化，不推断Apple内部安装基数。FDA页为guidance摘要，不等于完整guidance，也不据此认定产品豁免。

| 财务输入（全部待审建模假设，USD） | 值 |
|---|---:|
| 期初现金 | 1000000 |
| 硬件单价 | 299 |
| 每件制造/物流/退货保修准备 | 140 / 15 / 15 |
| 可选订阅月费/每订阅用户月度可变成本 | 4.99 / 1 |
| 订阅附加率/首年平均付费月数 | 40% / 6 |
| 首年固定启动成本/营销 | 350000 / 90000 |
| 首年销量：低/中/高 | 500 / 1000 / 2000 |

固定公式：硬件收入=U×299；硬件可变成本=U×(140+15+15)；订阅付费月量=U×0.4×6；订阅收入=付费月量×4.99；订阅可变成本=付费月量×1；首年贡献=硬件收入−硬件可变成本+订阅收入−订阅可变成本；情景现金变化=贡献−350000−90000；期末现金=1000000+现金变化。首年盈亏平衡销量=ceil((350000+90000)/((299−140−15−15)+0.4×6×(4.99−1)))；分母≤0为不适用。固定成本已含团队、设计、模具和合规准备，不重复添加；退货准备仅一次成本处理。未模拟存货/回款时点，不能称完整营运资金预测。

待审输入：[brief.json](cases/intelligent_ring/brief.json)、[packet.json](cases/intelligent_ring/packet.json)。

| ID | 官方来源与用途 | 边界 |
|---|---|---|
| RING-01 | [Oura Membership](https://support.ouraring.com/hc/en-us/articles/4409086524819-Oura-Membership)：美国订阅价与功能范围 | 厂商自述，不是独立临床有效性证据 |
| RING-02 | [Samsung US 2024 wearable announcement](https://news.samsung.com/us/samsung-galaxy-ring-watch7-watch-ultra-wearables-provide-intelligent-health-wellness-data/)：历史上市价、订阅方式与定位 | 2024上市参考，不是2026实时最低价或需求数据 |
| RING-03 | [FDA General Wellness guidance page](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/general-wellness-policy-low-risk-devices)：2026版本的范围摘要 | 没有抓取完整PDF；不支持对模拟产品作最终监管结论 |

## 完整快照、审核与未覆盖项

6个来源都保存抓取返回的原始HTML和完整可见文本；固定片段逐字对应txt行号，见packet。完整路径、UTC抓取时间及SHA-256见 `source_manifest.csv`；整包hash见 `bundle_manifest.json`。正式A–D仅用同一case的同一packet固定片段，不允许临时补搜。

这些材料足以形成可审阅的有界案例输入，并不声称证据穷尽：没有本产品访谈、转化/CAC/churn、供应商成本、市场规模、产品有效性或完整合规意见。输出应保留这些unknown，给出验证动作，不伪造引用。来源日期未知时null，历史数据标明时期。用户内容审核与最终输出的人工Gold Ledger是两个阶段；此时全部支持性人工结论仍为空。

请一次核查：两个case是否符合选题意图；完整brief和假设数字是否可接受；固定来源及片段是否合适、是否需补资料。确认前case/packet均pending，8行not_run，正式执行关闭。若有改动建立下一case/packet版本并重算hash；不更改已形成的S0快照。
