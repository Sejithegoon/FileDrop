"""Smoke tests for the scaffold. Feature tests map to acceptance criteria AC-1..AC-28."""

import socket

import pytest
from fastapi.testclient import TestClient

from app.api.console import create_console_app
from app.api.lan import create_lan_app
from app.core.listeners import LanServer
from app.core.network import PublicAddressError, is_lan_address, resolve_lan_host


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_lan_health():
    r = TestClient(create_lan_app()).get("/api/v1/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_console_requires_header():
    lan = LanServer(create_lan_app, "127.0.0.1", _free_port())
    client = TestClient(create_console_app(lan, lambda: None))
    assert client.get("/api/server").json()["state"] == "stopped"
    assert client.post("/api/server/start").status_code == 403


def test_lan_server_start_stop():
    lan = LanServer(create_lan_app, "127.0.0.1", _free_port())
    assert lan.start()["state"] == "running"
    assert lan.stop()["state"] == "stopped"
    assert lan.start()["state"] == "running"  # restartable after a stop
    lan.stop()


def test_port_in_use_reports_error():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        lan = LanServer(create_lan_app, "127.0.0.1", busy.getsockname()[1])
        status = lan.start()
    assert status["state"] == "stopped" and status["error"]


@pytest.mark.parametrize("addr,ok", [("192.168.1.20", True), ("10.0.0.5", True), ("8.8.8.8", False)])
def test_is_lan_address(addr, ok):
    assert is_lan_address(addr) is ok


def test_refuses_public_and_wildcard():
    for host in ("8.8.8.8", "0.0.0.0"):
        with pytest.raises(PublicAddressError):
            resolve_lan_host(host)
