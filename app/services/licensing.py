"""Install, activate, check and remove the Pro licence.

Talking to the licence server is always best-effort: a failure leaves the licence as
it was, and the weekly check-in tries again later. The server only ever returns a
signed status, which edition.compute() verifies before it changes anything.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from app import __version__
from app.core import edition
from app.core.errors import ApiError
from app.db.ids import now_ms
from app.services import settings_store, storage_config

log = logging.getLogger(__name__)

LICENCE, STATUS, LAST_TRY = "licence", "licence_status", "licence_checked_at"
CHECK_EVERY_MS = 7 * 24 * 3600 * 1000
RETRY_EVERY_MS = 6 * 3600 * 1000  # until this PC has been activated once


def refresh(ctx, conn) -> edition.Capabilities:
    ctx.caps = edition.compute(settings_store.get(conn, LICENCE), settings_store.get(conn, STATUS),
                               storage_config.install_id(conn))
    return ctx.caps


def _post(url: str, action: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(f"{url.rstrip('/')}/{action}", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": f"FileDrop/{__version__}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read(64 * 1024))
    except urllib.error.HTTPError as exc:  # the server answers errors with JSON too
        try:
            return json.loads(exc.read(64 * 1024))
        except ValueError:
            raise exc


def contact_server(ctx, conn, action: str = "activate", timeout: float = 10) -> dict:
    """Activate or check this PC. Returns {"online": bool, "notice": str} (notice: a line for a toast)."""
    text, url = settings_store.get(conn, LICENCE), ctx.settings.licence_url
    if not text or not url:
        return {"online": False, "notice": ""}
    settings_store.set_value(conn, LAST_TRY, now_ms())
    try:
        reply = _post(url, action, {"licence": text, "install_id": storage_config.install_id(conn),
                                    "app_version": __version__}, timeout)
    except (OSError, ValueError) as exc:
        log.info("Licence server not reached: %s", exc)
        return {"online": False, "notice": "Couldn't reach the licence server. Pro keeps working; FileDrop will "
                                            "try again later."}
    blob = reply.get("status")
    if blob:
        lid = (ctx.caps.licence_id or edition.parse_licence(text)["lid"])
        if edition.parse_status(blob, lid, storage_config.install_id(conn)):
            settings_store.set_value(conn, STATUS, blob)
    refresh(ctx, conn)
    return {"online": True, "notice": str(reply.get("message", ""))[:300]}


def install(ctx, conn, text: str) -> dict:
    try:
        edition.parse_licence(text)
    except edition.LicenceError as exc:
        raise ApiError(400, "INVALID_LICENCE", str(exc))
    settings_store.set_value(conn, LICENCE, edition.normalise(text))
    settings_store.delete(conn, STATUS)
    refresh(ctx, conn)
    return contact_server(ctx, conn, "activate", timeout=8)


def remove(ctx, conn) -> dict:
    """Frees this PC's activation (when online) and goes back to Free. Files and accounts are untouched."""
    result = {"online": False, "notice": ""}
    if settings_store.get(conn, LICENCE):
        result = contact_server(ctx, conn, "deactivate", timeout=6)
    for key in (LICENCE, STATUS, LAST_TRY):
        settings_store.delete(conn, key)
    refresh(ctx, conn)
    return result


def due(ctx, conn) -> bool:
    if not settings_store.get(conn, LICENCE) or not ctx.settings.licence_url:
        return False
    last = settings_store.get(conn, LAST_TRY) or 0
    return now_ms() - last >= (CHECK_EVERY_MS if ctx.caps.activated else RETRY_EVERY_MS)


def require_pro(ctx, feature: str) -> None:
    if not ctx.caps.pro:
        raise ApiError(402, "PRO_REQUIRED", f"{feature} needs FileDrop Pro.", state=ctx.caps.state)
