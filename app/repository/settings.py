from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application_settings import ApplicationSettingsRecord


class SettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self) -> ApplicationSettingsRecord | None:
        return await self.session.get(ApplicationSettingsRecord, 1)

    async def save(self, record: ApplicationSettingsRecord) -> None:
        current = await self.get()

        if current is None:
            self.session.add(record)
            return

        for column in (
            "app_title",
            "app_description",
            "app_version",
            "app_debug",
            "uvicorn_host",
            "uvicorn_port",
            "uvicorn_log_level",
            "uvicorn_reload",
            "storage_dir",
            "database_url",
            "language",
            "auto_start",
            "open_browser",
        ):
            setattr(current, column, getattr(record, column))
