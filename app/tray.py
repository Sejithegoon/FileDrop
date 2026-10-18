"""System tray icon and menu."""

from __future__ import annotations

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


def build_tray(lan: LanServer, show: Callable[[], None], request_quit: Callable[[], None]) -> pystray.Icon:
    def toggle_server(icon, item):
        def work():
            lan.stop() if lan.state == "running" else lan.start()
            icon.update_menu()
        threading.Thread(target=work, daemon=True).start()

    def quit_app(icon, item):
        # No Yes/No box here: a dialog opened from the tray can end up hidden behind
        # other windows, which made Quit look like it did nothing.
        request_quit()

    menu = pystray.Menu(
        pystray.MenuItem("Open WiFiDrop", lambda icon, item: show(), default=True),
        pystray.MenuItem(lambda item: "Stop web server" if lan.state == "running" else "Start web server",
                         toggle_server),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit WiFiDrop", quit_app),
    )
    return pystray.Icon("WiFiDrop", icon_image(), "WiFiDrop", menu)
