"""Entry point: single-instance check, database, listeners, admin window and tray.

Closing the admin window only hides it. WiFiDrop keeps running in the tray
until Quit (tray menu or the window's Quit button) or Windows shutdown.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys
import threading
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app import __version__
from app.api.console import create_console_app
from app.api.helper import create_helper_app
from app.api.lan import create_lan_app
from app.core.context import AppContext
from app.core.listeners import LanServer, Listener
from app.core.settings import DB_NAME, Settings, default_data_dir, load_settings
from app.core import legacy, winacl
from app.core.storage import Storage
from app.db.database import DatabaseError, open_database
from app.services import audit, storage_config, uploads
from app.services.upkeep import Upkeep

log = logging.getLogger("wifidrop")

_MUTEX_NAME = r"Local\WiFiDrop.SingleInstance"
_mutex_handle = None  # kept for the life of the process


def acquire_single_instance() -> bool:
    global _mutex_handle
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    ERROR_ALREADY_EXISTS = 183
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def ask_running_copy_to_show(settings: Settings) -> None:
    req = urllib.request.Request(settings.console_url + "api/show", method="POST", data=b"",
                                 headers={"X-WiFiDrop": "1"})
    try:
        urllib.request.urlopen(req, timeout=3).close()
    except OSError as exc:
        log.warning("Could not reach the running copy: %s", exc)


def setup_logging(settings: Settings) -> None:
    handlers: list[logging.Handler] = []
    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(settings.log_dir / "wifidrop.log", maxBytes=2_000_000, backupCount=3,
                                            encoding="utf-8"))
    except OSError:
        pass
    if sys.stderr:  # None in a windowed PyInstaller build
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=handlers)


def prepare_database(ctx: AppContext) -> None:
    """Check and migrate before anyone connects. On failure the admin window still
    opens (so the admin sees why) but the LAN server stays blocked."""
    try:
        conn, report = open_database(ctx.settings.db_path, __version__, ctx.settings.backup_dir)
    except DatabaseError as exc:
        log.error("%s", exc)
        ctx.lan.block(str(exc))
        return
    try:
        log.info("Database at schema %s (was %s)", report.to_version, report.from_version)
        root = storage_config.configured_root(conn, ctx.settings)
        if root is None:
            ctx.lan.block("Choose where WiFiDrop saves files to finish setup.", key="storage")
        else:
            try:
                storage = Storage(root)
                storage.ensure()
                winacl.ensure_private(storage.root)
                ctx.storage = storage
                uploads.sweep(conn, storage)
            except OSError as exc:
                log.error("Storage folder %s is not available: %s", root, exc)
                ctx.lan.block(f"The storage folder {root} is not available. Connect the drive or change the "
                              f"folder.", key="storage")
    finally:
        conn.close()
    ctx.load_flags()


def run_window(ctx: AppContext, start_hidden: bool) -> None:
    import webview

    from app.tray import build_tray

    webview.settings["ALLOW_DOWNLOADS"] = True
    quitting = threading.Event()
    window = webview.create_window("WiFiDrop Admin", ctx.settings.console_url, width=1280, height=860,
                                   min_size=(900, 600), hidden=start_hidden, background_color="#000000")

    told_about_tray = threading.Event()

    def on_closing():
        if quitting.is_set():
            return True
        window.hide()  # keep running in the tray
        ctx.admin_lock.lock_all()  # closing the window locks it when a PIN is set
        if not told_about_tray.is_set():
            told_about_tray.set()
            try:
                icon.notify("WiFiDrop is still running. Right-click the tray icon and choose Quit WiFiDrop to stop it.",
                            "WiFiDrop")
            except Exception:  # notifications can be turned off in Windows
                pass
        return False

    def show():
        window.show()
        window.restore()

    def request_quit():
        # Runs on the tray thread or an API thread: never block it.
        if quitting.is_set():
            return
        quitting.set()

        def shut_down():
            icon.stop()
            window.destroy()
        threading.Thread(target=shut_down, name="quit", daemon=True).start()

    def choose_folder():
        dialog = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
        picked = window.create_file_dialog(dialog)
        return picked[0] if picked else None

    window.events.closing += on_closing
    ctx.choose_folder = choose_folder
    ctx.show_window = show
    ctx.request_quit = request_quit
    icon = build_tray(ctx.lan, show, request_quit)
    threading.Thread(target=icon.run, name="tray", daemon=True).start()
    webview.start()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="WiFiDrop")
    parser.add_argument("--headless", action="store_true", help="no window or tray; Ctrl+C quits (development)")
    parser.add_argument("--background", action="store_true", help="start hidden in the tray (Start with Windows)")
    parser.add_argument("--no-server", action="store_true", help="don't start the LAN web server on launch")
    parser.add_argument("--data-dir", help="use this folder for the database, files and logs (development)")
    parser.add_argument("--reset-admin-pin", action="store_true", help="remove a forgotten admin window PIN")
    args = parser.parse_args(argv)

    settings = load_settings()
    if args.data_dir:
        settings.data_dir = Path(args.data_dir).resolve()
    legacy.migrate_data_dir(settings, default_data_dir())  # FileDrop beta -> WiFiDrop
    legacy.migrate_database(settings.data_dir, DB_NAME)
    setup_logging(settings)

    if not acquire_single_instance():
        log.info("WiFiDrop is already running; showing its window")
        ask_running_copy_to_show(settings)
        return 0

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    winacl.ensure_private(settings.data_dir)
    ctx = AppContext(settings=settings)
    ctx.lan = LanServer(lambda: create_lan_app(ctx), settings.lan_host, settings.lan_port,
                        helper_factory=create_helper_app)
    prepare_database(ctx)
    ctx.lan.tls_dir = settings.tls_dir if ctx.https_enabled() else None
    if args.reset_admin_pin and ctx.admin_lock.enabled:
        conn = ctx.connect()
        try:
            ctx.admin_lock.remove(conn)
            audit.record(conn, "admin.pin_removed", actor="--reset-admin-pin")
        finally:
            conn.close()
        log.info("Admin window PIN removed")

    quit_event = threading.Event()
    ctx.request_quit = quit_event.set
    console = Listener(create_console_app(ctx), settings.console_host, settings.console_port, "console")
    try:
        console.start()
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1

    if settings.start_server_on_launch and not args.no_server:
        ctx.lan.start()
    upkeep = Upkeep(ctx)
    upkeep.start()

    # TODO: handle Windows sign-out/shutdown (WM_QUERYENDSESSION): stop new
    # transfers, mark uploads Interrupted, exit within 5 s.
    try:
        if args.headless:
            log.info("Admin page at %s (Ctrl+C to quit)", settings.console_url)
            while not quit_event.wait(0.5):
                pass
        else:
            run_window(ctx, start_hidden=args.background)
    except KeyboardInterrupt:
        pass
    finally:
        upkeep.stop()
        ctx.lan.stop()
        console.stop()
        log.info("WiFiDrop exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
