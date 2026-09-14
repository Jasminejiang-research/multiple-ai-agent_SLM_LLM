param(
    [ValidatePattern('^real_preflight_d_ai_education_0[2-9]$')]
    [string]$RunName = 'real_preflight_d_ai_education_02'
)

$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$runRoot = Join-Path $PSScriptRoot $RunName
$serverRoot = Join-Path $runRoot 'server'
$probeRoot = Join-Path $runRoot 'probe'
$ownerPath = Join-Path $serverRoot 'server_owner.json'
$configPath = Join-Path $repo 'slm\configs\granite_preflight_compact_s6.json'
$proposalPath = Join-Path $PSScriptRoot 'D_PREFLIGHT_PROPOSAL.json'
$authorizationPath = Join-Path $PSScriptRoot 'D_PREFLIGHT_AUTHORIZATION.json'
$tokenizerPath = Join-Path $repo 'docs\final_sprint\s3-v1\setup\tokenizer.json'
$tokenizerProvenancePath = Join-Path $repo 'docs\final_sprint\s3-v1\setup\tokenizer_provenance.json'
$leasesPath = Join-Path $repo 'data\granite_endpoint_leases'
$exitCode = 2

if (Test-Path -LiteralPath $runRoot) {
    throw 'Fresh D preflight directory already exists; never overwrite or resume it implicitly.'
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $configPath).Hash.ToLowerInvariant() -ne 'a42df429b55b1ff989b44b6e2abd242000782493c86f2287e729c48f72724d4f') {
    throw 'Authorized Granite compact config hash changed.'
}
if ((Get-FileHash -Algorithm SHA256 -LiteralPath $proposalPath).Hash.ToLowerInvariant() -ne 'fa08cd572dc04ce758ad0ebcb492d39384383d0cfef9a605674247dac1a31c42') {
    throw 'Authorized D proposal hash changed.'
}
$authorization = Get-Content -LiteralPath $authorizationPath -Raw | ConvertFrom-Json
if (-not $authorization.approved) {
    throw 'D preflight authorization is not approved.'
}
$priorResultPath = Join-Path $PSScriptRoot 'real_preflight_d_ai_education_01\probe\result.json'
if (-not (Test-Path -LiteralPath $priorResultPath)) {
    throw 'The preserved zero-call setup failure is required before this retry.'
}
$priorResult = Get-Content -LiteralPath $priorResultPath -Raw | ConvertFrom-Json
if ($priorResult.model_calls -ne 0 -or $priorResult.phases.warmup.budget.request_count -ne 0 -or
        $priorResult.phases.warmup.budget.charged_total_tokens -ne 0) {
    throw 'Retry refused: the prior attempt consumed model-call budget.'
}
try {
    $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    throw 'Port 11434 is occupied; do not start an overlapping preflight.'
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
    & (Join-Path $repo '.venv\Scripts\python.exe') -B -m slm.granite_preflight `
        --phase all `
        --case ai_education `
        --config $configPath `
        --output-dir $probeRoot `
        --server-owner $ownerPath `
        --tokenizer $tokenizerPath `
        --tokenizer-provenance $tokenizerProvenancePath
    $exitCode = $LASTEXITCODE
} finally {
    if (Test-Path -LiteralPath $ownerPath) {
        $owner = Get-Content -LiteralPath $ownerPath -Raw | ConvertFrom-Json
        $process = Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$owner.pid)
        if ($null -ne $process) {
            $createdUtc = $process.CreationDate.ToUniversalTime()
            $recordedUtc = [DateTime]::Parse($owner.started_at_utc).ToUniversalTime()
            $sameCreation = [Math]::Abs(($createdUtc - $recordedUtc).TotalSeconds) -le 10
            $sameImage = [IO.Path]::GetFullPath($process.ExecutablePath) -eq [IO.Path]::GetFullPath('C:\Users\JasmineJiang\AppData\Local\Programs\Ollama\ollama.exe')
            $sameCommand = $process.CommandLine -match 'ollama\.exe"?\s+serve'
            $foreignListener = Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -ne [int]$owner.pid }
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
