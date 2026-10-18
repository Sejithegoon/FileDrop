"""A counter that goes up whenever something changes, so open pages know to refresh.

Pages poll it every few seconds (only while visible) and reload what they show when the
number moves. It's in memory: a restart starts again from 0, which pages treat as a change.
"""

from __future__ import annotations

import threading

# Requests that change nothing other people see, or happen too often to signal (upload chunks).
_QUIET = ("/chunks/", "/api/lock", "/api/unlock", "/api/show", "/api/storage/check", "/api/storage/choose")


class ChangeFeed:
    def __init__(self):
        self._version = 0
        self._lock = threading.Lock()

    @property
    def version(self) -> int:
        return self._version

    def bump(self) -> None:
        with self._lock:
            self._version += 1

    def note_request(self, method: str, path: str, status: int) -> None:
        """Called after every API request: a successful change bumps the counter."""
        if method in ("POST", "PUT", "PATCH", "DELETE") and status < 400 and path.startswith("/api/") \
                and not any(q in path for q in _QUIET):
            self.bump()
