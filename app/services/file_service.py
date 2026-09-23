from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.models.file import FileRecord
from app.repository.file import FileRepository


class FileService:
    def __init__(self, session: AsyncSession, storage_dir: Path) -> None:
        self.repository = FileRepository(session)
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def upload(self, upload: UploadFile) -> FileRecord:
        file_id = uuid4()

        original_name = upload.filename or "unnamed"
        extension = Path(original_name).suffix.lower()
        storage_name = f"{file_id}{extension}"

        final_path = self.storage_dir / storage_name
        temporary_path = self.storage_dir / f".{storage_name}.tmp"

        size = 0

        try:
            with temporary_path.open("wb") as output:
                while chunk := await upload.read(1024 * 1024):
                    output.write(chunk)
                    size += len(chunk)

            temporary_path.replace(final_path)

            record = FileRecord(
                id=file_id,
                original_name=original_name,
                storage_name=storage_name,
                content_type=upload.content_type,
                size_bytes=size,
            )

            return await self.repository.create(record)

        except Exception:
            temporary_path.unlink(missing_ok=True)
            final_path.unlink(missing_ok=True)
            raise

        finally:
            await upload.close()
