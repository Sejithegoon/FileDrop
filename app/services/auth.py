"""Sign-in, lockout and sessions. Only a SHA-256 of each session token is stored."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3

from app.core.errors import ApiError
from app.db.database import transaction
from app.db.ids import new_id, now_ms
from app.services import audit, users
from app.services.passwords import verify_password

COOKIE = "fd_session"
SESSION_MAX_MS = 30 * 24 * 3600 * 1000
SESSION_IDLE_MS = 3 * 24 * 3600 * 1000
LOCK_AFTER = 5
LOCK_MS = 15 * 60 * 1000
_TOUCH_EVERY_MS = 60 * 1000


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def login(conn: sqlite3.Connection, username: str, password: str, ip: str, user_agent: str):
    now = now_ms()
    user = users.by_username(conn, username or "")
    if user is None:
        verify_password(None, password)  # same timing as a real check
        audit.record(conn, "login", actor=(username or "")[:40] or "unknown", ip=ip, result="denied")
        raise ApiError(401, "INVALID_LOGIN", "Wrong username or password.")
    if user["locked_until"] and user["locked_until"] > now:
        minutes = max(1, (user["locked_until"] - now) // 60000)
        raise ApiError(429, "LOCKED_OUT", f"Too many wrong passwords. Try again in {minutes} min.")
    if not verify_password(user["password_hash"], password):
        failed = user["failed_logins"] + 1
        locked = now + LOCK_MS if failed >= LOCK_AFTER else None
        conn.execute("UPDATE users SET failed_logins = ?, locked_until = ? WHERE id = ?",
                     (0 if locked else failed, locked, user["id"]))
        audit.record(conn, "login", actor=user, ip=ip, result="denied", details={"locked": bool(locked)})
        raise ApiError(401, "INVALID_LOGIN", "Wrong username or password.")
    if user["status"] != "active":
        audit.record(conn, "login", actor=user, ip=ip, result="denied", details={"status": user["status"]})
        raise ApiError(403, "ACCOUNT_SUSPENDED", "This account is suspended. Contact your administrator.")

    token = secrets.token_urlsafe(32)
    with transaction(conn):
        conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (user["id"],))
        conn.execute(
            "INSERT INTO sessions (id, token_hash, user_id, created_at, last_seen_at, expires_at, ip, user_agent)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id(), _hash(token), user["id"], now, now, now + SESSION_MAX_MS, ip, (user_agent or "")[:300]),
        )
        audit.record(conn, "login", actor=user, ip=ip)
    return token, users.get(conn, user["id"])


def resolve(conn: sqlite3.Connection, token: str | None, ip: str | None = None):
    """(session, user) for a valid token, else None."""
    if not token:
        return None
    now = now_ms()
    session = conn.execute(
        "SELECT * FROM sessions WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?",
        (_hash(token), now),
    ).fetchone()
    if not session:
        return None
    if session["last_seen_at"] < now - SESSION_IDLE_MS:
        conn.execute("UPDATE sessions SET revoked_at = ?, revoke_reason = 'idle' WHERE id = ?", (now, session["id"]))
        return None
    user = users.get(conn, session["user_id"])
    if not user or user["status"] != "active":
        return None
    if session["last_seen_at"] < now - _TOUCH_EVERY_MS:
        conn.execute("UPDATE sessions SET last_seen_at = ?, ip = COALESCE(?, ip) WHERE id = ?",
                     (now, ip, session["id"]))
    return session, user


def logout(conn: sqlite3.Connection, session_id: str) -> None:
    conn.execute("UPDATE sessions SET revoked_at = ?, revoke_reason = 'logout' WHERE id = ? AND revoked_at IS NULL",
                 (now_ms(), session_id))


def revoke(conn: sqlite3.Connection, session_id: str, reason: str = "revoked by admin") -> None:
    conn.execute("UPDATE sessions SET revoked_at = ?, revoke_reason = ? WHERE id = ? AND revoked_at IS NULL",
                 (now_ms(), reason, session_id))


def active_sessions(conn: sqlite3.Connection) -> list[dict]:
    now = now_ms()
    rows = conn.execute(
        "SELECT s.id, s.user_id, u.username, u.display_name, s.ip, s.user_agent, s.created_at, s.last_seen_at"
        " FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.revoked_at IS NULL AND s.expires_at > ? AND s.last_seen_at > ? ORDER BY s.last_seen_at DESC",
        (now, now - SESSION_IDLE_MS),
    ).fetchall()
    return [dict(r) for r in rows]
