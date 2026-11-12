# Continuous integration and development installers

The workflow is defined in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Triggers and checks

Every pull request runs CI, including PRs targeting `dev` and `main`. Opening a PR, reopening it, and pushing additional commits to the PR trigger checks against GitHub's proposed merge commit. A separate dependency review blocks changes introducing high- or critical-severity vulnerabilities. A newer run for the same PR cancels the older one. Direct pushes and manual workflow dispatches do not run CI.

The `checks` job runs on Python 3.14 with both `ubuntu-24.04` and `windows-2022`. It installs dependencies from `poetry.lock`, validates the lock file, runs Ruff lint/format checks, and runs all pytest tests. The standalone server integration test starts `python -m app.server_start_up` on a loopback port and checks migration of a temporary legacy database, health, upload-page assets, invalid requests, successful file uploads, and stored bytes. It always stops the server process. Dependabot proposes weekly updates to Python dependencies and GitHub Actions.

After both platforms pass, the `Windows installer` job exports the runtime versions from `poetry.lock` as a temporary pip constraints file. Flet's packager uses these constraints to resolve Python dependencies. CI verifies the actual bundled libraries match those lockfile versions before compiling the installer with Inno Setup. Version metadata comes from `pyproject.toml`; `GITHUB_RUN_NUMBER` supplies the application build number. The Windows runner includes Visual Studio's C++ desktop tools and Inno Setup. Flet installs its matching Flutter SDK when required.

The Flet build template's `jni` override is replaced in `pyproject.toml` to keep it compatible with newer `jni_flutter` releases. This is a Flutter dependency, separate from the Python lock file. Remove the override when upgrading to a Flet version with the upstream fix; if a local build still uses stale dependencies, clean the generated Flutter build before retrying. See [Flet issue #6919](https://github.com/flet-dev/flet/issues/6919).

The installer smoke test installs and uninstalls to separate temporary directories in both `/CURRENTUSER` and `/ALLUSERS` modes. It requires an uninstaller and an installation registry entry in the selected scope, checks required files, launches the installed executable hidden, waits for the desktop initialization message in Flet's console log, and verifies the process stays alive and creates its settings database. It also checks that uninstall removes the application executable and registry entry. The test does not automatically acknowledge the security notice or expose a transfer server. The documented standalone upload-server flow, including migrations, is tested separately in pytest. Temporary data is removed after checks, and existing console logs are preserved during local runs. Windows reports a zero `MainWindowHandle` for hidden processes, so readiness uses the completed desktop initialization reported by the application. See [Microsoft's API documentation](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.mainwindowhandle).

The workflow uses only the `pull_request` event, read-only repository permissions, and no signing or deployment secrets. Actions are pinned to commit SHAs. Installer artifacts are uploaded only after both smoke tests succeed.

## Artifacts and diagnostics

- `TransferCove-test-<sha>` contains a test installer for a pull request.
- `test-results-<runner>-<sha>` contains the pytest JUnit report, including failed test results.
- `installer-logs-<sha>` contains install, application console, and uninstall logs, including logs from failed smoke tests.

Installers are retained for 14 days; reports and logs for 7 days. Download them from the workflow run under **Actions → CI → Artifacts**. These are unsigned development and test builds. Release installers are also unsigned until a Windows signing certificate and signing workflow are provisioned.

## Stable releases and desktop updates

The separate [release workflow](../.github/workflows/release.yml) runs when a `v*` tag is pushed. It accepts only stable `vX.Y.Z` tags that exactly match the version in `pyproject.toml` and the application configuration. The workflow runs tests and linting on Windows and Linux, builds the Windows app with the locked dependencies, verifies the packaged bundle, and smoke-tests fresh installs in both installer scopes. For 0.3.2, a separate upgrade test downloads the published 0.2.3 installer and verifies the SHA-256 pinned in [upgrade-baseline.json](../.github/upgrade-baseline.json). It initializes 0.2.3, seeds a saved preference and received file, upgrades to 0.3.2, and launches the upgraded application before checking its version, settings, received file, directory, and registry scope. The old release supports only AllUsers. A separate CurrentUser reinstall checks scope preservation using the same argument generator as the app; that scope test also runs in PR CI. These are separate checks: a same-version reinstall is not evidence of an upgrade between versions. Installer diagnostics are uploaded even when a release check fails. Update the baseline version, asset URL, SHA-256, and supported scope together when selecting a newer baseline for a future release.

After all checks pass, the workflow creates a draft GitHub Release, attaches `TransferCove-Setup-X.Y.Z.exe` and its `TransferCove-Setup-X.Y.Z.exe.sha256` checksum, then publishes the release. If asset upload or publication fails, the release remains a draft and is not offered by the updater. GitHub-generated release notes are shown in the app. The workflow uses the repository `GITHUB_TOKEN`; only the release job has `contents: write` permission.

The packaged Windows app checks published stable releases in the background at startup, no more than once per 24 hours. Users can run **Settings → About this app → Check for updates** at any time. The app selects the highest stable semantic version, requires the matching installer and checksum assets, and verifies the installer before offering to install it. The user confirms before TransferCove closes and starts the normal interactive installer. GitHub/network failures and missing assets appear as status messages; they do not prevent app use. Update checks run outside the UI event loop.

After confirmation, the updater verifies SHA-256 again while holding a Windows file handle that denies writing and deletion until process creation succeeds. It matches the running executable to its HKCU/HKLM installation and passes the original mode and directory to setup. Missing or changed downloads can be downloaded again; an ambiguous installation or launch error leaves the app open. Checking, downloading, confirmation, and installation are mutually exclusive, including repeated click events.

### Versioning and release procedure

Ordinary feature and fix PRs target `dev`; they do not each need a version increase. Increase the version once while preparing a release, and include that change in the release PR from `dev` to `main`. The current project version is **0.3.2**. Before 1.0, this project uses PATCH increments for fixes and MINOR increments for new functionality; see [Semantic Versioning](https://semver.org/).

Keep `pyproject.toml`, `AppConfig.version`, `.env.example`, and the README version in sync. Local `.env` overrides such as `APP__VERSION` should also be updated when running from source. After merging the release PR, create the matching `v0.3.2` tag on the final `main` commit and push that tag. Merging alone does not publish a release; the tag push starts the release workflow. Published versions and tags must not be reused for changed binaries.

Version 0.3.0 adds stable GitHub release checks, explicit installation confirmation, repeated checksum verification, and preservation of install scope and application data. Existing 0.2.3 users install 0.3.0 manually once; subsequent compatible releases can be offered by the updater.

The release workflow rejects version mismatches and does not publish a Release before installer checks succeed. The generated installer is unsigned; configure Windows code signing before treating these public releases as signed distributions.

## Local verification

Install Poetry 2.5.1 and use Python 3.14. From the repository root:

```text
poetry install --with dev
poetry check --lock
poetry run ruff check app tests tools main.py alembic
poetry run ruff format --check app tests tools main.py alembic
python -c "from pathlib import Path; Path('test-results').mkdir(parents=True, exist_ok=True)"
poetry run pytest --junitxml=test-results/pytest.xml
```

To build and test the installer on Windows with Visual Studio C++ tools and Inno Setup 6 installed, use PowerShell:

```powershell
poetry install --with dev,build
poetry run python tools/export_flet_constraints.py --output test-results/flet-runtime-constraints.txt
$env:PIP_CONSTRAINT = (Resolve-Path test-results/flet-runtime-constraints.txt).Path
poetry run flet build windows --yes --no-rich-output --python-version 3.14 --build-version (poetry version --short)
Remove-Item Env:PIP_CONSTRAINT
poetry run python tools/verify_flet_bundle.py --site-packages build/site-packages
./.github/scripts/build-installer.ps1 -InstallerName TransferCove-local-test
./.github/scripts/smoke-installer.ps1 -InstallerPath dist/installer/TransferCove-local-test.exe -InstallMode CurrentUser -TestUpgradePreservesData
./.github/scripts/smoke-installer.ps1 -InstallerPath dist/installer/TransferCove-local-test.exe -InstallMode AllUsers
```

Run PowerShell as administrator for the `/ALLUSERS` check. If the local PowerShell execution policy blocks scripts, invoke them through `powershell -NoProfile -ExecutionPolicy Bypass -File <script-path> <arguments>`. This applies only to that process. Use a clean Windows account or runner for installer smoke tests; the script refuses to run while TransferCove is open or an existing per-user or machine-wide installation is registered.

To exercise the real version transition on a clean runner, first download and verify the baseline using `.github/upgrade-baseline.json`, then pass `-PreviousInstallerPath <verified-baseline.exe> -PreviousVersion 0.2.3 -ExpectedVersion 0.3.2 -InstallMode AllUsers` to `smoke-installer.ps1` along with the candidate `-InstallerPath`. Equal or decreasing version transitions are rejected. Use `-PythonPath <python.exe>` if Python 3.14 is not on PATH.

After changing build/dev dependencies, run `poetry lock` and commit `pyproject.toml` and `poetry.lock` together. Flet CLI's version in the optional `build` group should match the runtime Flet version in the lock file.

## Enforcing checks before merging

The workflow reports checks on PRs. To prevent merging a PR with failed or missing checks, configure a GitHub branch protection rule or ruleset for `dev` (and `main` if desired) and require:

- `Tests and lint (ubuntu-24.04)`
- `Tests and lint (windows-2022)`
- `Dependency review`
- `Windows installer`

Branch protection is a repository setting and is not configured by the workflow file. Require review from a code owner for changes to `.github/`, `pyproject.toml`, and `poetry.lock`. Add the required checks after their first GitHub Actions run so that GitHub can identify their names.
