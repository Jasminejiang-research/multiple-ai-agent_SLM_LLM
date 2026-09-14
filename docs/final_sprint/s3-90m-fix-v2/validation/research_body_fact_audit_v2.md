# Research 正文事实抽查：独立90分钟测试 v2

范围：只读一次已完成的 Research body，不检查或干预进行中的 grounding，不修改模型输出，不作为人工 Gold 裁决。

正文证据：[full_d/events.jsonl](C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-90m-fix-v2/run_01/probe/full_d/events.jsonl)，attempt `a62c23a7-96bd-44d4-ada2-093c7803ea06`；成功响应 event `247be667-ef06-4008-8534-203ef7b816cc`，UTC `2026-09-07T12:23:08.761579+00:00`。实际703输出tokens、196.359秒、自然stop；结构通过仅指 body 契约。

## 明确发现

1. **学位时间段误读仍出现。** `market_trends[0].finding` 写为 “880,200 master’s degrees conferred between 2011-22”。冻结 `EDU-02-C1`（TXT299–305行）明确880,200是 **2021–22单学年**硕士学位授予量；2011–12至2021–22是从756,000增长至880,200的比较区间，不是累计授予区间。`EDU-02-C2`（342–354行）也重申2021–22。该段关于“不能直接证明本产品需求”的限制仍保留，但未纠正时间错配。

2. **旧百分比分母错误本次未出现，但不能据此认定已修复。** 本次正文没有69%、23%等百分比陈述。冻结 `EDU-02-C2` 的69%表示五大学科占全部硕士学位的比例；23%表示business占全部硕士学位的比例。正文省略这些数值，因此本次无法检验模型是否正确理解其分母。

3. **摘要盈亏平衡人数明确算错。** `analysis_summary` 写 “Break-even requires ~250 paying users”。冻结brief的每用户月价19、变动成本4、固定费用6000、营销费1500，对应既有 `finance_contract.py` 的月度经营盈亏平衡公式：`ceil((6000+1500)/(19-4)) = 500`。250是base情景平均付费人数，不是盈亏平衡人数。

4. **摘要“base case在12个月内盈亏平衡”与冻结情景不符。** 原文 “Financial projections show break-even within 12 months at base case”。冻结brief明确12个月为标准化经营情景，非用户增长曲线。base250用户每月经营结果为 `250×(19−4)−6000−1500 = −3750 USD`，全年经营亏损45000；另计18000一次性投入，期末现金为57000。仍有现金不等于盈亏平衡，现有输入无法支持正文所述时间结论。

其余检查：价格、变动成本、固定费用、营销费、120000启动现金及low/high100/500均与brief一致；未把Khanmigo价格当成MBA支付意愿证据，也未声称产品已满足FERPA。未发现其他同等明确的事实矛盾；这不是全部语义正确或完整D通过的证明。以上错误是否被后续Critic识别、修订须另看最终产物，本审计不预判。

## 冻结证据链

- [packet.json](C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-90m-fix-v2/runtime/docs/final_sprint/s0-v1/cases/ai_education/packet.json)：声明的packet SHA256 `2d05d0f5be08ec4f89f36b6db2af77137f700938a87684c74f2f29b744af4b03`。
- [EDU-02.txt](C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-90m-fix-v2/runtime/docs/final_sprint/s0-v1/cases/ai_education/sources/EDU-02.txt:304)：实际文件SHA256 `77a5e89be05b54e137ef920e582abbf0a8f5d479f9ff785c992934df721bc56c`，与packet记录一致。
- [brief.json](C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-90m-fix-v2/runtime/docs/final_sprint/s0-v1/cases/ai_education/brief.json)：`financial_inputs`及`constraints`；case声明brief SHA256 `368668bc82bb639cfb0af64cbe0a0fb6536195f5f2a49e0069f4e1f7bac6e4a4`。
- [finance_contract.py](C:/Users/JasmineJiang/Projects/multiple_ai_agent/.slm-claim-id-fix-stage/runtime/workflow/finance_contract.py:53)：既有 `monthly_operating_result`、`annual_cash_change`、`ending_cash`、`break_even_users` 公式，仅作确定性核算依据。

未访问网络或模型，未修改任何模型产物；仅新增此抽查记录。
