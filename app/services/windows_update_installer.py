"""Preserve an installed Windows application's scope and launch verified updates."""

from __future__ import annotations

import asyncio
import ctypes
import hashlib
import hmac
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from app.services.update_service import UpdateServiceError, VerifiedInstaller

APP_ID = "{A6F4C3F3-2DA6-4AF4-9E2F-7C0A0200BEEF}"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_ID}_is1"


class InstallerFileError(UpdateServiceError):
    """The downloaded file must be downloaded and verified again."""


class InstallScope(StrEnum):
    CURRENT_USER = "CurrentUser"
    ALL_USERS = "AllUsers"


@dataclass(frozen=True)
class InstallationTarget:
    scope: InstallScope
    directory: Path


def _kernel32():
    if sys.platform != "win32":
        raise UpdateServiceError("Update installation is supported only on Windows.")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def current_executable() -> Path:
    """Get the host EXE, including when Python is embedded in the Flet process."""
    from ctypes import wintypes

    function = _kernel32().GetModuleFileNameW
    function.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    function.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = function(None, buffer, len(buffer))
    if not length or length >= len(buffer):
        raise UpdateServiceError(
            "Windows could not identify the installed application."
        )
    return Path(buffer.value)


def _registered_installations() -> list[InstallationTarget]:
    import winreg

    targets = []
    for hive, scope in (
        (winreg.HKEY_CURRENT_USER, InstallScope.CURRENT_USER),
        (winreg.HKEY_LOCAL_MACHINE, InstallScope.ALL_USERS),
    ):
        try:
            with winreg.OpenKey(
                hive, UNINSTALL_KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            ) as key:
                directory, kind = winreg.QueryValueEx(key, "InstallLocation")
        except FileNotFoundError:
            continue
        if kind not in {winreg.REG_SZ, winreg.REG_EXPAND_SZ} or not directory:
            continue
        if kind == winreg.REG_EXPAND_SZ:
            directory = winreg.ExpandEnvironmentStrings(directory)
        path = Path(directory)
        if path.is_absolute():
            targets.append(InstallationTarget(scope, path.resolve()))
    return targets


def resolve_installation(executable: Path | None = None) -> InstallationTarget:
    """Match this EXE, not whichever installation happens to be found first."""
    executable = (executable or current_executable()).resolve()
    try:
        matches = [
            target
            for target in _registered_installations()
            if (target.directory / "TransferCove.exe").resolve() == executable
        ]
    except OSError as error:
        raise UpdateServiceError(
            "Windows could not read the installation registration."
        ) from error
    if len(matches) != 1:
        raise UpdateServiceError(
            "The application's installation could not be identified uniquely. "
            "Run TransferCove from its installed location and retry."
        )
    return matches[0]


def installer_arguments(target: InstallationTarget) -> list[str]:
    scope = "/CURRENTUSER" if target.scope == InstallScope.CURRENT_USER else "/ALLUSERS"
    return [scope, f"/DIR={target.directory}"]


@contextmanager
def locked_installer(path: Path) -> Iterator[BinaryIO]:
    """Permit reads/execution while denying writes, deletion, and rename."""
    import msvcrt
    from ctypes import wintypes

    kernel = _kernel32()
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream:
        yield stream


def verify_and_launch_sync(
    installer: VerifiedInstaller, target: InstallationTarget
) -> subprocess.Popen:
    try:
        with locked_installer(installer.path) as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if not hmac.compare_digest(digest, installer.sha256):
                raise InstallerFileError(
                    "The downloaded installer has changed. Download the update again."
                )
            try:
                # Keep the read lock through CreateProcess; the executable is then mapped.
                return subprocess.Popen(
                    [str(installer.path), *installer_arguments(target)],
                    cwd=str(installer.path.parent),
                )
            except OSError as error:
                raise UpdateServiceError(
                    "Windows could not start the installer. Retry the update."
                ) from error
    except OSError as error:
        raise InstallerFileError(
            "The downloaded installer cannot be read. Download the update again."
        ) from error


async def verify_and_launch(installer: VerifiedInstaller) -> None:
    def launch() -> None:
        target = resolve_installation()
        verify_and_launch_sync(installer, target)

    await asyncio.to_thread(launch)
