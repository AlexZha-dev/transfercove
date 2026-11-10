import asyncio
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import make_url

from alembic import command
from app.core.db import ensure_database_directory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
logger = logging.getLogger(__name__)


def upgrade_database(database_url: str) -> None:
    """Apply all Alembic migrations to the configured database."""

    config_path = PROJECT_ROOT / "alembic.ini"
    if not config_path.is_file():
        raise RuntimeError(f"Alembic configuration was not found: {config_path}")

    ensure_database_directory(database_url)
    config = Config(str(config_path))
    # Embedded migrations must preserve the application's handlers and loggers.
    config.attributes["configure_logger"] = False
    # Flet bundles bytecode-only migrations; source checkouts should ignore stale
    # bytecode from other branches that Alembic would otherwise treat as heads.
    source_revision = (
        PROJECT_ROOT / "alembic/versions/e5f0c48f0c1d_repair_files_table.py"
    )
    config.set_main_option(
        "sourceless", "false" if source_revision.is_file() else "true"
    )
    # ConfigParser treats percent signs as interpolation markers.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(config, "head")


def cleanup_legacy_history(database_url: str) -> None:
    """Best-effort cleanup of an existing local history database, never create one."""

    try:
        url = make_url(database_url)
        if url.get_backend_name() != "sqlite":
            logger.warning(
                "Skipping automatic history cleanup for a non-SQLite database; "
                "run Alembic manually if it contains legacy file history."
            )
            return
        if not url.database or url.database == ":memory:":
            return
        database_path = Path(url.database)
        if not database_path.is_file():
            return
        # mode=rw prevents creating a database if it disappears after is_file().
        # Close this connection before Alembic opens its own migration connection.
        with closing(
            sqlite3.connect(
                database_path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.2
            )
        ) as database:
            has_history = database.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='files'"
            ).fetchone()
        if has_history:
            upgrade_database(database_url)
    except Exception:
        # Receiving files no longer needs this database. Leave cleanup retryable
        # on the next start instead of preventing the transfer server from running.
        logger.warning(
            "Could not remove legacy file history; uploads remain available. "
            "Cleanup will be retried on the next start.",
            exc_info=True,
        )


async def cleanup_legacy_history_async(database_url: str) -> None:
    """Clean up old history without blocking Flet's event loop."""

    await asyncio.to_thread(cleanup_legacy_history, database_url)
