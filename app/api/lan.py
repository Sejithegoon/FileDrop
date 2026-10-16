"""The LAN-facing app: user and admin web UI plus the /api/v1 JSON API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.settings import resource_path


def create_lan_app() -> FastAPI:
    app = FastAPI(title="FileDrop", version=__version__, docs_url=None, redoc_url=None)

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"ok": True, "version": __version__}

    # Routers for auth, files, uploads, admin and events get included here.

    app.mount("/", StaticFiles(directory=resource_path("web"), html=True), name="web")
    return app
