"""Shared fixtures: a fresh app context with its own data folder, and an admin API client."""

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.api.console import create_console_app
from app.core.context import AppContext
from app.core.listeners import LanServer
from app.core.settings import Settings
from app.core.storage import Storage
from app.db.database import open_database

H = {"X-WiFiDrop": "1"}


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """Every test starts with an empty per-IP sign-in counter (it lives in memory)."""
    from app.services import auth
    auth.ip_limiter.clear()
    yield
    auth.ip_limiter.clear()


@pytest.fixture
def ctx(tmp_path):
    # No website, update feed or licence server: tests never touch the internet.
    settings = Settings(data_dir=tmp_path, console_port=8442, website_url="", update_feed_url="", licence_url="")
    storage = Storage(tmp_path / "storage")
    storage.ensure()
    conn, _ = open_database(settings.db_path, __version__, settings.backup_dir)
    conn.close()
    c = AppContext(settings=settings, storage=storage)
    c.lan = LanServer(lambda: None, "127.0.0.1", 0)
    return c


@pytest.fixture
def admin(ctx):
    return TestClient(create_console_app(ctx), base_url="http://127.0.0.1:8442", headers=H)


