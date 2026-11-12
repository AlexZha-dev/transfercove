import pytest

from tools.export_flet_constraints import runtime_constraints
from tools.verify_flet_bundle import check_bundle, expected_runtime_versions


def test_runtime_constraints_include_only_locked_main_group_packages() -> None:
    lock = {
        "package": [
            {
                "name": "SQLAlchemy",
                "version": "2.0.54",
                "groups": ["main"],
            },
            {
                "name": "pytest",
                "version": "9.1.1",
                "groups": ["dev"],
            },
            {
                "name": "flet-cli",
                "version": "0.86.5",
                "groups": ["build"],
            },
        ]
    }

    constraints = runtime_constraints(lock)

    assert constraints == (
        "# Generated from poetry.lock; do not edit.\nsqlalchemy==2.0.54\n"
    )


def test_runtime_constraints_keep_poetry_main_markers() -> None:
    lock = {
        "package": [
            {
                "name": "Colorama",
                "version": "0.4.6",
                "groups": ["main", "dev"],
                "markers": 'sys_platform == "win32"',
            },
            {
                "name": "platform-package",
                "version": "1.2.3",
                "groups": ["main", "build"],
                "markers": {
                    "build": 'sys_platform == "darwin"',
                    "main": 'sys_platform == "win32"',
                },
            },
        ]
    }

    constraints = runtime_constraints(lock)

    assert 'colorama==0.4.6; sys_platform == "win32"' in constraints
    assert 'platform-package==1.2.3; sys_platform == "win32"' in constraints
    assert "darwin" not in constraints


def test_runtime_constraints_are_sorted_and_report_empty_locks() -> None:
    lock = {
        "package": [
            {"name": "zlib-package", "version": "2.0", "groups": ["main"]},
            {"name": "a_package", "version": "1.0", "groups": ["main"]},
        ]
    }

    assert runtime_constraints(lock).splitlines()[1:] == [
        "a-package==1.0",
        "zlib-package==2.0",
    ]

    with pytest.raises(ValueError, match="no runtime dependencies"):
        runtime_constraints({"package": []})


def test_bundle_verification_selects_windows_python_runtime_packages() -> None:
    lock = {
        "package": [
            {"name": "any-python", "version": "1.0", "groups": ["main"]},
            {
                "name": "python-three-fifteen-only",
                "version": "2.0",
                "groups": ["main"],
                "python-versions": ">=3.15",
            },
            {
                "name": "linux-only",
                "version": "3.0",
                "groups": ["main"],
                "markers": 'sys_platform == "linux"',
            },
            {"name": "test-only", "version": "4.0", "groups": ["dev"]},
        ]
    }

    assert expected_runtime_versions(lock) == {"any-python": "1.0"}


def test_bundle_verification_detects_mismatched_package_versions(
    tmp_path,
) -> None:
    lock_path = tmp_path / "poetry.lock"
    lock_path.write_text(
        '[[package]]\nname = "sqlalchemy"\nversion = "2.0.54"\n'
        'groups = ["main"]\npython-versions = "*"\n',
        encoding="utf-8",
    )
    package_info = tmp_path / "site-packages" / "SQLAlchemy-2.1.3.dist-info"
    package_info.mkdir(parents=True)
    (package_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: SQLAlchemy\nVersion: 2.1.3\n",
        encoding="utf-8",
    )

    differences = check_bundle(lock_path, package_info.parent)

    assert differences == [
        "sqlalchemy: poetry.lock requires 2.0.54; bundle contains 2.1.3"
    ]


def test_bundle_verification_detects_missing_package(tmp_path) -> None:
    lock_path = tmp_path / "poetry.lock"
    lock_path.write_text(
        '[[package]]\nname = "sqlalchemy"\nversion = "2.0.54"\n'
        'groups = ["main"]\npython-versions = "*"\n',
        encoding="utf-8",
    )
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    assert check_bundle(lock_path, site_packages) == [
        "sqlalchemy: missing (poetry.lock requires 2.0.54)"
    ]
