from __future__ import annotations

import ipaddress
import socket


def is_lan_ipv4(value: str) -> bool:
    """Return whether *value* is a usable local-network IPv4 address."""

    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False

    return (
        address.version == 4
        and address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_unspecified
    )


def _probe_default_route() -> str | None:
    """Get the IPv4 selected by the OS for an outbound connection.

    UDP connect does not establish a connection or send a payload. It lets the
    operating system select the interface that would normally be used for
    network traffic, which is more reliable than resolving the computer name
    when Wi-Fi, Ethernet, VPN, or virtual adapters are present.
    """

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    except OSError:
        return None

    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return None
    finally:
        probe.close()


def _hostname_ipv4_addresses() -> list[str]:
    try:
        infos = socket.getaddrinfo(
            socket.gethostname(),
            None,
            family=socket.AF_INET,
            type=socket.SOCK_DGRAM,
        )
    except OSError:
        return []

    return [info[4][0] for info in infos if info[4]]


def get_lan_ipv4() -> str | None:
    """Return the best available private IPv4 address for sharing locally."""

    candidates = [_probe_default_route(), *_hostname_ipv4_addresses()]
    for candidate in candidates:
        if candidate and is_lan_ipv4(candidate):
            return candidate
    return None
