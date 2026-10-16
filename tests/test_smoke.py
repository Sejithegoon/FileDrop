"""Listener and network smoke tests."""

import socket

import pytest

from app.core.listeners import LanServer
from app.core.network import PublicAddressError, is_lan_address, resolve_lan_host


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _app():
    from fastapi import FastAPI
    return FastAPI()


def test_lan_server_start_stop():
    lan = LanServer(_app, "127.0.0.1", _free_port())
    assert lan.start()["state"] == "running"
    assert lan.stop()["state"] == "stopped"
    assert lan.start()["state"] == "running"  # restartable after a stop
    lan.stop()


def test_port_in_use_reports_error():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        lan = LanServer(_app, "127.0.0.1", busy.getsockname()[1])
        status = lan.start()
    assert status["state"] == "stopped" and status["error"]


def test_blocked_server_refuses_to_start():
    lan = LanServer(_app, "127.0.0.1", _free_port())
    lan.block("database problem")
    status = lan.start()
    assert status["state"] == "stopped" and status["error"] == "database problem"


@pytest.mark.parametrize("addr,ok", [("192.168.1.20", True), ("10.0.0.5", True), ("8.8.8.8", False)])
def test_is_lan_address(addr, ok):
    assert is_lan_address(addr) is ok


def test_refuses_public_and_wildcard():
    for host in ("8.8.8.8", "0.0.0.0"):
        with pytest.raises(PublicAddressError):
            resolve_lan_host(host)
