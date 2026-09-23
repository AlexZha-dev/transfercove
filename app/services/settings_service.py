from app.core.db import Database
from app.core.settings import Settings
from app.models.application_settings import ApplicationSettingsRecord
from app.repository.settings import SettingsRepository


class SettingsService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def initialize(self, fallback: Settings) -> Settings:
        await self.database.create_table(ApplicationSettingsRecord.__table__)

        async with self.database.transaction() as session:
            repository = SettingsRepository(session)
            record = await repository.get()

            if record is None:
                record = ApplicationSettingsRecord.from_settings(fallback)
                session.add(record)
                return fallback

            return record.to_settings()

    async def save(self, settings: Settings) -> Settings:
        async with self.database.transaction() as session:
            repository = SettingsRepository(session)
            await repository.save(
                ApplicationSettingsRecord.from_settings(settings)
            )

        return settings
