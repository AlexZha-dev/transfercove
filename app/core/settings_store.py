import os
from pathlib import Path

from app.core.db import Database
from app.core.settings import Settings
from app.services.settings_service import SettingsService


class SettingsStore:
    def __init__(self) -> None:
        data_dir = Path(
            os.getenv(
                "FLET_APP_STORAGE_DATA",
                Path.cwd() / ".flet-data" / "data",
            )
        )
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
