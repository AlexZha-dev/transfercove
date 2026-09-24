from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from starlette.datastructures import Headers, UploadFile

from app.core.db import Database
from app.models.file import FileRecord
from app.services.file_service import FileService, FileUploadError


def run(coroutine):
    return asyncio.run(coroutine)


def make_upload(content: bytes, filename: str = "photo.PNG") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "image/png"}),
    )


def test_file_service_stores_lowercase_extension_and_record(tmp_path: Path) -> None:
    async def scenario() -> tuple[FileRecord, Path, UploadFile]:
        database = Database(
            f"sqlite+aiosqlite:///{(tmp_path / 'service.db').as_posix()}"
        )
        await database.create_table(FileRecord.__table__)
        upload = make_upload(b"image bytes")

        async with database.transaction() as session:
            record = await FileService(session, tmp_path / "files").upload(upload)

        await database.dispose()
        return record, tmp_path / "files", upload

    record, storage_dir, upload = run(scenario())

    assert record.original_name == "photo.PNG"
    assert record.storage_name.endswith(".png")
    assert record.size_bytes == len(b"image bytes")
    assert record.content_type == "image/png"
    assert (storage_dir / record.storage_name).read_bytes() == b"image bytes"
    assert upload.file.closed


def test_file_service_removes_partial_file_when_repository_fails(tmp_path: Path) -> None:
    async def scenario() -> tuple[Path, UploadFile]:
        database = Database(
            f"sqlite+aiosqlite:///{(tmp_path / 'failure.db').as_posix()}"
        )
        await database.create_table(FileRecord.__table__)
        upload = make_upload(b"will not be persisted", "failed.bin")
        storage_dir = tmp_path / "files"

        async with database.transaction() as session:
            service = FileService(session, storage_dir)

            async def fail_create(_record: FileRecord):
                raise RuntimeError("database unavailable")

            service.repository.create = fail_create
            with pytest.raises(FileUploadError, match="database unavailable"):
                await service.upload(upload)

        await database.dispose()
        return storage_dir, upload

    storage_dir, upload = run(scenario())

    assert list(storage_dir.iterdir()) == []
    assert upload.file.closed


def test_file_service_reports_unavailable_storage_directory(tmp_path: Path) -> None:
    async def scenario() -> None:
        database = Database(
            f"sqlite+aiosqlite:///{(tmp_path / 'storage-error.db').as_posix()}"
        )
        storage_path = tmp_path / "not-a-directory"
        storage_path.write_bytes(b"a file, not a directory")

        with pytest.raises(FileUploadError, match="Cannot create or access"):
            FileService(None, storage_path)  # type: ignore[arg-type]

        await database.dispose()

    run(scenario())
