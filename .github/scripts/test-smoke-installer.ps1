$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Simulate installer outcomes without touching the real registry or installed app.
$global:transferCoveSmokeFixture = [pscustomobject]@{ Scenario = ''; Installed = $false; UninstallCalls = 0 }

function Test-Path {
    param([string]$LiteralPath, [string]$PathType)
    if ($LiteralPath -like 'HKCU:*') {
        return $global:transferCoveSmokeFixture.Installed -and $global:transferCoveSmokeFixture.Scenario -eq 'wrong-scope'
    }
    if ($LiteralPath -like 'HKLM:*') { return $false }
    if ($LiteralPath -like '*unins000.exe') {
        return $global:transferCoveSmokeFixture.Installed -and $global:transferCoveSmokeFixture.Scenario -ne 'missing-uninstaller'
    }
    return $false
}

function Get-Process {
    [CmdletBinding()]
    param([string]$Name)
}

function New-Item {
    param([string]$ItemType, [string]$Path, [switch]$Force)
}

function Remove-Item {
    param([string]$LiteralPath, [switch]$Recurse, [switch]$Force)
}

function Start-Process {
    param([string]$FilePath, [string[]]$ArgumentList, [switch]$PassThru, [string]$WindowStyle)
    if ($FilePath -like '*unins000.exe') {
        $global:transferCoveSmokeFixture.UninstallCalls++
        $global:transferCoveSmokeFixture.Installed = $false
    }
    else {
        $global:transferCoveSmokeFixture.Installed = $true
    }
    $process = [pscustomobject]@{ HasExited = $true; ExitCode = 0; Id = 1 }
    $process | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { param($timeout) return $true }
    return $process
}

$smokeScript = Join-Path $PSScriptRoot 'smoke-installer.ps1'
$fixtureInstaller = Join-Path $PSScriptRoot 'build-installer.ps1'
foreach ($case in @(
    @{ Name = 'missing-uninstaller'; Mode = 'CurrentUser'; Error = 'Installed uninstaller is missing'; Uninstalls = 0 },
    @{ Name = 'missing-registration'; Mode = 'CurrentUser'; Error = 'Installer did not register CurrentUser'; Uninstalls = 1 },
    @{ Name = 'wrong-scope'; Mode = 'AllUsers'; Error = 'Installer did not register AllUsers'; Uninstalls = 1 }
)) {
    $global:transferCoveSmokeFixture.Scenario = $case.Name
    $global:transferCoveSmokeFixture.Installed = $false
    $global:transferCoveSmokeFixture.UninstallCalls = 0
    $caught = $null
    try {
        & $smokeScript -InstallerPath $fixtureInstaller -InstallMode $case.Mode
    }
    catch {
        $caught = $_.Exception.Message
    }
    if ($null -eq $caught -or -not $caught.Contains($case.Error)) {
        throw "Scenario $($case.Name) expected '$($case.Error)', got '$caught'"
    }
    if ($global:transferCoveSmokeFixture.UninstallCalls -ne $case.Uninstalls) {
        throw "Scenario $($case.Name) expected $($case.Uninstalls) cleanup uninstall calls, got $($global:transferCoveSmokeFixture.UninstallCalls)"
    }
    Write-Output "Passed: $($case.Name)"
}

# Version validation must fail before any installer process is started.
foreach ($case in @(
    @{ Name = 'same-version'; Previous = '0.3.0'; Expected = '0.3.0'; Error = 'Upgrade target must be newer' },
    @{ Name = 'downgrade'; Previous = '0.3.1'; Expected = '0.3.0'; Error = 'Upgrade target must be newer' },
    @{ Name = 'missing-old-version'; Previous = ''; Expected = '0.3.0'; Error = 'A valid PreviousVersion is required' },
    @{ Name = 'same-installer'; Previous = '0.2.3'; Expected = '0.3.0'; Error = 'An upgrade must use two different installers' }
)) {
    $global:transferCoveSmokeFixture.Installed = $false
    $global:transferCoveSmokeFixture.UninstallCalls = 0
    $caught = $null
    try {
        & $smokeScript -InstallerPath $fixtureInstaller -PreviousInstallerPath $fixtureInstaller `
            -PreviousVersion $case.Previous -ExpectedVersion $case.Expected
    }
    catch { $caught = $_.Exception.Message }
    if ($null -eq $caught -or -not $caught.Contains($case.Error)) {
        throw "Scenario $($case.Name) expected '$($case.Error)', got '$caught'"
    }
    if ($global:transferCoveSmokeFixture.Installed -or $global:transferCoveSmokeFixture.UninstallCalls -ne 0) {
        throw "Scenario $($case.Name) unexpectedly ran an installer"
    }
    Write-Output "Passed: $($case.Name)"
}
