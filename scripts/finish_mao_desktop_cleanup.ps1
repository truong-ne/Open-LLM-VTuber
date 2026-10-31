param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$cleanupRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd('\')
$cleanupPrefix = $cleanupRoot + '\'
$cleanupTargets = [Collections.Generic.List[string]]::new()
foreach ($relative in @(
    'private/tools/vtuber-desktop/resources/app.asar.original',
    'private/tools/vtuber-desktop-unpacked/out/main/index.js.before-draco',
    'private/tools/vtuber-desktop-unpacked/out/renderer/assets/index-CW5qlpM1.js',
    'private/tools/vtuber-desktop-unpacked/out/renderer/assets/index-DBAmt0B7.css',
    'private/tools/vtuber-desktop-unpacked/out/renderer/draco-shell.html',
    'private/tools/vtuber-desktop-unpacked/out/renderer/libs/live2d.min.js',
    'private/tools/vtuber-desktop-unpacked/out/renderer/libs/live2dcubismcore.js',
    'private/tools/vtuber-desktop-unpacked/out/renderer/libs/live2dcubismcore.min.js'
)) { $cleanupTargets.Add((Join-Path $cleanupRoot $relative)) }
$dependencyRoot = Join-Path $cleanupRoot 'private/tools/vtuber-desktop-unpacked/node_modules'
Get-ChildItem -LiteralPath $dependencyRoot -Force | Where-Object Name -ne '@electron-toolkit' |
    ForEach-Object { $cleanupTargets.Add($_.FullName) }
$cleanupPlan = foreach ($target in $cleanupTargets) {
    $absolute = [IO.Path]::GetFullPath($target)
    if (-not $absolute.StartsWith($cleanupPrefix, [StringComparison]::OrdinalIgnoreCase)) { throw "Target outside workspace: $absolute" }
    if (-not (Test-Path -LiteralPath $absolute)) { continue }
    $item = Get-Item -LiteralPath $absolute -Force
    $ancestor = $item
    while ($ancestor.FullName -ne $cleanupRoot) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing link: $($ancestor.FullName)" }
        $ancestor = if ($ancestor -is [IO.DirectoryInfo]) { $ancestor.Parent } else { $ancestor.Directory }
        if ($null -eq $ancestor) { throw "Cannot verify ancestry: $absolute" }
    }
    $entries = if ($item.PSIsContainer) { @(Get-ChildItem -LiteralPath $absolute -Recurse -Force) } else { @($item) }
    if ($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw "Target contains links: $absolute" }
    $files = @($entries | Where-Object { -not $_.PSIsContainer })
    [pscustomobject]@{path=$absolute; bytes=[long](($files | Measure-Object Length -Sum).Sum); files=$files.Count}
}
$cleanupPlan | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $cleanupRoot 'logs/mao-desktop-pending-cleanup.json') -Encoding utf8
$cleanupPlan | Measure-Object bytes -Sum | Select-Object Count,Sum
if ($Apply) {
    $cleanupFailures = @()
    foreach ($entry in $cleanupPlan) {
        try { Remove-Item -LiteralPath $entry.path -Recurse -Force -ErrorAction Stop }
        catch { $cleanupFailures += [pscustomobject]@{path=$entry.path; reason=$_.Exception.Message} }
    }
    $cleanupRemaining = @($cleanupPlan | Where-Object { Test-Path -LiteralPath $_.path })
    $cleanupRemaining | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $cleanupRoot 'logs/mao-desktop-pending-cleanup.json') -Encoding utf8
    $cleanupFailures | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $cleanupRoot 'logs/mao-desktop-cleanup-failures.json') -Encoding utf8
    @($cleanupRemaining | ForEach-Object { $_.path }) | Set-Content -LiteralPath (Join-Path $cleanupRoot 'logs/mao-desktop-manual-delete.txt') -Encoding utf8
    [pscustomobject]@{removedTargets=@($cleanupPlan).Count-$cleanupRemaining.Count; remainingTargets=$cleanupRemaining.Count} | ConvertTo-Json
} else { Write-Output 'Preview only. Run with -Apply to delete the listed obsolete desktop files.' }
