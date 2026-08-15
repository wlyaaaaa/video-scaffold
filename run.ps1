#Requires -Version 7.0
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        'doctor', 'doctor-live', 'test', 'demo',
        'tts', 'timing', 'prompts', 'build', 'lint', 'preview',
        'render', 'merge', 'cover', 'chapters', 'verify', 'cleanup',
        'module', 'script', 'python'
    )]
    [string] $Task = 'doctor',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]] $TaskArgs
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

$pythonCommand = $null
$pythonPrefix = @()
if (Test-Path -LiteralPath $venvPython) {
    $pythonCommand = $venvPython
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command py).Source
    $pythonPrefix = @('-3.11')
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = (Get-Command python).Source
}
else {
    throw 'Python 3.11+ was not found. Install a supported native Python runtime first.'
}

$workflowTasks = @(
    'tts', 'timing', 'prompts', 'build', 'lint', 'preview',
    'render', 'merge', 'cover', 'chapters', 'verify', 'cleanup'
)
if ($Task -in $workflowTasks) {
    $arguments = @('-m', 'pipeline.workflow', $Task) + $TaskArgs
}
else {
    $arguments = switch ($Task) {
        'doctor'      { @('-m', 'pipeline.doctor') + $TaskArgs; break }
        'doctor-live' { @('-m', 'pipeline.doctor', '--live-fish') + $TaskArgs; break }
        'test'        { @('-m', 'unittest', 'discover', '-s', 'tests', '-v') + $TaskArgs; break }
        'demo'        { @('run_demo.py') + $TaskArgs; break }
        'module'      {
            if (-not $TaskArgs) { throw 'module requires a module name, for example: module pipeline.fish_tts' }
            @('-m') + $TaskArgs
            break
        }
        'script'      {
            if (-not $TaskArgs) { throw 'script requires a script path.' }
            $TaskArgs
            break
        }
        'python'      { $TaskArgs; break }
    }
}

Push-Location $projectRoot
try {
    & $pythonCommand @pythonPrefix @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
