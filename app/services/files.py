"""Folders, files and trash inside a space. Permission checks happen in the routes."""

from __future__ import annotations

import os
import sqlite3

from app.core.errors import ApiError
from app.core.names import InvalidName, clean_name, name_key
from app.core.storage import Storage
from app.db.database import transaction
from app.db.ids import new_id, now_ms

_ANCESTORS = """
WITH RECURSIVE up(id, parent_id, name, trashed_at, depth) AS (
    SELECT id, parent_id, name, trashed_at, 0 FROM items WHERE id = ?
    UNION ALL
    SELECT i.id, i.parent_id, i.name, i.trashed_at, up.depth + 1 FROM items i JOIN up ON i.id = up.parent_id
)
SELECT id, parent_id, name, trashed_at FROM up ORDER BY depth DESC
"""

_SUBTREE_BLOBS = """
WITH RECURSIVE down(id) AS (
    SELECT id FROM items WHERE id = ?
    UNION ALL
    SELECT i.id FROM items i JOIN down ON i.parent_id = down.id
)
SELECT blob_id FROM items WHERE id IN (SELECT id FROM down) AND blob_id IS NOT NULL
"""


def get(conn: sqlite3.Connection, item_id: str):
    return conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def ancestors(conn: sqlite3.Connection, item_id: str) -> list:
    """Root first, the item itself last."""
    return conn.execute(_ANCESTORS, (item_id,)).fetchall()


def is_visible(conn: sqlite3.Connection, item_id: str) -> bool:
    """Not trashed, and not inside a trashed folder."""
    return all(r["trashed_at"] is None for r in ancestors(conn, item_id))


def crumbs(conn: sqlite3.Connection, folder_id: str) -> list[dict]:
    return [{"id": r["id"], "name": r["name"]} for r in ancestors(conn, folder_id)]


def children(conn: sqlite3.Connection, folder_id: str) -> list:
    return conn.execute(
        "SELECT i.*, (SELECT count(*) FROM items c WHERE c.parent_id = i.id AND c.trashed_at IS NULL) AS child_count"
        " FROM items i WHERE i.parent_id = ? AND i.trashed_at IS NULL"
        " ORDER BY i.kind = 'file', i.name_key", (folder_id,)).fetchall()


def trashed(conn: sqlite3.Connection, space_id: str) -> list:
    return conn.execute("SELECT * FROM items WHERE space_id = ? AND trashed_at IS NOT NULL ORDER BY trashed_at DESC",
                        (space_id,)).fetchall()


def _clean(name: str) -> str:
    try:
        return clean_name(name)
    except InvalidName as exc:
        raise ApiError(400, "INVALID_NAME", str(exc))


def _taken(conn: sqlite3.Connection, parent_id: str, name: str, except_id: str | None = None) -> bool:
    return conn.execute(
        "SELECT 1 FROM items WHERE parent_id = ? AND name_key = ? AND trashed_at IS NULL AND id IS NOT ?",
        (parent_id, name_key(name), except_id)).fetchone() is not None


def unique_name(conn: sqlite3.Connection, parent_id: str, name: str) -> str:
    """name, or "name (2).ext", "name (3).ext"... whichever is free."""
    if not _taken(conn, parent_id, name):
        return name
    stem, ext = os.path.splitext(name)
    if not stem:  # ".gitignore"
        stem, ext = ext, ""
    n = 2
    while True:
        candidate = f"{stem} ({n}){ext}"
        if len(candidate) > 255:
            candidate = f"{stem[: 255 - len(ext) - 8]} ({n}){ext}"
        if not _taken(conn, parent_id, candidate):
            return candidate
        n += 1


def require_folder(conn: sqlite3.Connection, folder_id: str, space_id: str):
    folder = get(conn, folder_id)
    if not folder or folder["space_id"] != space_id or folder["kind"] != "folder" or not is_visible(conn, folder_id):
        raise ApiError(404, "NOT_FOUND", "That folder no longer exists.")
    return folder


def create_folder(conn: sqlite3.Connection, parent, name: str, actor_id: str | None, actor_name: str) -> str:
    name = _clean(name)
    iid, now = new_id(), now_ms()
    with transaction(conn):
        if _taken(conn, parent["id"], name):
            raise ApiError(409, "NAME_CONFLICT", "Something with that name is already here.")
        conn.execute(
            "INSERT INTO items (id, space_id, parent_id, kind, name, name_key, created_by, created_by_name,"
            " created_at, modified_at) VALUES (?, ?, ?, 'folder', ?, ?, ?, ?, ?, ?)",
            (iid, parent["space_id"], parent["id"], name, name_key(name), actor_id, actor_name, now, now))
    return iid


def rename(conn: sqlite3.Connection, item, new_name: str) -> str:
    if item["parent_id"] is None:
        raise ApiError(400, "INVALID_TARGET", "The top folder can't be renamed.")
    new_name = _clean(new_name)
    with transaction(conn):
        if _taken(conn, item["parent_id"], new_name, except_id=item["id"]):
            raise ApiError(409, "NAME_CONFLICT", "Something with that name is already here.")
        conn.execute("UPDATE items SET name = ?, name_key = ?, modified_at = ? WHERE id = ?",
                     (new_name, name_key(new_name), now_ms(), item["id"]))
    return new_name


def trash(conn: sqlite3.Connection, item, actor_id: str | None) -> None:
    if item["parent_id"] is None:
        raise ApiError(400, "INVALID_TARGET", "The top folder can't be deleted.")
    conn.execute("UPDATE items SET trashed_at = ?, trashed_by = ? WHERE id = ?", (now_ms(), actor_id, item["id"]))


def restore(conn: sqlite3.Connection, item) -> None:
    """Back to its folder, or to the top folder if that folder is gone. Renamed on a clash."""
    with transaction(conn):
        parent_id = item["parent_id"]
        if not is_visible(conn, parent_id):
            parent_id = conn.execute("SELECT id FROM items WHERE space_id = ? AND parent_id IS NULL",
                                     (item["space_id"],)).fetchone()[0]
        name = unique_name(conn, parent_id, item["name"])
        conn.execute("UPDATE items SET trashed_at = NULL, trashed_by = NULL, parent_id = ?, name = ?, name_key = ?"
                     " WHERE id = ?", (parent_id, name, name_key(name), item["id"]))


def purge(conn: sqlite3.Connection, storage: Storage, item) -> None:
    """Delete forever: the item, everything inside it, and the files on disk."""
    if item["parent_id"] is None:
        raise ApiError(400, "INVALID_TARGET", "The top folder can't be deleted.")
    with transaction(conn):
        blobs = [r[0] for r in conn.execute(_SUBTREE_BLOBS, (item["id"],))]
        conn.execute("DELETE FROM items WHERE id = ?", (item["id"],))
    storage.delete_blobs(blobs)


def empty_trash(conn: sqlite3.Connection, storage: Storage, space_id: str) -> int:
    items = trashed(conn, space_id)
    for item in items:
        if get(conn, item["id"]):  # may already be gone with a trashed parent
            purge(conn, storage, item)
    return len(items)


def to_json(item, user=None, can_modify: bool = False) -> dict:
    return {
        "id": item["id"], "kind": item["kind"], "name": item["name"], "size": item["size_bytes"],
        "created_at": item["created_at"], "modified_at": item["modified_at"],
        "created_by_name": item["created_by_name"],
        "mine": bool(user and item["created_by"] == user["id"]),
        "can_modify": can_modify, "trashed_at": item["trashed_at"],
        "child_count": item["child_count"] if "child_count" in item.keys() else None,
        "state": item["state"],
    }
