"""Upgrading from the FileDrop beta keeps everything: data folder, database, storage and old pages."""

from app.core import legacy
from app.core.settings import DB_NAME, Settings
from app.services import storage_config
from tests.test_api import make_user, web


def test_beta_data_folder_and_database_are_moved(tmp_path):
    old = tmp_path / "FileDrop"
    (old / "logs").mkdir(parents=True)
    (old / "filedrop.db").write_bytes(b"db")
    (old / "filedrop.db-wal").write_bytes(b"wal")
    new = tmp_path / "WiFiDrop"
    settings = Settings(data_dir=new)
    legacy.migrate_data_dir(settings, new)
    legacy.migrate_database(settings.data_dir, DB_NAME)
    assert settings.data_dir == new and not old.exists()
    assert (new / "wifidrop.db").read_bytes() == b"db" and (new / "wifidrop.db-wal").read_bytes() == b"wal"
    assert (new / "logs").is_dir()


def test_migration_never_touches_an_existing_wifidrop_folder(tmp_path):
    old, new = tmp_path / "FileDrop", tmp_path / "WiFiDrop"
    old.mkdir(); new.mkdir()
    (old / "filedrop.db").write_bytes(b"old")
    (new / "wifidrop.db").write_bytes(b"new")
    settings = Settings(data_dir=new)
    legacy.migrate_data_dir(settings, new)
    legacy.migrate_database(new, DB_NAME)
    assert (new / "wifidrop.db").read_bytes() == b"new" and (old / "filedrop.db").exists()


def test_custom_data_folder_is_left_alone(tmp_path):
    (tmp_path / "FileDrop").mkdir()
    settings = Settings(data_dir=tmp_path / "custom")
    legacy.migrate_data_dir(settings, tmp_path / "WiFiDrop")
    assert settings.data_dir == tmp_path / "custom" and (tmp_path / "FileDrop").exists()


def test_beta_storage_folder_is_still_recognised(tmp_path):
    (tmp_path / "store").mkdir()
    (tmp_path / "store" / "filedrop-storage.json").write_text("{}")
    assert storage_config.is_store(tmp_path / "store")


def test_pages_cached_by_the_beta_still_work(ctx, admin):
    make_user(admin, "sam")
    old_page = web(ctx)
    old_page.headers.pop("X-WiFiDrop")
    old_page.headers["X-FileDrop"] = "1"
    assert old_page.post("/api/v1/auth/login", json={"username": "sam", "password": "password123"}).status_code == 200
    no_header = web(ctx)
    no_header.headers.pop("X-WiFiDrop")
    assert no_header.post("/api/v1/auth/login", json={"username": "sam", "password": "password123"}).status_code == 403
