"""Accounts. Each account gets a private space with a root folder."""

from __future__ import annotations

import sqlite3

from app.core.errors import ApiError
from app.core.names import InvalidName, clean_username, name_key
from app.core.storage import Storage
from app.db.database import transaction
from app.db.ids import new_id, now_ms
from app.services.passwords import hash_password, validate_password, verify_password

RESERVE_MS = 30 * 24 * 3600 * 1000
UNCHANGED = object()

_LIST_SQL = """
SELECT u.*, s.id AS space_id, s.quota_bytes,
       (SELECT COALESCE(SUM(size_bytes), 0) FROM items WHERE space_id = s.id) AS used_bytes,
       (SELECT count(*) FROM sessions WHERE user_id = u.id AND revoked_at IS NULL AND expires_at > :now)
           AS active_sessions,
       (SELECT max(last_seen_at) FROM sessions WHERE user_id = u.id) AS last_seen_at
FROM users u LEFT JOIN spaces s ON s.owner_user_id = u.id AND s.kind = 'private'
"""


def public(row) -> dict:
    d = dict(row)
    d.pop("password_hash", None)
    d["must_change_password"] = bool(d.get("must_change_password"))
    return d


def get(conn: sqlite3.Connection, user_id: str):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_required(conn: sqlite3.Connection, user_id: str):
    user = get(conn, user_id)
    if not user:
        raise ApiError(404, "NOT_FOUND", "User not found.")
    return user


def by_username(conn: sqlite3.Connection, username: str):
    return conn.execute("SELECT * FROM users WHERE username_key = ?", (username.strip().lower(),)).fetchone()


def list_all(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(_LIST_SQL + " ORDER BY u.role, u.username_key", {"now": now_ms()}).fetchall()
    return [public(r) for r in rows]


def create(conn: sqlite3.Connection, username: str, password: str, display_name: str | None = None,
           role: str = "user", quota_bytes: int | None = None, must_change_password: bool = False) -> str:
    try:
        key = clean_username(username)
    except InvalidName as exc:
        raise ApiError(400, "INVALID_USERNAME", str(exc))
    if role not in ("admin", "user"):
        raise ApiError(400, "INVALID_ROLE", "Role must be admin or user.")
    if quota_bytes is not None and quota_bytes < 0:
        raise ApiError(400, "INVALID_QUOTA", "Quota can't be negative.")
    validate_password(password)
    display = (display_name or "").strip() or key
    now = now_ms()
    uid, sid = new_id(), new_id()
    with transaction(conn):
        if conn.execute("SELECT 1 FROM users WHERE username_key = ?", (key,)).fetchone() or conn.execute(
            "SELECT 1 FROM reserved_usernames WHERE username_key = ? AND reserved_until > ?", (key, now)
        ).fetchone():
            raise ApiError(409, "USERNAME_TAKEN", "That username is taken.")
        conn.execute(
            "INSERT INTO users (id, username, username_key, display_name, password_hash, role, must_change_password,"
            " password_changed_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uid, key, key, display[:100], hash_password(password), role, int(must_change_password), now, now, now),
        )
        conn.execute(
            "INSERT INTO spaces (id, kind, name, name_key, owner_user_id, quota_bytes, created_at)"
            " VALUES (?, 'private', ?, ?, ?, ?, ?)",
            (sid, "My files", name_key("My files"), uid, quota_bytes, now),
        )
        conn.execute(
            "INSERT INTO items (id, space_id, parent_id, kind, name, name_key, created_by, created_by_name,"
            " created_at, modified_at) VALUES (?, ?, NULL, 'folder', '/', '/', ?, ?, ?, ?)",
            (new_id(), sid, uid, key, now, now),
        )
    return uid


def _active_admins(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT count(*) FROM users WHERE role = 'admin' AND status = 'active'").fetchone()[0]


def _guard_last_admin(conn: sqlite3.Connection, user) -> None:
    if user["role"] == "admin" and user["status"] == "active" and _active_admins(conn) <= 1:
        raise ApiError(409, "LAST_ADMIN", "This is the only active admin account.")


def update(conn: sqlite3.Connection, user_id: str, *, display_name: str | None = None, role: str | None = None,
           quota_bytes=UNCHANGED, status: str | None = None) -> None:
    user = get_required(conn, user_id)
    with transaction(conn):
        if display_name is not None and display_name.strip():
            conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name.strip()[:100], user_id))
        if role is not None and role != user["role"]:
            if role not in ("admin", "user"):
                raise ApiError(400, "INVALID_ROLE", "Role must be admin or user.")
            if role == "user":
                _guard_last_admin(conn, user)
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
            revoke_sessions(conn, user_id, "role changed")
        if status is not None and status != user["status"]:
            if status not in ("active", "suspended"):
                raise ApiError(400, "INVALID_STATUS", "Status must be active or suspended.")
            if status == "suspended":
                _guard_last_admin(conn, user)
                revoke_sessions(conn, user_id, "suspended")
            conn.execute("UPDATE users SET status = ?, failed_logins = 0, locked_until = NULL WHERE id = ?",
                         (status, user_id))
        if quota_bytes is not UNCHANGED:
            if quota_bytes is not None and quota_bytes < 0:
                raise ApiError(400, "INVALID_QUOTA", "Quota can't be negative.")
            conn.execute("UPDATE spaces SET quota_bytes = ? WHERE owner_user_id = ? AND kind = 'private'",
                         (quota_bytes, user_id))
        conn.execute("UPDATE users SET updated_at = ? WHERE id = ?", (now_ms(), user_id))


def set_password(conn: sqlite3.Connection, user_id: str, password: str, must_change: bool,
                 keep_session: str | None = None) -> None:
    validate_password(password)
    now = now_ms()
    with transaction(conn):
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = ?, password_changed_at = ?, updated_at = ?,"
            " failed_logins = 0, locked_until = NULL WHERE id = ?",
            (hash_password(password), int(must_change), now, now, user_id),
        )
        revoke_sessions(conn, user_id, "password changed", except_id=keep_session)


def change_own_password(conn: sqlite3.Connection, user, current: str, new: str, session_id: str) -> None:
    if not verify_password(user["password_hash"], current):
        raise ApiError(400, "WRONG_PASSWORD", "Your current password is wrong.")
    if current == new:
        raise ApiError(400, "SAME_PASSWORD", "Choose a different password.")
    set_password(conn, user["id"], new, must_change=False, keep_session=session_id)


def revoke_sessions(conn: sqlite3.Connection, user_id: str, reason: str, except_id: str | None = None) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = ?, revoke_reason = ? WHERE user_id = ? AND revoked_at IS NULL"
        " AND id IS NOT ?",
        (now_ms(), reason, user_id, except_id),
    )


def delete(conn: sqlite3.Connection, storage: Storage | None, user_id: str) -> None:
    """Delete now: the account, its private files and sessions. Shared uploads stay."""
    user = get_required(conn, user_id)
    with transaction(conn):
        _guard_last_admin(conn, user)
        blobs = [r[0] for r in conn.execute(
            "SELECT i.blob_id FROM items i JOIN spaces s ON s.id = i.space_id"
            " WHERE s.owner_user_id = ? AND s.kind = 'private' AND i.blob_id IS NOT NULL", (user_id,))]
        uploads = [r[0] for r in conn.execute("SELECT id FROM uploads WHERE user_id = ?", (user_id,))]
        conn.execute("UPDATE items SET created_by_name = created_by_name || ' (former user)' WHERE created_by = ?",
                     (user_id,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.execute(
            "INSERT INTO reserved_usernames (username_key, reserved_until) VALUES (?, ?)"
            " ON CONFLICT(username_key) DO UPDATE SET reserved_until = excluded.reserved_until",
            (user["username_key"], now_ms() + RESERVE_MS),
        )
    if storage:
        storage.delete_blobs(blobs)
        for upload_id in uploads:
            storage.staging_path(upload_id).unlink(missing_ok=True)
