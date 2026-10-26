param([switch]$Stop,[ValidateRange(1024,65535)][int]$Port=12395)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskPython=Join-Path $taskRoot '.venv/Scripts/python.exe'
$taskPidFile=Join-Path $taskRoot "private/mao-playroom-$Port.pid"
$taskRecorded=0
if(Test-Path -LiteralPath $taskPidFile){$null=[int]::TryParse((Get-Content -LiteralPath $taskPidFile -Raw).Trim(),[ref]$taskRecorded)}
$taskProcesses=@(Get-CimInstance Win32_Process)
$taskOwner=$taskProcesses | Where-Object {$_.ProcessId -eq $taskRecorded -and $_.ExecutablePath -eq $taskPython -and ($_.CommandLine -like "*-m http.server $Port --bind 127.0.0.1 --directory web_tool*" -or $_.CommandLine -like "*-u scripts/serve_mao_playroom.py --port $Port*")}
if($Stop){
 if($taskOwner){
  $taskProcesses | Where-Object {$_.ParentProcessId -eq $taskOwner.ProcessId -and ($_.CommandLine -like "*-m http.server $Port --bind 127.0.0.1 --directory web_tool*" -or $_.CommandLine -like "*-u scripts/serve_mao_playroom.py --port $Port*")} | ForEach-Object {Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue}
  Stop-Process -Id $taskOwner.ProcessId -ErrorAction SilentlyContinue
 }
 Write-Output 'Mao playroom preview stopped. AI and OBS were not started.'
 return
}
if(-not $taskOwner){
 if(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue){throw "Port $Port is occupied. Use another port."}
 $taskProcess=Start-Process -FilePath $taskPython -ArgumentList @('-u','scripts/serve_mao_playroom.py','--port',"$Port") -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRoot 'private/playroom-preview.log') -RedirectStandardError (Join-Path $taskRoot 'private/playroom-preview.err.log') -PassThru
 $taskProcess.Id | Set-Content -LiteralPath $taskPidFile
}
Write-Output "http://127.0.0.1:$Port/mao-5070/playroom.html"
Write-Output 'Playroom server ready. It does not start Qwen, TTS, PostgreSQL, OBS or a public stream.'
