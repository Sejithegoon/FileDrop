"""Settings stored as JSON rows. Unknown keys are left untouched."""

from __future__ import annotations

import json
import sqlite3

from app.db.ids import now_ms

DEFAULTS = {
    "uploads_paused": False,
    "downloads_paused": False,
    "max_upload_bytes": None,  # None = no limit
}


def get(conn: sqlite3.Connection, key: str):
    row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else DEFAULTS.get(key)


def set_value(conn: sqlite3.Connection, key: str, value, by: str | None = None) -> None:
    conn.execute(
        "INSERT INTO settings (key, value_json, updated_at, updated_by) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = excluded.updated_at, "
        "updated_by = excluded.updated_by",
        (key, json.dumps(value), now_ms(), by),
    )
