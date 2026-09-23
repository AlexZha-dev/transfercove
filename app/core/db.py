from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import settings

engine = create_async_engine(settings.transmitter.database_url, echo=settings.app.debug)

session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def session_context() -> AsyncGenerator[AsyncSession]:
    async with session_factory() as session, session.begin():
        yield session


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_context() as session:
        yield session
