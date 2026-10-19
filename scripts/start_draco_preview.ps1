$ErrorActionPreference = 'Stop'
$taskWorkspace = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskWorkspace '.venv/Scripts/python.exe'
$taskUrl = 'http://127.0.0.1:12394/mao-5070/draco/'
$taskListening = Get-NetTCPConnection -LocalPort 12394 -State Listen -ErrorAction SilentlyContinue
if ($taskListening) {
    $taskPage = Invoke-WebRequest -Uri $taskUrl -TimeoutSec 5
    if ($taskPage.Content -notmatch 'Draco') { throw 'Port 12394 is used by another service.' }
} else {
    Start-Process -FilePath $taskPython -ArgumentList @('-m','http.server','12394','--bind','127.0.0.1','--directory','web_tool') -WorkingDirectory $taskWorkspace -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskWorkspace 'private/draco-preview-http.log') -RedirectStandardError (Join-Path $taskWorkspace 'private/draco-preview-http.err.log') | Out-Null
}
Write-Output $taskUrl
