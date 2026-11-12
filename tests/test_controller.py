import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.controller.controller import AppController
from app.core.settings import Settings, UvicornConfig


def test_server_url_uses_lan_address_for_wildcard_bind(monkeypatch) -> None:
    controller = AppController.__new__(AppController)
    controller.settings = Settings(
        uvicorn=UvicornConfig(host="0.0.0.0", port=8123),
    )
    monkeypatch.setattr(
        "app.controller.controller.get_lan_ipv4", lambda: "192.168.1.42"
    )

    assert controller.advertised_host == "192.168.1.42"
    assert controller.server_url == "http://192.168.1.42:8123/"


def test_server_url_keeps_explicit_bind_address() -> None:
    controller = AppController.__new__(AppController)
    controller.settings = Settings(
        uvicorn=UvicornConfig(host="127.0.0.1", port=8123),
    )

    assert controller.server_url == "http://127.0.0.1:8123/"


@pytest.mark.parametrize(
    ("language", "port", "restart"),
    [("ru", 8000, False), ("en", 8001, True), ("ru", 8001, True), ("en", 8000, True)],
)
def test_save_settings_only_skips_restart_for_language_change(language, port, restart):
    controller = AppController.__new__(AppController)
    controller.settings = Settings(uvicorn=UvicornConfig(port=8000))
    controller.server_manager = SimpleNamespace(is_running=True)
    controller.settings_store = SimpleNamespace(save=AsyncMock(side_effect=lambda s: s))
    controller.stop_server = AsyncMock()
    controller.start_server = AsyncMock(return_value=True)
    controller.notify = Mock()
    updated = controller.settings.model_copy(deep=True)
    updated.desktop.language = language
    updated.uvicorn.port = port

    assert asyncio.run(controller.save_settings(updated))
    assert controller.settings is updated
    assert controller.stop_server.await_count == int(restart)
    assert controller.start_server.await_count == int(restart)
