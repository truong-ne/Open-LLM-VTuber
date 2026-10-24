param(
    [string]$Video = '',
    [string]$Dance = 'white-top-dance',
    [int]$Port = 12394
)
# Opens the dance editor next to a reference clip. Needs Node only; loads no AI models.
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$url = "http://127.0.0.1:$Port/mao-5070/draco/dance-editor.html?dance=$Dance"
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Output "Port $Port is already in use; reusing it. Stop that server first to change the reference video."
} else {
    $arguments = @((Join-Path $PSScriptRoot 'serve_dance_editor.mjs'), '--port', "$Port")
    if ($Video) { $arguments += @('--video', (Resolve-Path $Video).Path) }
    New-Item -ItemType Directory -Force (Join-Path $workspace 'private') | Out-Null
    Start-Process -FilePath node -ArgumentList $arguments -WorkingDirectory $workspace -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $workspace 'private/dance-editor.log') `
        -RedirectStandardError (Join-Path $workspace 'private/dance-editor.err.log') | Out-Null
    Start-Sleep -Seconds 1
}
Start-Process $url
Write-Output $url
