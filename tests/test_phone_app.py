"""What the WiFiDrop phone app needs from the PC: token sign-in, server info, a pinned key in the QR code,
and an announcement on the network."""

import hashlib
import re
import socket
import ssl

from fastapi.testclient import TestClient

from app.api.lan import create_lan_app
from app.core import tls
from app.core.listeners import LanServer
from app.db.ids import now_ms
from app.services import auth, storage_config
from tests.test_api import H, make_user, my_space, upload


def app_login(ctx, username, password="password123", device="Sam's iPhone"):
    c = TestClient(create_lan_app(ctx), headers=H)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password, "client": "app", "device": device})
    assert r.status_code == 200, r.text
    return r


def bearer(ctx, token):
    return TestClient(create_lan_app(ctx), headers={**H, "Authorization": f"Bearer {token}"})


def test_app_sign_in_returns_a_token_instead_of_a_cookie(ctx, admin):
    make_user(admin, "sam")
    r = app_login(ctx, "sam")
    body = r.json()
    assert body["token"] and auth.COOKIE not in r.cookies
    assert body["user"]["username"] == "sam" and body["edition"] == "free" and body["features"] == {"auto_upload": False}

    c = bearer(ctx, body["token"])
    assert c.get("/api/v1/me").json()["user"]["username"] == "sam"
    space = my_space(c)
    root = c.get(f"/api/v1/spaces/{space['id']}/items").json()["folder_id"]
    item = upload(c, space["id"], root, "IMG_0001.HEIC", b"heic bytes")
    assert c.get(f"/api/v1/download/{item['id']}").content == b"heic bytes"

    # The web page's sign-in is unchanged: a cookie, and no token in the reply.
    w = TestClient(create_lan_app(ctx), headers=H)
    r = w.post("/api/v1/auth/login", json={"username": "sam", "password": "password123"})
    assert "token" not in r.json() and auth.COOKIE in r.cookies


def test_bad_or_signed_out_tokens_are_refused(ctx, admin):
    make_user(admin, "sam")
    token = app_login(ctx, "sam").json()["token"]
    assert bearer(ctx, "not-a-token").get("/api/v1/me").status_code == 401
    c = bearer(ctx, token)
    assert c.post("/api/v1/auth/logout").status_code == 200
    assert c.get("/api/v1/me").status_code == 401


def test_app_tokens_still_need_the_request_header(ctx, admin):
    make_user(admin, "sam")
    token = app_login(ctx, "sam").json()["token"]
    c = TestClient(create_lan_app(ctx), headers={"Authorization": f"Bearer {token}"})
    assert c.post("/api/v1/auth/logout").status_code == 403


def test_app_sessions_outlast_a_quiet_week_but_web_ones_do_not(ctx, admin):
    make_user(admin, "sam")
    token = app_login(ctx, "sam").json()["token"]
    w = TestClient(create_lan_app(ctx), headers=H)
    w.post("/api/v1/auth/login", json={"username": "sam", "password": "password123"})
    conn = ctx.connect()
    conn.execute("UPDATE sessions SET last_seen_at = ?", (now_ms() - 10 * 24 * 3600 * 1000,))
    conn.close()
    assert w.get("/api/v1/me").status_code == 401
    assert bearer(ctx, token).get("/api/v1/me").status_code == 200


def test_admin_window_shows_which_phone_is_signed_in(ctx, admin):
    make_user(admin, "sam")
    app_login(ctx, "sam", device="Sam's iPhone")
    sessions = admin.get("/api/sessions").json()["sessions"]
    assert len(sessions) == 1 and sessions[0]["client"] == "app" and "Sam's iPhone" in sessions[0]["user_agent"]
    admin.post(f"/api/sessions/{sessions[0]['id']}/revoke")
    assert admin.get("/api/sessions").json()["sessions"] == []


def test_info_identifies_the_pc_without_revealing_the_install_id(ctx):
    c = TestClient(create_lan_app(ctx), headers=H)
    info = c.get("/api/v1/info").json()
    assert info["app"] == "wifidrop" and info["api"] >= info["min_app_api"] >= 1 and info["name"]
    conn = ctx.connect()
    install_id = storage_config.install_id(conn)
    conn.close()
    assert re.fullmatch(r"[0-9a-f]{20}", info["server_id"]) and install_id not in info["server_id"]
    assert c.get("/api/v1/info").json()["server_id"] == info["server_id"]


def test_key_pin_survives_certificate_renewal(tmp_path):
    first = tls.ensure_certificate(tmp_path, "192.168.1.20")
    moved = tls.ensure_certificate(tmp_path, "192.168.1.31")  # new address: new certificate, same key
    assert first.fingerprint != moved.fingerprint and first.pin == moved.pin
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", first.pin)
    assert re.fullmatch(r"[A-Z2-7]{4}-[A-Z2-7]{4}", tls.pin_code(first.pin))


def test_pin_matches_the_key_the_server_presents(tmp_path):
    import base64

    from cryptography import x509
    from cryptography.hazmat.primitives import serialization
    from fastapi import FastAPI

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    lan = LanServer(lambda: FastAPI(), "127.0.0.1", port, tls_dir=tmp_path)
    status = lan.start()
    try:
        der = ssl.get_server_certificate(("127.0.0.1", port))
        cert = x509.load_pem_x509_certificate(der.encode())
        spki = cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        assert base64.urlsafe_b64encode(hashlib.sha256(spki).digest()).rstrip(b"=").decode() == status["pin"]
        assert status["pin_code"] == tls.pin_code(status["pin"])
    finally:
        lan.stop()


def test_qr_code_carries_the_pin_only_over_https(ctx, admin):
    from app.api.console import pairing_url
    conn = ctx.connect()
    plain = pairing_url("http://10.0.0.5:8443/", {"pin": None}, conn)
    secure = pairing_url("https://10.0.0.5:8443/", {"pin": "abc_-123"}, conn)
    conn.close()
    assert plain == "http://10.0.0.5:8443/"
    sid = TestClient(create_lan_app(ctx), headers=H).get("/api/v1/info").json()["server_id"]
    assert secure == f"https://10.0.0.5:8443/?wd=1&pin=abc_-123&id={sid}"
    assert admin.get("/api/overview").status_code == 200


class FakeAnnouncer:
    def __init__(self):
        self.started, self.stopped = [], 0

    def start(self, ip, port, name, txt):
        self.started.append((ip, port, txt))
        return True

    def stop(self):
        self.stopped += 1


def test_running_server_is_announced_and_withdrawn(tmp_path):
    from fastapi import FastAPI
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    fake = FakeAnnouncer()
    lan = LanServer(lambda: FastAPI(), "127.0.0.1", port, tls_dir=tmp_path, announcer=fake,
                    announce_txt=lambda: {"id": "abc"})
    assert lan.start()["state"] == "running"
    try:
        assert fake.started == [("127.0.0.1", port, {"api": "1", "https": "1", "ip": "127.0.0.1", "id": "abc"})]
    finally:
        lan.stop()
    assert fake.stopped >= 1


def test_announcement_failure_never_stops_the_server(tmp_path):
    from fastapi import FastAPI

    class Broken(FakeAnnouncer):
        def start(self, *a):
            raise OSError("no mDNS here")

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    lan = LanServer(lambda: FastAPI(), "127.0.0.1", port, announcer=Broken())
    assert lan.start()["state"] == "running"
    lan.stop()


def test_announcement_name_fits_in_a_dns_label():
    from app.core.discovery import instance_name
    name = instance_name("A" * 80 + ".corp")
    label = name.removesuffix("._wifidrop._tcp.local")
    assert len(label.encode()) <= 63 and "." not in label
