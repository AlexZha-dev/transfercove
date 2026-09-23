from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.sql.schema import Table


class Database:
    def __init__(self, url: str, echo: bool = False) -> None:
        self.engine: AsyncEngine = create_async_engine(url, echo=echo)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            async with session.begin():
                yield session

    async def create_table(self, table: Table) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(table.create, checkfirst=True)

    async def dispose(self) -> None:
        await self.engine.dispose()
