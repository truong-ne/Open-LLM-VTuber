param([switch]$Restart)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
& (Join-Path $taskRoot 'private/start-local.ps1')
$taskPython = [IO.Path]::GetFullPath((Join-Path $taskRoot '.venv/Scripts/python.exe'))
$taskPlatform = & $taskPython -c "import sys,yaml; from pathlib import Path; print(yaml.safe_load(Path(sys.argv[1]).read_text(encoding='utf-8')).get('live_config',{}).get('active_platform','local'))" (Join-Path $taskRoot 'conf.yaml')
if ($LASTEXITCODE -ne 0 -or $taskPlatform -notin @('youtube','tiktok','local')) { throw 'Invalid default live chat platform.' }
$taskScripts = @{youtube='scripts/run_youtube_live.py';tiktok='scripts/run_tiktok_live.py';local='scripts/run_local_host.py'}
$taskScript = $taskScripts[$taskPlatform]
$taskProcesses = @(Get-CimInstance Win32_Process)
$taskReaders = @($taskProcesses | Where-Object {
    $_.ExecutablePath -eq $taskPython -and ($_.CommandLine -like '*scripts/run_tiktok_live.py*' -or $_.CommandLine -like '*scripts/run_youtube_live.py*' -or $_.CommandLine -like '*scripts/run_local_host.py*')
})
$taskMatching = @($taskReaders | Where-Object { $_.CommandLine -like ('*' + $taskScript + '*') })
if ($taskMatching -and -not $Restart -and $taskReaders.Count -eq 1) {
    Write-Output "Mao $taskPlatform reader and proactive host are already running."
    return
}
foreach ($taskReader in $taskReaders) {
    $taskProcesses | Where-Object { $_.ParentProcessId -eq $taskReader.ProcessId -and $_.Name -eq 'python.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    Stop-Process -Id $taskReader.ProcessId -ErrorAction SilentlyContinue
}
$env:PYTHONUTF8 = '1'
$taskLabel = if ($taskPlatform -eq 'local') { 'local-host' } else { $taskPlatform }
$taskReader = Start-Process -FilePath $taskPython -ArgumentList @('-u',$taskScript) -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskRoot "logs/$taskLabel.stdout.log") -RedirectStandardError (Join-Path $taskRoot "logs/$taskLabel.stderr.log") -PassThru
$taskReader.Id | Set-Content -LiteralPath (Join-Path $taskRoot "private/$taskLabel.pid")
Write-Output "Mao $taskPlatform reader and proactive host started."
