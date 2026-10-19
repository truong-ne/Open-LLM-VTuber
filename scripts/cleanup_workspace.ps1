param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$cleanupRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot)).TrimEnd([IO.Path]::DirectorySeparatorChar)
$cleanupPrefix = $cleanupRoot + [IO.Path]::DirectorySeparatorChar
$cleanupCutoff = [DateTime]::UtcNow.AddHours(-1)
$cleanupCandidates = [Collections.Generic.List[string]]::new()

function Add-CleanupCandidate([string]$RelativePath) {
    $candidate = [IO.Path]::GetFullPath((Join-Path $cleanupRoot $RelativePath))
    if (-not $candidate.StartsWith($cleanupPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Cleanup target escapes workspace: $candidate"
    }
    if (Test-Path -LiteralPath $candidate) { $cleanupCandidates.Add($candidate) }
}

# Only disposable downloads/inspection scripts from the model migration.
foreach ($relative in @(
    'private/tools/rvc-inspect',
    'private/check_mao_llm_upgrade.py',
    'private/verify_mao_qwen_production.py',
    'private/check_linh_lan_voice.py',
    'private/check_linh_lan_websocket.py',
    'cache/linh_lan_baseline.wav'
)) { Add-CleanupCandidate $relative }

$voiceDir = Join-Path $cleanupRoot 'models/rvc/linh_lan_ch'
$voiceModel = Join-Path $voiceDir 'LinhLan.pth'
$voiceIndex = Join-Path $voiceDir 'added_IVF51_Flat_nprobe_1_LinhLan_v2.index'
if ((Test-Path -LiteralPath $voiceModel) -and (Test-Path -LiteralPath $voiceIndex)) {
    if ((Get-FileHash -LiteralPath $voiceModel).Hash -eq '527EB3D01F4E2DE96ADE20757DFA721335F33BF0DB5FC90472EAFEF727843C73' -and
        (Get-FileHash -LiteralPath $voiceIndex).Hash -eq '5DACB8C9F9FA0E5785571D348F1DCB3C41E103A61F2CCB3EF26184AEF4B5C5BF') {
        Add-CleanupCandidate 'models/rvc/linh_lan_ch/LinhLanChan.zip'
    }
}

# Live audio and the three shared Linh Lan samples stay available.
Get-ChildItem -LiteralPath (Join-Path $cleanupRoot 'cache') -File | Where-Object {
    $_.Name -match '^\d{8}_\d{6}_[a-f0-9]{8}\.wav$' -and $_.LastWriteTimeUtc -lt $cleanupCutoff
} | ForEach-Object { Add-CleanupCandidate ('cache/' + $_.Name) }

Get-ChildItem -LiteralPath (Join-Path $cleanupRoot 'logs') -File | Where-Object {
    $_.Name -match '^debug_(\d{4}-\d{2}-\d{2})' -and
    [DateTime]::ParseExact($Matches[1], 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture).Date -lt [DateTime]::Today -and
    $_.LastWriteTimeUtc -lt $cleanupCutoff
} | ForEach-Object { Add-CleanupCandidate ('logs/' + $_.Name) }

$cleanupBytes = 0L
$cleanupFiles = 0
$cleanupReport = @()
foreach ($candidate in ($cleanupCandidates | Sort-Object -Unique)) {
    # Reject junctions/symlinks, including any ancestor or descendant of a directory.
    $item = Get-Item -LiteralPath $candidate -Force
    $ancestor = $item
    while ($ancestor.FullName -ne $cleanupRoot) {
        if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Refusing reparse point: $($ancestor.FullName)" }
        $ancestor = if ($ancestor -is [IO.DirectoryInfo]) { $ancestor.Parent } else { $ancestor.Directory }
        if ($null -eq $ancestor) { throw "Cannot verify cleanup ancestry: $candidate" }
    }
    $entries = if ($item.PSIsContainer) { @(Get-ChildItem -LiteralPath $candidate -Recurse -Force) } else { @($item) }
    if ($entries | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint }) { throw "Refusing directory with reparse points: $candidate" }
    $files = @($entries | Where-Object { -not $_.PSIsContainer })
    $bytes = [long](($files | Measure-Object -Property Length -Sum).Sum)
    if ($Apply) { Remove-Item -LiteralPath $candidate -Recurse -Force }
    $cleanupBytes += $bytes
    $cleanupFiles += $files.Count
    $cleanupReport += [pscustomobject]@{ path=$candidate.Substring($cleanupPrefix.Length); bytes=$bytes; files=$files.Count }
}
$summary = [pscustomobject]@{
    applied=[bool]$Apply; files=$cleanupFiles; bytes=$cleanupBytes
    mib=[Math]::Round($cleanupBytes / 1MB, 2); targets=$cleanupReport
}
if ($Apply) {
    $summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $cleanupRoot 'logs/workspace-cleanup.json') -Encoding utf8
}
$summary | Select-Object applied,files,bytes,mib | ConvertTo-Json -Compress
