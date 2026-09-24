from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.engine import make_url
from sqlalchemy.sql.schema import Table


def ensure_database_directory(url: str) -> None:
    parsed_url = make_url(url)
    if parsed_url.get_backend_name() != "sqlite":
        return

    database_path = parsed_url.database
    if not database_path or database_path == ":memory:" or database_path.startswith(
        "file:"
    ):
        return

    Path(database_path).parent.mkdir(parents=True, exist_ok=True)


class Database:
    def __init__(self, url: str, echo: bool = False) -> None:
        ensure_database_directory(url)
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
