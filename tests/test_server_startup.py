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

import httpx
import pytest

from app.core.settings import Settings, TransmitterSettings, UvicornConfig
from app.server.manager import ServerManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_embedded_server_migrates_legacy_database(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as database:
        database.execute("CREATE TABLE alembic_version (version_num varchar(32))")
        database.execute("INSERT INTO alembic_version VALUES ('e5f0c48f0c1d')")
        database.execute("CREATE TABLE files (original_name TEXT)")
        database.execute("INSERT INTO files VALUES ('old.txt')")

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
        finally:
            await manager.stop()

    asyncio.run(run_server())
    with sqlite3.connect(database_path) as database:
        assert (
            database.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
            ).fetchone()
            is None
        )


def test_standalone_server_starts_and_persists_upload(tmp_path: Path) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    database_path = tmp_path / "files.db"
    storage_dir = tmp_path / "files"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    storage_dir.mkdir()
    (storage_dir / "old-uuid.txt").write_bytes(b"legacy content")
    with sqlite3.connect(database_path) as database:
        database.execute("CREATE TABLE alembic_version (version_num varchar(32))")
        database.execute("INSERT INTO alembic_version VALUES ('e5f0c48f0c1d')")
        database.execute("CREATE TABLE files (original_name TEXT, storage_name TEXT)")
        database.execute("INSERT INTO files VALUES ('old.txt', 'old-uuid.txt')")

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
                with sqlite3.connect(database_path) as database:
                    assert (
                        database.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
                        ).fetchone()
                        is None
                    )
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
