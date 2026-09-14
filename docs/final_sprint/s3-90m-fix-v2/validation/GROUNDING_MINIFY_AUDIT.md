# Saved grounding JSON formatting audit

This is a read-only offline comparison of the first Research grounding response from `s3-90m-fix-v1/run_01`. No model was called, and the historical response remains unchanged.

| Metric | Original response | Equivalent compact JSON |
|---|---:|---:|
| Characters | 23,877 | 19,530 |
| Saved official tokenizer, no special tokens | 6,000 | 4,801 |

The service separately reported **6,055 generated tokens**, with 1026.200 seconds decoding (5.900 tokens/second). Offline re-encoding gives 6,000; the 55-token difference is **unattributed**. It is not assumed to be EOS or special tokens.

Removing only JSON formatting whitespace reduces offline tokens by **1,199 (19.98%)**. All JSON values, 17 claim occurrences, metadata, references and strings remain equal. Duplicate raw object keys are rejected before comparison. The original response still failed claim-identity validation; this experiment does not repair it.

At the first request's unchanged decode rate, this reduction would correspond to approximately **203.2 seconds**. This is a hypothetical projection, not measured savings or proof of a complete D plan within 90 minutes.

Source response, usage, event-log and tokenizer/provenance paths and SHA-256 values, exact source event IDs, metric definitions and the full reproduction command are in [grounding_minify_audit.json](grounding_minify_audit.json). The script refuses to overwrite its audit outputs; reproduce into a fresh directory:

```powershell
& 'C:\Users\JasmineJiang\Projects\multiple-ai-agent_SLM_LLM\.venv\Scripts\python.exe' -B 'C:\Users\JasmineJiang\Projects\multiple_ai_agent\.slm-claim-id-fix-stage\validation\audit_grounding_minify.py' --repo 'C:\Users\JasmineJiang\Projects\multiple-ai-agent_SLM_LLM' --output '<fresh-audit-directory>'
```
