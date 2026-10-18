"""Choosing the storage folder at first run and moving it later."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.api.console import create_console_app
from app.api.lan import create_lan_app
from app.core.context import AppContext
from app.core.errors import ApiError
from app.core.listeners import LanServer
from app.core.settings import Settings
from app.db.database import open_database
from app.services import settings_store, storage_config

H = {"X-FileDrop": "1"}


@pytest.fixture
def ctx(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", console_port=8442, website_url="", update_feed_url="", licence_url="")
    conn, _ = open_database(settings.db_path, __version__, settings.backup_dir)
    conn.close()
    c = AppContext(settings=settings)
    c.lan = LanServer(lambda: None, "127.0.0.1", 0)
    c.lan.block("Choose where FileDrop saves files to finish setup.", key="storage")
    settings.start_server_on_launch = False
    return c


@pytest.fixture
def admin(ctx):
    return TestClient(create_console_app(ctx), base_url="http://127.0.0.1:8442", headers=H)


def test_nothing_configured_on_a_fresh_install(ctx):
    conn = ctx.connect()
    assert storage_config.configured_root(conn, ctx.settings) is None
    conn.close()


def test_old_default_folder_is_adopted(ctx):
    legacy = ctx.settings.data_dir / "storage" / "blobs" / "ab" / "cd"
    legacy.mkdir(parents=True)
    (legacy / "abcd1234").write_bytes(b"x")
    conn = ctx.connect()
    assert storage_config.configured_root(conn, ctx.settings) == ctx.settings.data_dir / "storage"
    assert settings_store.get(conn, storage_config.KEY) == str(ctx.settings.data_dir / "storage")
    conn.close()


def test_choice_rules(ctx, tmp_path):
    busy = tmp_path / "Documents"
    busy.mkdir()
    (busy / "taxes.pdf").write_bytes(b"x")
    assert storage_config.resolve_choice(str(busy), ctx.settings) == busy / "WiFiDrop Files"
    empty = tmp_path / "empty"
    empty.mkdir()
    assert storage_config.resolve_choice(str(empty), ctx.settings) == empty
    with pytest.raises(ApiError):
        storage_config.resolve_choice("relative\\path", ctx.settings)
    with pytest.raises(ApiError):
        storage_config.resolve_choice(str(ctx.settings.data_dir / "backups"), ctx.settings)


def test_first_run_setup(ctx, admin, tmp_path):
    o = admin.get("/api/overview").json()
    assert o["storage"] is None and o["server"]["error"]
    target = tmp_path / "Files"
    check = admin.post("/api/storage/check", json={"path": str(target)}).json()
    assert check["path"] == str(target) and not check["exists"]

    r = admin.post("/api/storage/setup", json={"path": str(target)})
    assert r.status_code == 200, r.text
    assert (target / "blobs").is_dir() and (target / storage_config.MARKER).is_file()
    assert ctx.lan.blocked_reason is None
    assert admin.get("/api/overview").json()["storage"]["root"] == str(target)
    assert admin.post("/api/storage/setup", json={"path": str(tmp_path / "Other")}).status_code == 409


def _upload(c, space_id, parent_id, name, data):
    up = c.post("/api/v1/uploads", json={"space_id": space_id, "parent_id": parent_id, "name": name,
                                         "size": len(data)}).json()
    c.put(f"/api/v1/uploads/{up['id']}/chunks/0", content=data)
    return c.post(f"/api/v1/uploads/{up['id']}/complete", json={}).json()


def _wait(admin):
    for _ in range(100):
        m = admin.get("/api/storage/move").json()
        if m["state"] != "moving":
            return m
        time.sleep(0.05)
    raise AssertionError("move did not finish")


def test_move_storage_keeps_every_file(ctx, admin, tmp_path):
    old, new = tmp_path / "Old", tmp_path / "New"
    admin.post("/api/storage/setup", json={"path": str(old)})
    admin.post("/api/users", json={"username": "sam", "password": "password123", "must_change_password": False})
    web = TestClient(create_lan_app(ctx), headers=H)
    web.post("/api/v1/auth/login", json={"username": "sam", "password": "password123"})
    space = web.get("/api/v1/spaces").json()["spaces"][0]
    items = [_upload(web, space["id"], space["root_id"], f"f{i}.txt", f"file {i}".encode() * 100) for i in range(5)]

    r = admin.post("/api/storage/move", json={"path": str(new)})
    assert r.status_code == 200, r.text
    assert _wait(admin)["state"] == "done"
    assert Path(ctx.storage.root) == new
    for i, item in enumerate(items):
        assert web.get(f"/api/v1/download/{item['id']}").content == f"file {i}".encode() * 100
    assert not (old / "blobs").exists()
    conn = ctx.connect()
    assert settings_store.get(conn, storage_config.KEY) == str(new)
    conn.close()


def test_move_refused_while_uploading(ctx, admin, tmp_path):
    admin.post("/api/storage/setup", json={"path": str(tmp_path / "Old")})
    admin.post("/api/users", json={"username": "sam", "password": "password123", "must_change_password": False})
    web = TestClient(create_lan_app(ctx), headers=H)
    web.post("/api/v1/auth/login", json={"username": "sam", "password": "password123"})
    space = web.get("/api/v1/spaces").json()["spaces"][0]
    web.post("/api/v1/uploads", json={"space_id": space["id"], "parent_id": space["root_id"], "name": "a", "size": 10})
    r = admin.post("/api/storage/move", json={"path": str(tmp_path / "New")})
    assert r.status_code == 409 and r.json()["error"]["code"] == "UPLOADS_ACTIVE"


def test_move_into_itself_is_refused(ctx, admin, tmp_path):
    admin.post("/api/storage/setup", json={"path": str(tmp_path / "Old")})
    r = admin.post("/api/storage/move", json={"path": str(tmp_path / "Old" / "inner")})
    assert r.status_code == 400
