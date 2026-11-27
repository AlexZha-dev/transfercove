import asyncio
import datetime
from pathlib import Path

import pytest

from app.core.settings import Settings
from app.core.settings_store import SettingsStore, migrate_legacy_data
from app.models.application_settings import ApplicationSettingsRecord


@pytest.mark.parametrize("legacy", [False, True], ids=["new", "upgrade"])
def test_concurrent_startups_agree_on_persisted_address(monkeypatch, tmp_path, legacy):
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path))
    monkeypatch.delenv("UVICORN__HOST", raising=False)
    candidates = iter(["192.168.1.42", "10.0.0.7"])
    monkeypatch.setattr(
        "app.services.settings_service.get_lan_ipv4", lambda: next(candidates)
    )

    async def scenario():
        first, second = SettingsStore(), SettingsStore()
        fallback = Settings(_env_file=None)
        try:
            if legacy:
                await first.database.create_table(ApplicationSettingsRecord.__table__)
                async with first.database.transaction() as session:
                    session.add(ApplicationSettingsRecord.from_settings(fallback))
            a, b = await asyncio.gather(first.load(fallback), second.load(fallback))
            async with first.database.session() as session:
                saved = await session.get(ApplicationSettingsRecord, 1)
                assert saved.uvicorn_host in {"192.168.1.42", "10.0.0.7"}
                assert a.uvicorn.host == b.uvicorn.host == saved.uvicorn_host
        finally:
            await first.close()
            await second.close()

    asyncio.run(scenario())


def test_migrate_legacy_data_copies_existing_windows_data(
    monkeypatch, tmp_path: Path
) -> None:
    app_data = tmp_path / "appdata"
    legacy_dir = app_data / "Your Company" / "TransferCove" / "data"
    target_dir = app_data / "TransferCove" / "data"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "desktop-settings.db").write_bytes(b"settings")
    (legacy_dir / "files").mkdir()
    (legacy_dir / "files" / "example.bin").write_bytes(b"payload")

    monkeypatch.setenv("APPDATA", str(app_data))
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(target_dir))

    migrate_legacy_data(target_dir)

    assert (target_dir / "desktop-settings.db").read_bytes() == b"settings"
    assert (target_dir / "files" / "example.bin").read_bytes() == b"payload"


def test_migrate_legacy_data_does_not_overwrite_new_data(
    monkeypatch, tmp_path: Path
) -> None:
    app_data = tmp_path / "appdata"
    legacy_dir = app_data / "Your Company" / "TransferCove" / "data"
    target_dir = app_data / "TransferCove" / "data"
    legacy_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)
    (legacy_dir / "desktop-settings.db").write_bytes(b"old")
    (target_dir / "desktop-settings.db").write_bytes(b"new")

    monkeypatch.setenv("APPDATA", str(app_data))
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(target_dir))

    migrate_legacy_data(target_dir)

    assert (target_dir / "desktop-settings.db").read_bytes() == b"new"


def test_update_check_time_persists_separately_from_app_preferences(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "app-data"))
    store = SettingsStore()
    checked_at = datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC)

    async def scenario() -> datetime.datetime | None:
        try:
            await store.load(Settings())
            assert await store.get_last_update_check() is None
            await store.set_last_update_check(checked_at)
            return await store.get_last_update_check()
        finally:
            await store.close()

    saved = asyncio.run(scenario())

    assert saved is not None
    if saved.tzinfo is None:
        saved = saved.replace(tzinfo=datetime.UTC)
    assert saved == checked_at
