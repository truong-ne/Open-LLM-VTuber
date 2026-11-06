param([ValidateSet('mao','manual')][string]$Mode='mao')
$ErrorActionPreference='Stop'
$wesnothWorkspace = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $wesnothWorkspace
if ($Mode -eq 'mao' -and -not (Get-NetTCPConnection -LocalPort 12393 -State Listen -ErrorAction SilentlyContinue)) {
    throw 'Mao is not running. Open Mao Desktop first, then run this script again.'
}
& (Join-Path $wesnothWorkspace '.venv/Scripts/python.exe') (Join-Path $wesnothWorkspace 'scripts/mao_wesnoth.py') run --mode $Mode
exit $LASTEXITCODE
