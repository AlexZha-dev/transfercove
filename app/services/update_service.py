from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit

GITHUB_RELEASES_URL = "https://api.github.com/repos/AlexZha-dev/transfercove/releases"
_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_MAX_RELEASE_PAGE_BYTES = 4 * 1024 * 1024
_MAX_CHECKSUM_BYTES = 4096


class UpdateServiceError(RuntimeError):
    """A release lookup or installer download failed safely."""


class NoCompatibleInstallerError(UpdateServiceError):
    """The newest stable release does not contain the expected Windows assets."""


class ChecksumMismatchError(UpdateServiceError):
    """The downloaded installer did not match its published SHA-256 checksum."""


@dataclass(frozen=True)
class UpdateRelease:
    version: str
    tag_name: str
    release_notes: str
    installer_name: str
    installer_url: str
    checksum_url: str


@dataclass(frozen=True)
class VerifiedInstaller:
    path: Path
    sha256: str
    version: str


class UpdateOperation(StrEnum):
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    CONFIRMING = "confirming"
    INSTALLING = "installing"


@dataclass
class UpdateViewState:
    supported: bool
    status: str = "Update check will run in the background."
    is_error: bool = False
    operation: UpdateOperation = UpdateOperation.IDLE
    release: UpdateRelease | None = None
    installer: VerifiedInstaller | None = None

    @property
    def busy(self) -> bool:
        return self.operation != UpdateOperation.IDLE

    @property
    def checking(self) -> bool:
        return self.operation == UpdateOperation.CHECKING


def should_check_for_updates(
    last_checked_at: datetime | None,
    now: datetime,
    *,
    manual: bool = False,
) -> bool:
    """Apply the 24-hour startup interval while allowing manual retries."""

    if manual or last_checked_at is None:
        return True
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now - last_checked_at >= timedelta(hours=24)


def parse_version(value: str) -> tuple[int, int, int] | None:
    """Parse the project's supported X.Y.Z version format."""

    match = _VERSION_PATTERN.fullmatch(value)
    if match is None:
        return None
    parts = match.groups()
    return int(parts[0]), int(parts[1]), int(parts[2])


def _asset_url(asset: dict[str, Any], *, tag_name: str, name: str) -> str | None:
    url = asset.get("browser_download_url")
    if not isinstance(url, str):
        return None

    parsed = urlsplit(url)
    expected_path = (
        f"/AlexZha-dev/transfercove/releases/download/{quote(tag_name, safe='')}/"
        f"{quote(name, safe='')}"
    )
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or unquote(parsed.path) != expected_path
    ):
        return None
    return url


def select_update(
    releases: list[dict[str, Any]], current_version: str
) -> UpdateRelease | None:
    """Select the highest stable version newer than the installed version."""

    installed = parse_version(current_version)
    if installed is None:
        raise ValueError(f"Unsupported installed version: {current_version}")

    candidates: list[tuple[tuple[int, int, int], dict[str, Any], str]] = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        if release.get("draft") is not False or release.get("prerelease") is not False:
            continue
        if not release.get("published_at"):
            continue

        tag_name = release.get("tag_name")
        if not isinstance(tag_name, str) or not tag_name.startswith("v"):
            continue
        version = tag_name[1:]
        parsed_version = parse_version(version)
        if parsed_version is not None and parsed_version > installed:
            candidates.append((parsed_version, release, version))

    if not candidates:
        return None

    _, release, version = max(candidates, key=lambda candidate: candidate[0])
    installer_name = f"TransferCove-Setup-{version}.exe"
    checksum_name = f"{installer_name}.sha256"
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise NoCompatibleInstallerError(
            f"Release {version} has no compatible Windows installer."
        )

    installer_url = None
    checksum_url = None
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("name") not in {
            installer_name,
            checksum_name,
        }:
            continue
        if asset.get("name") == installer_name:
            installer_url = _asset_url(
                asset, tag_name=f"v{version}", name=installer_name
            )
        else:
            checksum_url = _asset_url(asset, tag_name=f"v{version}", name=checksum_name)

    if installer_url is None or checksum_url is None:
        raise NoCompatibleInstallerError(
            f"Release {version} is missing its Windows installer or SHA-256 checksum."
        )

    notes = release.get("body")
    return UpdateRelease(
        version=version,
        tag_name=f"v{version}",
        release_notes=notes if isinstance(notes, str) else "",
        installer_name=installer_name,
        installer_url=installer_url,
        checksum_url=checksum_url,
    )


class UpdateService:
    def __init__(self, current_version: str) -> None:
        if parse_version(current_version) is None:
            raise ValueError(f"Unsupported installed version: {current_version}")
        self.current_version = current_version

    async def check_for_update(self) -> UpdateRelease | None:
        """Check GitHub without blocking the Flet event loop."""

        return await asyncio.to_thread(self._check_for_update_sync)

    def _check_for_update_sync(self) -> UpdateRelease | None:
        releases: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urlencode({"per_page": 100, "page": page})
            url = f"{GITHUB_RELEASES_URL}?{query}"
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "Accept": "application/vnd.github+json",
                        "User-Agent": "TransferCove-update-checker",
                    },
                )
                with urllib.request.urlopen(request, timeout=20) as response:
                    raw = response.read(_MAX_RELEASE_PAGE_BYTES + 1)
            except HTTPError as error:
                if error.code in {403, 429}:
                    raise UpdateServiceError(
                        "GitHub rate-limited the update check. Try again later."
                    ) from error
                raise UpdateServiceError(
                    f"GitHub could not provide release information (HTTP {error.code})."
                ) from error
            except (URLError, TimeoutError, OSError) as error:
                raise UpdateServiceError(
                    "GitHub is unreachable. Check your internet connection and retry."
                ) from error

            if len(raw) > _MAX_RELEASE_PAGE_BYTES:
                raise UpdateServiceError(
                    "GitHub returned an unexpectedly large release list."
                )
            try:
                data = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise UpdateServiceError(
                    "GitHub returned invalid release information."
                ) from error
            if not isinstance(data, list) or any(
                not isinstance(item, dict) for item in data
            ):
                raise UpdateServiceError("GitHub returned invalid release information.")

            releases.extend(data)
            if len(data) < 100:
                break
            page += 1

        return select_update(releases, self.current_version)

    async def download_and_verify(
        self, release: UpdateRelease, *, destination_dir: Path | None = None
    ) -> VerifiedInstaller:
        """Download an installer and return it only after SHA-256 verification."""

        return await asyncio.to_thread(
            self._download_and_verify_sync, release, destination_dir
        )

    def _download_and_verify_sync(
        self, release: UpdateRelease, destination_dir: Path | None
    ) -> VerifiedInstaller:
        if destination_dir is None:
            local_app_data = os.getenv("LOCALAPPDATA")
            base = (
                Path(local_app_data) if local_app_data else Path(tempfile.gettempdir())
            )
            destination_dir = base / "TransferCove" / "updates" / release.version
        destination_dir.mkdir(parents=True, exist_ok=True)
        installer_path = destination_dir / release.installer_name

        try:
            checksum_request = urllib.request.Request(
                release.checksum_url,
                headers={"User-Agent": "TransferCove-update-checker"},
            )
            with urllib.request.urlopen(checksum_request, timeout=30) as response:
                checksum_data = response.read(_MAX_CHECKSUM_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise UpdateServiceError(
                "The release checksum could not be downloaded. The installer was not run."
            ) from error
        if len(checksum_data) > _MAX_CHECKSUM_BYTES:
            raise UpdateServiceError("The release checksum file is invalid.")

        try:
            checksum_text = checksum_data.decode("ascii").strip()
        except UnicodeDecodeError as error:
            raise UpdateServiceError("The release checksum file is invalid.") from error
        checksum_parts = checksum_text.split()
        if (
            not checksum_parts
            or not _SHA256_PATTERN.fullmatch(checksum_parts[0])
            or len(checksum_parts) > 2
            or (
                len(checksum_parts) == 2
                and checksum_parts[1].lstrip("*") != release.installer_name
            )
        ):
            raise UpdateServiceError("The release checksum file is invalid.")
        expected_hash = checksum_parts[0].lower()

        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{release.installer_name}.",
            suffix=".part",
            dir=destination_dir,
        )
        temporary_path = Path(temporary_name)
        digest = hashlib.sha256()
        try:
            request = urllib.request.Request(
                release.installer_url,
                headers={"User-Agent": "TransferCove-update-checker"},
            )
            with os.fdopen(file_descriptor, "wb") as installer_file:
                try:
                    with urllib.request.urlopen(request, timeout=60) as response:
                        while chunk := response.read(1024 * 1024):
                            installer_file.write(chunk)
                            digest.update(chunk)
                except (HTTPError, URLError, TimeoutError, OSError) as error:
                    raise UpdateServiceError(
                        "The installer download failed. The installer was not run."
                    ) from error
                installer_file.flush()
                os.fsync(installer_file.fileno())

            if not hmac.compare_digest(digest.hexdigest(), expected_hash):
                raise ChecksumMismatchError(
                    "The installer checksum does not match the published SHA-256."
                )
            os.replace(temporary_path, installer_path)
            return VerifiedInstaller(
                installer_path.resolve(), expected_hash, release.version
            )
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
