"""Optional PIN for the admin window.

With a PIN set, every admin API call except unlock/show needs a short-lived
unlock cookie. Tokens live in memory only: they vanish on restart, when the
window is closed (hidden to the tray), or after 30 idle minutes. Background
polling by the dashboard doesn't count as activity.
"""

from __future__ import annotations

import secrets
import threading
import time

from app.core.errors import ApiError
from app.services import settings_store
from app.services.passwords import hash_password, verify_password

KEY = "admin_pin_hash"
COOKIE = "fd_admin"
IDLE_SECONDS = 30 * 60
MIN_LEN, MAX_LEN = 4, 64
FAIL_LIMIT, FAIL_PAUSE = 5, 60


class AdminLock:
    def __init__(self):
        self.pin_hash: str | None = None
        self._tokens: dict[str, float] = {}
        self._fails: list[float] = []
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.pin_hash is not None

    def load(self, conn) -> None:
        self.pin_hash = settings_store.get(conn, KEY)

    def is_unlocked(self, token: str | None, activity: bool) -> bool:
        if not self.enabled:
            return True
        now = time.monotonic()
        with self._lock:
            expiry = self._tokens.get(token or "")
            if not expiry or expiry < now:
                self._tokens.pop(token or "", None)
                return False
            if activity:
                self._tokens[token] = now + IDLE_SECONDS
            return True

    def unlock(self, pin: str) -> str:
        now = time.monotonic()
        with self._lock:
            self._fails = [t for t in self._fails if t > now - FAIL_PAUSE]
            if len(self._fails) >= FAIL_LIMIT:
                raise ApiError(429, "LOCKED_OUT", "Too many wrong PINs. Wait a minute and try again.")
        if not verify_password(self.pin_hash, pin):
            with self._lock:
                self._fails.append(now)
            raise ApiError(401, "WRONG_PIN", "That PIN is not right.")
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._fails.clear()
            self._tokens[token] = now + IDLE_SECONDS
        return token

    def lock_all(self) -> None:
        with self._lock:
            self._tokens.clear()

    def set_pin(self, conn, pin: str) -> str:
        pin = pin.strip()
        if not MIN_LEN <= len(pin) <= MAX_LEN:
            raise ApiError(400, "INVALID_PIN", f"Use {MIN_LEN} to {MAX_LEN} characters.")
        self.pin_hash = hash_password(pin)
        settings_store.set_value(conn, KEY, self.pin_hash)
        self.lock_all()
        return self.unlock(pin)

    def remove(self, conn) -> None:
        self.pin_hash = None
        settings_store.set_value(conn, KEY, None)
        self.lock_all()
