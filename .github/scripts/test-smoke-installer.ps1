$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Simulate installer outcomes without touching the real registry or installed app.
$global:transferCoveSmokeFixture = [pscustomobject]@{ Scenario = ''; Installed = $false; UninstallCalls = 0 }

function Test-Path {
    param([string]$LiteralPath, [string]$PathType)
    if ($global:transferCoveSmokeFixture.Scenario -eq 'empty-console' -and $LiteralPath -like '*console.log') {
        return $true
    }
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
    param([string]$FilePath, [string[]]$ArgumentList, [switch]$PassThru, [string]$WindowStyle, [string]$WorkingDirectory)
    if ($global:transferCoveSmokeFixture.Scenario -eq 'empty-console') {
        $process = [pscustomobject]@{ HasExited = $false; Id = 1 }
        $process | Add-Member -MemberType ScriptMethod -Name Refresh -Value { }
        return $process
    }
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

# Exercise the real readiness loop while Flet has created an empty console log.
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($smokeScript, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'Could not parse smoke-installer.ps1' }
$startup = $ast.Find({
    param($node)
    $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Start-SmokeApplication'
}, $true)
if ($null -eq $startup) { throw 'Start-SmokeApplication was not found' }
Invoke-Expression $startup.Extent.Text

function Clear-Content { param([string]$LiteralPath) }
function Copy-Item { param([string]$LiteralPath, [string]$Destination, [switch]$Force) }
function Start-Sleep { param([int]$Milliseconds, [int]$Seconds) }
function Get-Content {
    param([string]$LiteralPath, [switch]$Raw)
    $script:consoleReads++
    if ($script:consoleReads -gt 1) { return 'TransferCove desktop initialized version=0.3.0' }
}
function Read-ApplicationSettings { return [pscustomobject]@{ version = '0.3.0' } }

$global:transferCoveSmokeFixture.Scenario = 'empty-console'
$script:consoleReads = 0
$installDirectory = $PSScriptRoot
$testRoot = $PSScriptRoot
$consoleLog = Join-Path $testRoot 'console.log'
$logs = $testRoot
$StartupTimeoutSeconds = 1
Start-SmokeApplication '0.3.0' $false 'initial'
if ($script:consoleReads -lt 3) { throw 'Readiness did not wait for the startup marker' }
Write-Output 'Passed: empty-console'

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
