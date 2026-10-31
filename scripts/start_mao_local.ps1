param(
    [ValidateSet('local_dev', 'test', 'local_companion')]
    [string]$Profile = 'local_companion',
    [switch]$Doctor,
    [switch]$NoDashboard
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $taskRoot
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create the project .venv first.' }
$env:PYTHONUTF8 = '1'
$env:MAO_RUNTIME_PROFILE=$Profile
$env:HF_HOME = Join-Path $taskRoot 'models'
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'
$env:OLLAMA_MODELS = Join-Path $taskRoot 'models/ollama'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$taskFfmpeg = Join-Path $taskRoot 'private/tools/ffmpeg/ffmpeg-master-latest-win64-lgpl-shared/bin'
if (Test-Path -LiteralPath $taskFfmpeg) { $env:PATH = $taskFfmpeg + ';' + $env:PATH }
if ($Doctor) {
    & $taskPython scripts/mao_doctor.py --profile $Profile
} else {
    $taskPort = if ($Profile -eq 'test') { 12394 } else { 12393 }
    if (Get-NetTCPConnection -LocalPort $taskPort -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $taskPort is already in use. Stop the existing server before starting another."
    }
    if (-not (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue)) {
        $taskOllama = Join-Path $taskRoot 'private/tools/ollama/ollama.exe'
        if (-not (Test-Path -LiteralPath $taskOllama)) { throw 'Start the configured Ollama provider first.' }
        New-Item -ItemType Directory -Path (Join-Path $taskRoot 'logs') -Force | Out-Null
        $taskProvider = Start-Process -FilePath $taskOllama -ArgumentList 'serve' -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput 'logs/ollama.stdout.log' -RedirectStandardError 'logs/ollama.stderr.log' -PassThru
        $taskProvider.Id | Set-Content -LiteralPath (Join-Path $taskRoot 'private/ollama.pid')
        $taskReady = $false
        for ($taskAttempt = 0; $taskAttempt -lt 20; $taskAttempt++) {
            if (Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue) { $taskReady = $true; break }
            if ($taskProvider.HasExited) { throw 'Ollama exited during startup; see logs/ollama.stderr.log.' }
            Start-Sleep -Milliseconds 250
        }
        if (-not $taskReady) { throw 'Ollama did not open port 11434; see logs/ollama.stderr.log.' }
    }
    if (-not $NoDashboard) {
        $taskDashboardPort=if($Profile -eq 'test'){12396}else{12395}
        if (-not (Get-NetTCPConnection -LocalPort $taskDashboardPort -State Listen -ErrorAction SilentlyContinue)) {
            $taskDashboardScript=Join-Path $taskRoot 'scripts/serve_mao_playroom.py'
            Start-Process -FilePath $taskPython -ArgumentList '-u', ('"{0}"' -f $taskDashboardScript), '--port', $taskDashboardPort -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput "logs/dashboard-$Profile.stdout.log" -RedirectStandardError "logs/dashboard-$Profile.stderr.log" | Out-Null
        }
        Write-Host "Dashboard: http://127.0.0.1:$taskDashboardPort/mao-5070/runtime.html"
    }
    # Foreground process: Ctrl+C stops this server. No live/idle adapters are started.
    & $taskPython -u run_server.py --profile $Profile
}
exit $LASTEXITCODE
