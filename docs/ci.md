# Continuous integration and development installers

The workflow is defined in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Triggers and checks

Every pull request runs CI, including PRs targeting `dev` and `main`. Opening a PR, reopening it, and pushing additional commits to the PR trigger checks against GitHub's proposed merge commit. A separate dependency review blocks changes introducing high- or critical-severity vulnerabilities. A newer run for the same PR cancels the older one. Direct pushes and manual workflow dispatches do not run CI.

The `checks` job runs on Python 3.14 with both `ubuntu-24.04` and `windows-2022`. It installs dependencies from `poetry.lock`, validates the lock file, runs Ruff lint/format checks, and runs all pytest tests. The standalone server integration test starts `python -m app.server_start_up` on a loopback port and checks migration of a temporary legacy database, health, upload-page assets, invalid requests, successful file uploads, and stored bytes. It always stops the server process. Dependabot proposes weekly updates to Python dependencies and GitHub Actions.

After both platforms pass, the `Windows installer` job exports the runtime versions from `poetry.lock` as a temporary pip constraints file. Flet's packager uses these constraints to resolve Python dependencies. CI verifies the actual bundled libraries match those lockfile versions before compiling the installer with Inno Setup. Version metadata comes from `pyproject.toml`; `GITHUB_RUN_NUMBER` supplies the application build number. The Windows runner includes Visual Studio's C++ desktop tools and Inno Setup. Flet installs its matching Flutter SDK when required.

The Flet build template's `jni` override is replaced in `pyproject.toml` to keep it compatible with newer `jni_flutter` releases. This is a Flutter dependency, separate from the Python lock file. Remove the override when upgrading to a Flet version with the upstream fix; if a local build still uses stale dependencies, clean the generated Flutter build before retrying. See [Flet issue #6919](https://github.com/flet-dev/flet/issues/6919).

The installer smoke test installs and uninstalls to separate temporary directories in both `/CURRENTUSER` and `/ALLUSERS` modes. It requires an uninstaller and an installation registry entry in the selected scope, checks required files, launches the installed executable hidden, waits for the desktop initialization message in Flet's console log, and verifies the process stays alive and creates its settings database. It also checks that uninstall removes the application executable and registry entry. The test does not automatically acknowledge the security notice or expose a transfer server. The documented standalone upload-server flow, including migrations, is tested separately in pytest. Temporary data is removed after checks, and existing console logs are preserved during local runs. Windows reports a zero `MainWindowHandle` for hidden processes, so readiness uses the completed desktop initialization reported by the application. See [Microsoft's API documentation](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.mainwindowhandle).

The candidate is installed from scratch in both scopes. The current-user smoke test also checks downgrade rejection and same-version repair. A separate upgrade test verifies the SHA-256 of the published release pinned in `.github/upgrade-baseline.json`, installs it, then upgrades to the candidate. It checks that original retired files disappear and that locally modified files, received files and settings survive.

The workflow uses only the `pull_request` event, read-only repository permissions, and no signing or deployment secrets. Actions are pinned to commit SHAs. Installer artifacts are uploaded after all three smoke scenarios succeed.

## Artifacts and diagnostics

- `TransferCove-test-<sha>` contains a test installer for a pull request.
- `test-results-<runner>-<sha>` contains the pytest JUnit report, including failed test results.
- `installer-logs-<sha>` contains install, application console, and uninstall logs, including logs from failed smoke tests.

Installers are retained for 14 days; reports and logs for 7 days. Download them from the workflow run under **Actions → CI → Artifacts**. These are unsigned development and test builds. Release installers are also unsigned until a Windows signing certificate and signing workflow are provisioned.

## Stable releases and desktop updates

Stable releases are built, verified, and published manually. Pushing a `v*` tag does not run a release workflow. PR CI continues to build and test development installers; its artifacts are separate from the manually prepared release assets.

Build from the final tagged `main` commit using the local verification commands below. Run the Python checks, verify the Flet bundle, and smoke-test the installer in both installation scopes. Use the previous-release upgrade test below to check preservation of settings and received files. Update [upgrade-baseline.json](../.github/upgrade-baseline.json) when selecting a newer baseline.

The installer build script produces `TransferCove-Setup-X.Y.Z.exe` and `TransferCove-Setup-X.Y.Z.exe.sha256`. The checksum contains the SHA-256 hash and installer filename. Create a draft GitHub Release for the matching `vX.Y.Z` tag, attach both files, and add release notes. Verify the version and attachments before publishing the draft as a stable release. Drafts and prereleases are not offered by the updater. Generate the checksum from the final installer again if the binary changes, including after signing.

The packaged Windows app checks published stable releases in the background at startup, no more than once per 24 hours. Users can run **Settings → About this app → Check for updates** at any time. The app selects the highest stable semantic version, requires the matching installer and checksum assets, and verifies the installer before offering to install it. The user confirms before TransferCove closes and starts the normal interactive installer. GitHub/network failures and missing assets appear as status messages; they do not prevent app use. Update checks run outside the UI event loop.

After confirmation, the updater verifies SHA-256 again while holding a Windows file handle that denies writing and deletion until process creation succeeds. It matches the running executable to its HKCU/HKLM installation and passes the original mode and directory to setup. Missing or changed downloads can be downloaded again; an ambiguous installation or launch error leaves the app open. Checking, downloading, confirmation, and installation are mutually exclusive, including repeated click events.

### Versioning and release procedure

Windows Setup requires Windows 10 or newer. It reads the release version from the first three numeric version components of the packaged EXE. The fourth component is the Flutter build number. The build fails if the packaged version differs from the Poetry version.

During release preparation, run `python tools/record_windows_payload.py build/windows` on the verified final bundle and commit the updated inventory in `installer/windows/released-payload.txt`. It contains SHA-256 hashes from the published 0.2.3, 0.3.2 and 0.3.3 installers and accumulates hashes when files change. Keep historical entries so users can skip releases. Setup includes only retired paths in its cleanup list. It checks file contents before removal, preserves unfamiliar content, skips reparse points and removes directories only when empty.

Setup compares the first three numeric components of the registered version and installed EXE. It accepts legacy Flutter versions such as `0.3.2+42`. A newer release blocks installation. If the registered version is unreadable, Setup can recover the release from the EXE in the registered directory. Already published installers follow their original behavior.

If a retired file is locked during preparation, Setup identifies it and stops before copying the new bundle (exit code 7). If cleanup fails after copying, Setup logs the affected paths, suppresses application launch and exits with code 20. Close the process holding the file or resolve the reported access error, then run the same installer again. Successful repair returns 0.

Ordinary feature and fix PRs target `dev`; they do not each need a version increase. Increase the version once while preparing a release, and include that change in the release PR from `dev` to `main`. The current project version is **0.3.3**. Before 1.0, this project uses PATCH increments for fixes and MINOR increments for new functionality; see [Semantic Versioning](https://semver.org/).

Keep `pyproject.toml`, `AppConfig.version`, `.env.example`, and the README version in sync. Local `.env` overrides such as `APP__VERSION` should also be updated when running from source. After merging the release PR, create the matching `v0.3.3` tag on the final `main` commit and push that tag. Neither merging nor pushing the tag publishes a release. Follow the manual build and publication procedure above. Published versions and tags must not be reused for changed binaries.

Version 0.3.0 adds stable GitHub release checks, explicit installation confirmation, repeated checksum verification, and preservation of install scope and application data. Existing 0.2.3 users install 0.3.0 manually once; subsequent compatible releases can be offered by the updater.

Before publishing, verify that the tag, `pyproject.toml`, application version, and installer version match, and that all local checks succeed. The generated installer is unsigned; configure Windows code signing before treating these public releases as signed distributions.

## Local verification

Install Poetry 2.5.1 and use Python 3.14. From the repository root:

```text
poetry install --with dev
poetry check --lock
poetry run python -m app.core.localization
poetry run ruff check app tests tools main.py alembic
poetry run ruff format --check app tests tools main.py alembic
python -c "from pathlib import Path; Path('test-results').mkdir(parents=True, exist_ok=True)"
poetry run pytest --junitxml=test-results/pytest.xml
```

To build and test the installer on Windows with Visual Studio C++ tools and Inno Setup 6.3 or newer installed, use PowerShell:

```powershell
poetry install --with dev,build
poetry run python tools/export_flet_constraints.py --output test-results/flet-runtime-constraints.txt
$env:PIP_CONSTRAINT = (Resolve-Path test-results/flet-runtime-constraints.txt).Path
poetry run flet build windows --yes --no-rich-output --python-version 3.14 --build-version (poetry version --short)
Remove-Item Env:PIP_CONSTRAINT
poetry run python tools/verify_flet_bundle.py --site-packages build/site-packages
poetry run python tools/verify_locale_bundle.py
./.github/scripts/build-installer.ps1
./.github/scripts/smoke-installer.ps1 -InstallerPath "dist/installer/TransferCove-Setup-$(poetry version --short).exe" -InstallMode CurrentUser -TestUpgradePreservesData
./.github/scripts/smoke-installer.ps1 -InstallerPath "dist/installer/TransferCove-Setup-$(poetry version --short).exe" -InstallMode AllUsers
```

Run PowerShell as administrator for the `/ALLUSERS` check. If the local PowerShell execution policy blocks scripts, invoke them through `powershell -NoProfile -ExecutionPolicy Bypass -File <script-path> <arguments>`. This applies only to that process. Use a clean Windows account or runner for installer smoke tests; the script refuses to run while TransferCove is open or an existing per-user or machine-wide installation is registered.

To exercise the real version transition on a clean runner, first download and verify the baseline using `.github/upgrade-baseline.json`, then pass `-PreviousInstallerPath <verified-baseline.exe> -PreviousVersion 0.2.3 -ExpectedVersion 0.3.3 -InstallMode AllUsers` to `smoke-installer.ps1` along with the candidate `-InstallerPath`. Equal or decreasing version transitions are rejected. Use `-PythonPath <python.exe>` if Python 3.14 is not on PATH.

After changing build/dev dependencies, run `poetry lock` and commit `pyproject.toml` and `poetry.lock` together. Flet CLI's version in the optional `build` group should match the runtime Flet version in the lock file.

## Enforcing checks before merging

The workflow reports checks on PRs. To prevent merging a PR with failed or missing checks, configure a GitHub branch protection rule or ruleset for `dev` (and `main` if desired) and require:

- `Tests and lint (ubuntu-24.04)`
- `Tests and lint (windows-2022)`
- `Dependency review`
- `Windows installer`

Branch protection is a repository setting and is not configured by the workflow file. Require review from a code owner for changes to `.github/`, `pyproject.toml`, and `poetry.lock`. Add the required checks after their first GitHub Actions run so that GitHub can identify their names.
