param(
    [string]$InstallerName,
    [guid]$AppId = 'A6F4C3F3-2DA6-4AF4-9E2F-7C0A0200BEEF',
    [string]$CompilerPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not (Test-Path -LiteralPath $CompilerPath -PathType Leaf)) {
    throw "Inno Setup compiler not found: $CompilerPath"
}

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $projectRoot
try {
    $version = & poetry version --short
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read the project version' }
    $version = $version.Trim()
    if ($version -notmatch '^\d+\.\d+\.\d+$') { throw "Invalid build version: $version" }
    if (-not $InstallerName) { $InstallerName = "TransferCove-Setup-$version" }
    if ($InstallerName -notmatch '^[A-Za-z0-9._-]+$') { throw 'Invalid installer filename' }

    $appIdValue = '{' + $AppId.ToString().ToUpperInvariant() + '}'
    & $CompilerPath '/Qp' "/DMyAppVersion=$version" "/DInstallerName=$InstallerName" "/DMyAppId=`"$appIdValue`"" 'installer/windows/TransferCove.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed' }

    $installerPath = Join-Path $projectRoot "dist/installer/$InstallerName.exe"
    if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
        throw "Installer was not generated: $installerPath"
    }
    Write-Output "Installer: $installerPath"
    if ($env:GITHUB_OUTPUT) {
        "installer-path=$installerPath" | Out-File -FilePath $env:GITHUB_OUTPUT -Encoding utf8 -Append
    }
}
finally {
    Pop-Location
}
