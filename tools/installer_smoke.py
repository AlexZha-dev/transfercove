"""Small stdlib-only helpers for the real Windows installer smoke scenarios."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.windows_update_installer import (  # noqa: E402
    installer_arguments,
    resolve_installation,
)


def read_settings(database: Path) -> dict:
    if not database.is_file():
        return {}
    with sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True) as connection:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'application_settings'"
        ).fetchone():
            return {}
        row = connection.execute(
            "SELECT app_title, app_version, storage_dir FROM application_settings WHERE id = 1"
        ).fetchone()
    return dict(zip(("title", "version", "storage_dir"), row)) if row else {}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version")
    for command in ("read", "seed"):
        child = sub.add_parser(command)
        child.add_argument("--database", type=Path, required=True)
    args_parser = sub.add_parser("arguments")
    args_parser.add_argument("--executable", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "version":
        project = Path(__file__).resolve().parents[1] / "pyproject.toml"
        print(tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"])
    elif args.command == "read":
        print(json.dumps(read_settings(args.database.resolve())))
    elif args.command == "seed":
        with sqlite3.connect(args.database) as connection:
            changed = connection.execute(
                "UPDATE application_settings SET app_title = ? WHERE id = 1",
                ("Preserved upgrade setting",),
            ).rowcount
            if changed != 1:
                raise RuntimeError("Application settings row was not found")
    else:
        target = resolve_installation(args.executable)
        print(
            json.dumps(
                {
                    "scope": target.scope.value,
                    "directory": str(target.directory),
                    "command_line": subprocess.list2cmdline(
                        installer_arguments(target)
                    ),
                }
            )
        )


if __name__ == "__main__":
    main()
