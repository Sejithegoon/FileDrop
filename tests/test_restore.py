"""Restoring from a backup (same PC and new PC) and the live-update counter."""

import shutil
import sqlite3
from contextlib import closing

import pytest

from app import __version__
from app.core.context import AppContext
from app.core.listeners import LanServer
from app.core.settings import Settings
from app.db.database import LATEST_SCHEMA, open_database
from app.services import backups, restore
from tests.test_api import login, make_user, my_space, upload, web


def root_of(c, space):
    return c.get(f"/api/v1/spaces/{space['id']}/items").json()["folder_id"]


def names(c, space):
    return sorted(i["name"] for i in c.get(f"/api/v1/spaces/{space['id']}/items").json()["items"])


@pytest.fixture
def backed_up(ctx, admin, tmp_path):
    """Sam has a.txt, a backup is taken, then b.txt is added and Max is created afterwards."""
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    upload(c, space["id"], root_of(c, space), "a.txt", b"before the backup")
    dest = tmp_path / "usb"
    conn = ctx.connect()
    result = backups.run(conn, ctx.storage, str(dest), 7)
    conn.close()
    assert result["ok"], result
    upload(c, space["id"], root_of(c, space), "b.txt", b"after the backup")
    make_user(admin, "max")
    return dest, space


def test_inspect_lists_copies_and_accepts_parent_or_legacy_folder(ctx, backed_up, tmp_path):
    dest, _ = backed_up
    listed = restore.list_snapshots(str(dest))
    assert len(listed["snapshots"]) == 1 and listed["snapshots"][0]["users"] == 1 and listed["snapshots"][0]["files"] == 1
    assert restore.list_snapshots(str(dest / backups.FOLDER_NAME))["folder"] == listed["folder"]
    legacy = tmp_path / "old-drive"
    shutil.copytree(dest / backups.FOLDER_NAME, legacy / "FileDrop backup")
    assert restore.list_snapshots(str(legacy))["snapshots"]
    with pytest.raises(Exception):
        restore.list_snapshots(str(tmp_path / "empty"))


def test_restore_on_the_same_pc(ctx, admin, backed_up):
    dest, space = backed_up
    snap = restore.list_snapshots(str(dest))["snapshots"][0]["name"]
    r = admin.post("/api/backup/restore", json={"folder": str(dest), "name": snap})
    assert r.status_code == 200, r.text
    assert r.json()["users"] == 1
    usernames = [u["username"] for u in admin.get("/api/users").json()["users"]]
    assert usernames == ["sam"]  # Max was created after the backup
    c = login(ctx, "sam")  # everyone signs in again
    assert names(c, space) == ["a.txt"]
    assert list(ctx.settings.backup_dir.glob("*before-restore*.db")), "the pre-restore state is kept"


def test_restore_on_a_new_pc(ctx, backed_up, tmp_path):
    dest, space = backed_up
    snap = restore.list_snapshots(str(dest))["snapshots"][0]["name"]
    # A fresh install: its own data folder, no storage folder chosen yet.
    settings = Settings(data_dir=tmp_path / "newpc", console_port=8442, website_url="", update_feed_url="", licence_url="")
    conn, _ = open_database(settings.db_path, __version__, settings.backup_dir)
    conn.close()
    new = AppContext(settings=settings)
    new.lan = LanServer(lambda: None, "127.0.0.1", 0)
    from fastapi.testclient import TestClient
    from app.api.console import create_console_app
    adm = TestClient(create_console_app(new), base_url="http://127.0.0.1:8442", headers={"X-WiFiDrop": "1"})
    r = adm.post("/api/backup/restore", json={"folder": str(dest), "name": snap})
    assert r.status_code == 400  # must choose where the files go
    r = adm.post("/api/backup/restore", json={"folder": str(dest), "name": snap,
                                              "storage_path": str(tmp_path / "newpc-files")})
    assert r.status_code == 200, r.text
    assert r.json()["copied"] == 1 and r.json()["missing"] == 0
    c = login(new, "sam")
    item = c.get(f"/api/v1/spaces/{space['id']}/items").json()["items"][0]
    assert item["name"] == "a.txt"
    assert c.get(f"/api/v1/download/{item['id']}").content == b"before the backup"


def test_backup_from_a_newer_version_is_refused(ctx, admin, backed_up):
    dest, _ = backed_up
    snap = next((dest / backups.FOLDER_NAME / "database").glob("*.db"))
    with closing(sqlite3.connect(snap)) as c:
        c.execute(f"PRAGMA user_version = {LATEST_SCHEMA + 1}")
    r = admin.post("/api/backup/restore", json={"folder": str(dest), "name": snap.name})
    assert r.status_code == 409 and r.json()["error"]["code"] == "BACKUP_TOO_NEW"
    assert len(admin.get("/api/users").json()["users"]) == 2  # nothing changed


def test_change_counter_moves_on_changes_only(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    v0 = c.get("/api/v1/changes").json()["version"]
    space = my_space(c)
    c.get(f"/api/v1/spaces/{space['id']}/items")
    assert c.get("/api/v1/changes").json()["version"] == v0  # looking changes nothing
    item = upload(c, space["id"], root_of(c, space), "x.txt", b"hello")
    v1 = c.get("/api/v1/changes").json()["version"]
    assert v1 > v0
    assert admin.get("/api/changes").json()["version"] == v1  # the admin window sees the same counter
    assert admin.post(f"/api/items/{item['id']}/delete").status_code == 200
    assert c.get("/api/v1/changes").json()["version"] > v1
    gone = c.get(f"/api/v1/download/{item['id']}", headers={"Range": "bytes=0-0"})
    assert gone.status_code == 404
    assert web(ctx).get("/api/v1/changes").status_code == 401  # signed-in users only
