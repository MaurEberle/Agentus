# Download a vendor file and verify SHA-256. Used by the Windows build and NSIS.
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [Parameter(Mandatory = $true)][string]$Sha256
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$expected = $Sha256.Trim().ToLowerInvariant()
$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
}

if (Test-Path -LiteralPath $OutFile) {
    $have = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($have -eq $expected) {
        Write-Host "hash ok $OutFile"
        exit 0
    }
    Remove-Item -LiteralPath $OutFile -Force
}

Write-Host "download $Url"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$partial = "$OutFile.partial"
if (Test-Path -LiteralPath $partial) {
    Remove-Item -LiteralPath $partial -Force
}
$client = New-Object System.Net.WebClient
try {
    $client.DownloadFile($Url, $partial)
}
finally {
    $client.Dispose()
}
$have = (Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant()
if ($have -ne $expected) {
    Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
    throw "sha256 mismatch for $OutFile: got $have expected $expected"
}
Move-Item -LiteralPath $partial -Destination $OutFile -Force
Write-Host "saved $OutFile"
