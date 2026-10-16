"""Spaces (private and shared), access levels and membership."""

from __future__ import annotations

import sqlite3

from app.core.errors import ApiError
from app.core.names import InvalidName, clean_name, name_key
from app.core.storage import Storage
from app.db.database import transaction
from app.db.ids import new_id, now_ms

LEVELS = ("view", "upload", "manage", "owner")


def rank(level: str | None) -> int:
    return LEVELS.index(level) + 1 if level else 0


def get(conn: sqlite3.Connection, space_id: str):
    return conn.execute("SELECT * FROM spaces WHERE id = ?", (space_id,)).fetchone()


def level_for(conn: sqlite3.Connection, user, space) -> str | None:
    """The user's access to a space: owner, manage, upload, view or None."""
    if space is None or space["status"] != "active":
        return None
    if space["kind"] == "private":
        return "owner" if space["owner_user_id"] == user["id"] else None
    if user["role"] == "admin":
        return "manage"
    row = conn.execute("SELECT level FROM space_members WHERE space_id = ? AND user_id = ?",
                       (space["id"], user["id"])).fetchone()
    return row[0] if row else None


def can_upload(level: str | None) -> bool:
    return rank(level) >= rank("upload")


def can_modify(level: str | None, item, user) -> bool:
    """Rename, move or delete this item."""
    if rank(level) >= rank("manage"):
        return True
    return level == "upload" and item["created_by"] == user["id"]


def usage(conn: sqlite3.Connection, space_id: str) -> int:
    return conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM items WHERE space_id = ?", (space_id,)).fetchone()[0]


def root_id(conn: sqlite3.Connection, space_id: str) -> str:
    return conn.execute("SELECT id FROM items WHERE space_id = ? AND parent_id IS NULL", (space_id,)).fetchone()[0]


def _summary(conn, row, level=None) -> dict:
    return {
        "id": row["id"], "kind": row["kind"], "name": row["name"], "level": level,
        "quota_bytes": row["quota_bytes"], "used_bytes": usage(conn, row["id"]), "root_id": root_id(conn, row["id"]),
    }


def accessible(conn: sqlite3.Connection, user) -> list[dict]:
    out = []
    own = conn.execute("SELECT * FROM spaces WHERE owner_user_id = ? AND kind = 'private' AND status = 'active'",
                       (user["id"],)).fetchone()
    if own:
        out.append(_summary(conn, own, "owner"))
    if user["role"] == "admin":
        rows = conn.execute("SELECT *, 'manage' AS lvl FROM spaces WHERE kind = 'shared' AND status = 'active'"
                            " ORDER BY name_key").fetchall()
    else:
        rows = conn.execute(
            "SELECT s.*, m.level AS lvl FROM spaces s JOIN space_members m ON m.space_id = s.id"
            " WHERE m.user_id = ? AND s.kind = 'shared' AND s.status = 'active' ORDER BY s.name_key",
            (user["id"],)).fetchall()
    out += [_summary(conn, r, r["lvl"]) for r in rows]
    return out


def list_all(conn: sqlite3.Connection) -> list[dict]:
    """Every space, for the admin window: shared ones with members, private ones with owner."""
    rows = conn.execute(
        "SELECT s.*, u.username AS owner_username, u.display_name AS owner_display FROM spaces s"
        " LEFT JOIN users u ON u.id = s.owner_user_id WHERE s.status = 'active'"
        " ORDER BY s.kind DESC, s.name_key, u.username_key").fetchall()
    out = []
    for r in rows:
        d = _summary(conn, r)
        d["owner_username"], d["owner_display"] = r["owner_username"], r["owner_display"]
        if r["kind"] == "shared":
            d["members"] = [dict(m) for m in conn.execute(
                "SELECT m.user_id, m.level, u.username, u.display_name FROM space_members m"
                " JOIN users u ON u.id = m.user_id WHERE m.space_id = ? ORDER BY u.username_key", (r["id"],))]
        out.append(d)
    return out


def _clean_space_name(name: str) -> str:
    try:
        return clean_name(name)
    except InvalidName as exc:
        raise ApiError(400, "INVALID_NAME", str(exc))


def create_shared(conn: sqlite3.Connection, name: str, quota_bytes: int | None, actor_name: str) -> str:
    name = _clean_space_name(name)
    sid, now = new_id(), now_ms()
    with transaction(conn):
        if conn.execute("SELECT 1 FROM spaces WHERE kind = 'shared' AND name_key = ?", (name_key(name),)).fetchone():
            raise ApiError(409, "NAME_CONFLICT", "A shared folder with that name already exists.")
        conn.execute("INSERT INTO spaces (id, kind, name, name_key, quota_bytes, created_at)"
                     " VALUES (?, 'shared', ?, ?, ?, ?)", (sid, name, name_key(name), quota_bytes, now))
        conn.execute("INSERT INTO items (id, space_id, parent_id, kind, name, name_key, created_by_name, created_at,"
                     " modified_at) VALUES (?, ?, NULL, 'folder', '/', '/', ?, ?, ?)",
                     (new_id(), sid, actor_name, now, now))
    return sid


def update_shared(conn: sqlite3.Connection, space_id: str, name: str | None, quota_bytes, set_quota: bool) -> None:
    space = get(conn, space_id)
    if not space or space["kind"] != "shared":
        raise ApiError(404, "NOT_FOUND", "Shared folder not found.")
    try:
        with transaction(conn):
            if name is not None:
                name = _clean_space_name(name)
                conn.execute("UPDATE spaces SET name = ?, name_key = ? WHERE id = ?", (name, name_key(name), space_id))
            if set_quota:
                conn.execute("UPDATE spaces SET quota_bytes = ? WHERE id = ?", (quota_bytes, space_id))
    except sqlite3.IntegrityError:
        raise ApiError(409, "NAME_CONFLICT", "A shared folder with that name already exists.")


def delete_shared(conn: sqlite3.Connection, storage: Storage, space_id: str) -> None:
    space = get(conn, space_id)
    if not space or space["kind"] != "shared":
        raise ApiError(404, "NOT_FOUND", "Shared folder not found.")
    with transaction(conn):
        blobs = [r[0] for r in conn.execute(
            "SELECT blob_id FROM items WHERE space_id = ? AND blob_id IS NOT NULL", (space_id,))]
        uploads = [r[0] for r in conn.execute("SELECT id FROM uploads WHERE space_id = ?", (space_id,))]
        conn.execute("DELETE FROM spaces WHERE id = ?", (space_id,))
    storage.delete_blobs(blobs)
    for upload_id in uploads:
        storage.staging_path(upload_id).unlink(missing_ok=True)


def set_member(conn: sqlite3.Connection, space_id: str, user_id: str, level: str | None, actor_id=None) -> None:
    space = get(conn, space_id)
    if not space or space["kind"] != "shared":
        raise ApiError(404, "NOT_FOUND", "Shared folder not found.")
    if level is None:
        conn.execute("DELETE FROM space_members WHERE space_id = ? AND user_id = ?", (space_id, user_id))
        return
    if level not in ("view", "upload", "manage"):
        raise ApiError(400, "INVALID_LEVEL", "Level must be view, upload or manage.")
    conn.execute(
        "INSERT INTO space_members (space_id, user_id, level, granted_by, granted_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(space_id, user_id) DO UPDATE SET level = excluded.level, granted_by = excluded.granted_by,"
        " granted_at = excluded.granted_at",
        (space_id, user_id, level, actor_id, now_ms()),
    )
