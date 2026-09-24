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
