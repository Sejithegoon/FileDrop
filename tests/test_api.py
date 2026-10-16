"""End-to-end API flows: admin creates users and shared folders, users sign in and move files."""

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.api.console import create_console_app
from app.api.lan import create_lan_app
from app.core.context import AppContext
from app.core.listeners import LanServer
from app.core.settings import Settings
from app.core.storage import Storage
from app.db.database import open_database

H = {"X-FileDrop": "1"}


@pytest.fixture
def ctx(tmp_path):
    settings = Settings(data_dir=tmp_path, console_port=8442)
    storage = Storage(tmp_path / "storage")
    storage.ensure()
    conn, _ = open_database(settings.db_path, __version__, settings.backup_dir)
    conn.close()
    c = AppContext(settings=settings, storage=storage)
    c.lan = LanServer(lambda: None, "127.0.0.1", 0)
    return c


@pytest.fixture
def admin(ctx):
    return TestClient(create_console_app(ctx), base_url="http://127.0.0.1:8442", headers=H)


def web(ctx):
    return TestClient(create_lan_app(ctx), headers=H)


def make_user(admin, username, password="password123", role="user", must_change=False, quota=None):
    r = admin.post("/api/users", json={"username": username, "password": password, "role": role,
                                       "must_change_password": must_change, "quota_bytes": quota})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def login(ctx, username, password="password123"):
    c = web(ctx)
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c


def my_space(c):
    return next(s for s in c.get("/api/v1/spaces").json()["spaces"] if s["kind"] == "private")


def upload(c, space_id, parent_id, name, data: bytes):
    r = c.post("/api/v1/uploads", json={"space_id": space_id, "parent_id": parent_id, "name": name, "size": len(data)})
    assert r.status_code == 200, r.text
    up = r.json()
    chunk = up["chunk_size"]
    for i in range(0, max(1, -(-len(data) // chunk)) if data else 0):
        r = c.put(f"/api/v1/uploads/{up['id']}/chunks/{i}", content=data[i * chunk:(i + 1) * chunk])
        assert r.status_code == 200, r.text
    r = c.post(f"/api/v1/uploads/{up['id']}/complete", json={})
    assert r.status_code == 200, r.text
    return r.json()


# --- admin API safety -------------------------------------------------------------

def test_admin_api_rejects_other_hosts_and_missing_header(ctx):
    app = create_console_app(ctx)
    assert TestClient(app, base_url="http://evil.example:8442", headers=H).get("/api/overview").status_code == 403
    assert TestClient(app, base_url="http://127.0.0.1:8442").post("/api/server/start").status_code == 403


def test_web_api_requires_csrf_header(ctx, admin):
    make_user(admin, "sam")
    c = TestClient(create_lan_app(ctx))
    assert c.post("/api/v1/auth/login", json={"username": "sam", "password": "password123"}).status_code == 403


# --- sign-in ------------------------------------------------------------------------

def test_login_logout_and_wrong_password(ctx, admin):
    make_user(admin, "sam")
    bad = web(ctx).post("/api/v1/auth/login", json={"username": "sam", "password": "nope-nope"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "INVALID_LOGIN"
    unknown = web(ctx).post("/api/v1/auth/login", json={"username": "ghost", "password": "nope-nope"})
    assert unknown.json()["error"]["message"] == bad.json()["error"]["message"]

    c = login(ctx, "sam")
    assert c.get("/api/v1/me").json()["user"]["username"] == "sam"
    c.post("/api/v1/auth/logout", json={})
    assert c.get("/api/v1/me").status_code == 401


def test_lockout_after_five_failures(ctx, admin):
    make_user(admin, "sam")
    for _ in range(5):
        web(ctx).post("/api/v1/auth/login", json={"username": "sam", "password": "wrong-pass"})
    r = web(ctx).post("/api/v1/auth/login", json={"username": "sam", "password": "password123"})
    assert r.status_code == 429


def test_temporary_password_must_be_changed(ctx, admin):
    make_user(admin, "sam", password="temp-pass-1", must_change=True)
    c = login(ctx, "sam", "temp-pass-1")
    assert c.get("/api/v1/spaces").json()["error"]["code"] == "PASSWORD_CHANGE_REQUIRED"
    r = c.post("/api/v1/me/password", json={"current": "temp-pass-1", "new": "my-own-pass"})
    assert r.status_code == 200 and not r.json()["user"]["must_change_password"]
    assert c.get("/api/v1/spaces").status_code == 200


def test_suspend_signs_out_and_blocks(ctx, admin):
    uid = make_user(admin, "sam")
    c = login(ctx, "sam")
    admin.patch(f"/api/users/{uid}", json={"status": "suspended"})
    assert c.get("/api/v1/me").status_code == 401
    r = web(ctx).post("/api/v1/auth/login", json={"username": "sam", "password": "password123"})
    assert r.json()["error"]["code"] == "ACCOUNT_SUSPENDED"
    admin.patch(f"/api/users/{uid}", json={"status": "active"})
    login(ctx, "sam")


def test_last_admin_is_protected(ctx, admin):
    uid = make_user(admin, "boss", role="admin")
    assert admin.patch(f"/api/users/{uid}", json={"status": "suspended"}).json()["error"]["code"] == "LAST_ADMIN"
    assert admin.patch(f"/api/users/{uid}", json={"role": "user"}).json()["error"]["code"] == "LAST_ADMIN"


# --- files ----------------------------------------------------------------------------

def test_upload_download_rename_trash_restore(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    data = b"hello world " * 1000
    item = upload(c, space["id"], space["root_id"], "notes.txt", data)
    assert item["size"] == len(data)

    r = c.get(f"/api/v1/download/{item['id']}")
    assert r.status_code == 200 and r.content == data
    assert "attachment" in r.headers["content-disposition"] and r.headers["x-content-type-options"] == "nosniff"
    ranged = c.get(f"/api/v1/download/{item['id']}", headers={"Range": "bytes=0-4"})
    assert ranged.status_code == 206 and ranged.content == b"hello"

    # same name again: kept as "notes (2).txt"
    assert upload(c, space["id"], space["root_id"], "NOTES.txt", b"x")["name"] == "NOTES (2).txt"

    assert c.patch(f"/api/v1/items/{item['id']}", json={"name": "renamed.txt"}).status_code == 200
    assert c.delete(f"/api/v1/items/{item['id']}").status_code == 200
    names = [i["name"] for i in c.get(f"/api/v1/spaces/{space['id']}/items").json()["items"]]
    assert "renamed.txt" not in names
    assert [i["name"] for i in c.get(f"/api/v1/spaces/{space['id']}/trash").json()["items"]] == ["renamed.txt"]
    c.post(f"/api/v1/items/{item['id']}/restore", json={})
    names = [i["name"] for i in c.get(f"/api/v1/spaces/{space['id']}/items").json()["items"]]
    assert "renamed.txt" in names


def test_multi_chunk_upload_and_resume(ctx, admin, monkeypatch):
    from app.services import uploads
    monkeypatch.setattr(uploads, "CHUNK_SIZE", 1000)
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    data = bytes(range(256)) * 10  # 2560 bytes = 3 chunks
    up = c.post("/api/v1/uploads", json={"space_id": space["id"], "parent_id": space["root_id"],
                                         "name": "a.bin", "size": len(data)}).json()
    c.put(f"/api/v1/uploads/{up['id']}/chunks/0", content=data[:1000])
    c.put(f"/api/v1/uploads/{up['id']}/chunks/0", content=data[:1000])  # retry is harmless
    skip = c.put(f"/api/v1/uploads/{up['id']}/chunks/2", content=data[2000:])
    assert skip.status_code == 409 and skip.json()["error"]["details"]["received"] == 1000
    assert c.get(f"/api/v1/uploads/{up['id']}").json()["received"] == 1000
    c.put(f"/api/v1/uploads/{up['id']}/chunks/1", content=data[1000:2000])
    c.put(f"/api/v1/uploads/{up['id']}/chunks/2", content=data[2000:])
    item = c.post(f"/api/v1/uploads/{up['id']}/complete", json={}).json()
    assert c.get(f"/api/v1/download/{item['id']}").content == data


def test_empty_file_and_folders(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    folder = c.post(f"/api/v1/spaces/{space['id']}/folders", json={"parent_id": space["root_id"], "name": "Trip"}).json()
    assert c.post(f"/api/v1/spaces/{space['id']}/folders",
                  json={"parent_id": space["root_id"], "name": "trip"}).status_code == 409
    item = upload(c, space["id"], folder["id"], "empty.txt", b"")
    assert c.get(f"/api/v1/download/{item['id']}").content == b""
    listing = c.get(f"/api/v1/spaces/{space['id']}/items?folder={folder['id']}").json()
    assert [x["name"] for x in listing["crumbs"]][1:] == ["Trip"]


def test_quota_is_enforced(ctx, admin):
    make_user(admin, "sam", quota=100)
    c = login(ctx, "sam")
    space = my_space(c)
    upload(c, space["id"], space["root_id"], "small.bin", b"x" * 60)
    r = c.post("/api/v1/uploads", json={"space_id": space["id"], "parent_id": space["root_id"],
                                        "name": "big.bin", "size": 60})
    assert r.status_code == 413 and r.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_users_cannot_see_each_other(ctx, admin):
    make_user(admin, "sam")
    make_user(admin, "alex")
    sam, alex = login(ctx, "sam"), login(ctx, "alex")
    space = my_space(sam)
    item = upload(sam, space["id"], space["root_id"], "secret.txt", b"secret")
    assert alex.get(f"/api/v1/spaces/{space['id']}/items").status_code == 404
    assert alex.get(f"/api/v1/download/{item['id']}").status_code == 404
    assert alex.delete(f"/api/v1/items/{item['id']}").status_code == 404


def test_pauses(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    item = upload(c, space["id"], space["root_id"], "a.txt", b"abc")
    admin.post("/api/controls", json={"uploads_paused": True})
    r = c.post("/api/v1/uploads", json={"space_id": space["id"], "parent_id": space["root_id"], "name": "b", "size": 1})
    assert r.status_code == 503 and r.json()["error"]["code"] == "UPLOADS_PAUSED"
    assert c.get(f"/api/v1/download/{item['id']}").status_code == 200
    admin.post("/api/controls", json={"uploads_paused": False, "downloads_paused": True})
    assert c.get(f"/api/v1/download/{item['id']}").json()["error"]["code"] == "DOWNLOADS_PAUSED"


# --- shared folders ----------------------------------------------------------------------

def test_shared_folder_levels(ctx, admin):
    sam_id, alex_id = make_user(admin, "sam"), make_user(admin, "alex")
    make_user(admin, "kim")
    sid = admin.post("/api/spaces", json={"name": "Family"}).json()["id"]
    admin.put(f"/api/spaces/{sid}/members/{sam_id}", json={"level": "upload"})
    admin.put(f"/api/spaces/{sid}/members/{alex_id}", json={"level": "view"})
    sam, alex, kim = login(ctx, "sam"), login(ctx, "alex"), login(ctx, "kim")

    shared = next(s for s in sam.get("/api/v1/spaces").json()["spaces"] if s["kind"] == "shared")
    assert shared["level"] == "upload"
    item = upload(sam, sid, shared["root_id"], "pic.jpg", b"jpeg")

    # view: can list and download, can't upload or delete
    assert alex.get(f"/api/v1/download/{item['id']}").status_code == 200
    assert alex.post("/api/v1/uploads", json={"space_id": sid, "parent_id": shared["root_id"], "name": "x",
                                              "size": 1}).status_code == 403
    assert alex.delete(f"/api/v1/items/{item['id']}").status_code == 403
    # no access: doesn't even see it
    assert all(s["kind"] != "shared" for s in kim.get("/api/v1/spaces").json()["spaces"])
    assert kim.get(f"/api/v1/download/{item['id']}").status_code == 404

    # upload level can only change own items; manage can change anyone's
    admin.put(f"/api/spaces/{sid}/members/{alex_id}", json={"level": "upload"})
    assert alex.delete(f"/api/v1/items/{item['id']}").status_code == 403
    admin.put(f"/api/spaces/{sid}/members/{alex_id}", json={"level": "manage"})
    assert alex.delete(f"/api/v1/items/{item['id']}").status_code == 200

    # removing access takes effect at once
    admin.put(f"/api/spaces/{sid}/members/{sam_id}", json={"level": None})
    assert sam.get(f"/api/v1/spaces/{sid}/items").status_code == 404


def test_deleting_user_keeps_shared_uploads(ctx, admin):
    sam_id = make_user(admin, "sam")
    sid = admin.post("/api/spaces", json={"name": "Family"}).json()["id"]
    admin.put(f"/api/spaces/{sid}/members/{sam_id}", json={"level": "upload"})
    sam = login(ctx, "sam")
    root = admin.get(f"/api/spaces/{sid}/items").json()["folder_id"]
    upload(sam, sid, root, "keep.jpg", b"keep")
    private = my_space(sam)
    gone = upload(sam, private["id"], private["root_id"], "gone.txt", b"bye")

    assert admin.post(f"/api/users/{sam_id}/delete", json={"confirm": "wrong"}).status_code == 428
    assert admin.post(f"/api/users/{sam_id}/delete", json={"confirm": "sam"}).status_code == 200
    items = admin.get(f"/api/spaces/{sid}/items").json()["items"]
    assert [(i["name"], i["created_by_name"]) for i in items] == [("keep.jpg", "sam (former user)")]
    assert not list(ctx.storage.blobs.rglob("*")) or all(gone["id"] not in str(p) for p in ctx.storage.blobs.rglob("*"))
    assert admin.post("/api/users", json={"username": "sam", "password": "password123"}).status_code == 409


def test_overview_and_audit(ctx, admin):
    make_user(admin, "sam")
    o = admin.get("/api/overview").json()
    assert o["counts"]["users"] == 1 and "<svg" in o["qr"]
    actions = [a["action"] for a in admin.get("/api/audit").json()["entries"]]
    assert "user.create" in actions


def test_subfolders_and_move(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    root = space["root_id"]
    pics = c.post(f"/api/v1/spaces/{space['id']}/folders", json={"parent_id": root, "name": "Pics"}).json()
    school = c.post(f"/api/v1/spaces/{space['id']}/folders", json={"parent_id": root, "name": "School"}).json()
    term = c.post(f"/api/v1/spaces/{space['id']}/folders", json={"parent_id": school["id"], "name": "Term 1"}).json()
    photo = upload(c, space["id"], root, "beach.jpg", b"jpg")

    folders = c.get(f"/api/v1/spaces/{space['id']}/folders").json()["folders"]
    assert [f["path"] for f in folders] == ["", "Pics", "School", "School/Term 1"]

    moved = c.patch(f"/api/v1/items/{photo['id']}", json={"parent_id": pics["id"]}).json()
    assert moved["name"] == "beach.jpg"
    listing = c.get(f"/api/v1/spaces/{space['id']}/items?folder={pics['id']}").json()
    assert [i["name"] for i in listing["items"]] == ["beach.jpg"]

    # a clash is renamed, like uploads
    upload(c, space["id"], root, "beach.jpg", b"other")
    second = next(i for i in c.get(f"/api/v1/spaces/{space['id']}/items").json()["items"] if i["name"] == "beach.jpg")
    assert c.patch(f"/api/v1/items/{second['id']}", json={"parent_id": pics["id"]}).json()["name"] == "beach (2).jpg"

    # a folder can't go inside itself, and the move list hides it
    assert c.patch(f"/api/v1/items/{school['id']}", json={"parent_id": term["id"]}).status_code == 400
    paths = [f["path"] for f in c.get(f"/api/v1/spaces/{space['id']}/folders?exclude={school['id']}").json()["folders"]]
    assert paths == ["", "Pics"]


def test_move_rules_in_shared_folder(ctx, admin):
    sam_id, alex_id = make_user(admin, "sam"), make_user(admin, "alex")
    sid = admin.post("/api/spaces", json={"name": "Family"}).json()["id"]
    admin.put(f"/api/spaces/{sid}/members/{sam_id}", json={"level": "upload"})
    admin.put(f"/api/spaces/{sid}/members/{alex_id}", json={"level": "upload"})
    sam, alex = login(ctx, "sam"), login(ctx, "alex")
    root = admin.get(f"/api/spaces/{sid}/items").json()["folder_id"]
    folder = sam.post(f"/api/v1/spaces/{sid}/folders", json={"parent_id": root, "name": "Trip"}).json()
    item = upload(sam, sid, root, "pic.jpg", b"x")
    assert alex.patch(f"/api/v1/items/{item['id']}", json={"parent_id": folder["id"]}).status_code == 403
    assert sam.patch(f"/api/v1/items/{item['id']}", json={"parent_id": folder["id"]}).status_code == 200
    # can't move into another space
    private = my_space(sam)
    r = sam.patch(f"/api/v1/items/{item['id']}", json={"parent_id": private["root_id"]})
    assert r.status_code == 404


def test_ip_rate_limit_across_accounts(ctx, admin):
    from app.services import auth
    auth.ip_limiter.clear()
    for n in range(4):
        make_user(admin, f"user{n}")
    try:
        for i in range(auth.IP_FAIL_LIMIT):
            web(ctx).post("/api/v1/auth/login", json={"username": f"user{i % 4}", "password": "wrong-pass"})
        r = web(ctx).post("/api/v1/auth/login", json={"username": "user0", "password": "password123"})
        assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMITED"
    finally:
        auth.ip_limiter.clear()


def test_admin_pin_locks_the_admin_api(ctx, admin):
    assert admin.get("/api/lock").json() == {"pin_set": False, "unlocked": True}
    assert admin.post("/api/lock/set", json={"pin": "12"}).status_code == 400
    assert admin.post("/api/lock/set", json={"pin": "4321"}).status_code == 200
    assert admin.get("/api/users").status_code == 200  # the window that set it stays unlocked

    other = TestClient(create_console_app(ctx), base_url="http://127.0.0.1:8442", headers=H)
    r = other.get("/api/users")
    assert r.status_code == 401 and r.json()["error"]["code"] == "LOCKED"
    assert other.post("/api/show").status_code == 200  # second launch can still raise the window
    assert other.post("/api/unlock", json={"pin": "0000"}).json()["error"]["code"] == "WRONG_PIN"
    assert other.post("/api/unlock", json={"pin": "4321"}).status_code == 200
    assert other.get("/api/users").status_code == 200

    other.post("/api/lock/now")
    assert other.get("/api/users").status_code == 401
    assert admin.get("/api/users").status_code == 401  # locking ends every unlocked window

    admin.post("/api/unlock", json={"pin": "4321"})
    admin.post("/api/lock/remove")
    assert other.get("/api/users").status_code == 200


def test_admin_pin_survives_restart(ctx, admin):
    admin.post("/api/lock/set", json={"pin": "4321"})
    restarted = AppContext(settings=ctx.settings, storage=ctx.storage)
    restarted.lan = ctx.lan
    restarted.load_flags()
    fresh = TestClient(create_console_app(restarted), base_url="http://127.0.0.1:8442", headers=H)
    assert fresh.get("/api/users").status_code == 401
