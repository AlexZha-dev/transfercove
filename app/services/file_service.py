import logging
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.models.file import FileRecord
from app.repository.file import FileRepository

logger = logging.getLogger(__name__)


class FileUploadError(RuntimeError):
    """Raised when an uploaded file or its metadata cannot be persisted."""


class FileService:
    def __init__(self, session: AsyncSession, storage_dir: Path) -> None:
        self.repository = FileRepository(session)
        self.storage_dir = storage_dir
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            logger.exception(
                "Upload storage directory is unavailable: path=%s",
                self.storage_dir,
            )
            raise FileUploadError(
                "Cannot create or access the upload directory "
                f"'{self.storage_dir}': {type(error).__name__}: {error}"
            ) from error

    async def upload(self, upload: UploadFile) -> FileRecord:
        file_id = uuid4()

        original_name = upload.filename or "unnamed"
        extension = Path(original_name).suffix.lower()
        storage_name = f"{file_id}{extension}"

        final_path = self.storage_dir / storage_name
        temporary_path = self.storage_dir / f".{storage_name}.tmp"

        size = 0

        stage = "writing the temporary file"

        try:
            with temporary_path.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    output.write(chunk)
                    size += len(chunk)

            stage = "moving the temporary file"
            temporary_path.replace(final_path)

            record = FileRecord(
                id=file_id,
                original_name=original_name,
                storage_name=storage_name,
                content_type=upload.content_type,
                size_bytes=size,
            )

            stage = "saving file metadata to the database"
            return await self.repository.create(record)

        except Exception as error:
            logger.exception(
                "Upload failed: stage=%s filename=%r storage_dir=%s "
                "temporary_path=%s final_path=%s",
                stage,
                original_name,
                self.storage_dir,
                temporary_path,
                final_path,
            )
            self._cleanup_upload_files(temporary_path, final_path)
            if isinstance(error, FileUploadError):
                raise
            raise FileUploadError(
                f"Upload failed while {stage} for '{original_name}': "
                f"{type(error).__name__}: {error}"
            ) from error

        finally:
            await upload.close()

    @staticmethod
    def _cleanup_upload_files(*paths: Path) -> None:
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("Could not remove failed upload file: path=%s", path)
