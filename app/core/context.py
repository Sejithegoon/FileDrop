"""Shared state for both FastAPI apps: settings, storage, global pauses, LAN server, window hooks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

from app.core.settings import Settings
from app.core.storage import Storage
from app.db.database import connect
from app.services import settings_store


@dataclass
class AppContext:
    settings: Settings
    storage: Storage
    lan: object | None = None  # LanServer, set by main
    request_quit: Callable[[], None] = lambda: None
    show_window: Callable[[], None] | None = None
    uploads_paused: bool = False
    downloads_paused: bool = False

    def connect(self) -> sqlite3.Connection:
        return connect(self.settings.db_path)

    def load_flags(self) -> None:
        conn = self.connect()
        try:
            self.uploads_paused = bool(settings_store.get(conn, "uploads_paused"))
            self.downloads_paused = bool(settings_store.get(conn, "downloads_paused"))
        finally:
            conn.close()
