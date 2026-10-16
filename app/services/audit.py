"""Append-only audit log."""

from __future__ import annotations

import json
import sqlite3

from app.db.ids import now_ms


def record(conn: sqlite3.Connection, action: str, *, actor=None, ip: str | None = None,
           target_type: str | None = None, target_id: str | None = None, target_name: str | None = None,
           details: dict | None = None, result: str = "ok") -> None:
    """actor: a users row, or a plain name such as "console"."""
    if actor is None or isinstance(actor, str):
        actor_id, actor_name = None, actor or "system"
    else:
        actor_id, actor_name = actor["id"], actor["username"]
    conn.execute(
        "INSERT INTO audit_log (at, actor_user_id, actor_name, actor_ip, action, target_type, target_id,"
        " target_name, details_json, result) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now_ms(), actor_id, actor_name, ip, action, target_type, target_id, target_name,
         json.dumps(details or {}), result),
    )


def recent(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) | {"details": json.loads(r["details_json"])} for r in rows]
