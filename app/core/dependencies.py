from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Database


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database = request.app.state.database

    async with database.transaction() as session:
        yield session
