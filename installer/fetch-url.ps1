# Download a vendor file and verify SHA-256. Used by the Windows build and NSIS.
# -TrustedPublisher: if the hash does not match, keep the file when Authenticode
#   is Valid and the certificate subject contains this substring (evergreen).
# -Force: re-download even when a matching local file already exists.
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [Parameter(Mandatory = $true)][string]$OutFile,
    [Parameter(Mandatory = $true)][string]$Sha256,
    [string]$TrustedPublisher = "",
    [switch]$Force
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$expected = $Sha256.Trim().ToLowerInvariant()
$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir | Out-Null
}

function Test-TrustedSignature {
    param([string]$Path, [string]$Publisher)
    if (-not $Publisher) {
        return $false
    }
    $sig = Get-AuthenticodeSignature -LiteralPath $Path
    if ($sig.Status -ne "Valid" -or -not $sig.SignerCertificate) {
        return $false
    }
    return $sig.SignerCertificate.Subject -like ("*" + $Publisher + "*")
}

function Invoke-FileDownload {
    param([string]$From, [string]$To)
    $partial = "$To.partial"
    if (Test-Path -LiteralPath $partial) {
        Remove-Item -LiteralPath $partial -Force
    }
    $curl = Join-Path $env:SystemRoot "System32\curl.exe"
    if (Test-Path -LiteralPath $curl) {
        & $curl -fL --retry 3 --retry-delay 2 --connect-timeout 30 `
            -A "AgentusNetwork-fetch" --proto "=https" --proto-redir "=https" `
            -o $partial -- $From
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
            throw "curl exited $LASTEXITCODE downloading $From"
        }
    }
    else {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $client = New-Object System.Net.WebClient
        try {
            $client.Headers["User-Agent"] = "AgentusNetwork-fetch"
            $client.DownloadFile($From, $partial)
        }
        finally {
            $client.Dispose()
        }
    }
    if (-not (Test-Path -LiteralPath $partial) -or (Get-Item -LiteralPath $partial).Length -le 0) {
        throw "download produced no data for $From"
    }
    Move-Item -LiteralPath $partial -Destination $To -Force
}

if ((-not $Force) -and (Test-Path -LiteralPath $OutFile)) {
    $have = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($have -eq $expected) {
        Write-Host "hash ok $OutFile"
        exit 0
    }
    if (Test-TrustedSignature -Path $OutFile -Publisher $TrustedPublisher) {
        Write-Host "hash updated $OutFile sha256=$have (authenticode ok)"
        exit 0
    }
    Remove-Item -LiteralPath $OutFile -Force
}

Write-Host "download $Url"
Invoke-FileDownload -From $Url -To $OutFile
$have = (Get-FileHash -LiteralPath $OutFile -Algorithm SHA256).Hash.ToLowerInvariant()
if ($have -eq $expected) {
    Write-Host "saved $OutFile"
    exit 0
}
if (Test-TrustedSignature -Path $OutFile -Publisher $TrustedPublisher) {
    Write-Host "hash updated $OutFile sha256=$have expected $expected (authenticode ok)"
    exit 0
}
Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue
throw "sha256 mismatch for ${OutFile}: got ${have} expected ${expected}"
