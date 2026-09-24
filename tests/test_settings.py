from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.settings import (
    AppConfig,
    Settings,
    UvicornConfig,
    is_packaged_build,
    resolve_storage_path,
)


def test_relative_storage_path_uses_flet_data_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path))

    assert resolve_storage_path(Path("uploads")) == (tmp_path / "uploads").resolve()


def test_absolute_storage_path_is_preserved(tmp_path: Path) -> None:
    absolute_path = (tmp_path / "uploads").resolve()

    assert resolve_storage_path(absolute_path) == absolute_path


def test_packaged_build_detection_uses_flet_console_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FLET_APP_CONSOLE", raising=False)
    assert is_packaged_build() is False

    monkeypatch.setenv("FLET_APP_CONSOLE", "C:/Temp/TransferCove/console.log")
    assert is_packaged_build() is True


def test_settings_builds_nested_configuration() -> None:
    settings = Settings(
        app=AppConfig(title="Test transmitter", version="9.9.9"),
        uvicorn=UvicornConfig(port=9001),
    )

    assert settings.app.title == "Test transmitter"
    assert settings.app.version == "9.9.9"
    assert settings.uvicorn.port == 9001
    assert settings.desktop.language == "en"


def test_uvicorn_port_is_validated() -> None:
    with pytest.raises(ValidationError):
        UvicornConfig(port=0)

    with pytest.raises(ValidationError):
        UvicornConfig(port=65536)
