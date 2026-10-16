"""LAN address selection (HOST-5: bind only to private interfaces)."""

from __future__ import annotations

import ipaddress
import socket


class PublicAddressError(RuntimeError):
    pass


def primary_ipv4() -> str:
    """The IPv4 address Windows would use for outbound traffic. Sends no packets."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def is_lan_address(addr: str) -> bool:
    ip = ipaddress.ip_address(addr)
    return ip.is_private or ip.is_link_local or ip.is_loopback


def resolve_lan_host(configured: str) -> str:
    host = primary_ipv4() if configured == "auto" else configured
    if host in ("0.0.0.0", "::"):
        raise PublicAddressError("Binding to all interfaces is not allowed; choose a LAN address.")
    if not is_lan_address(host):
        raise PublicAddressError(f"{host} is not a private LAN address.")
    return host
