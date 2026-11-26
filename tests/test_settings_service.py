from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.db import Database
from app.core.settings import (
    AppConfig,
    Settings,
    TransmitterSettings,
    UploadLimits,
    UvicornConfig,
)
from app.services.settings_service import SettingsService


def test_settings_service_initializes_and_persists_preferences(tmp_path: Path) -> None:
    async def scenario() -> tuple[Settings, Settings]:
        database = Database(
            f"sqlite+aiosqlite:///{(tmp_path / 'settings.db').as_posix()}"
        )
        service = SettingsService(database)
        fallback = Settings(
            app=AppConfig(title="First title", version="0.3.0"),
            uvicorn=UvicornConfig(log_level="warning"),
            transmitter=TransmitterSettings(
                storage_dir=tmp_path / "first-files",
                database_url="sqlite+aiosqlite:///first.db",
            ),
        )

        first = await service.initialize(fallback)
        changed = first.model_copy(
            update={
                "app": AppConfig(title="Saved title", version="0.2.3"),
                "uvicorn": first.uvicorn.model_copy(update={"log_level": "debug"}),
                "transmitter": first.transmitter.model_copy(
                    update={"database_url": "sqlite+aiosqlite:///saved.db"}
                ),
                "desktop": first.desktop.model_copy(
                    update={"auto_start": True, "language": "ru"}
                ),
            }
        )
        await service.save(changed)
        loaded = await service.initialize(fallback)
        await database.dispose()
        return first, loaded

    first, loaded = asyncio.run(scenario())

    assert first.app.title == "First title"
    assert loaded.app.title == "Saved title"
    assert loaded.app.version == "0.3.0"
    assert loaded.desktop.auto_start is True
    assert loaded.desktop.language == "ru"
    assert loaded.uvicorn.log_level == "warning"
    assert loaded.transmitter.database_url == "sqlite+aiosqlite:///first.db"


def test_upload_limits_persist_with_existing_settings_database(tmp_path: Path) -> None:
    async def scenario():
        database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'old.db').as_posix()}")
        from app.models.application_settings import ApplicationSettingsRecord

        await database.create_table(ApplicationSettingsRecord.__table__)
        fallback = Settings()
        async with database.transaction() as session:
            session.add(ApplicationSettingsRecord.from_settings(fallback))
        service = SettingsService(database)
        loaded = await service.initialize(fallback)
        assert loaded.upload_limits == UploadLimits()
        limits = UploadLimits(
            max_file_mib=20, max_concurrent=3, reserve_mib=10, idle_timeout_seconds=8
        )
        await service.save(loaded.model_copy(update={"upload_limits": limits}))
        reloaded = await service.initialize(fallback)
        await database.dispose()
        assert reloaded.upload_limits == limits
        assert reloaded.app.title == fallback.app.title

    asyncio.run(scenario())


def test_lan_address_migration_retries_and_preserves_manual_choice(
    tmp_path, monkeypatch
):
    from app.models.application_settings import ApplicationSettingsRecord

    async def scenario():
        database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'old.db').as_posix()}")
        await database.create_table(ApplicationSettingsRecord.__table__)
        async with database.transaction() as session:
            session.add(ApplicationSettingsRecord.from_settings(Settings()))
        service = SettingsService(database)
        monkeypatch.setattr("app.services.settings_service.get_lan_ipv4", lambda: None)
        first = await service.initialize(Settings())
        assert first.uvicorn.host == "127.0.0.1"
        assert service.lan_detection_pending
        await service.save(first)
        monkeypatch.setattr(
            "app.services.settings_service.get_lan_ipv4", lambda: "192.168.1.42"
        )
        migrated = await service.initialize(Settings())
        assert migrated.uvicorn.host == "192.168.1.42"
        migrated.uvicorn.host = "127.0.0.1"
        await service.save(migrated)
        assert (await service.initialize(Settings())).uvicorn.host == "127.0.0.1"
        await database.dispose()

    asyncio.run(scenario())


def test_new_settings_detect_lan_and_respect_explicit_host(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.settings_service.get_lan_ipv4", lambda: "192.168.1.42"
    )

    async def scenario(name, fallback):
        database = Database(f"sqlite+aiosqlite:///{(tmp_path / name).as_posix()}")
        result = await SettingsService(database).initialize(fallback)
        await database.dispose()
        return result.uvicorn.host

    assert asyncio.run(scenario("new.db", Settings())) == "192.168.1.42"
    explicit = Settings(uvicorn=UvicornConfig(host="127.0.0.1"))
    assert asyncio.run(scenario("explicit.db", explicit)) == "127.0.0.1"
    monkeypatch.setenv("UVICORN__HOST", "127.0.0.1")
    assert asyncio.run(scenario("env.db", Settings())) == "127.0.0.1"
