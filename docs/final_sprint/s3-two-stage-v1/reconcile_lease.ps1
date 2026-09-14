$ErrorActionPreference = 'Stop'
$repoRoot = [IO.Path]::GetFullPath('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')
$reportRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'docs/final_sprint/s3-two-stage-v1'))
$leasePath = [IO.Path]::GetFullPath((Join-Path $repoRoot 'data/granite_endpoint_leases/2fb24565ac96fa6667ae7aac126b1d1c01bd9ec999315b419e6010a19e5d9461.lease.json'))
$auditRoot = [IO.Path]::GetFullPath((Join-Path $reportRoot 'run_01/audit'))
$archivePath = [IO.Path]::GetFullPath((Join-Path $auditRoot 'terminated_unknown_request.lease.json'))
if (-not $leasePath.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar) -or -not $archivePath.StartsWith($reportRoot + [IO.Path]::DirectorySeparatorChar)) { throw 'Path escaped the named repository/report' }
$modelProcesses = @(Get-CimInstance Win32_Process -Filter "Name LIKE '%ollama%'" -ErrorAction Stop)
$listeners = @(Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue)
if ($modelProcesses.Count -ne 0 -or $listeners.Count -ne 0) { throw 'Model termination/idle not confirmed; keep lease quarantined' }
$lease = Get-Content -LiteralPath $leasePath -Raw | ConvertFrom-Json
if ($lease.run_id -ne '0ede28ad-20e9-4ef2-834d-02cbb6212b7f' -or $lease.attempt_id -ne '05c2b631-e57d-4cc4-8e11-d6266b67f39e') { throw 'Lease is not this interrupted request' }
if (Test-Path -LiteralPath $archivePath) { throw 'Archive already exists; preserve it' }
$beforeHash = (Get-FileHash -LiteralPath $leasePath -Algorithm SHA256).Hash.ToLowerInvariant()
New-Item -ItemType Directory -Path $auditRoot -Force | Out-Null
Move-Item -LiteralPath $leasePath -Destination $archivePath
if ((Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $beforeHash) { throw 'Lease archive hash mismatch' }
$pagefile = @(Get-CimInstance Win32_PageFileUsage -ErrorAction Stop)
$proof = [ordered]@{
    observed_at_utc = [DateTime]::UtcNow.ToString('o')
    model_process_count = $modelProcesses.Count
    port_11434_listener_count = $listeners.Count
    active_lease_count = @(Get-ChildItem -LiteralPath (Split-Path -Parent $leasePath) -Filter '*.lease.json' -File).Count
    archived_lease = $archivePath
    archived_lease_sha256 = $beforeHash
    request_outcome = 'cancelled; provider token usage unavailable; original full reservation retained'
    reconciliation = 'Verified no model process or endpoint listener; archived only the matching run/attempt lease without changing request outcome or retrying'
    post_stop_pagefile_query_succeeded = $true
    post_stop_pagefile_current_usage_mib = ($pagefile | Measure-Object -Property CurrentUsage -Sum).Sum
}
$proof | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $auditRoot 'external_cleanup.json') -Encoding utf8
$proof | ConvertTo-Json -Depth 5
