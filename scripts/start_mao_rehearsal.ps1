param([ValidateRange(10,600)][int]$Seconds=120)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
$taskObsRoot = Join-Path $taskRoot 'private/tools/obs-33.0.0'
$taskObsExe = Join-Path $taskObsRoot 'bin/64bit/obs64.exe'
if (-not (Test-Path -LiteralPath $taskObsExe)) { throw 'Portable OBS is missing. Follow doc/mao_daily_learning_and_rehearsal.vi.md.' }
& (Join-Path $taskRoot 'private/start-local.ps1')
$taskDeadline = (Get-Date).AddSeconds(180)
do {
    try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:12393/' -TimeoutSec 2; break }
    catch { if ((Get-Date) -ge $taskDeadline) { throw 'Mao has not finished starting.' }; Start-Sleep -Seconds 2 }
} while ($true)
$taskExistingObs = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'obs64.exe' })
if ($taskExistingObs) { throw 'Close OBS before starting the isolated test, to keep other recordings untouched.' }
# Enable authenticated control only during this local test. Never print the key.
$taskObsConfig = Join-Path $taskObsRoot 'config/obs-studio/plugin_config/obs-websocket/config.json'
if (-not (Test-Path -LiteralPath $taskObsConfig)) { throw 'Private OBS configuration is missing. Follow the setup document.' }
$taskSettings = Get-Content -LiteralPath $taskObsConfig -Raw | ConvertFrom-Json
if (-not $taskSettings.auth_required -or $taskSettings.server_password.Length -lt 24) { throw 'OBS control requires a strong private password.' }
$taskSettings.server_enabled = $true
$taskSettings | ConvertTo-Json | Set-Content -LiteralPath $taskObsConfig -Encoding utf8
# Only this private portable checkout's stale run markers are disposable. No
# OBS process is running (checked above); keep crashes and logs for diagnosis.
$taskSentinel = [IO.Path]::GetFullPath((Join-Path $taskObsRoot 'config/obs-studio/.sentinel'))
if (Test-Path -LiteralPath $taskSentinel) {
    Get-ChildItem -LiteralPath $taskSentinel -File -Filter 'run_*' | ForEach-Object { Remove-Item -LiteralPath $_.FullName }
}
$taskObs = Start-Process -FilePath $taskObsExe -WorkingDirectory (Split-Path -Parent $taskObsExe) -ArgumentList @('--portable','--profile','"Mao Local Test"','--only-bundled-plugins','--disable-updater','--minimize-to-tray') -WindowStyle Hidden -PassThru
try {
    $taskDeadline = (Get-Date).AddSeconds(45)
    while (-not (Get-NetTCPConnection -LocalPort $taskSettings.server_port -State Listen -ErrorAction SilentlyContinue)) {
        if ($taskObs.HasExited -or (Get-Date) -ge $taskDeadline) { throw 'OBS control did not become ready.' }
        Start-Sleep -Seconds 1
    }
    Push-Location -LiteralPath $taskRoot
    try {
        & $taskPython scripts/mao_obs_rehearsal.py configure
        if ($LASTEXITCODE -ne 0) { throw 'Could not configure the isolated scene.' }
        & $taskPython scripts/mao_obs_rehearsal.py record --seconds $Seconds
        if ($LASTEXITCODE -ne 0) { throw 'Local recording failed; inspect the OBS log.' }
    } finally { Pop-Location }
} finally {
    # This process was created here. Do not stop any other OBS instance.
    if (-not $taskObs.HasExited) {
        $null = $taskObs.CloseMainWindow()
        if (-not $taskObs.WaitForExit(10000)) {
            # StopRecord has already finalized our file, or setup failed before
            # recording. This is the private process created above.
            Stop-Process -Id $taskObs.Id -ErrorAction SilentlyContinue
            $taskObs.WaitForExit()
        }
    }
    if ($taskObs.HasExited) {
        $taskSettings.server_enabled = $false
        $taskSettings | ConvertTo-Json | Set-Content -LiteralPath $taskObsConfig -Encoding utf8
    }
}
Write-Output 'Local rehearsal finished. No public broadcast was started. Recordings: private/rehearsals.'
