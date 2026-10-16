"""Entry point: single-instance check, console listener, LAN listener, tray.

Closing the console page never stops FileDrop. Only tray Quit, the console's
Quit button, or Windows shutdown ends the process.
"""

from __future__ import annotations

import argparse
import ctypes
import logging
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler

from app.api.console import create_console_app
from app.api.lan import create_lan_app
from app.core.listeners import LanServer, Listener
from app.core.settings import Settings, load_settings

log = logging.getLogger("filedrop")

_MUTEX_NAME = r"Local\FileDrop.SingleInstance"
_mutex_handle = None  # kept for the life of the process


def acquire_single_instance() -> bool:
    global _mutex_handle
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    ERROR_ALREADY_EXISTS = 183
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def setup_logging(settings: Settings) -> None:
    handlers: list[logging.Handler] = []
    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(settings.log_dir / "filedrop.log", maxBytes=2_000_000, backupCount=3))
    except OSError:
        pass
    if sys.stderr:  # None in a windowed PyInstaller build
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=handlers)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="FileDrop")
    parser.add_argument("--headless", action="store_true", help="no tray icon; Ctrl+C quits (development)")
    parser.add_argument("--start-server", action="store_true", help="start the LAN web server on launch")
    args = parser.parse_args(argv)

    settings = load_settings()
    setup_logging(settings)

    if not acquire_single_instance():
        log.info("FileDrop is already running; opening its console")
        webbrowser.open(settings.console_url)
        return 0

    quit_event = threading.Event()
    lan = LanServer(create_lan_app, settings.lan_host, settings.lan_port)
    console = Listener(create_console_app(lan, quit_event.set), settings.console_host, settings.console_port, "console")
    try:
        console.start()
    except RuntimeError as exc:
        log.error("%s", exc)
        return 1

    if args.start_server or settings.start_server_on_launch:
        lan.start()

    # TODO: handle Windows sign-out/shutdown (WM_QUERYENDSESSION): stop new
    # transfers, mark uploads Interrupted, exit within 5 s.
    try:
        if args.headless:
            log.info("Console at %s (Ctrl+C to quit)", settings.console_url)
            while not quit_event.wait(0.5):
                pass
        else:
            from app.tray import build_tray

            icon = build_tray(lan, settings.console_url, quit_event.set)
            threading.Thread(target=lambda: (quit_event.wait(), icon.stop()), daemon=True).start()
            icon.run()
    except KeyboardInterrupt:
        pass
    finally:
        lan.stop()
        console.stop()
        log.info("FileDrop exited")
    return 0


if __name__ == "__main__":
    sys.exit(main())
