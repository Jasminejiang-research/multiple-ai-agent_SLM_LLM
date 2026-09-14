# Reviewable next run: AI education, Granite, complete D

Status: **pending user confirmation of a new independent validation allowance**. The code repair itself is authorized and can be installed without this confirmation.

- One fresh non-formal complete-D run, using the original AI-education frozen inputs and the same Granite H Micro Q4_K_M CPU model/digest/Ollama 0.33.2.
- 5400 seconds for this SLM plan, including its Research, Strategy, Finance, Writer, Critics, conditional revisions and structural repairs. Any LLM run has its own clock; this launcher makes zero Gemini calls.
- At most 8192 tokens per response, 36 requests, and 500,000 total charged tokens. Unknown requests retain their reservation. No automatic restart after failure or deadline.
- The old aggregate allowance has only 4206.517 seconds remaining. A fresh 5400-second allowance would be additional to the preserved historical 16 requests / 296,569 charged tokens / 10,193.483 seconds. No previous consumption is erased or refunded.
- Keep the laptop connected to AC with the lid open. The run makes scoped System/Execution power requests; manual sleep and Windows battery policies can still suspend it. A long telemetry gap stops validation instead of certifying unobserved time.
- Full 13-section/financial/grounding/lineage validation remains mandatory. Success, partial artifact, resource stop, deadline and cleanup failure are reported separately. Ninety-minute success is not guaranteed before the real run.

After confirmation, record the exact user approval in `authorization.json`, keep the old authorization and result hash, then execute:

```powershell
& 'C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-90m-fix-v2/Invoke-RecoveryTrial.ps1' -SharedRepo 'C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM'
```

The unique `run_01` directory must not already exist. The launcher checks the frozen source and authorization before starting the owned server. It does not run formal S5 rows. A–D's formal shared budget and freeze remain a separate outstanding decision.
