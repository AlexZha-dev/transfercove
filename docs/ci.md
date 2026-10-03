# Continuous integration and development installers

The workflow is defined in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Triggers and checks

Every pull request runs CI, including PRs targeting `dev` and `main`. Opening a PR, reopening it, and pushing additional commits trigger checks against GitHub's proposed merge commit. Pushes to `dev` also run the full pipeline. `workflow_dispatch` supports manual runs once the workflow exists on the repository's default branch. A newer run for the same PR or branch cancels the older one.

The `checks` job runs on Python 3.14 with both `ubuntu-24.04` and `windows-2022`. It installs dependencies from `poetry.lock`, validates the lock file, runs Ruff lint/format checks, and runs all pytest tests. The standalone server integration test applies migrations to a temporary SQLite database, starts `python -m app.server_start_up` on a loopback port, and checks health, upload-page assets, invalid requests, successful file uploads, stored bytes, and database metadata. It always stops the server process.

After both platforms pass, the `Windows installer` job uses the locked Flet CLI to build the application, then compiles it with the runner's Inno Setup compiler. Version metadata comes from `pyproject.toml`; `GITHUB_RUN_NUMBER` supplies the application build number. The Windows runner already includes Visual Studio's C++ desktop tools and Inno Setup. Flet installs its matching Flutter SDK when required.

The installer smoke test installs to a unique temporary directory with `/CURRENTUSER` and without restarting Windows or launching the app from the installer. It checks required files, launches the installed executable hidden, waits for the desktop initialization message in Flet's console log, and verifies that the process stays alive and creates its settings database. This tests the bundled Python runtime and actual desktop initialization, including the first-run security notice. It does not automatically acknowledge that notice or expose a transfer server. The upload-only server is tested independently in pytest. The smoke test stops the application, uninstalls it, removes temporary data, and preserves existing console logs during local runs. Windows reports a zero `MainWindowHandle` for hidden processes, so readiness uses the completed desktop initialization reported by the application. See [Microsoft's API documentation](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.mainwindowhandle).

The workflow uses the `pull_request` event with read-only repository permissions and no signing or deployment secrets. Actions are pinned to commit SHAs. Installer artifacts are uploaded only after the smoke test succeeds.

## Artifacts and diagnostics

- `TransferCove-dev-<sha>` contains `TransferCove-dev-<sha>.exe` after a push to `dev`.
- `TransferCove-test-<sha>` contains a test installer after a pull request or manual run.
- `test-results-<runner>-<sha>` contains the pytest JUnit report, including failed test results.
- `installer-logs-<sha>` contains install, application console, and uninstall logs, including logs from failed smoke tests.

Installers are retained for 14 days; reports and logs for 7 days. Download them from the workflow run under **Actions → CI → Artifacts**. These are unsigned test builds; release publishing and certificate management are separate from this workflow.

## Local verification

Install Poetry 2.5.1 and use Python 3.14. From the repository root:

```text
poetry install --with dev
poetry check --lock
poetry run ruff check app tests tools main.py alembic
poetry run ruff format --check app tests tools main.py alembic
poetry run pytest --junitxml=test-results/pytest.xml
```

To build and test the installer on Windows with Visual Studio C++ tools and Inno Setup 6 installed, use PowerShell:

```powershell
poetry install --with dev,build
poetry run flet build windows --yes --no-rich-output --python-version 3.14 --build-version (poetry version --short)
./.github/scripts/build-installer.ps1 -InstallerName TransferCove-local-test
./.github/scripts/smoke-installer.ps1 -InstallerPath dist/installer/TransferCove-local-test.exe
```

If the local PowerShell execution policy blocks scripts, invoke them through `powershell -NoProfile -ExecutionPolicy Bypass -File <script-path> <arguments>`. This applies only to that process. Use a clean Windows account or runner for installer smoke tests; the script refuses to run while TransferCove is open or an existing per-user installation is registered.

After changing build/dev dependencies, run `poetry lock` and commit `pyproject.toml` and `poetry.lock` together. Flet CLI's version in the optional `build` group should match the runtime Flet version in the lock file.

## Enforcing checks before merging

The workflow reports checks on PRs. To prevent merging a PR with failed or missing checks, configure a GitHub branch protection rule or ruleset for `dev` (and `main` if desired) and require:

- `Tests and lint (ubuntu-24.04)`
- `Tests and lint (windows-2022)`
- `Windows installer`

Branch protection is a repository setting and is not configured by the workflow file. Add the required checks after their first GitHub Actions run so that GitHub can identify their names.
