param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,
    [guid]$AppId = 'A6F4C3F3-2DA6-4AF4-9E2F-7C0A0200BEEF',
    [ValidateSet('CurrentUser', 'AllUsers')]
    [string]$InstallMode = 'CurrentUser',
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
foreach ($uninstallKey in $uninstallKeys) {
    if (Test-Path -LiteralPath $uninstallKey) {
        throw "A TransferCove installation already exists at $uninstallKey; use a clean runner."
    }
}
if (Get-Process -Name TransferCove -ErrorAction SilentlyContinue) {
    throw 'TransferCove is already running; use a clean runner.'
}
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$logs = [System.IO.Path]::GetFullPath($LogDirectory)
$null = New-Item -ItemType Directory -Path $logs -Force
$tempBase = [System.IO.Path]::GetTempPath()
$testRoot = Join-Path $tempBase ('transfercove-smoke-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $testRoot
$installDirectory = Join-Path $testRoot 'installed'
$dataDirectory = Join-Path $testRoot 'data'
$consoleLog = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'TransferCove/console.log'
$previousConsoleLog = Join-Path $testRoot 'previous-console.log'
$hadConsoleLog = Test-Path -LiteralPath $consoleLog
if ($hadConsoleLog) { Copy-Item -LiteralPath $consoleLog -Destination $previousConsoleLog }
$installLog = Join-Path $logs 'install.log'
$uninstallLog = Join-Path $logs 'uninstall.log'
$applicationProcess = $null
$setupProcess = $null
$savedEnvironment = @{}
$testEnvironment = @{
    FLET_APP_STORAGE_DATA = $dataDirectory
    TRANSMITTER__STORAGE_DIR = (Join-Path $dataDirectory 'files')
    TRANSMITTER__DATABASE_URL = ('sqlite+aiosqlite:///' + (Join-Path $dataDirectory 'files.db').Replace('\', '/'))
    DESKTOP__AUTO_START = 'False'
    DESKTOP__OPEN_BROWSER = 'False'
    APPDATA = (Join-Path $testRoot 'appdata')
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
    $setupProcess = Start-Process -FilePath $installer -ArgumentList $installArguments `
        -PassThru -WindowStyle Hidden
    if (-not $setupProcess.WaitForExit(120000)) { throw 'Installer timed out' }
    if ($setupProcess.ExitCode -ne 0) { throw "Installer exited with $($setupProcess.ExitCode)" }

    foreach ($filename in @('TransferCove.exe', 'LICENSE', 'THIRD-PARTY-NOTICES.txt', 'SECURITY-NOTICE.txt')) {
        if (-not (Test-Path -LiteralPath (Join-Path $installDirectory $filename) -PathType Leaf)) {
            throw "Installed file is missing: $filename"
        }
    }
    foreach ($name in $testEnvironment.Keys) {
        $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $testEnvironment[$name], 'Process')
    }

    $startedAt = [DateTime]::UtcNow
    $applicationProcess = Start-Process -FilePath (Join-Path $installDirectory 'TransferCove.exe') `
        -WorkingDirectory $testRoot -PassThru -WindowStyle Hidden
    $deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $applicationProcess.Refresh()
        if ($applicationProcess.HasExited) { throw 'Installed application exited during startup' }
        if ((Test-Path -LiteralPath $consoleLog) -and (Get-Item -LiteralPath $consoleLog).LastWriteTimeUtc -ge $startedAt) {
            $content = Get-Content -LiteralPath $consoleLog -Raw
            if ($content -match 'Traceback \(most recent call last\)|Unhandled exception') {
                throw 'Installed application reported an exception'
            }
            # Windows reports MainWindowHandle = 0 for hidden processes. This
            # message is emitted only after the real desktop view initializes.
            if ($content -match 'TransferCove desktop initialized') {
                $ready = $true
                break
            }
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) { throw 'Installed desktop did not initialize before the timeout' }
    Start-Sleep -Seconds 3
    $applicationProcess.Refresh()
    if ($applicationProcess.HasExited) { throw 'Installed application exited after initialization' }
    if ((Get-Content -LiteralPath $consoleLog -Raw) -match 'Traceback \(most recent call last\)|Unhandled exception') {
        throw 'Installed application reported an exception after initialization'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dataDirectory 'desktop-settings.db'))) {
        throw 'Installed application did not initialize its settings database'
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

    $uninstaller = Join-Path $installDirectory 'unins000.exe'
    if (Test-Path -LiteralPath $uninstaller) {
        $uninstallProcess = Start-Process -FilePath $uninstaller -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$uninstallLog`""
        ) -PassThru -WindowStyle Hidden
        if (-not $uninstallProcess.WaitForExit(60000)) {
            Stop-Process -Id $uninstallProcess.Id -Force
            throw 'Uninstaller timed out'
        }
        if ($uninstallProcess.ExitCode -ne 0) { throw 'Uninstaller failed' }
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
}
