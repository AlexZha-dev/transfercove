import asyncio
import datetime
from pathlib import Path

from app.core.settings import Settings
from app.core.settings_store import SettingsStore, migrate_legacy_data


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
