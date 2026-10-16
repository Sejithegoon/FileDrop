"""Where file contents are stored: chosen at first run, changeable later.

The choice is saved in the settings table. FILEDROP_STORAGE_DIR overrides it
(development and tests). Moving to a new folder copies every blob, switches
over, then removes the old copies, so a failed move changes nothing.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import threading
from pathlib import Path

from app.core.errors import ApiError
from app.core.storage import Storage
from app.db.ids import now_ms
from app.services import settings_store

log = logging.getLogger(__name__)

KEY = "storage_root"
MARKER = "filedrop-storage.json"
SUBFOLDER = "FileDrop Files"


def is_store(path: Path) -> bool:
    return (path / MARKER).is_file() or (path / "blobs").is_dir()


def _has_files(path: Path) -> bool:
    return path.is_dir() and any(p.is_file() for p in path.rglob("*"))


def configured_root(conn: sqlite3.Connection, settings) -> Path | None:
    if settings.storage_dir:
        return Path(settings.storage_dir)
    value = settings_store.get(conn, KEY)
    if value:
        return Path(value)
    legacy = settings.data_dir / "storage"  # versions before the setup screen used this
    if _has_files(legacy / "blobs"):
        settings_store.set_value(conn, KEY, str(legacy))
        return legacy
    return None


def suggested_root() -> Path:
    return Path.home() / SUBFOLDER


def _forbidden(path: Path, settings) -> str | None:
    p = str(path).lower().rstrip("\\/")
    for var in ("WINDIR", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        sys_dir = os.environ.get(var)
        if sys_dir and (p == sys_dir.lower() or p.startswith(sys_dir.lower() + "\\")):
            return "Pick a folder outside Windows and Program Files."
    data = str(settings.data_dir).lower().rstrip("\\/")
    if p == data or p.startswith(data + "\\backups") or p.startswith(data + "\\logs"):
        return "Pick a folder outside FileDrop's own data folder."
    return None


def resolve_choice(raw: str, settings) -> Path:
    """The folder files will actually go into. A non-empty folder that isn't a
    FileDrop store gets a "FileDrop Files" subfolder so nothing is mixed in."""
    raw = (raw or "").strip().strip('"')
    if not raw:
        raise ApiError(400, "INVALID_PATH", "Choose a folder.")
    path = Path(os.path.expandvars(raw)).expanduser()
    if not path.is_absolute():
        raise ApiError(400, "INVALID_PATH", "Use a full path, like D:\\FileDrop Files.")
    if path.exists() and not path.is_dir():
        raise ApiError(400, "INVALID_PATH", "That's a file, not a folder.")
    if path.is_dir() and any(path.iterdir()) and not is_store(path):
        path = path / SUBFOLDER
    problem = _forbidden(path, settings)
    if problem:
        raise ApiError(400, "INVALID_PATH", problem)
    return path


def check(raw: str, settings) -> dict:
    path = resolve_choice(raw, settings)
    anchor = path
    while not anchor.exists() and anchor.parent != anchor:
        anchor = anchor.parent
    if not anchor.exists():
        raise ApiError(400, "INVALID_PATH", "That drive doesn't exist.")
    return {"path": str(path), "free_bytes": shutil.disk_usage(anchor).free, "exists": path.exists(),
            "existing_store": path.is_dir() and is_store(path)}


def prepare(path: Path, install_id: str) -> Storage:
    """Create the folder layout and prove we can write there."""
    try:
        storage = Storage(path)
        storage.ensure()
        probe = path / ".filedrop-write-test"
        probe.write_bytes(b"ok")
        probe.unlink()
        if not (path / MARKER).exists():
            (path / MARKER).write_text(json.dumps({"install_id": install_id, "created_at": now_ms()}))
    except OSError as exc:
        raise ApiError(400, "STORAGE_UNUSABLE", f"FileDrop can't write to {path}: {exc.strerror or exc}")
    return storage


def install_id(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM meta WHERE key = 'install_id'").fetchone()
    return row[0] if row else ""


class StorageMover:
    """Moves blobs to a new root in a background thread. One move at a time."""

    def __init__(self):
        self.state = "idle"  # idle | moving | done | error
        self.copied = self.total = 0
        self.error: str | None = None
        self.target: str | None = None
        self._lock = threading.Lock()

    def status(self) -> dict:
        return {"state": self.state, "copied_bytes": self.copied, "total_bytes": self.total,
                "error": self.error, "target": self.target}

    def start(self, ctx, new_root: Path) -> None:
        with self._lock:
            if self.state == "moving":
                raise ApiError(409, "MOVE_RUNNING", "A move is already running.")
            old = ctx.storage
            if old and Path(old.root).resolve() == new_root.resolve():
                raise ApiError(400, "SAME_FOLDER", "Files are already stored there.")
            if old and (new_root.resolve().is_relative_to(Path(old.root).resolve())
                        or Path(old.root).resolve().is_relative_to(new_root.resolve())):
                raise ApiError(400, "NESTED_FOLDER", "The new folder can't be inside the old one, or the other way round.")
            conn = ctx.connect()
            try:
                busy = conn.execute("SELECT count(*) FROM uploads WHERE status IN"
                                    " ('queued', 'in_progress', 'interrupted', 'finalising')").fetchone()[0]
                iid = install_id(conn)
            finally:
                conn.close()
            if busy:
                raise ApiError(409, "UPLOADS_ACTIVE", "Wait for running uploads to finish, then try again.")
            target = prepare(new_root, iid)
            self.state, self.copied, self.total, self.error, self.target = "moving", 0, 0, None, str(new_root)
            ctx.storage_moving = True
        threading.Thread(target=self._run, args=(ctx, old, target), name="storage-move", daemon=True).start()

    def _run(self, ctx, old: Storage | None, new: Storage) -> None:
        copied_paths: list[Path] = []
        try:
            files = [p for p in old.blobs.rglob("*") if p.is_file()] if old else []
            self.total = sum(p.stat().st_size for p in files)
            for src in files:
                dest = new.blobs / src.relative_to(old.blobs)
                dest.parent.mkdir(parents=True, exist_ok=True)
                tmp = dest.with_name(dest.name + ".moving")
                shutil.copy2(src, tmp)
                if tmp.stat().st_size != src.stat().st_size:
                    raise OSError(f"copy of {src.name} is incomplete")
                os.replace(tmp, dest)
                copied_paths.append(dest)
                self.copied += src.stat().st_size
            conn = ctx.connect()
            try:
                settings_store.set_value(conn, KEY, str(new.root))
            finally:
                conn.close()
            ctx.storage = new
            log.info("Storage moved to %s", new.root)
            if old:
                shutil.rmtree(old.blobs, ignore_errors=True)
                shutil.rmtree(old.staging, ignore_errors=True)
                (old.root / MARKER).unlink(missing_ok=True)
            self.state = "done"
        except Exception as exc:  # leave everything as it was
            log.error("Storage move failed: %s", exc)
            for p in copied_paths:
                p.unlink(missing_ok=True)
            self.state, self.error = "error", str(exc)
        finally:
            ctx.storage_moving = False
