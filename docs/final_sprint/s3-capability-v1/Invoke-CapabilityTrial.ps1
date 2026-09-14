param(
    [Parameter(Mandatory=$true)][string]$SharedRepo,
    [string]$RunName = 'run_01',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
if ($RunName -notmatch '^run_[0-9]+$') { throw 'RunName must be run_<number>.' }
$repo = (Resolve-Path -LiteralPath $SharedRepo).Path
$runtime = Join-Path $PSScriptRoot 'runtime'
$python = Join-Path $repo '.venv/Scripts/python.exe'
$runRoot = Join-Path $PSScriptRoot $RunName
$owner = Join-Path $runRoot 'server/server_owner.json'
if (Test-Path -LiteralPath $runRoot) { throw 'Use a new run name; existing evidence must be preserved.' }
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime_manifest.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $candidate = Join-Path $runtime $entry.path
    if ((Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw ('Snapshot hash mismatch: ' + $entry.path)
    }
}
$trialArgs = @('-B', '-m', 'slm.capability_trial',
    '--config', (Join-Path $PSScriptRoot 'trial_config.json'),
    '--authorization', (Join-Path $PSScriptRoot 'authorization.json'),
    '--shared-repo', $repo, '--output-dir', (Join-Path $runRoot 'probe'),
    '--server-owner', $owner,
    '--tokenizer', (Join-Path $repo 'docs/final_sprint/s3-v1/setup/tokenizer.json'),
    '--tokenizer-provenance', (Join-Path $repo 'docs/final_sprint/s3-v1/setup/tokenizer_provenance.json'))
Push-Location -LiteralPath $runtime
try {
    & $python @trialArgs --check-only
    if ($LASTEXITCODE -ne 0) { throw 'Trial authorization/config check failed; model service was not started.' }
    if ($CheckOnly) { return }
    New-Item -ItemType Directory -Path $runRoot | Out-Null
    & (Join-Path $repo 'slm/start_granite.ps1') -OutputDirectory (Join-Path $runRoot 'server')
    & $python @trialArgs *> (Join-Path $runRoot 'console.log')
    $trialExit = $LASTEXITCODE
    Write-Output ('Trial exit code: ' + $trialExit + '; result: ' + (Join-Path $runRoot 'probe/result.json'))
} finally {
    if (Test-Path -LiteralPath $owner) {
        $ownerRecord = Get-Content -LiteralPath $owner -Raw | ConvertFrom-Json
        $ownedProcess = Get-CimInstance Win32_Process -Filter ('ProcessId = ' + [int]$ownerRecord.pid)
        if ($null -ne $ownedProcess) {
            # The existing ownership helper verifies executable, command and creation time before stopping it.
            & $python -B (Join-Path $PSScriptRoot 'cleanup_owned.py') $owner (Join-Path $runRoot 'launcher_cleanup')
        }
    }
    Pop-Location
}
if ($null -ne $trialExit) { exit $trialExit }
