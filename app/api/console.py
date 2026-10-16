"""The host console app. Served on 127.0.0.1 only, always on while FileDrop runs."""

from __future__ import annotations

import threading
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.listeners import LanServer
from app.core.settings import resource_path


def _require_console_header(x_filedrop_console: str | None = Header(default=None)) -> None:
    # A custom header forces a CORS preflight, so other websites open in the
    # host's browser cannot drive these endpoints.
    if x_filedrop_console != "1":
        raise HTTPException(status_code=403, detail="Console requests must come from the console page.")


def create_console_app(lan: LanServer, request_quit: Callable[[], None]) -> FastAPI:
    app = FastAPI(title="FileDrop console", version=__version__, docs_url=None, redoc_url=None)
    guarded = [Depends(_require_console_header)]

    @app.get("/api/server")
    def server_status() -> dict:
        return lan.status()

    @app.post("/api/server/start", dependencies=guarded)
    def server_start() -> dict:
        return lan.start()

    @app.post("/api/server/stop", dependencies=guarded)
    def server_stop() -> dict:
        return lan.stop()

    @app.post("/api/quit", dependencies=guarded)
    def quit_app() -> dict:
        threading.Timer(0.2, request_quit).start()  # let this response go out first
        return {"quitting": True}

    app.mount("/", StaticFiles(directory=resource_path("console"), html=True), name="console")
    return app
