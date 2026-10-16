"""System tray icon and menu."""

from __future__ import annotations

import ctypes
import sys
import threading
import webbrowser
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from app.core.listeners import LanServer


def _icon_image() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(37, 99, 235, 255))
    d.polygon([(32, 14), (48, 32), (38, 32), (38, 48), (26, 48), (26, 32), (16, 32)], fill="white")
    return img


def _confirm(text: str) -> bool:
    if sys.platform != "win32":
        return True
    MB_YESNO, MB_ICONQUESTION, MB_TOPMOST, IDYES = 0x4, 0x20, 0x40000, 6
    return ctypes.windll.user32.MessageBoxW(0, text, "FileDrop", MB_YESNO | MB_ICONQUESTION | MB_TOPMOST) == IDYES


def build_tray(lan: LanServer, console_url: str, request_quit: Callable[[], None]) -> pystray.Icon:
    def open_console(icon, item):
        webbrowser.open(console_url)

    def toggle_server(icon, item):
        def work():
            lan.stop() if lan.state == "running" else lan.start()
            icon.update_menu()
        threading.Thread(target=work, daemon=True).start()

    def quit_app(icon, item):
        # TODO: list active transfers and sessions once they exist.
        if _confirm("Quit FileDrop? The web server will stop for everyone."):
            request_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Open console", open_console, default=True),
        pystray.MenuItem(
            lambda item: "Stop web server" if lan.state == "running" else "Start web server",
            toggle_server,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit FileDrop", quit_app),
    )
    return pystray.Icon("FileDrop", _icon_image(), "FileDrop", menu)
