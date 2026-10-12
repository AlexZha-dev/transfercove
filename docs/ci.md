# Continuous integration and development installers

The workflow is defined in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Triggers and checks

Every pull request runs CI, including PRs targeting `dev` and `main`. Opening a PR, reopening it, and pushing additional commits to the PR trigger checks against GitHub's proposed merge commit. A separate dependency review blocks changes introducing high- or critical-severity vulnerabilities. A newer run for the same PR cancels the older one. Direct pushes and manual workflow dispatches do not run CI.

The `checks` job runs on Python 3.14 with both `ubuntu-24.04` and `windows-2022`. It installs dependencies from `poetry.lock`, validates the lock file, runs Ruff lint/format checks, and runs all pytest tests. The standalone server integration test applies migrations to a temporary SQLite database, starts `python -m app.server_start_up` on a loopback port, and checks health, upload-page assets, invalid requests, successful file uploads, stored bytes, and database metadata. It always stops the server process. Dependabot proposes weekly updates to Python dependencies and GitHub Actions.

After both platforms pass, the `Windows installer` job exports the runtime versions from `poetry.lock` as a temporary pip constraints file. Flet's packager uses these constraints to resolve Python dependencies. CI verifies the actual bundled libraries match those lockfile versions before compiling the installer with Inno Setup. Version metadata comes from `pyproject.toml`; `GITHUB_RUN_NUMBER` supplies the application build number. The Windows runner includes Visual Studio's C++ desktop tools and Inno Setup. Flet installs its matching Flutter SDK when required.

The installer smoke test installs and uninstalls to separate temporary directories in both `/CURRENTUSER` and `/ALLUSERS` modes. It checks required files, launches the installed executable hidden, waits for the desktop initialization message in Flet's console log, and verifies the process stays alive and creates its settings database. It also checks that uninstall removes the registry entry. The test does not automatically acknowledge the security notice or expose a transfer server. The documented standalone upload-server flow, including migrations, is tested separately in pytest. Temporary data is removed after checks, and existing console logs are preserved during local runs. Windows reports a zero `MainWindowHandle` for hidden processes, so readiness uses the completed desktop initialization reported by the application. See [Microsoft's API documentation](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.mainwindowhandle).

The workflow uses only the `pull_request` event, read-only repository permissions, and no signing or deployment secrets. Actions are pinned to commit SHAs. Installer artifacts are uploaded only after both smoke tests succeed.

## Artifacts and diagnostics

- `TransferCove-test-<sha>` contains a test installer for a pull request.
- `test-results-<runner>-<sha>` contains the pytest JUnit report, including failed test results.
- `installer-logs-<sha>` contains install, application console, and uninstall logs, including logs from failed smoke tests.

Installers are retained for 14 days; reports and logs for 7 days. Download them from the workflow run under **Actions → CI → Artifacts**. These are unsigned development and test builds. A signed production release still requires a provisioned Windows signing certificate and a protected release workflow.

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
./.github/scripts/smoke-installer.ps1 -InstallerPath dist/installer/TransferCove-local-test.exe -InstallMode CurrentUser
./.github/scripts/smoke-installer.ps1 -InstallerPath dist/installer/TransferCove-local-test.exe -InstallMode AllUsers
```

Run PowerShell as administrator for the `/ALLUSERS` check. If the local PowerShell execution policy blocks scripts, invoke them through `powershell -NoProfile -ExecutionPolicy Bypass -File <script-path> <arguments>`. This applies only to that process. Use a clean Windows account or runner for installer smoke tests; the script refuses to run while TransferCove is open or an existing per-user or machine-wide installation is registered.

After changing build/dev dependencies, run `poetry lock` and commit `pyproject.toml` and `poetry.lock` together. Flet CLI's version in the optional `build` group should match the runtime Flet version in the lock file.

## Enforcing checks before merging

The workflow reports checks on PRs. To prevent merging a PR with failed or missing checks, configure a GitHub branch protection rule or ruleset for `dev` (and `main` if desired) and require:

- `Tests and lint (ubuntu-24.04)`
- `Tests and lint (windows-2022)`
- `Dependency review`
- `Windows installer`

Branch protection is a repository setting and is not configured by the workflow file. Require review from a code owner for changes to `.github/`, `pyproject.toml`, and `poetry.lock`. Add the required checks after their first GitHub Actions run so that GitHub can identify their names.
