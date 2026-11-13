param(
    [Parameter(Mandatory = $true)][string]$Tag,
    [Parameter(Mandatory = $true)][string]$InstallerPath,
    [Parameter(Mandatory = $true)][string]$ChecksumPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$checksum = (Resolve-Path -LiteralPath $ChecksumPath).Path
$headers = @{
    Accept = 'application/vnd.github+json'
    Authorization = "Bearer $env:GH_TOKEN"
    'X-GitHub-Api-Version' = '2026-03-10'
}
$releasesUrl = "https://api.github.com/repos/$env:GITHUB_REPOSITORY/releases"

# The authenticated list includes drafts; GET /releases/tags only finds
# published releases. Check every page before creating or changing anything.
$matchingReleases = @()
$page = 1
do {
    $response = Invoke-RestMethod -Method Get -Uri "$releasesUrl`?per_page=100&page=$page" -Headers $headers
    $batch = @($response | Where-Object { $null -ne $_ })
    $matchingReleases += @($batch | Where-Object { $_.tag_name -ceq $Tag })
    $page++
} while ($batch.Count -eq 100)

if ($matchingReleases.Count -gt 1) {
    throw "Multiple releases use tag $Tag. Review them in GitHub before retrying."
}
if ($matchingReleases.Count -eq 1) {
    $existing = $matchingReleases[0]
    if ($existing.draft) {
        throw "A draft release for $Tag already exists. Review it in GitHub before retrying; it was not modified."
    }
    if ($existing.prerelease) {
        throw "The existing release for $Tag is a prerelease. It was not modified."
    }
    $assetNames = @($existing.assets | Where-Object { $null -ne $_ -and $_.state -eq 'uploaded' } | ForEach-Object { $_.name })
    foreach ($path in @($installer, $checksum)) {
        $name = [System.IO.Path]::GetFileName($path)
        if ($name -cnotin $assetNames) {
            throw "The existing release for $Tag is missing $name. It was not modified."
        }
    }
    Write-Warning "Release $Tag is already published. Its assets were not replaced or verified against this CI build."
    return
}

$releaseBody = @{
    tag_name = $Tag
    name = $Tag
    draft = $true
    prerelease = $false
    generate_release_notes = $true
    make_latest = 'true'
} | ConvertTo-Json
$release = Invoke-RestMethod -Method Post -Uri $releasesUrl `
    -Headers $headers -ContentType 'application/json' -Body $releaseBody
$uploadUrl = [string]$release.upload_url -replace '\{\?name,label\}$', ''
foreach ($assetPath in @($installer, $checksum)) {
    $assetName = [System.IO.Path]::GetFileName($assetPath)
    $assetUrl = "$uploadUrl`?name=$([Uri]::EscapeDataString($assetName))"
    Invoke-RestMethod -Method Post -Uri $assetUrl -Headers $headers `
        -ContentType 'application/octet-stream' -InFile $assetPath | Out-Null
}
$publishBody = @{ draft = $false; prerelease = $false } | ConvertTo-Json
Invoke-RestMethod -Method Patch -Uri $release.url -Headers $headers `
    -ContentType 'application/json' -Body $publishBody | Out-Null
