param([Parameter(Mandatory=$true)][string]$SharedRepo, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $SharedRepo).Path
$python = Join-Path $repo '.venv/Scripts/python.exe'
$runRoot = Join-Path $PSScriptRoot 'run_01'
if (Test-Path -LiteralPath $runRoot) { throw 'Trial directory already exists; preserve its evidence.' }
$helperManifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'helper_manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $helperManifest.files) {
    if ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $entry.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw ('Trial helper mismatch: ' + $entry.path)
    }
}
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime_manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    if ((Get-FileHash -LiteralPath (Join-Path (Join-Path $PSScriptRoot 'runtime') $entry.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw ('Frozen trial source mismatch: ' + $entry.path)
    }
}
$owner = Join-Path $runRoot 'server/server_owner.json'
$runnerArgs = @('-B', (Join-Path $PSScriptRoot 'research_runner.py'), '--shared-repo', $repo, '--output', (Join-Path $runRoot 'probe'), '--server-owner', $owner)
& $python @runnerArgs --check-only
if ($LASTEXITCODE -ne 0) { throw 'Authorization/carryover validation failed before model startup.' }
if ($CheckOnly) { return }
New-Item -ItemType Directory -Path $runRoot | Out-Null
try {
    & (Join-Path $repo 'slm/start_granite.ps1') -OutputDirectory (Join-Path $runRoot 'server')
    & $python @runnerArgs *> (Join-Path $runRoot 'console.log')
    $trialExit = $LASTEXITCODE
    Write-Output ('Recovery trial exit code: ' + $trialExit + '; result: ' + (Join-Path $runRoot 'probe/result.json'))
} finally {
    if (Test-Path -LiteralPath $owner) {
        $ownership = Get-Content -LiteralPath $owner -Raw | ConvertFrom-Json
        $ownedProcess = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$ownership.pid)
        if ($null -ne $ownedProcess) {
            & $python -B (Join-Path $PSScriptRoot 'cleanup_owned.py') $owner (Join-Path $runRoot 'launcher_cleanup')
        }
    }
}
if ($null -ne $trialExit) { exit $trialExit }
