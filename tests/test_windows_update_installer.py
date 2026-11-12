import asyncio
import hashlib
import sys
from unittest.mock import Mock

import pytest

from app.services import windows_update_installer as windows
from app.services.update_service import UpdateServiceError, VerifiedInstaller
from app.services.windows_update_installer import (
    InstallationTarget,
    InstallerFileError,
    InstallScope,
)


@pytest.mark.parametrize("scope", list(InstallScope))
def test_resolves_running_installation_when_both_scopes_exist(
    monkeypatch, tmp_path, scope
):
    targets = [InstallationTarget(mode, tmp_path / mode.value) for mode in InstallScope]
    monkeypatch.setattr(windows, "_registered_installations", lambda: targets)
    expected = next(target for target in targets if target.scope == scope)
    executable = expected.directory / "TransferCove.exe"

    assert windows.resolve_installation(executable) == expected
    assert windows.installer_arguments(expected) == [
        "/CURRENTUSER" if scope == InstallScope.CURRENT_USER else "/ALLUSERS",
        f"/DIR={expected.directory}",
    ]


@pytest.mark.parametrize("registration", ["missing", "different", "ambiguous"])
def test_rejects_missing_or_ambiguous_installation(monkeypatch, tmp_path, registration):
    targets = []
    if registration == "different":
        targets = [InstallationTarget(InstallScope.CURRENT_USER, tmp_path / "other")]
    elif registration == "ambiguous":
        targets = [InstallationTarget(scope, tmp_path) for scope in InstallScope]
    monkeypatch.setattr(windows, "_registered_installations", lambda: targets)
    with pytest.raises(UpdateServiceError, match="uniquely"):
        windows.resolve_installation(tmp_path / "TransferCove.exe")


@pytest.fixture
def installer(tmp_path):
    path = tmp_path / "setup.exe"
    path.write_bytes(b"verified installer")
    return VerifiedInstaller(
        path, hashlib.sha256(path.read_bytes()).hexdigest(), "0.3.0"
    )


@pytest.fixture
def launch_context(monkeypatch, tmp_path):
    # Platform-independent behavior tests use a normal reader; Windows lock tests below
    # exercise the actual CreateFile sharing flags.
    monkeypatch.setattr(windows, "locked_installer", lambda path: path.open("rb"))
    launcher = Mock()
    monkeypatch.setattr(windows.subprocess, "Popen", launcher)
    target = InstallationTarget(InstallScope.CURRENT_USER, tmp_path / "Installed App")
    return launcher, target


@pytest.mark.parametrize("change", ["replace", "delete"])
def test_modified_or_missing_file_is_never_launched(installer, launch_context, change):
    launcher, target = launch_context
    if change == "replace":
        installer.path.write_bytes(b"replacement")
    else:
        installer.path.unlink()
    with pytest.raises(InstallerFileError):
        windows.verify_and_launch_sync(installer, target)
    launcher.assert_not_called()


def test_launch_preserves_scope_directory_and_interactive_setup(
    installer, launch_context
):
    launcher, target = launch_context
    windows.verify_and_launch_sync(installer, target)
    launcher.assert_called_once_with(
        [str(installer.path), "/CURRENTUSER", f"/DIR={target.directory}"],
        cwd=str(installer.path.parent),
    )


def test_launch_error_keeps_a_valid_download_retryable(installer, launch_context):
    launcher, target = launch_context
    launcher.side_effect = OSError("launch failed")
    with pytest.raises(UpdateServiceError, match="could not start") as error:
        windows.verify_and_launch_sync(installer, target)
    assert not isinstance(error.value, InstallerFileError)


def test_verification_and_launch_run_outside_ui_thread(
    monkeypatch, installer, launch_context
):
    import threading

    launcher, target = launch_context
    ui_thread = threading.get_ident()
    worker_threads = []

    def resolve():
        worker_threads.append(threading.get_ident())
        return target

    monkeypatch.setattr(windows, "resolve_installation", resolve)
    asyncio.run(windows.verify_and_launch(installer))
    assert worker_threads and worker_threads[0] != ui_thread
    launcher.assert_called_once()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file sharing semantics")
def test_windows_lock_denies_write_delete_and_rename(installer):
    with windows.locked_installer(installer.path) as stream:
        assert stream.read() == b"verified installer"
        with pytest.raises(OSError):
            installer.path.write_bytes(b"tampered")
        with pytest.raises(OSError):
            installer.path.unlink()
        with pytest.raises(OSError):
            installer.path.rename(installer.path.with_suffix(".moved"))
    installer.path.write_bytes(b"lock released")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file sharing semantics")
def test_lock_is_held_through_process_creation(monkeypatch, installer, tmp_path):
    def launch(*args, **kwargs):
        with pytest.raises(OSError):
            installer.path.write_bytes(b"changed between hash and launch")

    monkeypatch.setattr(windows.subprocess, "Popen", launch)
    windows.verify_and_launch_sync(
        installer, InstallationTarget(InstallScope.ALL_USERS, tmp_path)
    )
