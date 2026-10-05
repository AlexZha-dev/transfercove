"""Export the locked runtime versions used while Flet packages the app."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path
from typing import Any


def runtime_constraints(lock: dict[str, Any]) -> str:
    """Return pip constraints for every dependency selected in Poetry's main group."""

    packages = lock.get("package")
    if not isinstance(packages, list):
        raise ValueError("poetry.lock has no package list")

    requirements: list[str] = []
    for package in packages:
        if "main" not in package.get("groups", []):
            continue

        name = re.sub(r"[-_.]+", "-", package["name"]).lower()
        requirement = f"{name}=={package['version']}"
        markers = package.get("markers")
        marker = markers.get("main") if isinstance(markers, dict) else markers
        if marker:
            requirement += f"; {marker}"
        requirements.append(requirement)

    if not requirements:
        raise ValueError("poetry.lock contains no runtime dependencies")

    return (
        "# Generated from poetry.lock; do not edit.\n"
        + "\n".join(sorted(requirements))
        + "\n"
    )


def export_runtime_constraints(lock_path: Path, output_path: Path) -> None:
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(runtime_constraints(lock), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("poetry.lock"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    export_runtime_constraints(args.lock, args.output)
    print(f"Wrote Flet runtime constraints to {args.output}")


if __name__ == "__main__":
    main()
