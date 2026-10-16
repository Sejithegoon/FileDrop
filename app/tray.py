"""System tray icon and menu."""

from __future__ import annotations

import ctypes
import sys
import threading
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from app.core.listeners import LanServer


def icon_image(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64
    d.rounded_rectangle((4 * s, 4 * s, 60 * s, 60 * s), radius=14 * s, fill=(47, 123, 255, 255))
    d.polygon([(32 * s, 14 * s), (48 * s, 32 * s), (38 * s, 32 * s), (38 * s, 48 * s), (26 * s, 48 * s),
               (26 * s, 32 * s), (16 * s, 32 * s)], fill="white")
    return img


def confirm(text: str) -> bool:
    if sys.platform != "win32":
        return True
    MB_YESNO, MB_ICONQUESTION, MB_TOPMOST, IDYES = 0x4, 0x20, 0x40000, 6
    return ctypes.windll.user32.MessageBoxW(0, text, "FileDrop", MB_YESNO | MB_ICONQUESTION | MB_TOPMOST) == IDYES


def build_tray(lan: LanServer, show: Callable[[], None], request_quit: Callable[[], None]) -> pystray.Icon:
    def toggle_server(icon, item):
        def work():
            lan.stop() if lan.state == "running" else lan.start()
            icon.update_menu()
        threading.Thread(target=work, daemon=True).start()

    def quit_app(icon, item):
        if confirm("Quit FileDrop? The web server will stop for everyone."):
            request_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Open FileDrop", lambda icon, item: show(), default=True),
        pystray.MenuItem(lambda item: "Stop web server" if lan.state == "running" else "Start web server",
                         toggle_server),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit FileDrop", quit_app),
    )
    return pystray.Icon("FileDrop", icon_image(), "FileDrop", menu)
