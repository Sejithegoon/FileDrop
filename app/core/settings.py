"""Runtime settings.

Startup settings (ports, folders). Runtime settings such as pauses live in SQLite.
Environment variables override defaults, which is handy for development and tests.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _default_data_dir() -> Path:
    base = os.environ.get("PROGRAMDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "FileDrop"


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
    https: bool | None = None  # None: use the admin's choice (default on); True/False: forced by FILEDROP_HTTPS
    update_feed_url: str = ""  # JSON {version, url, notes}; set once the website hosts it
    website_url: str = ""  # e.g. https://example.ca; enables "Send feedback" in the admin window
    data_dir: Path = field(default_factory=_default_data_dir)
    storage_dir: Path | None = None  # fixed storage folder; normally chosen in the admin window

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def tls_dir(self) -> Path:
        return self.data_dir / "tls"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "filedrop.db"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def console_url(self) -> str:
        return f"http://{self.console_host}:{self.console_port}/"


def load_settings() -> Settings:
    s = Settings()
    env = os.environ
    if "FILEDROP_CONSOLE_PORT" in env:
        s.console_port = int(env["FILEDROP_CONSOLE_PORT"])
    if "FILEDROP_LAN_HOST" in env:
        s.lan_host = env["FILEDROP_LAN_HOST"]
    if "FILEDROP_LAN_PORT" in env:
        s.lan_port = int(env["FILEDROP_LAN_PORT"])
    if "FILEDROP_DATA_DIR" in env:
        s.data_dir = Path(env["FILEDROP_DATA_DIR"])
    if "FILEDROP_STORAGE_DIR" in env:
        s.storage_dir = Path(env["FILEDROP_STORAGE_DIR"])
    if "FILEDROP_WEBSITE" in env:
        s.website_url = env["FILEDROP_WEBSITE"].rstrip("/")
    if "FILEDROP_UPDATE_FEED" in env:
        s.update_feed_url = env["FILEDROP_UPDATE_FEED"]
    if "FILEDROP_HTTPS" in env:
        s.https = env["FILEDROP_HTTPS"] == "1"
    if "FILEDROP_START_SERVER" in env:
        s.start_server_on_launch = env["FILEDROP_START_SERVER"] == "1"
    return s
