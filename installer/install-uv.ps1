param(
    [string]$Zip,
    [Parameter(Mandatory = $true)][string]$Dest,
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

function Set-UserPath([string]$Directory, [bool]$Present) {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    $items = @()
    if ($current) {
        $items = @($current -split ";" | Where-Object { $_ -and $_.Trim() })
    }
    $norm = $Directory.TrimEnd("\")
    $kept = @($items | Where-Object { $_.TrimEnd("\") -ne $norm })
    if ($Present) {
        $next = @($norm) + $kept
    } else {
        $next = $kept
    }
    [Environment]::SetEnvironmentVariable("Path", ($next -join ";"), "User")
}

if ($Remove) {
    Set-UserPath $Dest $false
    exit 0
}

if (-not $Zip -or -not (Test-Path -LiteralPath $Zip)) {
    throw "uv zip missing"
}

$stage = Join-Path $env:TEMP ("agentus-uv-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    Expand-Archive -LiteralPath $Zip -DestinationPath $stage -Force
    $uvx = Get-ChildItem -LiteralPath $stage -Filter "uvx.exe" -Recurse | Select-Object -First 1
    $uv = Get-ChildItem -LiteralPath $stage -Filter "uv.exe" -Recurse | Select-Object -First 1
    if (-not $uvx) {
        throw "uvx.exe missing in archive"
    }
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    Copy-Item -LiteralPath $uvx.FullName -Destination (Join-Path $Dest "uvx.exe") -Force
    if ($uv) {
        Copy-Item -LiteralPath $uv.FullName -Destination (Join-Path $Dest "uv.exe") -Force
    }
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}

Set-UserPath $Dest $true
exit 0
