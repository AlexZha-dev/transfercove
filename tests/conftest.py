from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.settings import Settings, TransmitterSettings
from app.models.file import FileRecord


@pytest.fixture
def app_settings(tmp_path: Path) -> Settings:
    """Create an isolated configuration for each HTTP integration test."""

    database_path = tmp_path / "files.db"
    return Settings(
        transmitter=TransmitterSettings(
            storage_dir=tmp_path / "files",
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
        )
    )


@pytest.fixture
def client(app_settings: Settings):
    """Return a FastAPI test client with the files table ready for uploads."""

    application = create_app(app_settings)
    asyncio.run(application.state.database.create_table(FileRecord.__table__))

    with TestClient(application) as test_client:
        yield test_client
