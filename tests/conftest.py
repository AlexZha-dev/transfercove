from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.application import create_app
from app.core.settings import Settings, TransmitterSettings


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
    """Return a FastAPI test client with isolated storage and settings."""

    application = create_app(app_settings)
    with TestClient(application) as test_client:
        yield test_client
