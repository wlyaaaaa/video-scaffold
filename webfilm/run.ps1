#Requires -Version 7.0
[CmdletBinding()]
param([Parameter(Position=0,ValueFromRemainingArguments=$true)][string[]]$TaskArgs)
$ErrorActionPreference = 'Stop'
$lineRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $lineRoot
$machinePath = if ($env:WEBFILM_MACHINE) { $env:WEBFILM_MACHINE } else { Join-Path $repoRoot '.video-machine.json' }
$machine = if (Test-Path -LiteralPath $machinePath) { Get-Content -Raw -LiteralPath $machinePath | ConvertFrom-Json } else { $null }
$pythonCommand = $env:WEBFILM_PYTHON
if (-not $pythonCommand) { $pythonCommand = $env:VIDEO_PYTHON }
$pythonPrefix = @()
if (-not $pythonCommand -and (Test-Path -LiteralPath (Join-Path $repoRoot '.venv\Scripts\python.exe'))) {
    $pythonCommand = Join-Path $repoRoot '.venv\Scripts\python.exe'
}
if (-not $pythonCommand -and $machine.python_path) { $pythonCommand = $machine.python_path }
if (-not $pythonCommand) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $pythonCommand = (Get-Command py).Source; $pythonPrefix = @('-3.11') }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { $pythonCommand = (Get-Command python).Source }
    else { throw 'Python 3.11+ is required.' }
}
if (-not $TaskArgs) { $TaskArgs = @('doctor') }
Push-Location $repoRoot
try {
    & $pythonCommand @pythonPrefix -X utf8 -B -m webfilm @TaskArgs
    exit $LASTEXITCODE
}
finally { Pop-Location }
