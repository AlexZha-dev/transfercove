from __future__ import annotations

import asyncio
import datetime
import hashlib
import io
import json
import threading
import tomllib
from pathlib import Path
from urllib.error import HTTPError

import pytest

from app.core.settings import AppConfig
from app.services.update_service import (
    ChecksumMismatchError,
    NoCompatibleInstallerError,
    UpdateRelease,
    UpdateService,
    UpdateServiceError,
    parse_version,
    select_update,
    should_check_for_updates,
)


def _release(version: str, *, prerelease: bool = False, draft: bool = False):
    tag = f"v{version}"
    installer = f"TransferCove-Setup-{version}.exe"
    checksum = f"{installer}.sha256"
    base = f"https://github.com/AlexZha-dev/transfercove/releases/download/{tag}"
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "published_at": "2026-01-01T00:00:00Z",
        "body": f"Release {version} notes",
        "assets": [
            {"name": installer, "browser_download_url": f"{base}/{installer}"},
            {"name": checksum, "browser_download_url": f"{base}/{checksum}"},
        ],
    }


class _Response:
    def __init__(self, content: bytes):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self.content
        content, self.content = self.content[:size], self.content[size:]
        return content


def test_version_parser_accepts_only_numeric_stable_versions() -> None:
    assert parse_version("0.2.3") == (0, 2, 3)
    assert parse_version("1.10.0") > parse_version("1.9.9")
    assert parse_version("v1.2.3") is None
    assert parse_version("1.2.3-rc.1") is None
    assert parse_version("01.2.3") is None


def test_application_version_matches_project_release_version() -> None:
    project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(project_file.read_text(encoding="utf-8"))

    assert AppConfig().version == project["project"]["version"]


def test_select_update_chooses_highest_published_stable_release() -> None:
    result = select_update(
        [
            _release("0.2.4"),
            _release("0.3.0", prerelease=True),
            _release("0.9.0", draft=True),
            {**_release("0.8.0"), "tag_name": "v0.8.0-rc.1"},
            _release("0.2.10"),
        ],
        "0.2.3",
    )

    assert result is not None
    assert result.version == "0.2.10"
    assert result.release_notes == "Release 0.2.10 notes"
    assert result.installer_name == "TransferCove-Setup-0.2.10.exe"


def test_select_update_returns_none_when_no_stable_version_is_newer() -> None:
    assert (
        select_update([_release("0.2.3"), _release("0.2.4", prerelease=True)], "0.2.3")
        is None
    )


def test_select_update_requires_both_release_assets() -> None:
    release = _release("0.2.4")
    release["assets"] = release["assets"][:1]

    with pytest.raises(NoCompatibleInstallerError, match="checksum"):
        select_update([release], "0.2.3")


def test_select_update_rejects_installer_asset_from_another_host() -> None:
    release = _release("0.2.4")
    release["assets"][0]["browser_download_url"] = "https://example.com/installer.exe"

    with pytest.raises(NoCompatibleInstallerError):
        select_update([release], "0.2.3")


def test_update_check_reports_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    def limited(*_, **__):
        raise HTTPError("https://api.github.com", 403, "rate limit", {}, io.BytesIO())

    monkeypatch.setattr("urllib.request.urlopen", limited)

    with pytest.raises(UpdateServiceError, match="rate-limited"):
        UpdateService("0.2.3")._check_for_update_sync()


def test_update_check_reads_published_release_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_payload = json.dumps([_release("0.2.4")]).encode()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(release_payload),
    )

    release = UpdateService("0.2.3")._check_for_update_sync()

    assert release is not None
    assert release.version == "0.2.4"
    assert release.release_notes == "Release 0.2.4 notes"


def test_update_check_reports_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*_, **__):
        raise OSError("offline")

    monkeypatch.setattr("urllib.request.urlopen", offline)

    with pytest.raises(UpdateServiceError, match="unreachable"):
        UpdateService("0.2.3")._check_for_update_sync()


def test_update_service_check_runs_off_the_event_loop() -> None:
    service = UpdateService("0.2.3")
    started = threading.Event()
    finish = threading.Event()

    def slow_check():
        started.set()
        finish.wait(timeout=2)
        return None

    service._check_for_update_sync = slow_check

    async def scenario() -> None:
        task = asyncio.create_task(service.check_for_update())
        assert await asyncio.to_thread(started.wait, 1)
        assert not task.done()
        finish.set()
        assert await task is None

    asyncio.run(scenario())


def test_download_verifies_checksum_before_returning_installer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    installer = b"verified installer bytes"
    checksum = f"{hashlib.sha256(installer).hexdigest()}  TransferCove-Setup-0.2.4.exe\n".encode()
    release = UpdateRelease(
        version="0.2.4",
        tag_name="v0.2.4",
        release_notes="",
        installer_name="TransferCove-Setup-0.2.4.exe",
        installer_url="https://github.com/AlexZha-dev/transfercove/releases/download/v0.2.4/TransferCove-Setup-0.2.4.exe",
        checksum_url="https://github.com/AlexZha-dev/transfercove/releases/download/v0.2.4/TransferCove-Setup-0.2.4.exe.sha256",
    )

    def open_url(request, **_):
        url = request.full_url
        return _Response(checksum if url.endswith(".sha256") else installer)

    monkeypatch.setattr("urllib.request.urlopen", open_url)
    verified = asyncio.run(
        UpdateService("0.2.3").download_and_verify(release, destination_dir=tmp_path)
    )

    assert verified.path.read_bytes() == installer
    assert verified.sha256 == hashlib.sha256(installer).hexdigest()
    assert verified.version == release.version
    assert not list(tmp_path.glob("*.part"))


def test_checksum_mismatch_prevents_installer_file_from_being_returned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    installer = b"unverified installer bytes"
    checksum = f"{'0' * 64}  TransferCove-Setup-0.2.4.exe\n".encode()
    release = UpdateRelease(
        version="0.2.4",
        tag_name="v0.2.4",
        release_notes="",
        installer_name="TransferCove-Setup-0.2.4.exe",
        installer_url="https://github.com/AlexZha-dev/transfercove/releases/download/v0.2.4/TransferCove-Setup-0.2.4.exe",
        checksum_url="https://github.com/AlexZha-dev/transfercove/releases/download/v0.2.4/TransferCove-Setup-0.2.4.exe.sha256",
    )

    def open_url(request, **_):
        return _Response(
            checksum if request.full_url.endswith(".sha256") else installer
        )

    monkeypatch.setattr("urllib.request.urlopen", open_url)

    with pytest.raises(ChecksumMismatchError):
        asyncio.run(
            UpdateService("0.2.3").download_and_verify(
                release, destination_dir=tmp_path
            )
        )

    assert not (tmp_path / release.installer_name).exists()
    assert not list(tmp_path.glob("*.part"))


def test_automatic_checks_are_limited_to_24_hours_but_manual_checks_are_not() -> None:
    now = datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC)
    checked = now - datetime.timedelta(hours=23)

    assert not should_check_for_updates(checked, now)
    assert should_check_for_updates(checked, now, manual=True)
    assert should_check_for_updates(now - datetime.timedelta(hours=24), now)
    assert should_check_for_updates(None, now)
