from __future__ import annotations

from app.core import network


def test_is_lan_ipv4_rejects_non_shareable_addresses() -> None:
    assert network.is_lan_ipv4("192.168.1.42") is True
    assert network.is_lan_ipv4("10.0.0.7") is True
    assert network.is_lan_ipv4("127.0.0.1") is False
    assert network.is_lan_ipv4("169.254.10.20") is False
    assert network.is_lan_ipv4("not-an-ip") is False


def test_get_lan_ipv4_prefers_the_default_route(monkeypatch) -> None:
    monkeypatch.setattr(network, "_probe_default_route", lambda: "192.168.1.42")
    monkeypatch.setattr(
        network, "_hostname_ipv4_addresses", lambda: ["10.0.0.7"]
    )

    assert network.get_lan_ipv4() == "192.168.1.42"


def test_get_lan_ipv4_falls_back_to_hostname_addresses(monkeypatch) -> None:
    monkeypatch.setattr(network, "_probe_default_route", lambda: None)
    monkeypatch.setattr(
        network, "_hostname_ipv4_addresses", lambda: ["127.0.0.1", "10.0.0.7"]
    )

    assert network.get_lan_ipv4() == "10.0.0.7"
