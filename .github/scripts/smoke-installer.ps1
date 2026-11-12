param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [guid]$AppId = 'A6F4C3F3-2DA6-4AF4-9E2F-7C0A0200BEEF',
    [ValidateSet('CurrentUser', 'AllUsers')]
    [string]$InstallMode = 'CurrentUser',
    # Reinstall the candidate to exercise CurrentUser scope preservation.
    [switch]$TestUpgradePreservesData,
    [string]$PreviousInstallerPath,
    [string]$PreviousVersion,
    [string]$ExpectedVersion,
    [string]$PythonPath = 'python',
    [string]$LogDirectory = 'test-results/installer',
    [int]$StartupTimeoutSeconds = 60
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Avoid replacing an existing user's or machine-wide installation during local runs.
$uninstallKeyName = '{' + $AppId.ToString().ToUpperInvariant() + '}_is1'
$uninstallKeys = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$uninstallKeyName",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$uninstallKeyName"
)
$expectedUninstallKey = if ($InstallMode -eq 'CurrentUser') { $uninstallKeys[0] } else { $uninstallKeys[1] }
foreach ($uninstallKey in $uninstallKeys) {
    if (Test-Path -LiteralPath $uninstallKey) {
        throw "A TransferCove installation already exists at $uninstallKey; use a clean runner."
    }
}
if (Get-Process -Name TransferCove -ErrorAction SilentlyContinue) {
    throw 'TransferCove is already running; use a clean runner.'
}
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$helper = (Resolve-Path (Join-Path $PSScriptRoot '../../tools/installer_smoke.py')).Path
if (-not $ExpectedVersion) {
    $ExpectedVersion = & $PythonPath $helper version
    if ($LASTEXITCODE -ne 0) { throw 'Cannot read candidate version' }
    $ExpectedVersion = $ExpectedVersion.Trim()
}
if ($ExpectedVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid expected version' }
$initialInstaller = $installer
$initialVersion = $ExpectedVersion
if ($PreviousInstallerPath) {
    if (-not $PreviousVersion -or $PreviousVersion -notmatch '^\d+\.\d+\.\d+$') {
        throw 'A valid PreviousVersion is required for an upgrade test'
    }
    if ([version]$ExpectedVersion -le [version]$PreviousVersion) {
        throw 'Upgrade target must be newer than the previous version'
    }
    $initialInstaller = (Resolve-Path -LiteralPath $PreviousInstallerPath).Path
    if ($initialInstaller -eq $installer) { throw 'An upgrade must use two different installers' }
    $initialVersion = $PreviousVersion
}
elseif ($PreviousVersion) { throw 'PreviousInstallerPath is required with PreviousVersion' }
$testPreservation = $TestUpgradePreservesData -or [bool]$PreviousInstallerPath

$logs = [System.IO.Path]::GetFullPath($LogDirectory)
$null = New-Item -ItemType Directory -Path $logs -Force
$tempBase = [System.IO.Path]::GetTempPath()
$testRoot = Join-Path $tempBase ('transfercove-smoke-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $testRoot
$installDirectory = Join-Path $testRoot 'installed'
$uninstaller = Join-Path $installDirectory 'unins000.exe'
$dataDirectory = Join-Path $testRoot 'data'
$consoleLog = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'TransferCove/console.log'
$previousConsoleLog = Join-Path $testRoot 'previous-console.log'
$hadConsoleLog = Test-Path -LiteralPath $consoleLog
if ($hadConsoleLog) { Copy-Item -LiteralPath $consoleLog -Destination $previousConsoleLog }
$installLog = Join-Path $logs 'install.log'
$uninstallLog = Join-Path $logs 'uninstall.log'
$applicationProcess = $null
$setupProcess = $null
$installationSucceeded = $false
$savedEnvironment = @{}
$testEnvironment = @{
    FLET_APP_STORAGE_DATA = $dataDirectory
    TRANSMITTER__STORAGE_DIR = (Join-Path $dataDirectory 'files')
    TRANSMITTER__DATABASE_URL = ('sqlite+aiosqlite:///' + (Join-Path $dataDirectory 'files.db').Replace('\', '/'))
    DESKTOP__AUTO_START = 'False'
    DESKTOP__OPEN_BROWSER = 'False'
    APPDATA = (Join-Path $testRoot 'appdata')
}

function Read-ApplicationSettings {
    $json = & $PythonPath $helper read --database (Join-Path $dataDirectory 'desktop-settings.db')
    if ($LASTEXITCODE -ne 0) { throw 'Could not read application settings' }
    return ($json | ConvertFrom-Json)
}

function Start-SmokeApplication([string]$Version, [bool]$Legacy, [string]$Stage) {
    # Each launch must produce its own log, not reuse a previous readiness marker.
    if (Test-Path -LiteralPath $consoleLog) { Clear-Content -LiteralPath $consoleLog }
    $script:applicationProcess = Start-Process -FilePath (Join-Path $installDirectory 'TransferCove.exe') `
        -WorkingDirectory $testRoot -PassThru -WindowStyle Hidden
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $applicationProcess.Refresh()
        if ($applicationProcess.HasExited) { throw 'Installed application exited during startup' }
        $content = ''
        if (Test-Path -LiteralPath $consoleLog) {
            $content = [string](Get-Content -LiteralPath $consoleLog -Raw)
            if ($null -eq $content) { $content = '' }
            if ($content -match 'Traceback \(most recent call last\)|Unhandled exception') {
                throw 'Installed application reported an exception'
            }
        }
        $state = Read-ApplicationSettings
        $hasVersion = $null -ne $state.PSObject.Properties['version'] -and $state.version -eq $Version
        # v0.2.3 predates the readiness marker; its committed settings and live process
        # establish baseline initialization. Every candidate requires its exact marker.
        $hasMarker = $content.Contains("TransferCove desktop initialized version=$Version")
        if ($hasVersion -and ($Legacy -or $hasMarker)) { $ready = $true; break }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw "Installed desktop $Version did not initialize before the timeout" }
    Start-Sleep -Seconds 3
    $applicationProcess.Refresh()
    if ($applicationProcess.HasExited) { throw 'Installed application exited after initialization' }
    if (Test-Path -LiteralPath $consoleLog) {
        $content = [string](Get-Content -LiteralPath $consoleLog -Raw)
        Copy-Item -LiteralPath $consoleLog -Destination (Join-Path $logs "$Stage-console.log") -Force
        if ($content -match 'Traceback \(most recent call last\)|Unhandled exception') {
            throw 'Installed application reported an exception after initialization'
        }
    }
}

function Assert-InstallationRegistration([string]$Version) {
    if (-not (Test-Path -LiteralPath $expectedUninstallKey)) { throw 'Installation changed registry scope' }
    $registration = Get-ItemProperty -LiteralPath $expectedUninstallKey
    if ([System.IO.Path]::GetFullPath($registration.InstallLocation).TrimEnd('\') -ine $installDirectory.TrimEnd('\')) {
        throw 'Installation changed directory'
    }
    if ($registration.DisplayVersion -ne $Version) { throw 'Installer registered the wrong version' }
    foreach ($key in $uninstallKeys) {
        if ($key -ne $expectedUninstallKey -and (Test-Path -LiteralPath $key)) {
            throw 'Installation registered an unexpected second scope'
        }
    }
}

try {
    # Exercise the real installer in both registry scopes in separate runs.
    $installArguments = @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-'
    )
    if ($InstallMode -eq 'CurrentUser') {
        $installArguments += '/CURRENTUSER'
    }
    else {
        $installArguments += '/ALLUSERS'
    }
    $installArguments += @(
        "/DIR=`"$installDirectory`"", "/LOG=`"$installLog`""
    )
    $setupProcess = Start-Process -FilePath $initialInstaller -ArgumentList $installArguments `
        -PassThru -WindowStyle Hidden
    if (-not $setupProcess.WaitForExit(120000)) { throw 'Installer timed out' }
    if ($setupProcess.ExitCode -ne 0) { throw "Installer exited with $($setupProcess.ExitCode)" }
    $installationSucceeded = $true

    if (-not (Test-Path -LiteralPath $uninstaller -PathType Leaf)) {
        throw "Installed uninstaller is missing: $uninstaller"
    }
    if (-not (Test-Path -LiteralPath $expectedUninstallKey)) {
        throw "Installer did not register $InstallMode installation at $expectedUninstallKey"
    }
    $requiredFiles = @('TransferCove.exe', 'LICENSE', 'THIRD-PARTY-NOTICES.txt')
    if (-not $PreviousInstallerPath) { $requiredFiles += 'SECURITY-NOTICE.txt' }
    foreach ($filename in $requiredFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $installDirectory $filename) -PathType Leaf)) {
            throw "Installed file is missing: $filename"
        }
    }
    foreach ($name in $testEnvironment.Keys) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $testEnvironment[$name], 'Process')
    }

    Assert-InstallationRegistration $initialVersion
    Start-SmokeApplication $initialVersion ([bool]$PreviousInstallerPath) 'initial'

    if ($testPreservation) {
        $receivedDirectory = $testEnvironment['TRANSMITTER__STORAGE_DIR']
        $receivedFile = Join-Path $receivedDirectory 'received-before-upgrade.txt'
        $receivedContent = 'TransferCove upgrade preservation check'
        $null = New-Item -ItemType Directory -Path $receivedDirectory -Force
        [System.IO.File]::WriteAllText($receivedFile, $receivedContent)
        Stop-Process -Id $applicationProcess.Id -Force
        if (-not $applicationProcess.WaitForExit(10000)) { throw 'App did not stop before upgrade' }

        & $PythonPath $helper seed --database (Join-Path $dataDirectory 'desktop-settings.db')
        if ($LASTEXITCODE -ne 0) { throw 'Could not seed the pre-upgrade settings' }

        # Use exactly the same scope detection and argument generation as the updater.
        $argumentsJson = & $PythonPath $helper arguments --executable (Join-Path $installDirectory 'TransferCove.exe')
        if ($LASTEXITCODE -ne 0) { throw 'Could not determine existing installation arguments' }
        $arguments = $argumentsJson | ConvertFrom-Json
        if ($arguments.scope -ne $InstallMode) { throw 'Updater selected the wrong install scope' }
        $upgradeLog = Join-Path $logs 'upgrade-install.log'
        $upgradeArguments = $arguments.command_line + ' /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /LOG="' + $upgradeLog + '"'
        $setupProcess = Start-Process -FilePath $installer -ArgumentList $upgradeArguments `
            -PassThru -WindowStyle Hidden
        if (-not $setupProcess.WaitForExit(120000)) { throw 'Upgrade installer timed out' }
        if ($setupProcess.ExitCode -ne 0) { throw "Upgrade installer exited with $($setupProcess.ExitCode)" }
        Assert-InstallationRegistration $ExpectedVersion
        foreach ($filename in @('TransferCove.exe', 'LICENSE', 'THIRD-PARTY-NOTICES.txt', 'SECURITY-NOTICE.txt')) {
            if (-not (Test-Path -LiteralPath (Join-Path $installDirectory $filename) -PathType Leaf)) {
                throw "Upgraded installation is missing $filename"
            }
        }

        Start-SmokeApplication $ExpectedVersion $false 'upgraded'
        $state = Read-ApplicationSettings
        if ($state.title -cne 'Preserved upgrade setting' -or $state.version -ne $ExpectedVersion -or
            [System.IO.Path]::GetFullPath($state.storage_dir) -ine $receivedDirectory) {
            throw 'The upgraded application did not preserve its settings after startup'
        }
        if (-not (Test-Path -LiteralPath $receivedFile -PathType Leaf) -or
            [System.IO.File]::ReadAllText($receivedFile) -cne $receivedContent) {
            throw 'The upgraded application did not preserve the received file after startup'
        }
        Write-Output "Preserved settings, received files, directory and scope after $initialVersion -> $ExpectedVersion ($InstallMode)."
    }

    Write-Output "Installed application initialized successfully ($InstallMode)."
}
finally {
    foreach ($process in @($applicationProcess, $setupProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            $null = $process.WaitForExit(10000)
        }
    }
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    if ($null -ne $applicationProcess -and (Test-Path -LiteralPath $consoleLog)) {
        Copy-Item -LiteralPath $consoleLog -Destination (Join-Path $logs 'console.log') -Force
        Get-Content -LiteralPath $consoleLog
        if ($hadConsoleLog) {
            Copy-Item -LiteralPath $previousConsoleLog -Destination $consoleLog -Force
        }
    }

    $uninstallerMissing = $false
    if (Test-Path -LiteralPath $uninstaller) {
        $uninstallProcess = Start-Process -FilePath $uninstaller -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$uninstallLog`""
        ) -PassThru -WindowStyle Hidden
        if (-not $uninstallProcess.WaitForExit(60000)) {
            Stop-Process -Id $uninstallProcess.Id -Force
            throw 'Uninstaller timed out'
        }
        if ($uninstallProcess.ExitCode -ne 0) { throw 'Uninstaller failed' }
        if (Test-Path -LiteralPath (Join-Path $installDirectory 'TransferCove.exe')) {
            throw 'Uninstaller left the application executable behind'
        }
    }
    elseif ($installationSucceeded) {
        $uninstallerMissing = $true
    }
    foreach ($uninstallKey in $uninstallKeys) {
        if (Test-Path -LiteralPath $uninstallKey) {
            throw "Uninstaller left an installation registration behind: $uninstallKey"
        }
    }
    $resolvedRoot = [System.IO.Path]::GetFullPath($testRoot)
    $resolvedBase = [System.IO.Path]::GetFullPath($tempBase).TrimEnd('\') + '\'
    if (-not $resolvedRoot.StartsWith($resolvedBase, [StringComparison]::OrdinalIgnoreCase) -or
        [System.IO.Path]::GetFileName($resolvedRoot) -notlike 'transfercove-smoke-*') {
        throw "Refusing to clean an unexpected path: $resolvedRoot"
    }
    Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
    if ($uninstallerMissing) { throw "Installed uninstaller is missing: $uninstaller" }
}
