param(
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$OllamaPath = 'C:/Users/JasmineJiang/AppData/Local/Programs/Ollama/ollama.exe'
)
$ErrorActionPreference = 'Stop'
$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $outputRoot) { throw 'Use a fresh setup directory; existing ownership/logs must be preserved.' }
try {
    $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    throw 'An Ollama endpoint is already running; inspect ownership/config before starting another.'
} catch {
    if ($_.Exception.Message -like 'An Ollama*') { throw }
}
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$leases = Join-Path $repoRoot 'data/granite_endpoint_leases'
if (Test-Path -LiteralPath $leases) {
    if (@(Get-ChildItem -LiteralPath $leases -Filter '*.lease.json' -File).Count -gt 0) {
        throw 'A previous request is quarantined; confirm termination and explicitly archive/reconcile its lease first.'
    }
}
New-Item -ItemType Directory -Path $outputRoot | Out-Null
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '32768'
$env:OLLAMA_KEEP_ALIVE = '5m'
$env:OLLAMA_NOPRUNE = 'true'
$env:OLLAMA_NO_CLOUD = 'true'
$process = Start-Process -FilePath $OllamaPath -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $outputRoot 'server.stdout.log') -RedirectStandardError (Join-Path $outputRoot 'server.stderr.log')
[pscustomobject]@{pid=$process.Id; started_at_utc=[DateTime]::UtcNow.ToString('o'); endpoint='http://127.0.0.1:11434'; num_parallel=1; max_loaded_models=1; context_length=32768; generation_calls=0} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputRoot 'server_owner.json') -Encoding utf8
Write-Output ('Started S3-owned Ollama server pid=' + $process.Id + '; metadata: ' + $outputRoot)
$ready = $false
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    if ($process.HasExited) { throw 'Owned Ollama server exited during startup; preserve logs and inspect.' }
    try {
        $version = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 1
        $ready = $true
        break
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) { throw 'Owned Ollama endpoint did not become ready; preserve ownership metadata for cleanup.' }
