"""HTTP listeners run in background threads so the tray can own the main thread.

Listener      one uvicorn server on one host:port.
LanServer     the user-facing web server that Start/Stop controls.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import uvicorn

from .network import resolve_lan_host

log = logging.getLogger(__name__)


class Listener:
    def __init__(self, app, host: str, port: int, name: str):
        self.app, self.host, self.port, self.name = app, host, port, name
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._server and self._server.started)

    def start(self, timeout: float = 5.0) -> None:
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_config=None, lifespan="off")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._run, name=f"listener-{self.name}", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                log.info("%s listening on http://%s:%s", self.name, self.host, self.port)
                return
            if not self._thread.is_alive():
                break
            time.sleep(0.05)
        self.stop()
        raise RuntimeError(f"{self.name} could not listen on {self.host}:{self.port} (port in use?)")

    def _run(self) -> None:
        try:
            self._server.run()
        except SystemExit:  # uvicorn exits the thread when it cannot bind
            pass

    def stop(self, timeout: float = 5.0) -> None:
        if not self._server or not self._thread:
            return
        self._server.should_exit = True
        self._thread.join(timeout)
        if self._thread.is_alive():
            self._server.force_exit = True
            self._thread.join(timeout)
        log.info("%s stopped", self.name)
        self._server = self._thread = None


class LanServer:
    """Start/Stop state for the LAN listener. Drain mode and transfer cancellation come later."""

    def __init__(self, app_factory: Callable[[], object], host: str, port: int):
        self._app_factory = app_factory
        self._configured_host = host
        self.port = port
        self.state = "stopped"
        self.address: str | None = None
        self.last_error: str | None = None
        self.blocked_reason: str | None = None
        self._listener: Listener | None = None
        self._lock = threading.Lock()

    def block(self, reason: str) -> None:
        """Refuse to start, e.g. when the database can't be opened."""
        self.blocked_reason = self.last_error = reason

    def status(self) -> dict:
        return {
            "state": self.state,
            "url": f"http://{self.address}:{self.port}/" if self.state == "running" else None,
            "error": self.last_error,
        }

    def start(self) -> dict:
        with self._lock:
            if self.state == "running":
                return self.status()
            if self.blocked_reason:
                self.last_error = self.blocked_reason
                return self.status()
            self.state, self.last_error = "starting", None
            try:
                self.address = resolve_lan_host(self._configured_host)
                self._listener = Listener(self._app_factory(), self.address, self.port, "lan")
                self._listener.start()
                self.state = "running"
            except Exception as exc:
                log.error("LAN server failed to start: %s", exc)
                self.state, self.last_error, self._listener = "stopped", str(exc), None
            return self.status()

    def stop(self) -> dict:
        with self._lock:
            if self._listener:
                self.state = "stopping"
                self._listener.stop()
                self._listener = None
            self.state = "stopped"
            return self.status()
