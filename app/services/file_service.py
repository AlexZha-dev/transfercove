import logging
import ntpath
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from starlette.datastructures import UploadFile

from app.core.upload_limits import DiskSpaceGuard

logger = logging.getLogger(__name__)


class FileUploadError(RuntimeError):
    """Raised when an uploaded file cannot be persisted."""


@dataclass(frozen=True)
class UploadedFile:
    id: UUID
    original_name: str
    storage_name: str
    content_type: str | None
    size_bytes: int
    created_at: datetime


def safe_filename(filename: str) -> str:
    """Discard paths and characters that are unsafe on Windows or Unix."""
    name = re.split(r"[/\\]", filename)[-1]
    name = re.sub(r'[\x00-\x1f\x7f<>:"|?*]', "_", name).strip(" .")
    if not name:
        name = "unnamed"

    # Leave room for a collision suffix, and respect both UTF-8 and UTF-16 limits.
    suffix = Path(name).suffix
    if len(suffix.encode("utf-8")) > 40:
        suffix = ""
    stem = name[: -len(suffix)] if suffix else name
    # Reserve a byte for the prefix needed by Windows device names.
    while len((stem + suffix).encode("utf-8")) > 179:
        stem = stem[:-1]
    name = (stem.rstrip(" .") or "unnamed") + suffix
    # Check the final name on every platform, including superscript COM/LPT
    # digits and names that became reserved after trimming the stem.
    return "_" + name if ntpath.isreserved(name) else name


class FileService:
    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            logger.exception(
                "Upload storage directory is unavailable: path=%s", storage_dir
            )
            raise FileUploadError(
                f"Cannot create or access the upload directory '{storage_dir}': "
                f"{type(error).__name__}: {error}"
            ) from error

    async def upload(
        self,
        upload: UploadFile,
        *,
        reserve_bytes: int = 0,
        disk_guard: DiskSpaceGuard | None = None,
    ) -> UploadedFile:
        original_name = upload.filename or "unnamed"
        name = safe_filename(original_name)
        temporary_path = None
        size = 0
        disk_guard = disk_guard or DiskSpaceGuard()
        try:
            await disk_guard.check(self.storage_dir, reserve_bytes)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".transfercove-",
                suffix=".tmp",
                dir=self.storage_dir,
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                while chunk := await upload.read(1024 * 1024):
                    await disk_guard.write(
                        output, self.storage_dir, reserve_bytes, chunk
                    )
                    size += len(chunk)

            # Both operations publish a complete file without replacing a target.
            # On Unix, rename can replace an existing file, so use a hard link.
            stem, suffix = Path(name).stem, Path(name).suffix
            number = 0
            while True:
                candidate = name if number == 0 else f"{stem} ({number}){suffix}"
                try:
                    destination = self.storage_dir / candidate
                    if os.name == "nt":
                        os.rename(temporary_path, destination)
                    else:
                        os.link(temporary_path, destination)
                    break
                except FileExistsError:
                    number += 1

            return UploadedFile(
                id=uuid4(),
                original_name=original_name,
                storage_name=candidate,
                content_type=upload.content_type,
                size_bytes=size,
                created_at=datetime.now(UTC),
            )
        except Exception as error:
            logger.exception(
                "Upload failed: filename=%r storage_dir=%s",
                original_name,
                self.storage_dir,
            )
            raise FileUploadError(
                f"Cannot save '{original_name}': {type(error).__name__}: {error}"
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    logger.exception(
                        "Could not remove temporary upload: path=%s", temporary_path
                    )
            await upload.close()
