param(
    [ValidatePattern('^real_best_effort_ai_education_0[1-9]$')]
    [string]$RunName = 'real_best_effort_ai_education_01'
)

$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$runRoot = Join-Path $PSScriptRoot $RunName
$serverRoot = Join-Path $runRoot 'server'
$demoRoot = Join-Path $runRoot 'demo'
$ownerPath = Join-Path $serverRoot 'server_owner.json'
$configPath = Join-Path $repo 'slm\configs\granite_best_effort_demo_v1.json'
$authorizationPath = Join-Path $PSScriptRoot 'BEST_EFFORT_DEMO_AUTHORIZATION.json'
$priorDPath = Join-Path $PSScriptRoot 'D_PREFLIGHT_ATTEMPT_03.json'
$leasesPath = Join-Path $repo 'data\granite_endpoint_leases'
$exitCode = 2

if (Test-Path -LiteralPath $runRoot) {
    throw 'Fresh best-effort demo directory already exists; never overwrite or implicitly resume it.'
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $configPath).Hash.ToLowerInvariant() -ne
        'dc689a7ddf8fcf58f625468fb126abf3bb2d5349a93532bd62aa85ee81815340') {
    throw 'Authorized best-effort demo config hash changed.'
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $priorDPath).Hash.ToLowerInvariant() -ne
        '951480b3c5d35988c24c7e8ee7918d16db6392bfa1dfa32768273eebcadc7f2f') {
    throw 'Required preserved D no-go record changed.'
}
$authorization = Get-Content -LiteralPath $authorizationPath -Raw | ConvertFrom-Json
if (-not $authorization.approved -or $authorization.mode -ne 'slm_best_effort_demo' -or
        $authorization.formal_eligible -or $authorization.hard_limits.run_seconds -ne 1800 -or
        $authorization.hard_limits.max_physical_requests -ne 10 -or
        $authorization.hard_limits.max_total_tokens -ne 80000 -or
        $authorization.scope.gpu_layers -ne 0 -or $authorization.scope.paid_services) {
    throw 'Best-effort demo authorization is missing or differs from the approved non-formal hard limits.'
}
$priorD = Get-Content -LiteralPath $priorDPath -Raw | ConvertFrom-Json
if ($priorD.status -ne 'no_go' -or $priorD.downstream_gate.formal_s5_started -or
        $priorD.cumulative_actual.requests -ne 10 -or
        $priorD.cumulative_actual.charged_total_tokens -ne 30817) {
    throw 'Preserved D result is not the exact non-formal engineering no-go prerequisite.'
}
try {
    $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    throw 'Port 11434 is occupied; do not start an overlapping demo.'
} catch {
    if ($_.Exception.Message -like 'Port 11434*') { throw }
}
if (Test-Path -LiteralPath $leasesPath) {
    if (@(Get-ChildItem -LiteralPath $leasesPath -Filter '*.lease.json' -File).Count -gt 0) {
        throw 'An active endpoint lease exists; do not start another request.'
    }
}

New-Item -ItemType Directory -Path $runRoot | Out-Null
try {
    & (Join-Path $repo 'slm\start_granite.ps1') -OutputDirectory $serverRoot
    & (Join-Path $repo '.venv\Scripts\python.exe') -B -m slm.best_effort_demo `
        --case ai_education `
        --config $configPath `
        --output-dir $demoRoot `
        --server-owner $ownerPath
    $exitCode = $LASTEXITCODE
} finally {
    if (Test-Path -LiteralPath $ownerPath) {
        $owner = Get-Content -LiteralPath $ownerPath -Raw | ConvertFrom-Json
        $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$owner.pid)
        if ($null -ne $process) {
            $createdUtc = $process.CreationDate.ToUniversalTime()
            $recordedUtc = [DateTime]::Parse($owner.started_at_utc).ToUniversalTime()
            $sameCreation = [Math]::Abs(($createdUtc - $recordedUtc).TotalSeconds) -le 10
            $sameImage = [IO.Path]::GetFullPath($process.ExecutablePath) -eq
                [IO.Path]::GetFullPath('C:\Users\JasmineJiang\AppData\Local\Programs\Ollama\ollama.exe')
            $sameCommand = $process.CommandLine -match 'ollama\.exe"?\s+serve'
            $foreignListener = Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue |
                Where-Object { $_.OwningProcess -ne [int]$owner.pid }
            if (-not ($sameCreation -and $sameImage -and $sameCommand) -or $null -ne $foreignListener) {
                throw 'Cleanup refused: live process does not exactly match this fresh project-owned server.'
            }
            Stop-Process -Id ([int]$owner.pid) -Force
            Wait-Process -Id ([int]$owner.pid) -Timeout 20 -ErrorAction SilentlyContinue
            if (Get-Process -Id ([int]$owner.pid) -ErrorAction SilentlyContinue) {
                throw 'Project-owned Ollama process termination is unconfirmed.'
            }
        }
    }
}

exit $exitCode
