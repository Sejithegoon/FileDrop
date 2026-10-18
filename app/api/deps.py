"""FastAPI dependencies shared by the routes."""

from __future__ import annotations

from fastapi import Depends, Request

from app.core.context import AppContext
from app.core.errors import ApiError
from app.services import auth


def ctx_of(request: Request) -> AppContext:
    return request.app.state.ctx


def db(request: Request):
    conn = ctx_of(request).connect()
    try:
        yield conn
    finally:
        conn.close()


def csrf(request: Request) -> None:
    """State-changing requests must carry X-WiFiDrop: 1 (the beta's X-FileDrop is also accepted). Browsers won't send a custom
    header cross-site without a CORS preflight, which we never allow."""
    if request.method not in ("GET", "HEAD", "OPTIONS") and "1" not in (request.headers.get("x-wifidrop"), request.headers.get("x-filedrop")):
        raise ApiError(403, "CSRF", "Request blocked.")


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""


def session_and_user(request: Request, conn=Depends(db)):
    found = auth.resolve(conn, request.cookies.get(auth.COOKIE), client_ip(request))
    if not found:
        raise ApiError(401, "UNAUTHENTICATED", "Please sign in.")
    return found


def current_user(found=Depends(session_and_user)):
    session, user = found
    if user["must_change_password"]:
        raise ApiError(403, "PASSWORD_CHANGE_REQUIRED", "Choose a new password first.")
    return user
