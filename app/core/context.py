"""Shared state for both FastAPI apps: settings, storage, global pauses, LAN server, window hooks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Callable

from app.core.adminlock import AdminLock
from app.core.edition import Capabilities
from app.core.errors import ApiError
from app.core.settings import Settings
from app.core.storage import Storage
from app.db.database import connect
from app.services import licensing, settings_store
from app.services.storage_config import StorageMover


@dataclass
class AppContext:
    settings: Settings
    storage: Storage | None = None  # None until the admin picks a folder
    lan: object | None = None  # LanServer, set by main
    request_quit: Callable[[], None] = lambda: None
    show_window: Callable[[], None] | None = None
    choose_folder: Callable[[], str | None] | None = None  # native folder picker, desktop window only
    uploads_paused: bool = False
    downloads_paused: bool = False
    storage_moving: bool = False
    update_available: dict | None = None  # set by upkeep when the feed has a newer version
    mover: StorageMover = field(default_factory=StorageMover)
    admin_lock: AdminLock = field(default_factory=AdminLock)
    caps: Capabilities = field(default_factory=Capabilities)  # Free or Pro, from the verified licence

    def connect(self) -> sqlite3.Connection:
        return connect(self.settings.db_path)

    def require_storage(self) -> Storage:
        if self.storage is None:
            raise ApiError(409, "STORAGE_NOT_SET", "Choose where WiFiDrop saves files first.")
        return self.storage

    def https_enabled(self) -> bool:
        if self.settings.https is not None:
            return self.settings.https
        conn = self.connect()
        try:
            return bool(settings_store.get(conn, "https_enabled"))
        except sqlite3.Error:
            return True
        finally:
            conn.close()

    @property
    def uploads_blocked(self) -> bool:
        return self.uploads_paused or self.storage_moving

    def load_flags(self) -> None:
        conn = self.connect()
        try:
            self.uploads_paused = bool(settings_store.get(conn, "uploads_paused"))
            self.downloads_paused = bool(settings_store.get(conn, "downloads_paused"))
            self.admin_lock.load(conn)
            licensing.refresh(self, conn)
        finally:
            conn.close()
