$ErrorActionPreference = 'Stop'
$researchRun = 'C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM/docs/final_sprint/s3-research-15m-v2/run_01'
$researchCalls = @{}
$researchSample = $null
foreach ($researchLine in Get-Content -LiteralPath (Join-Path $researchRun 'probe/events.jsonl')) {
    try { $researchEvent = $researchLine | ConvertFrom-Json } catch { continue }
    if ($researchEvent.kind -eq 'call') { $researchCalls[$researchEvent.payload.attempt_id] = $researchEvent.payload }
    if ($researchEvent.kind -eq 'telemetry') { $researchSample = $researchEvent.payload }
}
[pscustomobject]@{
    observed_at_utc = [datetime]::UtcNow.ToString('o')
    sample = $researchSample | Select-Object elapsed_seconds,ram_available_bytes,pagefile_delta_bytes
    calls = @($researchCalls.Values | Sort-Object started_at_utc | Select-Object generation_stage,purpose,status,elapsed_seconds,prompt_tokens,output_tokens,finish_reason,error_type)
} | ConvertTo-Json -Depth 6 -Compress
Get-Content -LiteralPath (Join-Path $researchRun 'server/server.stderr.log') -Tail 2
if (Test-Path -LiteralPath (Join-Path $researchRun 'probe/result.json')) {
    $researchResult = Get-Content -LiteralPath (Join-Path $researchRun 'probe/result.json') -Raw | ConvertFrom-Json
    $researchResult | Select-Object status,research_probe_passed,research_artifact_produced,elapsed_seconds,error_type,error,http_requests,pool_remaining | ConvertTo-Json -Depth 4
}
