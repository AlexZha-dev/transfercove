$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$global:releasePublishTest = $null

function Invoke-RestMethod {
    param($Method, $Uri, $Headers, $ContentType, $Body, $InFile)
    $global:releasePublishTest.Calls.Add([pscustomobject]@{
        Method = $Method; Uri = $Uri; Body = $Body; InFile = $InFile
    })
    if ($Method -eq 'Get') {
        switch ($global:releasePublishTest.Scenario) {
            'network-error' { throw 'Simulated GitHub failure' }
            'new' { return ,@() }
            'upload-error' { return ,@() }
            'pagination' {
                if ($Uri -match 'page=1$') {
                    $pageEntries = @(foreach ($number in 1..100) {
                        [pscustomobject]@{ tag_name = "v1.0.$number" }
                    })
                    return ,$pageEntries
                }
            }
            'duplicate' {
                return ,@($global:releasePublishTest.Release, $global:releasePublishTest.Release)
            }
            'mixed' {
                return ,@([pscustomobject]@{ tag_name = 'v0.3.2' }, $global:releasePublishTest.Release)
            }
        }
        return ,@($global:releasePublishTest.Release)
    }
    if ($Method -eq 'Post' -and $Uri -like '*/releases') {
        return [pscustomobject]@{
            upload_url = 'https://uploads.example.test/assets{?name,label}'
            url = 'https://api.example.test/release/1'
        }
    }
    if ($Method -eq 'Post' -and $global:releasePublishTest.Scenario -eq 'upload-error') {
        throw 'Simulated upload failure'
    }
}

function New-TestFixture([string]$Scenario) {
    $assets = @(
        [pscustomobject]@{ name = 'TransferCove-Setup-0.3.3.exe'; state = 'uploaded' },
        [pscustomobject]@{ name = 'TransferCove-Setup-0.3.3.exe.sha256'; state = 'uploaded' }
    )
    if ($Scenario -eq 'missing-asset') { $assets = @($assets[0]) }
    if ($Scenario -eq 'empty-assets') { $assets = @() }
    $global:releasePublishTest = [pscustomobject]@{
        Scenario = $Scenario
        Calls = [System.Collections.Generic.List[object]]::new()
        Release = [pscustomobject]@{
            tag_name = 'v0.3.3'
            draft = ($Scenario -eq 'draft')
            prerelease = ($Scenario -eq 'prerelease')
            assets = $assets
        }
    }
}

function Assert-Methods([string]$Expected) {
    $actual = (@($global:releasePublishTest.Calls | ForEach-Object { $_.Method }) -join ',')
    if ($actual -ne $Expected) { throw "Expected $Expected; got $actual" }
}

$workspace = (Get-Location).Path
$testRoot = Join-Path $workspace ('.tmp-publish-release-' + [guid]::NewGuid().ToString('N'))
if (-not $testRoot.StartsWith($workspace + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Invalid test directory'
}
New-Item -ItemType Directory -Path $testRoot | Out-Null
$installer = Join-Path $testRoot 'TransferCove-Setup-0.3.3.exe'
$checksum = "$installer.sha256"
[System.IO.File]::WriteAllText($installer, 'installer')
[System.IO.File]::WriteAllText($checksum, 'checksum')
$scriptPath = Join-Path $PSScriptRoot 'publish-release.ps1'
$env:GH_TOKEN = 'test-token'
$env:GITHUB_REPOSITORY = 'example/repository'

try {
    New-TestFixture 'new'
    & $scriptPath -Tag 'v0.3.3' -InstallerPath $installer -ChecksumPath $checksum
    Assert-Methods 'Get,Post,Post,Post,Patch'
    $created = $global:releasePublishTest.Calls[1].Body | ConvertFrom-Json
    if (-not $created.draft -or $created.tag_name -ne 'v0.3.3') { throw 'Release was not created as a draft' }
    if ($global:releasePublishTest.Calls[2].InFile -ne $installer -or $global:releasePublishTest.Calls[3].InFile -ne $checksum) {
        throw 'Installer and checksum were not uploaded in order'
    }
    $published = $global:releasePublishTest.Calls[4].Body | ConvertFrom-Json
    if ($published.draft) { throw 'Release was not published' }

    foreach ($scenario in @('published', 'mixed', 'pagination')) {
        New-TestFixture $scenario
        & $scriptPath -Tag 'v0.3.3' -InstallerPath $installer -ChecksumPath $checksum
        if ($scenario -eq 'pagination') { Assert-Methods 'Get,Get' } else { Assert-Methods 'Get' }
    }

    foreach ($scenario in @('draft', 'prerelease', 'missing-asset', 'empty-assets', 'duplicate', 'network-error', 'upload-error')) {
        New-TestFixture $scenario
        $failed = $false
        try {
            & $scriptPath -Tag 'v0.3.3' -InstallerPath $installer -ChecksumPath $checksum
        } catch { $failed = $true }
        if (-not $failed) { throw "Expected failure for $scenario" }
        if ($scenario -eq 'upload-error') {
            Assert-Methods 'Get,Post,Post'
        } else {
            Assert-Methods 'Get'
        }
    }
    Write-Output 'Release publication tests passed.'
} finally {
    if (Test-Path -LiteralPath $testRoot) {
        $resolved = (Resolve-Path -LiteralPath $testRoot).Path
        if ($resolved -ne [System.IO.Path]::GetFullPath($testRoot) -or -not $resolved.StartsWith($workspace + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Unexpected test cleanup directory'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
