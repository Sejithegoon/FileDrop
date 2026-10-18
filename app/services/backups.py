"""Scheduled backups (Pro): a copy of the database and every file in another folder.

Layout of the backup folder (for example on an external drive):

    WiFiDrop backup/
        database/wifidrop-<time>-scheduled.db   one per run; the newest `keep` are kept
        files/ab/cd/<blob id>                    each stored file, copied once
        READ ME.txt                              how to restore

Files are copied only once, so later runs are quick. A file is removed from the backup
only when no kept database copy refers to it any more.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

from app.core.errors import ApiError
from app.db.database import backup_database
from app.db.ids import now_ms
from app.services import settings_store

log = logging.getLogger(__name__)

CONFIG, STATE = "backup", "backup_state"
FOLDER_NAME = "WiFiDrop backup"
DEFAULTS = {"enabled": False, "folder": "", "every_hours": 24, "keep": 7}
EVERY = (24, 168)  # daily or weekly
_running = threading.Lock()

README = """WiFiDrop backup
===============

database\\  Copies of the WiFiDrop database (accounts, folders, file names). The newest is the latest backup.
files\\     The stored files, under ID names. The database knows which ID is which file.

To restore:
- On this PC: open WiFiDrop, go to Backups, and use "Restore from a backup".
- On a new PC: install WiFiDrop. On the first screen, choose "Restore from a backup" and pick this folder.

Manual restore (only if the steps above aren't possible):
1. Install WiFiDrop, then quit it from the tray icon.
2. Copy the newest file from database\\ to C:\\ProgramData\\WiFiDrop\\wifidrop.db (replace the old one).
3. Copy everything inside files\\ into the "blobs" folder of your WiFiDrop storage folder.
4. Start WiFiDrop. If it asks where to save files, choose that storage folder.
"""


def config(conn) -> dict:
    return {**DEFAULTS, **(settings_store.get(conn, CONFIG) or {})}


def state(conn) -> dict:
    return settings_store.get(conn, STATE) or {}


def check_folder(folder: str, storage_root: Path) -> Path:
    if not folder.strip():
        raise ApiError(400, "INVALID_FOLDER", "Choose a folder for backups.")
    path = Path(folder.strip()).expanduser()
    if not path.is_absolute():
        raise ApiError(400, "INVALID_FOLDER", "Use a full path, for example E:\\Backups.")
    try:
        path, root = path.resolve(), storage_root.resolve()
    except OSError:
        raise ApiError(400, "INVALID_FOLDER", "That folder isn't available.")
    if path == root or root in path.parents or path in root.parents:
        raise ApiError(400, "INVALID_FOLDER", "Choose a folder outside the WiFiDrop storage folder, ideally on "
                                              "another drive.")
    return path


def save_config(conn, storage_root: Path, enabled: bool, folder: str, every_hours: int, keep: int) -> dict:
    if every_hours not in EVERY:
        raise ApiError(400, "INVALID_SCHEDULE", "Back up daily or weekly.")
    if not 1 <= keep <= 60:
        raise ApiError(400, "INVALID_KEEP", "Keep between 1 and 60 copies.")
    if enabled or folder.strip():
        folder = str(check_folder(folder, storage_root))
    settings_store.set_value(conn, CONFIG, {"enabled": enabled, "folder": folder, "every_hours": every_hours,
                                            "keep": keep})
    return config(conn)


def due(conn) -> bool:
    cfg = config(conn)
    if not cfg["enabled"] or not cfg["folder"]:
        return False
    last = state(conn)
    wait_hours = cfg["every_hours"] if last.get("ok", True) else 1  # retry a failed backup (drive unplugged) hourly
    return now_ms() - (last.get("last_at") or 0) >= wait_hours * 3600 * 1000


def _blob_ids(db: sqlite3.Connection) -> set[str]:
    return {r[0] for r in db.execute("SELECT blob_id FROM items WHERE blob_id IS NOT NULL")}


def run(conn, storage, folder: str, keep: int) -> dict:
    """Runs one backup now. Raises ApiError if another backup is running."""
    if not _running.acquire(blocking=False):
        raise ApiError(409, "BACKUP_RUNNING", "A backup is already running.")
    started = now_ms()
    try:
        dest = check_folder(folder, storage.root) / FOLDER_NAME
        files_dir = dest / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        snapshot = backup_database(conn, dest / "database", "scheduled", keep)
        copied = copied_bytes = 0
        with closing(sqlite3.connect(f"file:{snapshot.as_posix()}?mode=ro", uri=True)) as snap:
            wanted = _blob_ids(snap)
        for bid in wanted:
            target = files_dir / bid[:2] / bid[2:4] / bid
            if target.exists():
                continue
            source = storage.blob_path(bid)
            if not source.exists():  # deleted since the snapshot
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(bid + ".partial")
            shutil.copy2(source, tmp)
            tmp.replace(target)
            copied += 1
            copied_bytes += target.stat().st_size
        # Keep every file that any kept database copy still refers to.
        keep_ids = set()
        for db_file in [*(dest / "database").glob("wifidrop-*.db"), *(dest / "database").glob("filedrop-*.db")]:
            with closing(sqlite3.connect(f"file:{db_file.as_posix()}?mode=ro", uri=True)) as old:
                keep_ids |= _blob_ids(old)
        removed = 0
        for f in files_dir.glob("*/*/*"):
            if f.is_file() and f.name not in keep_ids:
                f.unlink(missing_ok=True)
                removed += 1
        (dest / "READ ME.txt").write_text(README, encoding="utf-8")
        result = {"last_at": started, "ok": True, "error": None, "files": len(wanted), "copied": copied,
                  "copied_bytes": copied_bytes, "removed": removed, "seconds": round((now_ms() - started) / 1000, 1),
                  "folder": str(dest)}
        log.info("Backup finished: %s files, %s new, %s removed", len(wanted), copied, removed)
    except ApiError as exc:
        result = {"last_at": started, "ok": False, "error": exc.message}
    except (OSError, sqlite3.Error) as exc:
        log.warning("Backup failed: %s", exc)
        result = {"last_at": started, "ok": False, "error": f"The backup failed: {exc}"}
    finally:
        _running.release()
    settings_store.set_value(conn, STATE, result)
    return result


def running() -> bool:
    return _running.locked()
