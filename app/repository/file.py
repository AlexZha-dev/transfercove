from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import FileRecord


class FileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: FileRecord) -> FileRecord:
        self.session.add(record)
        await self.session.flush()
        return record

    async def get(self, file_id: UUID) -> FileRecord | None:
        return await self.session.get(FileRecord, file_id)

    async def list(self) -> list[FileRecord]:
        result = await self.session.execute(
            select(FileRecord).order_by(FileRecord.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(self, record: FileRecord) -> None:
        await self.session.delete(record)
