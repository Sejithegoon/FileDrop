"""Sign-in, lockout and sessions. Only a SHA-256 of each session token is stored."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from collections import deque

from app.core.errors import ApiError
from app.db.database import transaction
from app.db.ids import new_id, now_ms
from app.services import audit, users
from app.services.passwords import verify_password

COOKIE = "wd_session"
SESSION_MAX_MS = 30 * 24 * 3600 * 1000
SESSION_IDLE_MS = 3 * 24 * 3600 * 1000
# The phone app keeps its token in the phone's secure storage and may only wake now and then to auto-upload.
APP_SESSION_MAX_MS = 365 * 24 * 3600 * 1000
APP_SESSION_IDLE_MS = 90 * 24 * 3600 * 1000
LOCK_AFTER = 5
LOCK_MS = 15 * 60 * 1000
_TOUCH_EVERY_MS = 60 * 1000


IP_FAIL_LIMIT = 20
IP_WINDOW_MS = 10 * 60 * 1000


class _IpLimiter:
    """Counts failed sign-ins per IP in memory. Stops one device guessing across many accounts."""

    def __init__(self):
        self._fails: dict[str, deque] = {}
        self._lock = threading.Lock()

    def blocked(self, ip: str, now: int) -> bool:
        with self._lock:
            q = self._fails.get(ip)
            while q and q[0] < now - IP_WINDOW_MS:
                q.popleft()
            return bool(q) and len(q) >= IP_FAIL_LIMIT

    def fail(self, ip: str, now: int) -> None:
        with self._lock:
            self._fails.setdefault(ip, deque()).append(now)

    def clear(self) -> None:
        with self._lock:
            self._fails.clear()


ip_limiter = _IpLimiter()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _idle_ms(session) -> int:
    return APP_SESSION_IDLE_MS if session["client"] == "app" else SESSION_IDLE_MS


def login(conn: sqlite3.Connection, username: str, password: str, ip: str, user_agent: str, client: str = "web"):
    now = now_ms()
    if ip_limiter.blocked(ip, now):
        raise ApiError(429, "RATE_LIMITED", "Too many failed sign-ins from this device. Try again in a few minutes.")
    user = users.by_username(conn, username or "")
    if user is None:
        ip_limiter.fail(ip, now)
        verify_password(None, password)  # same timing as a real check
        audit.record(conn, "login", actor=(username or "")[:40] or "unknown", ip=ip, result="denied")
        raise ApiError(401, "INVALID_LOGIN", "Wrong username or password.")
    if user["locked_until"] and user["locked_until"] > now:
        minutes = max(1, (user["locked_until"] - now) // 60000)
        raise ApiError(429, "LOCKED_OUT", f"Too many wrong passwords. Try again in {minutes} min.")
    if not verify_password(user["password_hash"], password):
        ip_limiter.fail(ip, now)
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
    lifetime = APP_SESSION_MAX_MS if client == "app" else SESSION_MAX_MS
    with transaction(conn):
        conn.execute("UPDATE users SET failed_logins = 0, locked_until = NULL WHERE id = ?", (user["id"],))
        conn.execute(
            "INSERT INTO sessions (id, token_hash, user_id, created_at, last_seen_at, expires_at, ip, user_agent, client)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id(), _hash(token), user["id"], now, now, now + lifetime, ip, (user_agent or "")[:300], client),
        )
        audit.record(conn, "login", actor=user, ip=ip, details={"client": client} if client != "web" else None)
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
    if session["last_seen_at"] < now - _idle_ms(session):
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
        "SELECT s.id, s.user_id, u.username, u.display_name, s.ip, s.user_agent, s.created_at, s.last_seen_at, s.client"
        " FROM sessions s JOIN users u ON u.id = s.user_id"
        " WHERE s.revoked_at IS NULL AND s.expires_at > ?"
        " AND s.last_seen_at > ? - (CASE s.client WHEN 'app' THEN ? ELSE ? END) ORDER BY s.last_seen_at DESC",
        (now, now, APP_SESSION_IDLE_MS, SESSION_IDLE_MS),
    ).fetchall()
    return [dict(r) for r in rows]
