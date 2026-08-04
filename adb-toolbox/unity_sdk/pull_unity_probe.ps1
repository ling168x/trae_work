$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)][string]$Serial,
    [Parameter(Mandatory = $false)][string]$RemotePath = "/sdcard/Android/data",
    [Parameter(Mandatory = $false)][string]$PackageName = "",
    [Parameter(Mandatory = $false)][string]$FileName = "unity_perf_probe.jsonl",
    [Parameter(Mandatory = $false)][string]$Output = "sessions/unity_probe.jsonl"
)

if ($PackageName -eq "") {
    throw "PackageName is required to resolve app sandbox path."
}

$deviceFile = "$RemotePath/$PackageName/files/$FileName"
Write-Host "Pulling $deviceFile ..."
adb -s $Serial pull $deviceFile $Output
Write-Host "Saved to $Output"
