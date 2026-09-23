import asyncio
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.core.db import ensure_database_directory

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def upgrade_database(database_url: str) -> None:
    """Apply all Alembic migrations to the configured database."""

    config_path = PROJECT_ROOT / "alembic.ini"
    if not config_path.is_file():
        raise RuntimeError(f"Alembic configuration was not found: {config_path}")

    ensure_database_directory(database_url)
    config = Config(str(config_path))
    # ConfigParser treats percent signs as interpolation markers.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


async def upgrade_database_async(database_url: str) -> None:
    """Run the synchronous Alembic command without blocking Flet's loop."""

    await asyncio.to_thread(upgrade_database, database_url)
