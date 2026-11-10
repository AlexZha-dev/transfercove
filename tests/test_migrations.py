from __future__ import annotations

import asyncio
import py_compile
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.core import migrations
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

    names = asyncio.run(table_names())
    assert names >= {"alembic_version", "application_settings"}
    assert "files" not in names


def test_database_migrations_handle_missing_files_table(tmp_path: Path) -> None:
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

    assert "files" not in tables


def test_migration_deletes_old_records_preserving_settings_and_files(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "legacy.db"
    old_file = tmp_path / "old-uuid.txt"
    old_file.write_bytes(b"existing content")
    with sqlite3.connect(database_path) as database:
        database.execute("CREATE TABLE alembic_version (version_num varchar(32))")
        database.execute("INSERT INTO alembic_version VALUES ('e5f0c48f0c1d')")
        database.execute("CREATE TABLE files (original_name TEXT, storage_name TEXT)")
        database.execute("INSERT INTO files VALUES ('old.txt', 'old-uuid.txt')")
        database.execute(
            "CREATE TABLE application_settings (id INTEGER, language TEXT)"
        )
        database.execute("INSERT INTO application_settings VALUES (1, 'en')")

    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    upgrade_database(database_url)
    upgrade_database(database_url)

    with sqlite3.connect(database_path) as database:
        assert (
            database.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
            ).fetchone()
            is None
        )
        assert database.execute(
            "SELECT language FROM application_settings"
        ).fetchone() == ("en",)
    assert old_file.read_bytes() == b"existing content"


def test_migration_handles_legacy_revision_with_no_files_table(tmp_path: Path) -> None:
    database_path = tmp_path / "missing.db"
    with sqlite3.connect(database_path) as database:
        database.execute("CREATE TABLE alembic_version (version_num varchar(32))")
        database.execute("INSERT INTO alembic_version VALUES ('e5f0c48f0c1d')")

    upgrade_database(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    with sqlite3.connect(database_path) as database:
        assert database.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("f24a9d3a1b62",)


def test_bytecode_only_migrations_are_supported(tmp_path: Path, monkeypatch) -> None:
    from app.core import migrations

    original_root = migrations.PROJECT_ROOT
    packaged_root = tmp_path / "packaged"
    versions = packaged_root / "alembic" / "versions"
    versions.mkdir(parents=True)
    shutil.copy(original_root / "alembic.ini", packaged_root / "alembic.ini")
    shutil.copy(
        original_root / "alembic" / "env.py", packaged_root / "alembic" / "env.py"
    )
    for source in (original_root / "alembic" / "versions").glob("*.py"):
        py_compile.compile(
            str(source), cfile=str(versions / f"{source.stem}.pyc"), doraise=True
        )

    monkeypatch.setattr(migrations, "PROJECT_ROOT", packaged_root)
    database_path = tmp_path / "packaged.db"
    migrations.upgrade_database(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    with sqlite3.connect(database_path) as database:
        assert database.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("f24a9d3a1b62",)


@pytest.mark.parametrize("state", ["missing", "directory", "empty", "cleaned"])
def test_cleanup_does_not_create_or_migrate_unused_databases(
    tmp_path: Path, monkeypatch, state: str
) -> None:
    database_path = tmp_path / "history.db"
    if state == "directory":
        database_path.mkdir()
    elif state in {"empty", "cleaned"}:
        with closing(sqlite3.connect(database_path)) as database:
            if state == "cleaned":
                database.execute("CREATE TABLE application_settings (language TEXT)")
                database.commit()

    def unexpected_migration(_url):
        pytest.fail("Unused history databases must not be migrated")

    monkeypatch.setattr(migrations, "upgrade_database", unexpected_migration)
    migrations.cleanup_legacy_history(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    if state == "missing":
        assert not database_path.exists()


@pytest.mark.parametrize(
    "database_url",
    ["sqlite+aiosqlite:///:memory:", "postgresql://localhost/history", "invalid-url"],
)
def test_cleanup_does_not_connect_to_unusable_urls(monkeypatch, database_url) -> None:
    def unexpected_connection(*args, **kwargs):
        pytest.fail("Cleanup must not open an unsupported database")

    monkeypatch.setattr(sqlite3, "connect", unexpected_connection)
    migrations.cleanup_legacy_history(database_url)


def test_cleanup_warns_and_retries_when_migration_fails(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    database_path = tmp_path / "legacy.db"
    with closing(sqlite3.connect(database_path)) as database:
        database.execute("CREATE TABLE alembic_version (version_num varchar(32))")
        database.execute("INSERT INTO alembic_version VALUES ('e5f0c48f0c1d')")
        database.execute("CREATE TABLE files (original_name TEXT)")
        database.execute("INSERT INTO files VALUES ('old.txt')")
        database.commit()

    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    with monkeypatch.context() as patch:

        def fail_migration(_url):
            raise OSError("database is read-only")

        patch.setattr(migrations, "upgrade_database", fail_migration)
        migrations.cleanup_legacy_history(database_url)
    assert "Could not remove legacy file history" in caplog.text
    with closing(sqlite3.connect(database_path)) as database:
        assert database.execute("SELECT original_name FROM files").fetchone() == (
            "old.txt",
        )

    migrations.cleanup_legacy_history(database_url)
    with closing(sqlite3.connect(database_path)) as database:
        assert (
            database.execute(
                "SELECT name FROM sqlite_master WHERE name='files'"
            ).fetchone()
            is None
        )


def test_cleanup_handles_locked_database(tmp_path: Path, caplog) -> None:
    database_path = tmp_path / "locked.db"
    with closing(sqlite3.connect(database_path)) as database:
        database.execute("CREATE TABLE files (original_name TEXT)")
        database.commit()
        database.execute("BEGIN EXCLUSIVE")
        try:
            migrations.cleanup_legacy_history(
                f"sqlite+aiosqlite:///{database_path.as_posix()}"
            )
        finally:
            database.rollback()
    assert "Could not remove legacy file history" in caplog.text
