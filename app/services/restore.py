"""Restore accounts, folders and files from a backup made by services/backups.py.

Works on this PC (roll back) and on a new PC (after a reinstall or a dead drive):
1. The current database is backed up first, so a restore can itself be undone.
2. Every file the backup needs is copied into the storage folder (files already there are kept).
3. The database is replaced with the backup's copy using SQLite's backup API, then upgraded if
   the backup came from an older WiFiDrop. A backup from a newer WiFiDrop is refused.
4. This PC keeps its own storage folder and install ID, and everyone signs in again.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from app import __version__
from app.core.errors import ApiError
from app.db.database import LATEST_SCHEMA, backup_database, open_database
from app.db.ids import now_ms
from app.services import backups, settings_store, storage_config, uploads

log = logging.getLogger(__name__)

LEGACY_FOLDER = "FileDrop backup"  # made by the FileDrop beta


def find_backup_dir(folder: str) -> Path:
    """Accepts the backup folder itself or the folder that contains it."""
    if not folder or not folder.strip():
        raise ApiError(400, "INVALID_FOLDER", "Choose the folder that holds your backup.")
    base = Path(folder.strip()).expanduser()
    for candidate in (base, base / backups.FOLDER_NAME, base / LEGACY_FOLDER):
        if (candidate / "database").is_dir() and any(_snapshot_files(candidate)):
            return candidate
    raise ApiError(404, "NO_BACKUP", f"No WiFiDrop backup found in {base}. Choose the folder named "
                                     f"\"{backups.FOLDER_NAME}\" or the drive it's on.")


def _snapshot_files(backup_dir: Path) -> list[Path]:
    db = backup_dir / "database"
    return sorted([*db.glob("wifidrop-*.db"), *db.glob("filedrop-*.db")], key=lambda p: p.stat().st_mtime, reverse=True)


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def list_snapshots(folder: str) -> dict:
    backup_dir = find_backup_dir(folder)
    items = []
    for f in _snapshot_files(backup_dir):
        try:
            with closing(_read_only(f)) as c:
                schema = c.execute("PRAGMA user_version").fetchone()[0]
                users = c.execute("SELECT count(*) FROM users").fetchone()[0]
                files, size = c.execute("SELECT count(*), COALESCE(SUM(size_bytes), 0) FROM items"
                                        " WHERE kind = 'file' AND trashed_at IS NULL").fetchone()
        except sqlite3.Error:
            continue  # not a WiFiDrop database or damaged; don't offer it
        items.append({"name": f.name, "created_at": int(f.stat().st_mtime * 1000), "users": users, "files": files,
                      "bytes": size, "newer": schema > LATEST_SCHEMA})
    return {"folder": str(backup_dir), "snapshots": items}


def restore(ctx, folder: str, name: str) -> dict:
    backup_dir = find_backup_dir(folder)
    snapshot = backup_dir / "database" / Path(name).name
    if Path(name).name != name or snapshot not in _snapshot_files(backup_dir):
        raise ApiError(404, "NOT_FOUND", "That backup copy no longer exists.")
    with closing(_read_only(snapshot)) as src:
        if src.execute("PRAGMA user_version").fetchone()[0] > LATEST_SCHEMA:
            raise ApiError(409, "BACKUP_TOO_NEW", "This backup was made by a newer WiFiDrop. Update WiFiDrop, then restore.")
        wanted = {r[0] for r in src.execute("SELECT blob_id FROM items WHERE blob_id IS NOT NULL")}
    storage = ctx.require_storage()
    if backups.running():
        raise ApiError(409, "BACKUP_RUNNING", "Wait for the running backup to finish.")

    was_running = ctx.lan.state == "running"
    ctx.lan.stop()
    ctx.storage_moving = True  # blocks uploads while files and the database are swapped
    try:
        conn = ctx.connect()
        try:
            keep_install_id = storage_config.install_id(conn)
            backup_database(conn, ctx.settings.backup_dir, "before-restore")
        finally:
            conn.close()

        copied = missing = 0
        files_dir = backup_dir / "files"
        for bid in wanted:
            target = storage.blob_path(bid)
            if target.exists():
                continue
            source = files_dir / bid[:2] / bid[2:4] / bid
            if not source.exists():
                missing += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(bid + ".restoring")
            shutil.copy2(source, tmp)
            tmp.replace(target)
            copied += 1

        with closing(_read_only(snapshot)) as src, closing(sqlite3.connect(ctx.settings.db_path)) as dest:
            src.backup(dest)
        conn, report = open_database(ctx.settings.db_path, __version__, ctx.settings.backup_dir)  # upgrade if older
        try:
            settings_store.set_value(conn, storage_config.KEY, str(storage.root))
            if keep_install_id:
                conn.execute("UPDATE meta SET value = ? WHERE key = 'install_id'", (keep_install_id,))
            conn.execute("UPDATE sessions SET revoked_at = ?, revoke_reason = 'restored from backup'"
                         " WHERE revoked_at IS NULL", (now_ms(),))
            uploads.sweep(conn, storage)
            users = conn.execute("SELECT count(*) FROM users").fetchone()[0]
        finally:
            conn.close()
        ctx.load_flags()  # pauses, admin PIN and licence come from the restored database
        log.info("Restored %s: %s users, %s files copied, %s missing", snapshot.name, users, copied, missing)
        return {"restored": snapshot.name, "users": users, "files": len(wanted), "copied": copied, "missing": missing,
                "upgraded_from": report.from_version if report.from_version != report.to_version else None}
    finally:
        ctx.storage_moving = False
        if was_running:
            ctx.lan.start()
        ctx.changes.bump()
