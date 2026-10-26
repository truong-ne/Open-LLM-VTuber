param()
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskObsRoot=Join-Path $taskRoot 'private/tools/obs-33.0.0'
$taskObsExe=Join-Path $taskObsRoot 'bin/64bit/obs64.exe'
$taskConfig=Join-Path $taskObsRoot 'config/obs-studio/plugin_config/obs-websocket/config.json'
$taskPython=Join-Path $taskRoot '.venv/Scripts/python.exe'
if(-not (Test-Path -LiteralPath $taskObsExe) -or -not (Test-Path -LiteralPath $taskConfig)){throw 'Set up the private OBS portable installation first. See doc/mao_daily_learning_and_rehearsal.vi.md.'}
$taskSettings=Get-Content -LiteralPath $taskConfig -Raw | ConvertFrom-Json
if(-not $taskSettings.auth_required -or $taskSettings.server_password.Length -lt 24){throw 'Private OBS control requires authentication.'}
$taskExisting=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'obs64.exe'})
if($taskExisting.Count -gt 1 -or ($taskExisting.Count -eq 1 -and $taskExisting[0].ExecutablePath -ne $taskObsExe)){throw 'Another OBS installation is running. Close it before configuring this private scene.'}
if($taskExisting.Count -eq 0){
 $taskSettings.server_enabled=$true
 $taskSettings | ConvertTo-Json | Set-Content -LiteralPath $taskConfig -Encoding utf8
 $taskSentinel=Join-Path $taskObsRoot 'config/obs-studio/.sentinel'
 if(Test-Path -LiteralPath $taskSentinel){
  Add-Type -AssemblyName Microsoft.VisualBasic
  Get-ChildItem -LiteralPath $taskSentinel -File -Filter 'run_*' | ForEach-Object {[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($_.FullName,'OnlyErrorDialogs','SendToRecycleBin')}
 }
 $taskProcess=Start-Process -FilePath $taskObsExe -WorkingDirectory (Split-Path -Parent $taskObsExe) -ArgumentList @('--portable','--profile','"Mao Local Test"','--only-bundled-plugins','--disable-updater','--minimize-to-tray') -WindowStyle Hidden -PassThru
 $taskProcess.Id | Set-Content -LiteralPath (Join-Path $taskRoot 'private/mao-playroom-obs.pid')
}
$taskDeadline=(Get-Date).AddSeconds(45)
while(-not (Get-NetTCPConnection -LocalPort $taskSettings.server_port -State Listen -ErrorAction SilentlyContinue)){
 if((Get-Date) -ge $taskDeadline){throw 'Private OBS is not ready.'}
 Start-Sleep -Seconds 1
}
Push-Location -LiteralPath $taskRoot
try{
 & $taskPython scripts/mao_playroom_obs.py configure
 if($LASTEXITCODE -ne 0){throw 'Open the dedicated game Chrome first, then retry. No stream was started.'}
}finally{Pop-Location}
Write-Output 'Private game scene ready. No stream or recording started.'
