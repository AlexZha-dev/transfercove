import asyncio
from pathlib import Path
from typing import cast

from sqlalchemy.sql.schema import Table

from app.core.db import Database
from app.core.network import get_lan_ipv4
from app.core.settings import Settings
from app.models.application_settings import ApplicationSettingsRecord
from app.models.settings_migration import LAN_ADDRESS_MIGRATION_ID, SettingsMigration
from app.models.upload_limits import UploadLimitsRecord
from app.repository.settings import SettingsRepository


class SettingsService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.lan_detection_pending = False

    async def initialize(self, fallback: Settings) -> Settings:
        self.lan_detection_pending = False
        await self.database.create_table(
            cast(Table, ApplicationSettingsRecord.__table__)
        )

        await self.database.create_table(cast(Table, UploadLimitsRecord.__table__))
        await self.database.create_table(cast(Table, SettingsMigration.__table__))

        address = await self._detect_address_if_needed(fallback)
        async with self.database.transaction(immediate=True) as session:
            limits = await session.get(UploadLimitsRecord, 1)
            if limits is None:
                limits = UploadLimitsRecord.from_limits(fallback.upload_limits)
                session.add(limits)
            repository = SettingsRepository(session)
            record = await repository.get()
            migration = await session.get(SettingsMigration, LAN_ADDRESS_MIGRATION_ID)

            if record is None:
                record = ApplicationSettingsRecord.from_settings(fallback)
                session.add(record)
                explicit_host = "host" in fallback.uvicorn.model_fields_set
            else:
                explicit_host = False

            if migration is None:
                if record.uvicorn_host == "127.0.0.1" and not explicit_host:
                    if address:
                        record.uvicorn_host = address
                    else:
                        self.lan_detection_pending = True
                if not self.lan_detection_pending:
                    session.add(SettingsMigration(id=LAN_ADDRESS_MIGRATION_ID))

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

    async def _detect_address_if_needed(self, fallback: Settings) -> str | None:
        async with self.database.session() as session:
            if await session.get(SettingsMigration, LAN_ADDRESS_MIGRATION_ID):
                return None
            record = await session.get(ApplicationSettingsRecord, 1)
            if record is None:
                if "host" in fallback.uvicorn.model_fields_set:
                    return None
            elif record.uvicorn_host != "127.0.0.1":
                return None

        # Another process may finish the migration while the network lookup runs.
        # initialize() rechecks the marker and host under the write lock.
        return await asyncio.to_thread(get_lan_ipv4)

    async def save(self, settings: Settings) -> Settings:
        async with self.database.transaction(immediate=True) as session:
            if (
                not self.lan_detection_pending or settings.uvicorn.host != "127.0.0.1"
            ) and await session.get(
                SettingsMigration, LAN_ADDRESS_MIGRATION_ID
            ) is None:
                session.add(SettingsMigration(id=LAN_ADDRESS_MIGRATION_ID))
            repository = SettingsRepository(session)
            await repository.save(ApplicationSettingsRecord.from_settings(settings))
            limits = await session.get(UploadLimitsRecord, 1)
            if limits is None:
                session.add(UploadLimitsRecord.from_limits(settings.upload_limits))
            else:
                for name, value in settings.upload_limits.model_dump().items():
                    setattr(limits, name, value)

        if settings.uvicorn.host != "127.0.0.1":
            self.lan_detection_pending = False
        return settings
