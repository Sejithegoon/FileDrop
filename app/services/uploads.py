"""Resumable chunked uploads.

The client creates an upload, sends 8 MB chunks in order (a chunk that already
arrived is accepted again and ignored, so retries are safe), then completes it.
Bytes go to staging/<upload id>.part. On complete the file is moved into the
blob store with an atomic rename inside the same transaction that adds the item.
"""

from __future__ import annotations

import mimetypes
import os
import sqlite3

from fastapi import Request
from starlette.concurrency import run_in_threadpool

from app.core.errors import ApiError
from app.core.names import InvalidName, clean_name, name_key
from app.core.storage import Storage
from app.db.database import transaction
from app.db.ids import new_id, now_ms
from app.services import files, settings_store, spaces

CHUNK_SIZE = 8 * 1024 * 1024
TTL_MS = 24 * 3600 * 1000
DISK_RESERVE = 1024 * 1024 * 1024  # keep 1 GB free on the host
ACTIVE = ("queued", "in_progress", "interrupted", "finalising")


def get(conn: sqlite3.Connection, upload_id: str):
    return conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()


def to_json(row) -> dict:
    return {"id": row["id"], "name": row["name"], "size": row["size_bytes"], "received": row["received_bytes"],
            "chunk_size": row["chunk_size"], "status": row["status"], "item_id": row["item_id"]}


def create(conn: sqlite3.Connection, storage: Storage, *, paused: bool, user, space, parent, name: str,
           size: int) -> dict:
    if paused:
        raise ApiError(503, "UPLOADS_PAUSED", "Uploads are paused by the administrator.")
    try:
        name = clean_name(name)
    except InvalidName as exc:
        raise ApiError(400, "INVALID_NAME", str(exc))
    if size < 0:
        raise ApiError(400, "INVALID_SIZE", "File size is not valid.")
    limit = settings_store.get(conn, "max_upload_bytes")
    if limit and size > limit:
        raise ApiError(413, "FILE_TOO_LARGE", "This file is larger than the upload limit.", limit=limit)
    if space["quota_bytes"] is not None:
        pending = conn.execute(
            f"SELECT COALESCE(SUM(size_bytes - received_bytes), 0) FROM uploads WHERE space_id = ?"
            f" AND status IN {ACTIVE}", (space["id"],)).fetchone()[0]
        used = spaces.usage(conn, space["id"])
        if used + pending + size > space["quota_bytes"]:
            raise ApiError(413, "QUOTA_EXCEEDED", "Not enough space left in this folder's quota.",
                           used=used, quota=space["quota_bytes"])
    if size > storage.disk()["free"] - DISK_RESERVE:
        raise ApiError(507, "INSUFFICIENT_STORAGE", "The server's disk is full.")

    uid, now = new_id(), now_ms()
    storage.staging_path(uid).write_bytes(b"")
    conn.execute(
        "INSERT INTO uploads (id, user_id, space_id, parent_id, name, size_bytes, chunk_size, on_conflict, status,"
        " created_at, updated_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'keep_both', 'in_progress', ?, ?, ?)",
        (uid, user["id"], space["id"], parent["id"], name, size, CHUNK_SIZE, now, now, now + TTL_MS))
    return to_json(get(conn, uid))


_WRITE_BATCH = 1024 * 1024


def _seek_truncate(f, offset: int) -> None:
    f.seek(offset)
    f.truncate(offset)


def _flush_sync(f) -> None:
    f.flush()
    os.fsync(f.fileno())


def _require_open(upload) -> None:
    if upload["status"] == "cancelled":
        raise ApiError(410, "UPLOAD_CANCELLED", "This upload was cancelled.")
    if upload["status"] in ("completed", "failed"):
        raise ApiError(409, "UPLOAD_FINISHED", "This upload has already finished.")


async def write_chunk(conn: sqlite3.Connection, storage: Storage, upload, index: int, request: Request) -> dict:
    _require_open(upload)
    size, chunk, received = upload["size_bytes"], upload["chunk_size"], upload["received_bytes"]
    offset = index * chunk
    expected = min(chunk, size - offset)
    if index < 0 or expected <= 0:
        raise ApiError(400, "BAD_CHUNK", "Chunk number is out of range.")
    if offset + expected <= received:  # a retry of a chunk we already have
        async for _ in request.stream():
            pass
        return to_json(upload)
    if offset != received:
        raise ApiError(409, "OUT_OF_ORDER", "Chunks must be sent in order.", received=received)

    path = storage.staging_path(upload["id"])
    if not path.exists():
        raise ApiError(410, "UPLOAD_EXPIRED", "This upload expired. Start it again.")
    # Disk work runs in a worker thread so one slow disk write never stalls
    # every other request on the server.
    written = 0
    f = await run_in_threadpool(open, path, "r+b")
    try:
        await run_in_threadpool(_seek_truncate, f, offset)
        buf = bytearray()
        async for part in request.stream():
            written += len(part)
            if written > expected:
                raise ApiError(400, "BAD_CHUNK", "Chunk is larger than expected.")
            buf += part
            if len(buf) >= _WRITE_BATCH:
                await run_in_threadpool(f.write, bytes(buf))
                buf.clear()
        if written != expected:
            raise ApiError(400, "INCOMPLETE_CHUNK", "Chunk arrived incomplete. It will be retried.")
        if buf:
            await run_in_threadpool(f.write, bytes(buf))
        await run_in_threadpool(_flush_sync, f)
    except BaseException:
        await run_in_threadpool(_seek_truncate, f, offset)
        raise
    finally:
        await run_in_threadpool(f.close)
    now = now_ms()
    conn.execute("UPDATE uploads SET received_bytes = ?, updated_at = ?, expires_at = ? WHERE id = ?",
                 (offset + written, now, now + TTL_MS, upload["id"]))
    return to_json(get(conn, upload["id"]))


def complete(conn: sqlite3.Connection, storage: Storage, upload, user) -> dict:
    _require_open(upload)
    path = storage.staging_path(upload["id"])
    if upload["received_bytes"] != upload["size_bytes"] or not path.exists() \
            or path.stat().st_size != upload["size_bytes"]:
        raise ApiError(400, "INCOMPLETE_UPLOAD", "Not all of the file has arrived yet.")
    parent = files.get(conn, upload["parent_id"])
    if not parent or not files.is_visible(conn, parent["id"]):
        cancel(conn, storage, upload)
        raise ApiError(409, "TARGET_GONE", "The folder you were uploading to was deleted.")

    blob_id, iid, now = storage.new_blob_id(), new_id(), now_ms()
    dest = storage.blob_path(blob_id)
    content_type = mimetypes.guess_type(upload["name"])[0] or "application/octet-stream"
    with transaction(conn):
        name = files.unique_name(conn, parent["id"], upload["name"])
        conn.execute(
            "INSERT INTO items (id, space_id, parent_id, kind, name, name_key, size_bytes, blob_id, content_type,"
            " created_by, created_by_name, created_at, modified_at) VALUES (?, ?, ?, 'file', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (iid, parent["space_id"], parent["id"], name, name_key(name), upload["size_bytes"], blob_id, content_type,
             user["id"], user["username"], now, now))
        conn.execute("UPDATE uploads SET status = 'completed', item_id = ?, updated_at = ? WHERE id = ?",
                     (iid, now, upload["id"]))
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, dest)  # last step: if it fails, the transaction rolls back
    return files.to_json(files.get(conn, iid), user, can_modify=True)


def cancel(conn: sqlite3.Connection, storage: Storage | None, upload) -> None:
    if upload["status"] in ACTIVE:
        conn.execute("UPDATE uploads SET status = 'cancelled', updated_at = ? WHERE id = ?", (now_ms(), upload["id"]))
    if storage:
        storage.staging_path(upload["id"]).unlink(missing_ok=True)


def cancel_for_user(conn: sqlite3.Connection, storage: Storage | None, user_id: str) -> None:
    for row in conn.execute(f"SELECT * FROM uploads WHERE user_id = ? AND status IN {ACTIVE}", (user_id,)).fetchall():
        cancel(conn, storage, row)


def active(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        f"SELECT up.*, u.username, s.name AS space_name, s.kind AS space_kind FROM uploads up"
        f" JOIN users u ON u.id = up.user_id JOIN spaces s ON s.id = up.space_id"
        f" WHERE up.status IN {ACTIVE} AND up.updated_at > ? ORDER BY up.updated_at DESC",
        (now_ms() - 10 * 60 * 1000,)).fetchall()
    return [to_json(r) | {"username": r["username"], "space_name": r["space_name"], "updated_at": r["updated_at"]}
            for r in rows]


def sweep(conn: sqlite3.Connection, storage: Storage) -> None:
    """Startup cleanup: expire stale uploads, delete stray staging files, prune old rows."""
    now = now_ms()
    for row in conn.execute(f"SELECT * FROM uploads WHERE status IN {ACTIVE} AND expires_at < ?", (now,)).fetchall():
        conn.execute("UPDATE uploads SET status = 'failed', error_code = 'EXPIRED' WHERE id = ?", (row["id"],))
        storage.staging_path(row["id"]).unlink(missing_ok=True)
    live = {r[0] for r in conn.execute(f"SELECT id FROM uploads WHERE status IN {ACTIVE}")}
    for part in storage.staging.glob("*.part"):
        if part.stem not in live:
            part.unlink(missing_ok=True)
    conn.execute(f"DELETE FROM uploads WHERE status NOT IN {ACTIVE} AND updated_at < ?", (now - 7 * 24 * 3600 * 1000,))
