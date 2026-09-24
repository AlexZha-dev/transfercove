import os
import shutil
from pathlib import Path

from app.core.db import Database
from app.core.settings import Settings
from app.services.settings_service import SettingsService


def migrate_legacy_data(data_dir: Path) -> None:
    """Copy data from the pre-release Windows storage location.

    Flet used ``Your Company`` as the default company component before the
    application metadata was configured. The new build stores data directly
    under ``%APPDATA%\\TransferCove``. Existing files are copied (never
    overwritten or deleted) on the first launch after that change.
    """

    storage_data = os.getenv("FLET_APP_STORAGE_DATA")
    app_data = os.getenv("APPDATA")
    if not storage_data or not app_data:
        return

    target_dir = Path(storage_data).resolve()
    legacy_dir = (Path(app_data) / "Your Company" / "TransferCove" / "data").resolve()
    if target_dir == legacy_dir or not legacy_dir.is_dir():
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    for source in legacy_dir.iterdir():
        destination = target_dir / source.name
        if destination.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


class SettingsStore:
    def __init__(self) -> None:
        data_dir = Path(
            os.getenv(
                "FLET_APP_STORAGE_DATA",
                Path.cwd() / ".flet-data" / "data",
            )
        )
        migrate_legacy_data(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)

        database_path = (data_dir / "desktop-settings.db").absolute()
        database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

        self.database = Database(database_url)
        self.service = SettingsService(self.database)

    async def load(self, fallback: Settings) -> Settings:
        return await self.service.initialize(fallback)

    async def save(self, settings: Settings) -> Settings:
        return await self.service.save(settings)

    async def close(self) -> None:
        await self.database.dispose()
