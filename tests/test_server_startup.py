"""Exercise the standalone upload server over a real HTTP connection."""

from __future__ import annotations

import asyncio
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.controller.controller import AppController
from app.core.settings import Settings, TransmitterSettings, UvicornConfig
from app.server.manager import ServerError, ServerErrorCode, ServerManager, ServerState

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_storage_failure_retains_structured_cause(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise PermissionError("storage denied")

    monkeypatch.setattr("app.server.manager.create_app", fail)

    async def scenario():
        manager = ServerManager()
        with pytest.raises(ServerError) as caught:
            await manager.start(
                Settings(transmitter=TransmitterSettings(storage_dir=tmp_path))
            )
        assert caught.value.code == ServerErrorCode.STORAGE_UNAVAILABLE
        assert isinstance(caught.value.__cause__, PermissionError)
        assert manager.state == ServerState.ERROR

    asyncio.run(scenario())


def test_occupied_port_does_not_exit_the_desktop_process(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        async def scenario():
            manager = ServerManager(startup_timeout=2)
            settings = Settings(
                uvicorn=UvicornConfig(host="127.0.0.1", port=port),
                transmitter=TransmitterSettings(storage_dir=tmp_path),
            )
            with pytest.raises(ServerError) as caught:
                await manager.start(settings)
            assert caught.value.code == ServerErrorCode.UNKNOWN
            assert manager.state == ServerState.ERROR

        asyncio.run(scenario())


def test_startup_timeout_has_a_structured_code(monkeypatch, tmp_path):
    async def timed_out(*args):
        raise TimeoutError("readiness timeout")

    async def scenario():
        manager = ServerManager()
        monkeypatch.setattr(manager, "_wait_until_ready", timed_out)
        with pytest.raises(ServerError) as caught:
            await manager.start(
                Settings(transmitter=TransmitterSettings(storage_dir=tmp_path))
            )
        assert caught.value.code == ServerErrorCode.STARTUP_TIMEOUT
        assert manager.state == ServerState.ERROR

    asyncio.run(scenario())


def test_language_change_keeps_running_server_and_uploads_available(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    settings = Settings(
        uvicorn=UvicornConfig(host="127.0.0.1", port=port),
        transmitter=TransmitterSettings(
            storage_dir=tmp_path / "files",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'files.db').as_posix()}",
        ),
    )

    async def scenario():
        controller = AppController.__new__(AppController)
        controller.settings = settings
        controller.server_manager = ServerManager()
        controller.settings_store = SimpleNamespace(
            save=AsyncMock(side_effect=lambda value: value)
        )
        controller.notify = Mock()
        try:
            await controller.server_manager.start(settings)
            server = controller.server_manager._server
            async with httpx.AsyncClient(trust_env=False) as client:
                started, resume = asyncio.Event(), asyncio.Event()

                async def multipart():
                    yield (
                        b'--boundary\r\nContent-Disposition: form-data; name="file"; '
                        b'filename="language.txt"\r\nContent-Type: text/plain\r\n\r\ncontent'
                    )
                    started.set()
                    await resume.wait()
                    yield b"\r\n--boundary--\r\n"

                upload = asyncio.create_task(
                    client.post(
                        f"http://127.0.0.1:{port}/v1/files",
                        content=multipart(),
                        headers={
                            "Content-Type": "multipart/form-data; boundary=boundary"
                        },
                    )
                )
                await asyncio.wait_for(started.wait(), timeout=5)
                updated = settings.model_copy(deep=True)
                updated.desktop.language = "ru"
                assert await controller.save_settings(updated)
                assert controller.server_manager._server is server
                assert controller.server_manager.is_running
                resume.set()
                response = await upload
                response.raise_for_status()
            assert (
                settings.transmitter.storage_dir / "language.txt"
            ).read_bytes() == b"content"
        finally:
            await controller.server_manager.stop()

    asyncio.run(scenario())


@pytest.mark.parametrize("history", ["legacy", "missing", "corrupt", "unavailable"])
def test_embedded_server_cleans_history_without_requiring_database(
    tmp_path: Path, history: str
) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    database_path = tmp_path / "legacy.db"
    if history == "legacy":
        with sqlite3.connect(database_path) as database:
            database.execute("CREATE TABLE alembic_version (version_num varchar(32))")
            database.execute("INSERT INTO alembic_version VALUES ('e5f0c48f0c1d')")
            database.execute("CREATE TABLE files (original_name TEXT)")
            database.execute("INSERT INTO files VALUES ('old.txt')")
    elif history == "corrupt":
        database_path.write_bytes(b"not a database")
    elif history == "unavailable":
        database_path.write_bytes(b"not a directory")
        database_path = database_path / "files.db"

    config = Settings(
        uvicorn=UvicornConfig(host="127.0.0.1", port=port),
        transmitter=TransmitterSettings(
            storage_dir=tmp_path / "files",
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
        ),
    )

    async def run_server() -> None:
        manager = ServerManager()
        try:
            await manager.start(config)
            assert manager.is_running
            async with httpx.AsyncClient(trust_env=False) as client:
                response = await client.post(
                    f"http://127.0.0.1:{port}/v1/files",
                    files={"file": ("smoke.txt", b"new upload", "text/plain")},
                )
                response.raise_for_status()
                assert response.json()["saved_filename"] == "smoke.txt"
                assert (
                    config.transmitter.storage_dir / "smoke.txt"
                ).read_bytes() == b"new upload"
        finally:
            await manager.stop()

    asyncio.run(run_server())
    if history == "legacy":
        with sqlite3.connect(database_path) as database:
            assert (
                database.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
                ).fetchone()
                is None
            )
    elif history == "corrupt":
        assert database_path.read_bytes() == b"not a database"
    else:
        assert not database_path.exists()


@pytest.mark.parametrize("history", ["legacy", "missing", "corrupt"])
def test_standalone_server_starts_and_persists_upload(
    tmp_path: Path, history: str
) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    database_path = tmp_path / "files.db"
    storage_dir = tmp_path / "files"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    storage_dir.mkdir()
    (storage_dir / "old-uuid.txt").write_bytes(b"legacy content")
    if history == "legacy":
        with sqlite3.connect(database_path) as database:
            database.execute("CREATE TABLE alembic_version (version_num varchar(32))")
            database.execute("INSERT INTO alembic_version VALUES ('e5f0c48f0c1d')")
            database.execute(
                "CREATE TABLE files (original_name TEXT, storage_name TEXT)"
            )
            database.execute("INSERT INTO files VALUES ('old.txt', 'old-uuid.txt')")
    elif history == "corrupt":
        database_path.write_bytes(b"not a database")

    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(
            ("APP__", "UVICORN__", "TRANSMITTER__", "DESKTOP__", "FLET_")
        )
    }
    environment.update(
        {
            "APP__DEBUG": "False",
            "UVICORN__HOST": "127.0.0.1",
            "UVICORN__PORT": str(port),
            "UVICORN__RELOAD": "False",
            "TRANSMITTER__STORAGE_DIR": str(storage_dir),
            "TRANSMITTER__DATABASE_URL": database_url,
        }
    )
    log_path = tmp_path / "server.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "app.server_start_up"],
            cwd=PROJECT_ROOT,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=2, trust_env=False
            ) as client:
                deadline = monotonic() + 20
                while monotonic() < deadline:
                    if process.poll() is not None:
                        pytest.fail("The standalone server exited during startup")
                    try:
                        response = client.get("/health")
                        if response.status_code == 200:
                            assert response.json() == {"status": "ok"}
                            break
                    except httpx.TransportError:
                        pass
                    sleep(0.1)
                else:
                    pytest.fail("The standalone server did not become ready")

                assert "TransferCove" in client.get("/").raise_for_status().text
                for asset in ("upload.css", "upload.js", "locales/en.js"):
                    client.get(f"/static/{asset}").raise_for_status()
                assert client.post("/v1/files", data={}).status_code == 422

                content = b"TransferCove CI upload smoke test\n"
                response = client.post(
                    "/v1/files",
                    files={"file": ("smoke.txt", content, "text/plain")},
                )
                response.raise_for_status()
                payload = response.json()
                assert payload["filename"] == "smoke.txt"
                assert payload["saved_filename"] == "smoke.txt"
                assert payload["size"] == len(content)

                assert (storage_dir / "smoke.txt").read_bytes() == content
                assert (storage_dir / "old-uuid.txt").read_bytes() == b"legacy content"
                if history == "legacy":
                    with sqlite3.connect(database_path) as database:
                        assert (
                            database.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
                            ).fetchone()
                            is None
                        )
                elif history == "corrupt":
                    assert database_path.read_bytes() == b"not a database"
                else:
                    assert not database_path.exists()
                assert process.poll() is None
        except BaseException:
            print(log_path.read_text(encoding="utf-8", errors="replace"))
            raise
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
