"""Fail when Flet packages runtime versions that differ from Poetry's lock."""

from __future__ import annotations

import argparse
import re
import tomllib
from collections.abc import Mapping
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

from packaging.markers import Marker
from packaging.specifiers import SpecifierSet

WINDOWS_PYTHON_314 = {
    "implementation_name": "cpython",
    "os_name": "nt",
    "platform_machine": "AMD64",
    "platform_python_implementation": "CPython",
    "platform_system": "Windows",
    "python_full_version": "3.14.0",
    "python_version": "3.14",
    "sys_platform": "win32",
}


def canonical_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def expected_runtime_versions(lock: dict[str, Any]) -> dict[str, str]:
    expected: dict[str, str] = {}
    for package in lock.get("package", []):
        if "main" not in package.get("groups", []):
            continue
        python_versions = package.get("python-versions", "*")
        if python_versions != "*" and not SpecifierSet(python_versions).contains(
            "3.14"
        ):
            continue

        markers = package.get("markers")
        marker = markers.get("main") if isinstance(markers, Mapping) else markers
        if marker and not Marker(marker).evaluate(WINDOWS_PYTHON_314):
            continue

        expected[canonical_name(package["name"])] = package["version"]

    if not expected:
        raise ValueError("poetry.lock contains no Windows Python 3.14 runtime packages")
    return expected


def check_bundle(lock_path: Path, site_packages: Path) -> list[str]:
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    expected = expected_runtime_versions(lock)
    actual = {
        canonical_name(distribution.metadata["Name"]): distribution.version
        for distribution in distributions(path=[str(site_packages)])
        if distribution.metadata.get("Name")
    }

    differences = []
    for name, version in sorted(expected.items()):
        bundled_version = actual.get(name)
        if bundled_version is None:
            differences.append(f"{name}: missing (poetry.lock requires {version})")
        elif bundled_version != version:
            differences.append(
                f"{name}: poetry.lock requires {version}; bundle contains {bundled_version}"
            )
    return differences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path("poetry.lock"))
    parser.add_argument("--site-packages", type=Path, required=True)
    args = parser.parse_args()

    differences = check_bundle(args.lock, args.site_packages)
    if differences:
        parser.exit(
            1,
            "Flet runtime dependencies do not match poetry.lock:\n"
            + "\n".join(f"  - {difference}" for difference in differences)
            + "\n",
        )

    count = len(
        expected_runtime_versions(tomllib.loads(args.lock.read_text(encoding="utf-8")))
    )
    print(f"All {count} bundled runtime dependencies match poetry.lock.")


if __name__ == "__main__":
    main()
