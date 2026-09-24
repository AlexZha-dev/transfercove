from pathlib import Path

from app.core.settings_store import migrate_legacy_data


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
