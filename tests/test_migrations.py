from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from sqlalchemy import inspect

from app.core.db import Database
from app.core.migrations import upgrade_database


def test_database_migrations_create_application_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "migrated.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    upgrade_database(database_url)

    async def table_names() -> set[str]:
        database = Database(database_url)
        async with database.engine.connect() as connection:
            names = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
        await database.dispose()
        return names

    assert asyncio.run(table_names()) >= {
        "alembic_version",
        "files",
        "application_settings",
    }


def test_database_migrations_repair_missing_files_table(tmp_path: Path) -> None:
    database_path = tmp_path / "broken.db"
    with sqlite3.connect(database_path) as database:
        database.execute("create table alembic_version (version_num varchar(32))")
        database.execute(
            "insert into alembic_version (version_num) values (?)",
            ("d0b65365c266",),
        )

    upgrade_database(f"sqlite+aiosqlite:///{database_path.as_posix()}")

    with sqlite3.connect(database_path) as database:
        tables = {
            row[0]
            for row in database.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }

    assert "files" in tables
