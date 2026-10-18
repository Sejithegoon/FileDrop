"""One-time moves from the FileDrop beta's names to WiFiDrop's. Safe to run on every start.

The beta kept its data in %ProgramData%\\FileDrop\\filedrop.db. On the first start of
WiFiDrop the folder and database file are renamed. If that isn't possible (for example
a file is open), WiFiDrop keeps using the old folder, so nothing is ever lost.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

OLD_DIR_NAME = "FileDrop"
OLD_DB = "filedrop.db"
OLD_STORAGE_MARKER = "filedrop-storage.json"
OLD_BACKUP_GLOB = "filedrop-*.db"


def migrate_data_dir(settings, default_dir: Path) -> None:
    """Rename %ProgramData%\\FileDrop to WiFiDrop when the default folder is in use."""
    old = default_dir.parent / OLD_DIR_NAME
    if settings.data_dir != default_dir or default_dir.exists() or not old.is_dir():
        return
    try:
        os.replace(old, default_dir)
        log.info("Moved the data folder from %s to %s", old, default_dir)
    except OSError as exc:
        log.warning("Keeping the data folder at %s (could not rename it: %s)", old, exc)
        settings.data_dir = old


def migrate_database(data_dir: Path, new_name: str) -> None:
    """Rename filedrop.db (and its WAL files) to the new name, if only the old one exists."""
    if (data_dir / new_name).exists() or not (data_dir / OLD_DB).exists():
        return
    for suffix in ("", "-wal", "-shm"):
        old = data_dir / (OLD_DB + suffix)
        if old.exists():
            try:
                os.replace(old, data_dir / (new_name + suffix))
            except OSError as exc:
                log.warning("Could not rename %s: %s", old, exc)
                return
