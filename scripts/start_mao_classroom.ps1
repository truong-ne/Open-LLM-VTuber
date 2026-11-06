param([string]$Account='@thanhoathirty6',[switch]$ControlsOnly,[switch]$ReloadBackend)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskPython=Join-Path $taskRoot '.venv/Scripts/python.exe'
Push-Location -LiteralPath $taskRoot
try {
    if ($ReloadBackend) {
        $taskOldServerId=0
        $taskServerPidFile=Join-Path $taskRoot 'private/server.pid'
        if (Test-Path -LiteralPath $taskServerPidFile) { [int]::TryParse((Get-Content -LiteralPath $taskServerPidFile -Raw).Trim(),[ref]$taskOldServerId) | Out-Null }
        & $taskPython scripts/mao_control.py stop
        if ($LASTEXITCODE -ne 0) { throw 'Could not stop the old backend gracefully.' }
        $taskDeadline=(Get-Date).AddSeconds(30)
        while ((Get-NetTCPConnection -LocalPort 12393 -State Listen -ErrorAction SilentlyContinue) -or ($taskOldServerId -gt 0 -and (Get-Process -Id $taskOldServerId -ErrorAction SilentlyContinue))) {
            if ((Get-Date) -ge $taskDeadline) { throw 'The previous backend is still stopping. Wait for it before retrying.' }
            Start-Sleep -Seconds 1
        }
    }
    & (Join-Path $PSScriptRoot 'start_mao_desktop.ps1') -Mode window -GameOnly -Restart:$ReloadBackend
    & $taskPython scripts/mao_classroom.py status
    if ($LASTEXITCODE -ne 0) { throw 'Restart the Mao backend to load the classroom feature before opening the class.' }
    if (-not $ControlsOnly) {
        & $taskPython scripts/mao_classroom.py on --account $Account
        if ($LASTEXITCODE -ne 0) { throw 'Could not enable classroom.' }
    }
    Write-Output 'Use Vua Tieng Viet in Mao Desktop. OBS: capture the Mao VTuber application window and keep Mao Voice enabled.'
} finally { Pop-Location }
