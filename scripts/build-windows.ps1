# Build Agentus Network Windows artifacts: freeze, NSIS setup, portable zip.
# Version is read from backend/pyproject.toml unless -Version is passed.
[CmdletBinding()]
param(
    [string]$Version,
    [switch]$SkipFrontend,
    [switch]$SkipNsis
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $RepoRoot "backend"
$Frontend = Join-Path $RepoRoot "frontend"
$Installer = Join-Path $RepoRoot "installer"
$Packaging = Join-Path $RepoRoot "packaging"
$Dist = Join-Path $RepoRoot "dist"
$Vendor = Join-Path $Installer "vendor"
$LockPath = Join-Path $Installer "vendor.lock.json"
$FetchUrl = Join-Path $Installer "fetch-url.ps1"
$Spec = Join-Path $Packaging "agentus_network.spec"
$Nsi = Join-Path $Installer "Agentus-Network.nsi"
$Toml = Join-Path $Backend "pyproject.toml"

function Test-PowerShellSyntax {
    param([Parameter(Mandatory = $true)][string]$Path)
    $tokens = $null
    $errors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
    if ($errors -and $errors.Count -gt 0) {
        throw "PowerShell parse error in ${Path}: $($errors[0])"
    }
}

function Read-ProjectVersion {
    $text = Get-Content -LiteralPath $Toml -Raw -Encoding UTF8
    $match = [regex]::Match($text, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $match.Success) {
        throw "version not found in $Toml"
    }
    return $match.Groups[1].Value
}

function Get-VersionQuad([string]$ver) {
    $parts = @($ver.Split("."))
    while ($parts.Count -lt 4) {
        $parts += "0"
    }
    return ($parts[0..3] -join ".")
}

function Get-PythonExe {
    $venv = Join-Path $Backend ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv) {
        return $venv
    }
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    throw "Python 3.12 not found. Create backend\.venv or install Python."
}

function Invoke-Python {
    param([Parameter(Mandatory = $true)][string[]]$PyArgs)
    $exe = Get-PythonExe
    $prefix = @()
    if ($exe -like "*\py.exe" -or (Split-Path -Leaf $exe) -eq "py.exe") {
        $prefix = @("-3.12")
    }
    & $exe @prefix @PyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "python exited $LASTEXITCODE : $($PyArgs -join ' ')"
    }
}

function Get-HttpUserAgent {
    return "AgentusNetwork-build"
}

function Invoke-HttpJson {
    param([Parameter(Mandatory = $true)][string]$Uri)
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $headers = @{
        "User-Agent" = Get-HttpUserAgent
        "Accept"     = "application/json"
    }
    return Invoke-RestMethod -Uri $Uri -Headers $headers
}

function Invoke-HttpDownload {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$OutFile,
        [int]$MinBytes = 65536
    )
    $dir = Split-Path -Parent $OutFile
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    $partial = "$OutFile.partial"
    if (Test-Path -LiteralPath $partial) {
        Remove-Item -LiteralPath $partial -Force
    }
    $curl = Join-Path $env:SystemRoot "System32\curl.exe"
    if (-not (Test-Path -LiteralPath $curl)) {
        throw "curl.exe not found under System32; cannot download $Url"
    }
    Write-Host "download $Url"
    & $curl -fL --retry 3 --retry-delay 2 --connect-timeout 30 `
        -A (Get-HttpUserAgent) -o $partial -- $Url
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
        throw "curl exited $LASTEXITCODE downloading $Url"
    }
    if (-not (Test-Path -LiteralPath $partial) -or (Get-Item -LiteralPath $partial).Length -lt $MinBytes) {
        $len = 0
        if (Test-Path -LiteralPath $partial) {
            $len = (Get-Item -LiteralPath $partial).Length
        }
        Remove-Item -LiteralPath $partial -Force -ErrorAction SilentlyContinue
        throw "download too small ($len bytes, min $MinBytes) from $Url"
    }
    Move-Item -LiteralPath $partial -Destination $OutFile -Force
}

function Find-CachedMakensis {
    $root = Join-Path $RepoRoot "build\nsis"
    if (-not (Test-Path -LiteralPath $root)) {
        return $null
    }
    $found = @(Get-ChildItem -Path $root -Filter makensis.exe -Recurse -ErrorAction SilentlyContinue |
            Sort-Object { $_.Directory.Name } -Descending)
    if ($found.Count -gt 0) {
        return $found[0].FullName
    }
    return $null
}

function Find-SystemMakensis {
    $cmd = Get-Command makensis -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }
    foreach ($candidate in @(
            "$env:LOCALAPPDATA\Programs\NSIS\makensis.exe",
            "${env:ProgramFiles(x86)}\NSIS\makensis.exe",
            "${env:ProgramFiles}\NSIS\makensis.exe"
        )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Get-LatestNsisRelease {
    $best = Invoke-HttpJson -Uri "https://sourceforge.net/projects/nsis/best_release.json"
    $filename = [string]$best.platform_releases.windows.filename
    $match = [regex]::Match($filename, 'nsis-(\d+\.\d+(?:\.\d+)?)')
    if (-not $match.Success) {
        throw "could not parse NSIS version from ${filename}"
    }
    $ver = $match.Groups[1].Value
    $zipName = "nsis-${ver}.zip"
    return [pscustomobject]@{
        Version = $ver
        ZipName = $zipName
        ZipUrl  = "https://sourceforge.net/projects/nsis/files/NSIS%203/${ver}/${zipName}/download"
    }
}

function Install-NsisPortable {
    param($Release)
    $root = Join-Path $RepoRoot "build\nsis"
    $dest = Join-Path $root "nsis-$($Release.Version)"
    $makensis = Join-Path $dest "makensis.exe"
    if (Test-Path -LiteralPath $makensis) {
        return $makensis
    }
    $zip = Join-Path $root $Release.ZipName
    $zipUrls = @(
        $Release.ZipUrl,
        "https://downloads.sourceforge.net/project/nsis/NSIS%203/$($Release.Version)/$($Release.ZipName)"
    )
    $isZip = {
        param($Path)
        if (-not (Test-Path -LiteralPath $Path)) { return $false }
        $head = [System.IO.File]::ReadAllBytes($Path)
        return ($head.Length -ge 64KB -and $head[0] -eq 0x50 -and $head[1] -eq 0x4B)
    }
    if (-not (& $isZip $zip)) {
        $saved = $false
        foreach ($zipUrl in $zipUrls) {
            try {
                Invoke-HttpDownload -Url $zipUrl -OutFile $zip
                if (& $isZip $zip) {
                    $saved = $true
                    break
                }
            }
            catch {
                Write-Warning $_.Exception.Message
            }
        }
        if (-not $saved) {
            throw "could not download portable NSIS zip $($Release.ZipName) (no admin setup.exe)"
        }
    }
    $stage = Join-Path $root ("extract-" + $Release.Version)
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $stage -Force
    $extracted = Get-ChildItem -Path $stage -Filter makensis.exe -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $extracted) {
        throw "makensis.exe missing inside $($Release.ZipName)"
    }
    $extractedRoot = $extracted.Directory.FullName
    if (Test-Path -LiteralPath $dest) {
        Remove-Item -LiteralPath $dest -Recurse -Force
    }
    Move-Item -LiteralPath $extractedRoot -Destination $dest
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
    if (-not (Test-Path -LiteralPath $makensis)) {
        throw "portable NSIS extract failed: $makensis"
    }
    Write-Host "nsis $($Release.Version) portable (no admin): $makensis"
    return $makensis
}

function Ensure-Makensis {
    $release = $null
    try {
        $release = Get-LatestNsisRelease
        Write-Host "nsis latest $($release.Version)"
    }
    catch {
        Write-Warning "Could not query latest NSIS release: $($_.Exception.Message)"
    }
    if ($release) {
        try {
            return Install-NsisPortable -Release $release
        }
        catch {
            Write-Warning "Portable NSIS $($release.Version) download failed (setup.exe is not used; it needs admin): $($_.Exception.Message)"
        }
    }
    $cached = Find-CachedMakensis
    if ($cached) {
        Write-Warning "using cached portable makensis $cached"
        return $cached
    }
    $system = Find-SystemMakensis
    if ($system) {
        Write-Warning "using existing makensis $system"
        return $system
    }
    throw "makensis not found. Portable NSIS zip download failed and no local copy exists. Re-run with network access (no admin required), or pass -SkipNsis."
}

function Get-OllamaSetupFromGitHubApi {
    $rel = Invoke-HttpJson -Uri "https://api.github.com/repos/ollama/ollama/releases/latest"
    $asset = @($rel.assets) | Where-Object { $_.name -eq "OllamaSetup.exe" } | Select-Object -First 1
    if (-not $asset) {
        throw "OllamaSetup.exe missing from $($rel.tag_name)"
    }
    $digest = [string]$asset.digest
    $digestMatch = [regex]::Match($digest, '^sha256:([0-9a-fA-F]{64})$')
    if (-not $digestMatch.Success) {
        throw "OllamaSetup.exe has no sha256 digest in $($rel.tag_name)"
    }
    return [pscustomobject]@{
        Tag    = [string]$rel.tag_name
        Url    = [string]$asset.browser_download_url
        Sha256 = $digestMatch.Groups[1].Value.ToLowerInvariant()
    }
}

function Get-OllamaSetupFromLatestRedirect {
    $curl = Join-Path $env:SystemRoot "System32\curl.exe"
    if (-not (Test-Path -LiteralPath $curl)) {
        throw "curl.exe not found; cannot resolve Ollama latest without GitHub API"
    }
    $effective = & $curl -fsSL -o NUL -w "%{url_effective}" -A (Get-HttpUserAgent) `
        --proto "=https" --proto-redir "=https" -- "https://github.com/ollama/ollama/releases/latest"
    if ($LASTEXITCODE -ne 0) {
        throw "curl exited $LASTEXITCODE resolving Ollama latest"
    }
    $tagMatch = [regex]::Match([string]$effective, '/releases/tag/(v[\d.]+)')
    if (-not $tagMatch.Success) {
        throw "could not parse Ollama tag from $effective"
    }
    $tag = $tagMatch.Groups[1].Value
    $sumsUrl = "https://github.com/ollama/ollama/releases/download/${tag}/sha256sum.txt"
    $sumsFile = Join-Path $env:TEMP "ollama-sha256sum-$tag.txt"
    Invoke-HttpDownload -Url $sumsUrl -OutFile $sumsFile -MinBytes 32
    $line = Get-Content -LiteralPath $sumsFile | Where-Object { $_ -match 'OllamaSetup\.exe\s*$' } | Select-Object -First 1
    $hashMatch = [regex]::Match([string]$line, '^([0-9a-fA-F]{64})\s')
    if (-not $hashMatch.Success) {
        throw "OllamaSetup.exe hash missing in sha256sum.txt for $tag"
    }
    return [pscustomobject]@{
        Tag    = $tag
        Url    = "https://github.com/ollama/ollama/releases/download/${tag}/OllamaSetup.exe"
        Sha256 = $hashMatch.Groups[1].Value.ToLowerInvariant()
    }
}

function Update-OllamaLockFromGitHub {
    param($Lock)
    $resolved = $null
    try {
        $resolved = Get-OllamaSetupFromGitHubApi
    }
    catch {
        Write-Warning "GitHub API latest Ollama failed: $($_.Exception.Message)"
        try {
            $resolved = Get-OllamaSetupFromLatestRedirect
        }
        catch {
            Write-Warning "Could not resolve latest Ollama release; using vendor.lock.json. $($_.Exception.Message)"
            return
        }
    }
    $Lock.ollama_setup.url = $resolved.Url
    $Lock.ollama_setup.sha256 = $resolved.Sha256
    Write-Host "ollama latest $($resolved.Tag) sha256=$($resolved.Sha256)"
}

function Write-GeneratedVersionNsh {
    param([string]$Ver, [string]$Quad, $Lock)
    $wv = $Lock.webview2_bootstrapper
    $ol = $Lock.ollama_setup
    $content = @"
; Generated by scripts/build-windows.ps1 - do not hand-edit
!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "$Ver"
!endif
!ifndef PRODUCT_VERSION_QUAD
  !define PRODUCT_VERSION_QUAD "$Quad"
!endif
!define WEBVIEW2_NAME "$($wv.name)"
!define WEBVIEW2_URL "$($wv.url)"
!define WEBVIEW2_SHA256 "$($wv.sha256)"
!define OLLAMA_NAME "$($ol.name)"
!define OLLAMA_URL "$($ol.url)"
!define OLLAMA_SHA256 "$($ol.sha256)"
"@
    $path = Join-Path $Installer "generated-version.nsh"
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($path, $content.TrimStart() + "`n", $utf8)
    Write-Host "wrote $path"
}

function Ensure-VendorFile {
    param(
        $Entry,
        [string]$DestDir,
        [string]$TrustedPublisher = "",
        [switch]$ForceLatest
    )
    $out = Join-Path $DestDir $Entry.name
    $fetchArgs = @{
        Url     = $Entry.url
        OutFile = $out
        Sha256  = $Entry.sha256
    }
    if ($TrustedPublisher) {
        $fetchArgs.TrustedPublisher = $TrustedPublisher
    }
    if ($ForceLatest) {
        $fetchArgs.Force = $true
    }
    & $FetchUrl @fetchArgs
    if ($LASTEXITCODE -ne 0) {
        throw "vendor fetch failed for $($Entry.name)"
    }
    $have = (Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($have -ne $Entry.sha256.Trim().ToLowerInvariant()) {
        Write-Host "vendor $($Entry.name) sha256 now $have"
        $Entry.sha256 = $have
    }
}

function Test-FreezeSmoke {
    $exe = Join-Path $Dist "AgentusNetwork\AgentusNetwork.exe"
    if (-not (Test-Path -LiteralPath $exe)) {
        throw "freeze missing $exe"
    }
    $indexCandidates = @(
        (Join-Path $Dist "AgentusNetwork\_internal\frontend\dist\index.html"),
        (Join-Path $Dist "AgentusNetwork\frontend\dist\index.html")
    )
    $index = $indexCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $index) {
        throw "freeze missing frontend/dist/index.html under onedir"
    }
    $help = @(
        (Join-Path $Dist "AgentusNetwork\_internal\help_docs\de\00-user-guide.md"),
        (Join-Path $Dist "AgentusNetwork\help_docs\de\00-user-guide.md")
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $help) {
        throw "freeze missing help_docs"
    }
    Write-Host "freeze smoke ok: $exe"
    Write-Host "spa: $index"
}

function New-PortableZip {
    param([string]$Ver)
    $onedir = Join-Path $Dist "AgentusNetwork"
    $stageRoot = Join-Path $Dist "portable"
    $stage = Join-Path $stageRoot "AgentusNetwork"
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stage | Out-Null
    Copy-Item -Path (Join-Path $onedir "*") -Destination $stage -Recurse -Force
    $marker = Join-Path $stage "portable.txt"
    Set-Content -LiteralPath $marker -Value "portable`n" -Encoding ascii
    if (Test-Path -LiteralPath (Join-Path $onedir "portable.txt")) {
        throw "portable.txt must not live in the NSIS onedir payload"
    }
    $zip = Join-Path $Dist "Agentus-Network-Portable-$Ver-x64.zip"
    if (Test-Path -LiteralPath $zip) {
        Remove-Item -LiteralPath $zip -Force
    }
    $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if ($tar) {
        Push-Location $stageRoot
        try {
            & $tar.Source -a -c -f $zip "AgentusNetwork"
            if ($LASTEXITCODE -ne 0) {
                throw "tar exited $LASTEXITCODE creating $zip"
            }
        }
        finally {
            Pop-Location
        }
    }
    else {
        Compress-Archive -Path $stage -DestinationPath $zip -Force
    }
    Write-Host "portable zip: $zip"
}

function Invoke-SignIfConfigured {
    param([string[]]$Files)
    $cert = $env:AGENTUS_NETWORK_SIGN_CERT
    if (-not $cert) {
        Write-Warning "No AGENTUS_NETWORK_SIGN_CERT; skipping signtool (v1)."
        return
    }
    $signtool = Get-Command signtool -ErrorAction SilentlyContinue
    if (-not $signtool) {
        Write-Warning "signtool not on PATH; skipping signing."
        return
    }
    foreach ($file in $Files) {
        if (-not (Test-Path -LiteralPath $file)) { continue }
        & $signtool.Source sign /fd SHA256 /a /f $cert $file
        if ($LASTEXITCODE -ne 0) {
            throw "signtool failed for $file"
        }
    }
}

Test-PowerShellSyntax -Path $FetchUrl
Test-PowerShellSyntax -Path $PSCommandPath

if (-not $Version) {
    $Version = Read-ProjectVersion
}
$VersionQuad = Get-VersionQuad $Version
Write-Host "version $Version ($VersionQuad)"

if (-not (Test-Path -LiteralPath $LockPath)) {
    throw "missing $LockPath"
}
$Lock = Get-Content -LiteralPath $LockPath -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($key in @("webview2_bootstrapper", "ollama_setup")) {
    $entry = $Lock.$key
    if (-not $entry -or -not $entry.name -or -not $entry.url -or -not $entry.sha256) {
        throw "vendor.lock.json missing $key name/url/sha256"
    }
}

if (-not $SkipNsis) {
    Update-OllamaLockFromGitHub -Lock $Lock
}
Write-GeneratedVersionNsh -Ver $Version -Quad $VersionQuad -Lock $Lock

if (-not $SkipFrontend) {
    Push-Location $Frontend
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $Frontend "node_modules"))) {
            Write-Host "npm ci"
            npm ci
            if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
        }
        Write-Host "npm run build"
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    }
    finally {
        Pop-Location
    }
}

$indexHtml = Join-Path $Frontend "dist\index.html"
if (-not (Test-Path -LiteralPath $indexHtml)) {
    throw "frontend/dist/index.html missing; run without -SkipFrontend"
}

Write-Host "pip install -e .[packaging]"
Push-Location $Backend
try {
    Invoke-Python -PyArgs @("-m", "pip", "install", "-e", ".[packaging]")
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $Dist)) {
    New-Item -ItemType Directory -Path $Dist | Out-Null
}

Write-Host "pyinstaller $Spec"
$pyiLog = Join-Path $RepoRoot "build\pyinstaller.log"
$pyiErr = Join-Path $RepoRoot "build\pyinstaller.err.log"
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "build"))) {
    New-Item -ItemType Directory -Path (Join-Path $RepoRoot "build") | Out-Null
}
$pyExe = Get-PythonExe
$pyPrefix = @()
if ($pyExe -like "*\py.exe" -or (Split-Path -Leaf $pyExe) -eq "py.exe") {
    $pyPrefix = @("-3.12")
}
$pyiArgs = $pyPrefix + @(
    "-m", "PyInstaller", $Spec,
    "--noconfirm", "--clean",
    "--log-level", "WARN",
    "--distpath", $Dist,
    "--workpath", (Join-Path $RepoRoot "build")
)
Push-Location $RepoRoot
try {
    $proc = Start-Process -FilePath $pyExe -ArgumentList $pyiArgs -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput $pyiLog -RedirectStandardError $pyiErr
    if ($proc.ExitCode -ne 0) {
        Write-Host (Get-Content -LiteralPath $pyiErr -Raw -ErrorAction SilentlyContinue)
        Write-Host (Get-Content -LiteralPath $pyiLog -Tail 40 -ErrorAction SilentlyContinue)
        throw "pyinstaller exited $($proc.ExitCode); see $pyiLog"
    }
}
finally {
    Pop-Location
}

Test-FreezeSmoke
New-PortableZip -Ver $Version

$setup = Join-Path $Dist "Agentus-Network-Setup-$Version-x64.exe"
$exe = Join-Path $Dist "AgentusNetwork\AgentusNetwork.exe"

if (-not $SkipNsis) {
    if (-not (Test-Path -LiteralPath $Vendor)) {
        New-Item -ItemType Directory -Path $Vendor | Out-Null
    }
    Ensure-VendorFile -Entry $Lock.webview2_bootstrapper -DestDir $Vendor `
        -TrustedPublisher "CN=Microsoft Corporation" -ForceLatest
    Write-GeneratedVersionNsh -Ver $Version -Quad $VersionQuad -Lock $Lock
    $makensis = Ensure-Makensis
    if (-not $makensis) {
        throw "makensis not found. Portable NSIS zip download failed and no local copy exists. Re-run with network access (no admin required), or pass -SkipNsis."
    }
    Write-Host "makensis $makensis"
    & $makensis "/DPRODUCT_VERSION=$Version" "/DPRODUCT_VERSION_QUAD=$VersionQuad" "/INPUTCHARSET" "UTF8" $Nsi
    if ($LASTEXITCODE -ne 0) {
        throw "makensis exited $LASTEXITCODE"
    }
    if (-not (Test-Path -LiteralPath $setup)) {
        throw "setup exe missing $setup"
    }
    $minBytes = 8MB
    $size = (Get-Item -LiteralPath $setup).Length
    if ($size -lt $minBytes) {
        throw "setup exe too small ($size bytes); payload missing?"
    }
    Write-Host "setup: $setup ($size bytes)"
}

$signFiles = @($exe)
if (Test-Path -LiteralPath $setup) { $signFiles += $setup }
Invoke-SignIfConfigured -Files $signFiles

Write-Host "done version=$Version"
Write-Host "freeze $exe"
Write-Host "portable $(Join-Path $Dist "Agentus-Network-Portable-$Version-x64.zip")"
if (Test-Path -LiteralPath $setup) {
    Write-Host "setup $setup"
}
