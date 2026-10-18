"""Runtime settings.

Startup settings (ports, folders). Runtime settings such as pauses live in SQLite.
Environment variables override defaults, which is handy for development and tests.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


WEBSITE = "https://wifidrop.ca"  # becomes the real domain at launch
LICENCE_URL = "https://chpjqelrwlowdiwxfugl.supabase.co/functions/v1/licence"


DB_NAME = "wifidrop.db"


def default_data_dir() -> Path:
    base = os.environ.get("PROGRAMDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "WiFiDrop"


def resource_path(*parts: str) -> Path:
    """Path to a bundled file, both from source and inside a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


@dataclass
class Settings:
    console_host: str = "127.0.0.1"
    console_port: int = 8442
    lan_host: str = "auto"  # "auto" = primary private IPv4 address
    lan_port: int = 8443
    start_server_on_launch: bool = True
    https: bool | None = None  # None: use the admin's choice (default on); True/False: forced by WIFIDROP_HTTPS
    update_feed_url: str = WEBSITE + "/update.json"  # JSON {version, url, notes}; "" turns the check off
    website_url: str = WEBSITE  # links to feedback, pricing and help; "" hides them
    licence_url: str = LICENCE_URL  # licence server; "" turns activation and check-ins off
    data_dir: Path = field(default_factory=default_data_dir)
    storage_dir: Path | None = None  # fixed storage folder; normally chosen in the admin window

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def tls_dir(self) -> Path:
        return self.data_dir / "tls"

    @property
    def db_path(self) -> Path:
        return self.data_dir / DB_NAME

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def console_url(self) -> str:
        return f"http://{self.console_host}:{self.console_port}/"


def _env(env, name: str) -> str | None:
    """WIFIDROP_<name>, or the FileDrop beta's FILEDROP_<name>."""
    return env.get("WIFIDROP_" + name, env.get("FILEDROP_" + name))


def load_settings() -> Settings:
    s = Settings()
    env = os.environ
    if _env(env, "CONSOLE_PORT") is not None:
        s.console_port = int(_env(env, "CONSOLE_PORT"))
    if _env(env, "LAN_HOST") is not None:
        s.lan_host = _env(env, "LAN_HOST")
    if _env(env, "LAN_PORT") is not None:
        s.lan_port = int(_env(env, "LAN_PORT"))
    if _env(env, "DATA_DIR") is not None:
        s.data_dir = Path(_env(env, "DATA_DIR"))
    if _env(env, "STORAGE_DIR") is not None:
        s.storage_dir = Path(_env(env, "STORAGE_DIR"))
    if _env(env, "WEBSITE") is not None:
        s.website_url = _env(env, "WEBSITE").rstrip("/")
    if _env(env, "UPDATE_FEED") is not None:
        s.update_feed_url = _env(env, "UPDATE_FEED")
    if _env(env, "LICENCE_URL") is not None:
        s.licence_url = _env(env, "LICENCE_URL")
    if _env(env, "HTTPS") is not None:
        s.https = _env(env, "HTTPS") == "1"
    if _env(env, "START_SERVER") is not None:
        s.start_server_on_launch = _env(env, "START_SERVER") == "1"
    return s
