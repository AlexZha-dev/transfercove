import asyncio
import errno
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.settings import Settings, TransmitterSettings, UploadLimits
from app.core.upload_limits import UploadLimitError, limited_stream


@pytest.fixture
def limited_client(tmp_path: Path):
    config = Settings(
        _env_file=None,
        transmitter=TransmitterSettings(
            storage_dir=tmp_path / "files",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'missing.db').as_posix()}",
        ),
        upload_limits=UploadLimits(
            max_file_mib=1, max_concurrent=1, reserve_mib=0, idle_timeout_seconds=1
        ),
    )
    with TestClient(create_app(config)) as client:
        yield client


def test_size_limit_accepts_boundary_and_rejects_larger(limited_client):
    response = limited_client.post(
        "/v1/files", files={"file": ("ok.bin", b"a" * (1024 * 1024))}
    )
    assert response.status_code == 200
    response = limited_client.post(
        "/v1/files", files={"file": ("large.bin", b"a" * (1024 * 1024 + 1))}
    )
    assert response.status_code == 413
    assert not (
        limited_client.app.state.settings.transmitter.storage_dir / "large.bin"
    ).exists()
    assert limited_client.app.state.active_uploads == 0


def test_rejects_multiple_file_parts_and_releases_slot(limited_client):
    response = limited_client.post(
        "/v1/files", files=[("file", ("one", b"1")), ("file", ("two", b"2"))]
    )
    assert response.status_code == 400
    assert (
        list(limited_client.app.state.settings.transmitter.storage_dir.iterdir()) == []
    )
    assert (
        limited_client.post("/v1/files", files={"file": ("ok", b"ok")}).status_code
        == 200
    )


def test_content_length_cannot_bypass_actual_file_limit(limited_client):
    body = (
        b'--abc\r\nContent-Disposition: form-data; name="file"; filename="large"\r\n\r\n'
        + b"x" * (1024 * 1024 + 1)
        + b"\r\n--abc--\r\n"
    )
    response = limited_client.post(
        "/v1/files",
        content=iter([body[:100], body[100:]]),
        headers={"Content-Type": "multipart/form-data; boundary=abc"},
    )
    assert response.status_code == 413
    assert limited_client.app.state.active_uploads == 0
    assert not list(limited_client.app.state.settings.transmitter.storage_dir.iterdir())


def test_busy_server_rejects_upload(limited_client):
    limited_client.app.state.active_uploads = 1
    try:
        response = limited_client.post("/v1/files", files={"file": ("one", b"1")})
        assert response.status_code == 429
    finally:
        limited_client.app.state.active_uploads = 0


def test_no_free_space_returns_507(limited_client, monkeypatch):
    from app.core import upload_limits

    monkeypatch.setattr(
        upload_limits.shutil,
        "disk_usage",
        lambda _path: type("Usage", (), {"free": 0})(),
    )
    response = limited_client.post("/v1/files", files={"file": ("one", b"1")})
    assert response.status_code == 507
    assert limited_client.app.state.active_uploads == 0
    assert not list(limited_client.app.state.settings.transmitter.storage_dir.iterdir())


def test_disk_full_while_saving_returns_507(limited_client, monkeypatch):
    from app.services.file_service import FileService

    async def fail(_service, _file, **_kwargs):
        raise OSError(errno.ENOSPC, "disk full")

    monkeypatch.setattr(FileService, "upload", fail)
    assert (
        limited_client.post("/v1/files", files={"file": ("one", b"1")}).status_code
        == 507
    )
    assert limited_client.app.state.active_uploads == 0


def test_idle_timeout_without_content_length():
    class SlowRequest:
        async def stream(self):
            await asyncio.sleep(0.1)
            yield b"data"

    async def scenario():
        with pytest.raises(UploadLimitError) as error:
            async for _ in limited_stream(SlowRequest(), max_bytes=10, timeout=0.01):
                pass
        assert error.value.status_code == 408

    asyncio.run(scenario())


def test_actual_simultaneous_requests_obey_limit(tmp_path):
    import httpx

    async def scenario():
        settings = Settings(
            _env_file=None,
            transmitter=TransmitterSettings(
                storage_dir=tmp_path / "files",
                database_url=f"sqlite+aiosqlite:///{(tmp_path / 'missing.db').as_posix()}",
            ),
            upload_limits=UploadLimits(
                max_file_mib=1, max_concurrent=1, reserve_mib=0, idle_timeout_seconds=3
            ),
        )
        app = create_app(settings)
        entered = asyncio.Event()
        release = asyncio.Event()

        async def body():
            yield b'--abc\r\nContent-Disposition: form-data; name="file"; filename="one.txt"\r\n\r\none'
            entered.set()
            await release.wait()
            yield b"\r\n--abc--\r\n"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = asyncio.create_task(
                client.post(
                    "/v1/files",
                    content=body(),
                    headers={"content-type": "multipart/form-data; boundary=abc"},
                )
            )
            await asyncio.wait_for(entered.wait(), 2)
            second = await client.post("/v1/files", files={"file": ("two.txt", b"two")})
            assert second.status_code == 429
            release.set()
            assert (await first).status_code == 200
            assert (
                await client.post("/v1/files", files={"file": ("two.txt", b"two")})
            ).status_code == 200

    asyncio.run(scenario())


def test_malformed_multipart_returns_400(limited_client):
    response = limited_client.post(
        "/v1/files",
        content=b"not-a-valid-multipart",
        headers={"content-type": "multipart/form-data; boundary=abc"},
    )
    assert response.status_code == 400
    assert limited_client.app.state.active_uploads == 0


def test_openapi_describes_file_input(limited_client):
    operation = limited_client.get("/openapi.json").json()["paths"]["/v1/files"]["post"]
    schema = operation["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert schema["properties"]["file"]["format"] == "binary"


def test_stalled_request_closes_spooled_file_and_releases_slot(tmp_path, monkeypatch):
    import tempfile

    import httpx

    from app.core.upload_limits import LimitedMultipartParser

    async def scenario():
        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        monkeypatch.setattr(LimitedMultipartParser, "spool_max_size", 8)
        settings = Settings(
            _env_file=None,
            transmitter=TransmitterSettings(
                storage_dir=tmp_path / "files",
                database_url=f"sqlite+aiosqlite:///{(tmp_path / 'missing.db').as_posix()}",
            ),
            upload_limits=UploadLimits(
                max_file_mib=1, max_concurrent=1, reserve_mib=0, idle_timeout_seconds=1
            ),
        )
        app = create_app(settings)

        async def body():
            yield (
                b'--abc\r\nContent-Disposition: form-data; name="file"; filename="one.txt"\r\n\r\n'
                + b"x" * 100
            )
            await asyncio.sleep(2)
            yield b"\r\n--abc--\r\n"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/files",
                content=body(),
                headers={"content-type": "multipart/form-data; boundary=abc"},
            )
            assert response.status_code == 408
            assert app.state.active_uploads == 0
            assert list((tmp_path / "files").iterdir()) == []
            assert sorted(item.name for item in tmp_path.iterdir()) == ["files"]
            assert (
                await client.post("/v1/files", files={"file": ("two.txt", b"two")})
            ).status_code == 200

    asyncio.run(scenario())


def test_destination_space_failure_cleans_temporary_upload(limited_client, monkeypatch):
    from app.core import upload_limits

    destination = limited_client.app.state.settings.transmitter.storage_dir
    original = upload_limits.shutil.disk_usage

    def usage(path):
        if Path(path) == destination:
            return type("Usage", (), {"free": 0})()
        return original(path)

    monkeypatch.setattr(upload_limits.shutil, "disk_usage", usage)
    response = limited_client.post("/v1/files", files={"file": ("one.txt", b"content")})
    assert response.status_code == 507
    assert list(destination.iterdir()) == []
    assert limited_client.app.state.active_uploads == 0


def test_spool_rollover_failure_returns_507_and_releases_slot(
    limited_client, monkeypatch
):
    import httpx

    from app.core.upload_limits import LimitedMultipartParser

    app = limited_client.app
    app.state.settings.upload_limits.reserve_mib = 1
    monkeypatch.setattr(LimitedMultipartParser, "spool_max_size", 8)
    monkeypatch.setattr(
        "app.core.upload_limits.shutil.disk_usage",
        lambda _path: type("Usage", (), {"free": 1024 * 1024 + 10})(),
    )

    async def body():
        yield b'--abc\r\nContent-Disposition: form-data; name="file"; filename="one.txt"\r\n\r\n12345678'
        yield b"12345678\r\n--abc--\r\n"

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/files",
                content=body(),
                headers={"content-type": "multipart/form-data; boundary=abc"},
            )
            assert response.status_code == 507
            assert app.state.active_uploads == 0
            assert list(app.state.settings.transmitter.storage_dir.iterdir()) == []
            response = await client.post("/v1/files", files={"file": ("ok", b"ok")})
            assert response.status_code == 200

    asyncio.run(scenario())


def test_large_multipart_headers_are_rejected(limited_client):
    body = (
        b'--abc\r\nContent-Disposition: form-data; name="file"; filename="'
        + b"x" * 17000
        + b'"\r\n\r\nhello\r\n--abc--\r\n'
    )
    response = limited_client.post(
        "/v1/files",
        content=body,
        headers={"content-type": "multipart/form-data; boundary=abc"},
    )
    assert response.status_code == 400
    assert limited_client.app.state.active_uploads == 0
    assert (
        list(limited_client.app.state.settings.transmitter.storage_dir.iterdir()) == []
    )


def test_cancelled_request_releases_upload_slot(tmp_path):
    import httpx

    async def scenario():
        settings = Settings(
            _env_file=None,
            transmitter=TransmitterSettings(
                storage_dir=tmp_path / "files",
                database_url=f"sqlite+aiosqlite:///{(tmp_path / 'missing.db').as_posix()}",
            ),
            upload_limits=UploadLimits(
                max_file_mib=1, max_concurrent=1, reserve_mib=0, idle_timeout_seconds=5
            ),
        )
        app = create_app(settings)
        entered = asyncio.Event()

        async def body():
            yield b'--abc\r\nContent-Disposition: form-data; name="file"; filename="one.txt"\r\n\r\npartial'
            entered.set()
            await asyncio.Event().wait()

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            task = asyncio.create_task(
                client.post(
                    "/v1/files",
                    content=body(),
                    headers={"content-type": "multipart/form-data; boundary=abc"},
                )
            )
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert app.state.active_uploads == 0
            assert list((tmp_path / "files").iterdir()) == []
            assert (
                await client.post("/v1/files", files={"file": ("two.txt", b"two")})
            ).status_code == 200

    asyncio.run(scenario())
