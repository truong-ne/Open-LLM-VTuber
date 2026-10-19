param([switch]$Restart,[ValidateSet('pet','window')][string]$Mode='pet')
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $taskRoot 'private/start-local.ps1')
$taskDeadline = (Get-Date).AddSeconds(150)
do {
    try { $taskResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:12393/' -TimeoutSec 3; break } catch {
        if ((Get-Date) -gt $taskDeadline) { throw 'Mao backend did not finish initialization. Check logs/server.stderr.log.' }
        Start-Sleep -Seconds 2
    }
} while ($true)
$taskExe = [IO.Path]::GetFullPath((Join-Path $taskRoot 'private/tools/vtuber-desktop/open-llm-vtuber-electron.exe'))
$taskClients = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $taskExe })
$taskDraco = @($taskClients | Where-Object { $_.CommandLine -like '*--mao-draco-local*' })
if ($Restart -or -not $taskDraco) {
    if ($taskClients) {
        Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*scripts/run_local_host.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        & (Join-Path $taskRoot '.venv/Scripts/python.exe') (Join-Path $taskRoot 'scripts/prepare_desktop_restart.py')
        if ($LASTEXITCODE -ne 0) { throw 'Current conversation has not released; desktop was kept running.' }
    }
    $taskClients | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    $taskNode = (Get-Command node -ErrorAction Stop).Source
    & $taskNode (Join-Path $taskRoot 'scripts/configure_draco_desktop.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the Draco desktop profile.' }
    $env:MAO_DESKTOP_MODEL = 'draco'
    $env:MAO_DESKTOP_START_MODE = $Mode
    $env:MAO_WORKSPACE = $taskRoot
    $taskDesktop = Start-Process -FilePath $taskExe -ArgumentList @('--mao-draco-local','--autoplay-policy=no-user-gesture-required') -WorkingDirectory (Split-Path -Parent $taskExe) -PassThru
    $taskDesktop.Id | Set-Content -LiteralPath (Join-Path $taskRoot 'private/draco-desktop.pid')
}
& (Join-Path $taskRoot 'scripts/start_mao_live.ps1')
Write-Output 'Mao Draco desktop started. Voice: Linh Lan Ch (RVC). Configured live chat reader enabled.'
