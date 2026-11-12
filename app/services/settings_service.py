from pathlib import Path
from typing import cast

from sqlalchemy.sql.schema import Table

from app.core.db import Database
from app.core.settings import Settings
from app.models.application_settings import ApplicationSettingsRecord
from app.models.upload_limits import UploadLimitsRecord
from app.repository.settings import SettingsRepository


class SettingsService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def initialize(self, fallback: Settings) -> Settings:
        await self.database.create_table(
            cast(Table, ApplicationSettingsRecord.__table__)
        )

        await self.database.create_table(cast(Table, UploadLimitsRecord.__table__))

        async with self.database.transaction() as session:
            limits = await session.get(UploadLimitsRecord, 1)
            if limits is None:
                limits = UploadLimitsRecord.from_limits(fallback.upload_limits)
                session.add(limits)
            repository = SettingsRepository(session)
            record = await repository.get()

            if record is None:
                record = ApplicationSettingsRecord.from_settings(fallback)
                session.add(record)
                return fallback

            record.app_version = fallback.app.version

            if (
                not Path(record.storage_dir).is_absolute()
                and fallback.transmitter.storage_dir.is_absolute()
            ):
                record.storage_dir = str(fallback.transmitter.storage_dir)

            saved = record.to_settings()
            return saved.model_copy(
                update={
                    "upload_limits": limits.to_limits(),
                    "uvicorn": saved.uvicorn.model_copy(
                        update={"log_level": fallback.uvicorn.log_level}
                    ),
                    "transmitter": saved.transmitter.model_copy(
                        update={"database_url": fallback.transmitter.database_url}
                    ),
                }
            )

    async def save(self, settings: Settings) -> Settings:
        async with self.database.transaction() as session:
            repository = SettingsRepository(session)
            await repository.save(ApplicationSettingsRecord.from_settings(settings))
            limits = await session.get(UploadLimitsRecord, 1)
            if limits is None:
                session.add(UploadLimitsRecord.from_limits(settings.upload_limits))
            else:
                for name, value in settings.upload_limits.model_dump().items():
                    setattr(limits, name, value)

        return settings
