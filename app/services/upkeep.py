"""Background upkeep: old trash, stale uploads, and the update check.

Runs in one daemon thread. Every task is best-effort: a failure is logged and
retried on the next round, and never affects file sharing.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.request

from app import __version__
from app.db.ids import now_ms
from app.services import files, uploads

log = logging.getLogger(__name__)

TRASH_DAYS = 30
ROUND_SECONDS = 3600
UPDATE_EVERY_MS = 24 * 3600 * 1000


def purge_old_trash(conn, storage, days: int = TRASH_DAYS) -> int:
    cutoff = now_ms() - days * 24 * 3600 * 1000
    old = conn.execute("SELECT * FROM items WHERE trashed_at IS NOT NULL AND trashed_at < ?", (cutoff,)).fetchall()
    purged = 0
    for item in old:
        if files.get(conn, item["id"]):  # may be gone already with a trashed parent
            files.purge(conn, storage, item)
            purged += 1
    return purged


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def check_for_update(feed_url: str, current: str = __version__) -> dict | None:
    """Reads {"version": "0.2.0", "url": "https://...", "notes": "..."} and returns it if newer."""
    req = urllib.request.Request(feed_url, headers={"User-Agent": f"FileDrop/{current}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read(64 * 1024))
    version, url = str(data.get("version", "")), str(data.get("url", ""))
    if not version or not url.startswith("https://"):
        return None
    if _version_tuple(version) <= _version_tuple(current):
        return None
    return {"version": version, "url": url, "notes": str(data.get("notes", ""))[:500]}


class Upkeep:
    def __init__(self, ctx):
        self.ctx = ctx
        self._stop = threading.Event()
        self._last_update_check = 0

    def start(self) -> None:
        threading.Thread(target=self._loop, name="upkeep", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(5 if not self._last_update_check else ROUND_SECONDS):
            self.run_once()

    def run_once(self) -> None:
        ctx = self.ctx
        if ctx.storage is not None and not ctx.storage_moving:
            conn = ctx.connect()
            try:
                n = purge_old_trash(conn, ctx.storage)
                if n:
                    log.info("Removed %s item(s) that were in the trash for over %s days", n, TRASH_DAYS)
                uploads.sweep(conn, ctx.storage)
            except Exception as exc:
                log.warning("Upkeep failed: %s", exc)
            finally:
                conn.close()
        feed = ctx.settings.update_feed_url
        if feed and now_ms() - self._last_update_check > UPDATE_EVERY_MS:
            try:
                ctx.update_available = check_for_update(feed)
            except Exception as exc:  # offline is normal
                log.info("Update check skipped: %s", exc)
        self._last_update_check = now_ms()
