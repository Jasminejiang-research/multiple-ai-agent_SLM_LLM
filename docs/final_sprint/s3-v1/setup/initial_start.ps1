$ErrorActionPreference = 'Stop'
$s3Root = [IO.Path]::GetFullPath($PSScriptRoot)
$s3Logs = Join-Path $s3Root 'docs/final_sprint/s3-v1/setup'
New-Item -ItemType Directory -Path $s3Logs -Force | Out-Null
try {
    $existing = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
    throw 'An Ollama endpoint is already running; inspect ownership/config before starting another.'
} catch {
    if ($_.Exception.Message -like 'An Ollama*') { throw }
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_CONTEXT_LENGTH = '32768'
$env:OLLAMA_KEEP_ALIVE = '5m'
$s3Process = Start-Process -FilePath 'C:/Users/JasmineJiang/AppData/Local/Programs/Ollama/ollama.exe' -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $s3Logs 'server.stdout.log') -RedirectStandardError (Join-Path $s3Logs 'server.stderr.log')
[pscustomobject]@{pid=$s3Process.Id; started_at_utc=[DateTime]::UtcNow.ToString('o'); endpoint='http://127.0.0.1:11434'; num_parallel=1; max_loaded_models=1; context_length=32768; generation_calls=0} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $s3Logs 'server_owner.json') -Encoding utf8
Write-Output ('Started S3-owned Ollama server pid=' + $s3Process.Id)
