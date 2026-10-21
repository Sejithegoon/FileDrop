"""HTTP listeners run in background threads so the tray can own the main thread.

Listener      one uvicorn server on one host:port.
LanServer     the user-facing web server that Start/Stop controls.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from pathlib import Path
from typing import Callable

import uvicorn

from .network import resolve_lan_host
from .tls import ensure_certificate, pin_code

log = logging.getLogger(__name__)


class Listener:
    def __init__(self, app, host: str, port: int, name: str, cert=None):
        self.app, self.host, self.port, self.name = app, host, port, name
        self.cert = cert  # tls.CertInfo for HTTPS, None for plain HTTP
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._server and self._server.started)

    def start(self, timeout: float = 5.0) -> None:
        tls = {"ssl_certfile": str(self.cert.cert_path), "ssl_keyfile": str(self.cert.key_path)} if self.cert else {}
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_config=None, lifespan="off", **tls)
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._run, name=f"listener-{self.name}", daemon=True)
        self._thread.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._server.started:
                log.info("%s listening on %s://%s:%s", self.name, "https" if self.cert else "http", self.host, self.port)
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
    """Start/Stop state for the LAN listener, over HTTPS when tls_dir is set."""

    HELPER_PORTS = (80, 8080)  # plain-HTTP help page; first free one wins

    def __init__(self, app_factory: Callable[[], object], host: str, port: int, tls_dir: Path | None = None,
                 helper_factory: Callable[[str], object] | None = None, announcer=None,
                 announce_txt: Callable[[], dict[str, str]] | None = None):
        self._app_factory = app_factory
        self._helper_factory = helper_factory
        self._helper: Listener | None = None
        self.helper_url: str | None = None
        self._configured_host = host
        self.port = port
        self.tls_dir = tls_dir  # HTTPS when set
        self.fingerprint: str | None = None
        self.pin: str | None = None  # public key pin for the phone app (see tls.public_key_pin)
        self.state = "stopped"
        self.address: str | None = None
        self.last_error: str | None = None
        self._blockers: dict[str, str] = {}
        self._listener: Listener | None = None
        self._lock = threading.Lock()
        self._announcer = announcer  # discovery.Announcer: lets the phone app find this PC
        self._announce_txt = announce_txt or (lambda: {})

    @property
    def scheme(self) -> str:
        return "https" if self.tls_dir else "http"

    @property
    def blocked_reason(self) -> str | None:
        return next(iter(self._blockers.values()), None)

    def block(self, reason: str, key: str = "db") -> None:
        """Refuse to start, e.g. when the database can't be opened or no storage folder is set."""
        self._blockers[key] = reason
        self.last_error = self.blocked_reason

    def unblock(self, key: str) -> None:
        self._blockers.pop(key, None)
        if self.state != "running":
            self.last_error = self.blocked_reason

    def status(self) -> dict:
        return {
            "state": self.state,
            "url": f"{self.scheme}://{self.address}:{self.port}/" if self.state == "running" else None,
            "https": self.tls_dir is not None, "fingerprint": self.fingerprint,
            "pin": self.pin, "pin_code": pin_code(self.pin) if self.pin else None,
            "helper_url": self.helper_url if self.state == "running" else None,
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
                cert = ensure_certificate(self.tls_dir, self.address) if self.tls_dir else None
                self.fingerprint = cert.fingerprint if cert else None
                self.pin = cert.pin if cert else None
                self._listener = Listener(self._app_factory(), self.address, self.port, "lan", cert)
                self._listener.start()
                self.state = "running"
                if cert and self._helper_factory:
                    self._start_helper()
                self._announce()
            except Exception as exc:
                log.error("LAN server failed to start: %s", exc)
                self.state, self.last_error, self._listener = "stopped", str(exc), None
            return self.status()

    def _announce(self) -> None:
        if not self._announcer:
            return
        try:
            txt = {"api": "1", "https": "1" if self.tls_dir else "0", "ip": self.address, "port": str(self.port),
                   **self._announce_txt()}
            self._announcer.start(self.address, self.port, socket.gethostname() or "PC", txt)
        except Exception as exc:  # discovery is a convenience; the server runs without it
            log.info("Network announcement skipped: %s", exc)

    def _start_helper(self) -> None:
        """Best effort: if ports 80 and 8080 are both taken, HTTPS still works without the help page."""
        secure_url = f"https://{self.address}:{self.port}/"
        for port in self.HELPER_PORTS:
            helper = Listener(self._helper_factory(secure_url), self.address, port, "http-help")
            try:
                helper.start(timeout=3.0)
            except RuntimeError:
                continue
            self._helper = helper
            self.helper_url = f"http://{self.address}/" if port == 80 else f"http://{self.address}:{port}/"
            return
        log.info("No free port for the plain-HTTP help page; skipping it")

    def stop(self) -> dict:
        with self._lock:
            if self._announcer:
                self._announcer.stop()
            if self._helper:
                self._helper.stop()
                self._helper, self.helper_url = None, None
            if self._listener:
                self.state = "stopping"
                self._listener.stop()
                self._listener = None
            self.state = "stopped"
            return self.status()
