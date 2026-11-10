from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import pytest
from starlette.datastructures import Headers, UploadFile

from app.services.file_service import FileService, FileUploadError, safe_filename


def run(coroutine):
    return asyncio.run(coroutine)


def make_upload(content: bytes, filename: str = "photo.PNG") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "image/png"}),
    )


def test_file_service_preserves_name_and_content(tmp_path: Path) -> None:
    async def scenario():
        upload = make_upload(b"image bytes")
        record = await FileService(tmp_path / "files").upload(upload)
        return record, tmp_path / "files", upload

    record, storage_dir, upload = run(scenario())

    assert record.original_name == "photo.PNG"
    assert record.storage_name == "photo.PNG"
    assert record.size_bytes == len(b"image bytes")
    assert record.content_type == "image/png"
    assert (storage_dir / record.storage_name).read_bytes() == b"image bytes"
    assert upload.file.closed


def test_file_service_removes_partial_file_when_read_fails(tmp_path: Path) -> None:
    async def scenario() -> tuple[Path, UploadFile]:
        upload = make_upload(b"will not be persisted", "failed.bin")
        storage_dir = tmp_path / "files"

        async def fail_read(_size):
            raise OSError("connection interrupted")

        upload.read = fail_read
        with pytest.raises(FileUploadError, match="connection interrupted"):
            await FileService(storage_dir).upload(upload)
        return storage_dir, upload

    storage_dir, upload = run(scenario())

    assert list(storage_dir.iterdir()) == []
    assert upload.file.closed


def test_file_service_reports_unavailable_storage_directory(tmp_path: Path) -> None:
    async def scenario() -> None:
        storage_path = tmp_path / "not-a-directory"
        storage_path.write_bytes(b"a file, not a directory")

        with pytest.raises(FileUploadError, match="Cannot create or access"):
            FileService(storage_path)

    run(scenario())


def test_existing_names_are_never_overwritten(tmp_path: Path) -> None:
    (tmp_path / "photo.PNG").write_bytes(b"existing")
    (tmp_path / "photo (1).PNG").write_bytes(b"other")
    result = run(FileService(tmp_path).upload(make_upload(b"new")))
    assert result.storage_name == "photo (2).PNG"
    assert (tmp_path / "photo.PNG").read_bytes() == b"existing"
    assert (tmp_path / "photo (1).PNG").read_bytes() == b"other"
    assert (tmp_path / result.storage_name).read_bytes() == b"new"


def test_simultaneous_uploads_do_not_overwrite(tmp_path: Path) -> None:
    def upload(content: bytes):
        return run(FileService(tmp_path).upload(make_upload(content)))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(upload, [b"one", b"two"]))
    assert len({result.storage_name for result in results}) == 2
    assert {(tmp_path / result.storage_name).read_bytes() for result in results} == {
        b"one",
        b"two",
    }


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("../../photo.txt", "photo.txt"),
        (r"C:\\tmp\\photo.txt", "photo.txt"),
        ("CON.txt", "_CON.txt"),
        ("..", "unnamed"),
        ("a:b?.txt", "a_b_.txt"),
    ],
)
def test_safe_filename(name: str, expected: str) -> None:
    assert safe_filename(name) == expected
