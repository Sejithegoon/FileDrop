"""Upgrade safety and schema guarantees. These must keep passing for every release."""

import sqlite3

import pytest

from app.core.names import InvalidName, clean_name, clean_username, name_key
from app.db import database as db
from app.db import migrations as mig
from app.db.ids import new_id, now_ms


@pytest.fixture
def paths(tmp_path):
    return tmp_path / "filedrop.db", tmp_path / "backups"


def open_db(paths, version="0.1.0"):
    return db.open_database(paths[0], version, paths[1])


# --- migrations and upgrades -------------------------------------------------

def test_fresh_database_is_fully_migrated(paths):
    conn, report = open_db(paths)
    assert report.created and report.from_version == 0 and report.to_version == db.LATEST_SCHEMA
    assert report.backup is None  # nothing to lose on a brand-new database
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert meta["first_app_version"] == meta["last_app_version"] == "0.1.0" and meta["install_id"]
    conn.close()


def test_reopen_is_a_no_op(paths):
    open_db(paths)[0].close()
    conn, report = open_db(paths, "0.2.0")
    assert report.from_version == report.to_version and report.backup is None
    meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
    assert meta["first_app_version"] == "0.1.0" and meta["last_app_version"] == "0.2.0"
    conn.close()


def test_upgrade_backs_up_then_migrates(paths, monkeypatch):
    conn, _ = open_db(paths)
    conn.execute("INSERT INTO settings (key, value_json, updated_at) VALUES ('keep_me', '1', 0)")
    conn.close()

    extra = mig.Migration(2, "add_column", "ALTER TABLE settings ADD COLUMN note TEXT;")
    monkeypatch.setattr(db, "MIGRATIONS", mig.MIGRATIONS + [extra])
    monkeypatch.setattr(db, "LATEST_SCHEMA", 2)

    conn, report = open_db(paths, "0.2.0")
    assert (report.from_version, report.to_version) == (1, 2)
    assert report.backup and report.backup.exists()
    assert conn.execute("SELECT value_json FROM settings WHERE key = 'keep_me'").fetchone()[0] == "1"
    backup = sqlite3.connect(report.backup)
    assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
    backup.close()
    conn.close()


def test_failed_migration_changes_nothing(paths, monkeypatch):
    open_db(paths)[0].close()
    bad = mig.Migration(2, "broken", "CREATE TABLE half_done (x INTEGER);\nTHIS IS NOT SQL;")
    monkeypatch.setattr(db, "MIGRATIONS", mig.MIGRATIONS + [bad])
    monkeypatch.setattr(db, "LATEST_SCHEMA", 2)

    with pytest.raises(db.MigrationFailedError) as err:
        open_db(paths, "0.2.0")
    assert err.value.backup and err.value.backup.exists()

    check = sqlite3.connect(paths[0])
    assert check.execute("PRAGMA user_version").fetchone()[0] == 1
    assert check.execute("SELECT count(*) FROM sqlite_master WHERE name = 'half_done'").fetchone()[0] == 0
    check.close()


def test_newer_database_is_refused_untouched(paths):
    open_db(paths)[0].close()
    raw = sqlite3.connect(paths[0])
    raw.execute(f"PRAGMA user_version = {db.LATEST_SCHEMA + 1}")
    raw.close()
    before = paths[0].read_bytes()

    with pytest.raises(db.DatabaseTooNewError):
        open_db(paths)
    assert paths[0].read_bytes() == before


def test_edited_migration_is_detected(paths, monkeypatch):
    open_db(paths)[0].close()
    edited = mig.Migration(1, "initial", mig.MIGRATIONS[0].sql + "\n-- edited\n")
    monkeypatch.setattr(db, "MIGRATIONS", [edited])
    with pytest.raises(db.MigrationChecksumError):
        open_db(paths)


def test_foreign_file_is_refused(paths):
    raw = sqlite3.connect(paths[0])
    raw.execute("CREATE TABLE something_else (x)")
    raw.close()
    with pytest.raises(db.DatabaseError, match="not a WiFiDrop database"):
        open_db(paths)


def test_backups_are_pruned(paths):
    conn, _ = open_db(paths)
    for _ in range(5):
        db.backup_database(conn, paths[1], "test", keep=3)
    assert len(list(paths[1].glob("filedrop-*.db"))) == 3
    conn.close()


def test_released_migrations_are_frozen():
    # Update this list only when appending a migration, never to change an existing hash.
    released = {1: "bc5feed3e6d06ff5ff3152000bac0acb83db93f922179ee594a83d910cce9818"}
    for m in mig.MIGRATIONS:
        if m.version in released:
            assert m.checksum == released[m.version]
    versions = [m.version for m in mig.MIGRATIONS]
    assert versions == list(range(1, len(versions) + 1))


# --- schema guarantees ---------------------------------------------------------

@pytest.fixture
def conn(paths):
    c, _ = open_db(paths)
    yield c
    c.close()


def add_user(conn, username="alice", role="user"):
    uid, t = new_id(), now_ms()
    conn.execute(
        "INSERT INTO users (id, username, username_key, display_name, password_hash, role, password_changed_at,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, 'x', ?, ?, ?, ?)",
        (uid, username, username, username, role, t, t, t),
    )
    return uid


def add_space(conn, kind="private", owner=None, name="Home"):
    sid, t = new_id(), now_ms()
    conn.execute(
        "INSERT INTO spaces (id, kind, name, name_key, owner_user_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (sid, kind, name, name_key(name), owner, t),
    )
    root = add_item(conn, sid, None, "folder", "/")
    return sid, root


def add_item(conn, space, parent, kind, name, by=None):
    iid, t = new_id(), now_ms()
    conn.execute(
        "INSERT INTO items (id, space_id, parent_id, kind, name, name_key, blob_id, created_by, created_by_name,"
        " created_at, modified_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'someone', ?, ?)",
        (iid, space, parent, kind, name, name_key(name), new_id() if kind == "file" else None, by, t, t),
    )
    return iid


def test_names_unique_per_folder_ignoring_case(conn):
    uid = add_user(conn)
    sid, root = add_space(conn, owner=uid)
    add_item(conn, sid, root, "file", "Photo.JPG")
    with pytest.raises(sqlite3.IntegrityError):
        add_item(conn, sid, root, "file", "photo.jpg")


def test_trashed_name_can_be_reused(conn):
    uid = add_user(conn)
    sid, root = add_space(conn, owner=uid)
    first = add_item(conn, sid, root, "file", "a.txt")
    conn.execute("UPDATE items SET trashed_at = ? WHERE id = ?", (now_ms(), first))
    add_item(conn, sid, root, "file", "a.txt")


def test_private_space_needs_owner_and_one_per_user(conn):
    with pytest.raises(sqlite3.IntegrityError):
        add_space(conn, kind="private", owner=None)
    uid = add_user(conn)
    add_space(conn, owner=uid)
    with pytest.raises(sqlite3.IntegrityError):
        add_space(conn, owner=uid, name="Second")


def test_members_only_on_shared_spaces(conn):
    uid = add_user(conn)
    private, _ = add_space(conn, owner=uid)
    shared, _ = add_space(conn, kind="shared", name="Family")
    conn.execute("INSERT INTO space_members (space_id, user_id, level, granted_at) VALUES (?, ?, 'upload', 0)",
                 (shared, uid))
    with pytest.raises(sqlite3.IntegrityError, match="shared spaces"):
        conn.execute("INSERT INTO space_members (space_id, user_id, level, granted_at) VALUES (?, ?, 'view', 0)",
                     (private, uid))


def test_parent_must_be_folder_in_same_space(conn):
    uid = add_user(conn)
    a, root_a = add_space(conn, owner=uid)
    b, _ = add_space(conn, kind="shared", name="Shared")
    f = add_item(conn, a, root_a, "file", "x.txt")
    with pytest.raises(sqlite3.IntegrityError):
        add_item(conn, a, f, "file", "inside-a-file.txt")
    with pytest.raises(sqlite3.IntegrityError):
        add_item(conn, b, root_a, "file", "wrong-space.txt")


def test_deleting_user_keeps_their_shared_uploads(conn):
    uid = add_user(conn)
    add_space(conn, owner=uid)
    shared, root = add_space(conn, kind="shared", name="Family")
    item = add_item(conn, shared, root, "file", "pic.jpg", by=uid)
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    row = conn.execute("SELECT created_by, created_by_name FROM items WHERE id = ?", (item,)).fetchone()
    assert row["created_by"] is None and row["created_by_name"] == "someone"
    assert conn.execute("SELECT count(*) FROM spaces WHERE kind = 'private'").fetchone()[0] == 0


def test_audit_log_is_append_only(conn):
    conn.execute("INSERT INTO audit_log (at, actor_name, action, result) VALUES (0, 'admin', 'login', 'ok')")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE audit_log SET action = 'other'")


# --- names ---------------------------------------------------------------------

def test_name_rules():
    assert clean_name("  CON.txt ") == "CON.txt"  # Windows-reserved names are fine: they never touch disk
    assert clean_name("café 📷.heic") == "café 📷.heic"
    for bad in ["", "   ", ".", "..", "a/b", "a\\b", "tab\there", "x" * 256]:
        with pytest.raises(InvalidName):
            clean_name(bad)
    assert name_key("Café") == name_key("CAFÉ")


def test_username_rules():
    assert clean_username(" Alice.B ") == "alice.b"
    for bad in ["a", "-alice", "has space", "x" * 33]:
        with pytest.raises(InvalidName):
            clean_username(bad)


def test_ids_sort_by_time():
    a, b = new_id(), new_id()
    assert len(a) == 32 and a[12] == "7"
    assert a[:12] <= b[:12]
