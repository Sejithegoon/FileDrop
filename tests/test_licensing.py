"""Free and Pro: licence signatures, the account limit, revocation, offline behaviour and backups."""

import base64
import json

import pytest
from cryptography.hazmat.primitives import serialization as ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core import edition
from app.services import backups, licensing, settings_store, storage_config
from tests.test_api import login, make_user, my_space, upload

KEY = Ed25519PrivateKey.generate()
PUB = base64.b64encode(KEY.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)).decode()
OTHER = Ed25519PrivateKey.generate()


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def sign(payload: dict, key=KEY) -> str:
    raw = json.dumps(payload).encode()
    return f"{b64(raw)}.{b64(key.sign(raw))}"


def licence(lid="WDP-TEST-0001", upd="2099-12-31", key=KEY, **extra) -> str:
    blob = sign({"v": 1, "typ": "licence", "lid": lid, "ed": "pro", "to": "sam@example.com",
                 "iat": "2026-10-16T00:00:00Z", "upd": upd, "max": 3, **extra}, key)
    return edition.normalise(blob)


def status(ctx, st, lid="WDP-TEST-0001", iid=None) -> str:
    conn = ctx.connect()
    iid = iid or storage_config.install_id(conn)
    conn.close()
    return sign({"v": 1, "typ": "status", "lid": lid, "iid": iid, "st": st, "at": "2026-10-16T12:00:00Z"})


class FakeServer:
    """Stands in for the licence Edge Function."""

    def __init__(self, ctx):
        self.ctx, self.calls, self.reply_status, self.offline = ctx, [], "active", False

    def __call__(self, url, action, body, timeout):
        self.calls.append(action)
        if self.offline:
            raise OSError("network unreachable")
        st = "inactive" if action == "deactivate" else self.reply_status
        return {"ok": True, "status": status(self.ctx, st), "message": f"{action} ok"}


@pytest.fixture(autouse=True)
def test_key(monkeypatch):
    monkeypatch.setattr(edition, "PUBLIC_KEYS", [PUB])


@pytest.fixture
def server(ctx, monkeypatch):
    fake = FakeServer(ctx)
    ctx.settings.licence_url = "https://licence.test/functions/v1/licence"
    monkeypatch.setattr(licensing, "_post", fake)
    return fake


def five_users(admin):
    for i in range(5):
        make_user(admin, f"user{i}")


# --- licence parsing -------------------------------------------------------------------

def test_licence_accepts_messy_paste_and_rejects_tampering():
    text = licence()
    messy = "\n\n  " + text.replace("\n", "\r\n   ") + "  \n"
    assert edition.parse_licence(messy)["lid"] == "WDP-TEST-0001"
    body = text.split("\n")[1]
    tampered = text.replace(body, body[:10] + ("A" if body[10] != "A" else "B") + body[11:])
    with pytest.raises(edition.LicenceError):
        edition.parse_licence(tampered)
    with pytest.raises(edition.LicenceError):
        edition.parse_licence(licence(key=OTHER))  # signed by someone else
    with pytest.raises(edition.LicenceError):
        edition.parse_licence("hello")


def test_status_for_another_pc_is_ignored(ctx):
    caps = edition.compute(licence(), status(ctx, "revoked", iid="someone-else"), "my-pc")
    assert caps.pro and caps.state == "pro"


def test_updates_window_uses_build_date_not_clock():
    assert edition.compute(licence(upd="2026-12-31"), None, "pc", build_date="2026-10-16").pro
    caps = edition.compute(licence(upd="2026-01-01"), None, "pc", build_date="2026-10-16")
    assert not caps.pro and caps.state == "updates_ended"


def test_shipped_public_key_is_a_real_public_key_only():
    import importlib.util
    import re
    src = open(importlib.util.find_spec("app.core.edition").origin, encoding="utf-8").read()
    keys = re.findall(r'^    "([A-Za-z0-9+/=]{44})",$', src, re.M)
    assert keys and all(len(base64.b64decode(k)) == 32 for k in keys)
    assert "PRIVATE KEY" not in src and "LICENCE_PRIVATE_KEY" not in src


# --- Free and Pro through the admin API --------------------------------------------------

def test_free_refuses_account_six(admin):
    five_users(admin)
    r = admin.post("/api/users", json={"username": "six", "password": "password123"})
    assert r.status_code == 402 and r.json()["error"]["code"] == "PRO_REQUIRED"
    assert admin.get("/api/overview").json()["edition"]["max_users"] == 5


def test_pro_licence_allows_account_six(admin, server):
    five_users(admin)
    r = admin.post("/api/licence", json={"licence": licence()})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pro"] and body["activated"] and body["online"] and server.calls == ["activate"]
    make_user(admin, "six")
    assert admin.get("/api/licence").json()["licensee"] == "sam@example.com"


def test_invalid_licence_is_refused_and_changes_nothing(admin, server):
    r = admin.post("/api/licence", json={"licence": licence(key=OTHER)})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_LICENCE"
    assert not admin.get("/api/licence").json()["pro"] and server.calls == []


def test_editing_the_database_cant_grant_pro(ctx, admin):
    conn = ctx.connect()
    settings_store.set_value(conn, licensing.LICENCE, licence(key=OTHER))
    licensing.refresh(ctx, conn)
    conn.close()
    assert ctx.caps.state == "invalid" and not ctx.caps.pro


def test_offline_activation_keeps_pro(admin, server):
    server.offline = True
    body = admin.post("/api/licence", json={"licence": licence()}).json()
    assert body["pro"] and not body["activated"] and not body["online"]
    assert "try again" in body["notice"]


def test_revoked_licence_turns_pro_read_only_without_touching_files(ctx, admin, server):
    admin.post("/api/licence", json={"licence": licence()})
    for i in range(6):
        make_user(admin, f"user{i}")
    c = login(ctx, "user5")
    space = my_space(c)
    upload(c, space["id"], c.get(f"/api/v1/spaces/{space['id']}/items").json()["folder_id"], "kept.txt", b"kept")
    server.reply_status = "revoked"
    body = admin.post("/api/licence/check").json()
    assert body["state"] == "revoked" and not body["pro"]
    assert admin.post("/api/users", json={"username": "seven", "password": "password123"}).status_code == 402
    c = login(ctx, "user5")  # existing accounts keep working
    items = c.get(f"/api/v1/spaces/{space['id']}/items").json()["items"]
    assert [i["name"] for i in items] == ["kept.txt"]


def test_too_many_pcs(admin, server):
    server.reply_status = "limit"
    body = admin.post("/api/licence", json={"licence": licence()}).json()
    assert body["state"] == "limit" and not body["pro"]


def test_remove_licence_goes_back_to_free(admin, server):
    admin.post("/api/licence", json={"licence": licence()})
    body = admin.post("/api/licence/remove").json()
    assert not body["pro"] and body["state"] == "free" and server.calls == ["activate", "deactivate"]


def test_check_in_schedule(ctx, admin, server):
    admin.post("/api/licence", json={"licence": licence()})
    conn = ctx.connect()
    assert not licensing.due(ctx, conn)  # just activated
    settings_store.set_value(conn, licensing.LAST_TRY, 0)
    assert licensing.due(ctx, conn)
    conn.close()


# --- scheduled backups ----------------------------------------------------------------------

def test_backups_need_pro(admin, tmp_path):
    r = admin.put("/api/backup", json={"enabled": True, "folder": str(tmp_path / "bk")})
    assert r.status_code == 402
    assert admin.post("/api/backup/run").status_code == 402


def test_backup_copies_and_prunes(ctx, admin, server, tmp_path):
    admin.post("/api/licence", json={"licence": licence()})
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    root = c.get(f"/api/v1/spaces/{space['id']}/items").json()["folder_id"]
    first = upload(c, space["id"], root, "a.txt", b"first file")
    upload(c, space["id"], root, "b.txt", b"second file")
    dest = tmp_path / "external"
    r = admin.put("/api/backup", json={"enabled": True, "folder": str(dest), "every_hours": 24, "keep": 1})
    assert r.status_code == 200, r.text
    assert admin.put("/api/backup", json={"enabled": True, "folder": str(ctx.storage.root / "x")}).status_code == 400

    conn = ctx.connect()
    assert backups.due(conn)
    one = backups.run(conn, ctx.storage, str(dest), 1)
    assert one["ok"] and one["files"] == 2 and one["copied"] == 2
    assert not backups.due(conn)
    two = backups.run(conn, ctx.storage, str(dest), 1)
    assert two["copied"] == 0  # files are copied once

    assert c.delete(f"/api/v1/items/{first['id']}").status_code == 200
    assert c.delete(f"/api/v1/items/{first['id']}/purge").status_code == 200  # gone for good
    three = backups.run(conn, ctx.storage, str(dest), 1)
    assert three["files"] == 1 and three["removed"] == 1
    files = [p for p in (dest / backups.FOLDER_NAME / "files").rglob("*") if p.is_file()]
    assert len(files) == 1 and files[0].read_bytes() == b"second file"
    assert len(list((dest / backups.FOLDER_NAME / "database").glob("*.db"))) == 1
    assert (dest / backups.FOLDER_NAME / "READ ME.txt").exists()
    conn.close()


def test_failed_backup_is_recorded_and_retried_sooner(ctx, admin, server, tmp_path):
    admin.post("/api/licence", json={"licence": licence()})
    conn = ctx.connect()
    backups.save_config(conn, ctx.storage.root, True, str(tmp_path / "drive"), 24, 7)
    r = backups.run(conn, ctx.storage, "relative\\path", 7)
    assert not r["ok"] and r["error"]
    settings_store.set_value(conn, backups.STATE, {**r, "last_at": r["last_at"] - 2 * 3600 * 1000})
    assert backups.due(conn)  # failed 2 hours ago: try again now, not tomorrow
    conn.close()


def test_licences_issued_before_the_rename_still_work():
    old = licence().replace("WIFIDROP LICENCE", "FILEDROP LICENCE")
    assert "FILEDROP" in old and edition.parse_licence(old)["lid"] == "WDP-TEST-0001"
    assert edition.normalise(old).startswith("-----BEGIN WIFIDROP LICENCE-----")
