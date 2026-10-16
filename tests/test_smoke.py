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


def test_certificate_is_reused_and_renewed_on_ip_change(tmp_path):
    from cryptography import x509

    from app.core.tls import ensure_certificate
    first = ensure_certificate(tmp_path, "192.168.1.20")
    key_before = first.key_path.read_bytes()
    assert ensure_certificate(tmp_path, "192.168.1.20").fingerprint == first.fingerprint  # no new warning
    moved = ensure_certificate(tmp_path, "10.0.0.7")
    assert moved.fingerprint != first.fingerprint
    assert moved.key_path.read_bytes() == key_before  # same key, new certificate
    cert = x509.load_pem_x509_certificate(moved.cert_path.read_bytes())
    ips = [str(i) for i in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
           .get_values_for_type(x509.IPAddress)]
    assert "10.0.0.7" in ips


def test_lan_server_serves_https(tmp_path):
    import ssl
    import urllib.request

    from fastapi import FastAPI
    app = FastAPI()
    app.get("/ping")(lambda: {"ok": True})
    lan = LanServer(lambda: app, "127.0.0.1", _free_port(), tls_dir=tmp_path)
    status = lan.start()
    try:
        assert status["state"] == "running" and status["url"].startswith("https://") and status["fingerprint"]
        insecure = ssl.create_default_context()
        insecure.check_hostname, insecure.verify_mode = False, ssl.CERT_NONE
        with urllib.request.urlopen(status["url"] + "ping", context=insecure, timeout=5) as r:
            assert r.read() == b'{"ok":true}'
    finally:
        lan.stop()
