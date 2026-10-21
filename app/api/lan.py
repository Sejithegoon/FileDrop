"""The LAN-facing app: the user web page plus the /api/v1 JSON API."""

from __future__ import annotations

import hashlib
import socket

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Literal

from app import __version__
from app.api.deps import client_ip, csrf, ctx_of, current_user, db, session_and_user, session_token
from app.core.errors import ApiError, install_error_handlers
from app.core.settings import resource_path
from app.core.names import name_key
from app.services import audit, auth, files, spaces, storage_config, thumbs, uploads, users

api = APIRouter(prefix="/api/v1", dependencies=[Depends(csrf)])

API_VERSION = 1  # bump when the phone app needs something new from this API
MIN_APP_API = 1  # oldest app API this server still serves; older apps ask the user to update


def pc_name() -> str:
    return socket.gethostname() or "WiFiDrop PC"


def server_id(conn) -> str:
    """A stable public id for this PC so the app recognises it after its address changes.
    Derived from the install id, which itself stays private (the licence server uses it)."""
    return hashlib.sha256(f"wifidrop-server:{storage_config.install_id(conn)}".encode()).hexdigest()[:20]


class LoginBody(BaseModel):
    username: str
    password: str
    client: Literal["web", "app"] = "web"  # "app": the phone app gets the token in the reply instead of a cookie
    device: str = ""  # the phone app's name for the phone, e.g. "Sam's iPhone"; shown in the admin window


class PasswordBody(BaseModel):
    current: str
    new: str


class NameBody(BaseModel):
    name: str


class ItemPatch(BaseModel):
    name: str | None = None
    parent_id: str | None = None


class FolderBody(BaseModel):
    parent_id: str
    name: str


class UploadBody(BaseModel):
    space_id: str
    parent_id: str
    name: str
    size: int


def _me(user, ctx) -> dict:
    return {
        "user": {"id": user["id"], "username": user["username"], "display_name": user["display_name"],
                 "role": user["role"], "must_change_password": bool(user["must_change_password"])},
        "status": {"uploads_paused": ctx.uploads_blocked, "downloads_paused": ctx.downloads_paused},
        "version": __version__,
        "edition": ctx.caps.edition, "features": {"auto_upload": ctx.caps.pro},
    }


def _space_access(conn, user, space_id: str):
    space = spaces.get(conn, space_id)
    level = spaces.level_for(conn, user, space)
    if not level:
        raise ApiError(404, "NOT_FOUND", "Folder not found.")
    return space, level


def _item_access(conn, user, item_id: str, *, allow_trashed: bool = False):
    item = files.get(conn, item_id)
    if not item:
        raise ApiError(404, "NOT_FOUND", "That item no longer exists.")
    space, level = _space_access(conn, user, item["space_id"])
    if not allow_trashed and not files.is_visible(conn, item_id):
        raise ApiError(404, "NOT_FOUND", "That item no longer exists.")
    return item, space, level


def _require_modify(level, item, user) -> None:
    if not spaces.can_modify(level, item, user):
        raise ApiError(403, "FORBIDDEN", "You can only change items you added.")


# ---- auth -------------------------------------------------------------------

@api.get("/health")
def health():
    return {"ok": True, "version": __version__}


@api.get("/info")
def info(request: Request, conn=Depends(db)):
    """Who this is, before signing in: lets the phone app check it found a WiFiDrop PC it can talk to."""
    return {"app": "wifidrop", "api": API_VERSION, "min_app_api": MIN_APP_API, "version": __version__,
            "name": pc_name(), "server_id": server_id(conn)}


@api.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, conn=Depends(db)):
    agent = request.headers.get("user-agent", "")
    if body.client == "app":
        agent = f"WiFiDrop app on {body.device.strip()[:80] or 'a phone'} ({agent[:150]})"
    token, user = auth.login(conn, body.username, body.password, client_ip(request), agent, body.client)
    if body.client == "app":
        return {**_me(user, ctx_of(request)), "token": token}
    response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_MAX_MS // 1000, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https",
                        path="/")
    return _me(user, ctx_of(request))


@api.post("/auth/logout")
def logout(request: Request, response: Response, conn=Depends(db)):
    found = auth.resolve(conn, session_token(request))
    if found:
        auth.logout(conn, found[0]["id"])
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@api.get("/me")
def me(request: Request, found=Depends(session_and_user)):
    return _me(found[1], ctx_of(request))


@api.post("/me/password")
def change_password(body: PasswordBody, request: Request, found=Depends(session_and_user), conn=Depends(db)):
    session, user = found
    users.change_own_password(conn, user, body.current, body.new, session["id"])
    audit.record(conn, "password.change", actor=user, ip=client_ip(request))
    return _me(users.get(conn, user["id"]), ctx_of(request))


# ---- browsing -----------------------------------------------------------------

@api.get("/spaces")
def list_spaces(user=Depends(current_user), conn=Depends(db)):
    return {"spaces": spaces.accessible(conn, user)}


@api.get("/spaces/{space_id}/items")
def list_items(space_id: str, folder: str = "root", user=Depends(current_user), conn=Depends(db)):
    space, level = _space_access(conn, user, space_id)
    folder_id = spaces.root_id(conn, space_id) if folder == "root" else folder
    files.require_folder(conn, folder_id, space_id)
    items = [files.to_json(i, user, spaces.can_modify(level, i, user)) for i in files.children(conn, folder_id)]
    return {
        "space": {"id": space["id"], "name": space["name"], "kind": space["kind"], "level": level,
                  "quota_bytes": space["quota_bytes"], "used_bytes": spaces.usage(conn, space_id)},
        "folder_id": folder_id, "crumbs": files.crumbs(conn, folder_id), "items": items,
        "can_upload": spaces.can_upload(level),
    }


@api.post("/spaces/{space_id}/folders")
def new_folder(space_id: str, body: FolderBody, user=Depends(current_user), conn=Depends(db)):
    space, level = _space_access(conn, user, space_id)
    if not spaces.can_upload(level):
        raise ApiError(403, "FORBIDDEN", "You can't add things to this folder.")
    parent = files.require_folder(conn, body.parent_id, space_id)
    iid = files.create_folder(conn, parent, body.name, user["id"], user["username"])
    return files.to_json(files.get(conn, iid), user, True)


@api.patch("/items/{item_id}")
def update_item(item_id: str, body: ItemPatch, user=Depends(current_user), conn=Depends(db)):
    """Rename (name) and/or move to another folder in the same space (parent_id)."""
    item, space, level = _item_access(conn, user, item_id)
    _require_modify(level, item, user)
    if body.parent_id is not None:
        if not spaces.can_upload(level):
            raise ApiError(403, "FORBIDDEN", "You can't add things to that folder.")
        files.move(conn, item, files.require_folder(conn, body.parent_id, item["space_id"]))
        item = files.get(conn, item_id)
    if body.name is not None:
        files.rename(conn, item, body.name)
    return files.to_json(files.get(conn, item_id), user, True)


@api.get("/spaces/{space_id}/folders")
def list_folders(space_id: str, exclude: str | None = None, user=Depends(current_user), conn=Depends(db)):
    space, level = _space_access(conn, user, space_id)
    return {"folders": files.folder_paths(conn, space_id, exclude)}


@api.delete("/items/{item_id}")
def trash_item(item_id: str, user=Depends(current_user), conn=Depends(db)):
    item, space, level = _item_access(conn, user, item_id)
    _require_modify(level, item, user)
    files.trash(conn, item, user["id"])
    return {"ok": True}


@api.get("/spaces/{space_id}/trash")
def list_trash(space_id: str, user=Depends(current_user), conn=Depends(db)):
    space, level = _space_access(conn, user, space_id)
    items = [i for i in files.trashed(conn, space_id) if spaces.can_modify(level, i, user)]
    return {"items": [files.to_json(i, user, True) for i in items]}


@api.post("/items/{item_id}/restore")
def restore_item(item_id: str, user=Depends(current_user), conn=Depends(db)):
    item, space, level = _item_access(conn, user, item_id, allow_trashed=True)
    _require_modify(level, item, user)
    files.restore(conn, item)
    return {"ok": True}


@api.delete("/items/{item_id}/purge")
def purge_item(item_id: str, request: Request, user=Depends(current_user), conn=Depends(db)):
    item, space, level = _item_access(conn, user, item_id, allow_trashed=True)
    _require_modify(level, item, user)
    files.purge(conn, ctx_of(request).require_storage(), item)
    return {"ok": True}


@api.delete("/spaces/{space_id}/trash")
def empty_trash(space_id: str, request: Request, user=Depends(current_user), conn=Depends(db)):
    space, level = _space_access(conn, user, space_id)
    if spaces.rank(level) < spaces.rank("manage"):
        raise ApiError(403, "FORBIDDEN", "Only managers can empty this trash.")
    return {"purged": files.empty_trash(conn, ctx_of(request).require_storage(), space_id)}


# ---- transfers ----------------------------------------------------------------

@api.post("/uploads")
def start_upload(body: UploadBody, request: Request, user=Depends(current_user), conn=Depends(db)):
    space, level = _space_access(conn, user, body.space_id)
    if not spaces.can_upload(level):
        raise ApiError(403, "FORBIDDEN", "You can't upload to this folder.")
    parent = files.require_folder(conn, body.parent_id, body.space_id)
    ctx = ctx_of(request)
    return uploads.create(conn, ctx.require_storage(), paused=ctx.uploads_blocked, user=user, space=space, parent=parent,
                          name=body.name, size=body.size)


def _own_upload(conn, user, upload_id: str):
    up = uploads.get(conn, upload_id)
    if not up or up["user_id"] != user["id"]:
        raise ApiError(404, "NOT_FOUND", "Upload not found.")
    return up


@api.get("/uploads/{upload_id}")
def upload_status(upload_id: str, user=Depends(current_user), conn=Depends(db)):
    return uploads.to_json(_own_upload(conn, user, upload_id))


@api.put("/uploads/{upload_id}/chunks/{index}")
async def upload_chunk(upload_id: str, index: int, request: Request, user=Depends(current_user), conn=Depends(db)):
    return await uploads.write_chunk(conn, ctx_of(request).require_storage(), _own_upload(conn, user, upload_id), index, request)


@api.post("/uploads/{upload_id}/complete")
def finish_upload(upload_id: str, request: Request, user=Depends(current_user), conn=Depends(db)):
    return uploads.complete(conn, ctx_of(request).require_storage(), _own_upload(conn, user, upload_id), user)


@api.delete("/uploads/{upload_id}")
def cancel_upload(upload_id: str, request: Request, user=Depends(current_user), conn=Depends(db)):
    uploads.cancel(conn, ctx_of(request).require_storage(), _own_upload(conn, user, upload_id))
    return {"ok": True}


def file_response(ctx, item, inline: bool = False) -> FileResponse:
    """The file itself. inline=True shows pictures, videos and audio inside the page (previews); every
    other type, and anything that could run code (SVG, HTML), is always a download."""
    path = ctx.require_storage().blob_path(item["blob_id"])
    if not path.exists():
        raise ApiError(404, "MISSING", "This file is missing on the server.")
    media_type = item["content_type"] or "application/octet-stream"
    show = inline and media_type in thumbs.INLINE_TYPES
    return FileResponse(path, filename=item["name"], media_type=media_type,
                        content_disposition_type="inline" if show else "attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
                                 "Content-Security-Policy": "sandbox; default-src 'none'"})


def thumb_response(ctx, item) -> FileResponse:
    path = thumbs.get(ctx.require_storage(), item)
    if not path:
        raise ApiError(404, "NO_PREVIEW", "This file has no preview.")
    return FileResponse(path, media_type="image/jpeg",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=604800"})


@api.get("/changes")
def changes(request: Request, user=Depends(current_user)):
    """A number that goes up when anything changes; the page reloads what it shows when it moves."""
    return {"version": ctx_of(request).changes.version}


@api.get("/download/{item_id}")
def download(item_id: str, request: Request, inline: bool = False, user=Depends(current_user), conn=Depends(db)):
    ctx = ctx_of(request)
    if ctx.downloads_paused:
        raise ApiError(503, "DOWNLOADS_PAUSED", "Downloads are paused by the administrator.")
    item, space, level = _item_access(conn, user, item_id)
    if item["kind"] != "file":
        raise ApiError(400, "NOT_A_FILE", "Only files can be downloaded.")
    return file_response(ctx, item, inline)


@api.get("/thumb/{item_id}")
async def thumb(item_id: str, request: Request, user=Depends(current_user), conn=Depends(db)):
    """A small JPEG preview for the file lists (404 NO_PREVIEW when there isn't one)."""
    item, space, level = _item_access(conn, user, item_id)
    return await run_in_threadpool(thumb_response, ctx_of(request), item)


@api.put("/items/{item_id}/thumb")
async def put_thumb(item_id: str, request: Request, user=Depends(current_user), conn=Depends(db)):
    """The phone app sends a preview it made for an iPhone photo (HEIC) or a video it just uploaded."""
    item, space, level = _item_access(conn, user, item_id)
    if not (item["created_by"] == user["id"] or spaces.can_modify(level, item, user)):
        raise ApiError(403, "FORBIDDEN", "You can only add previews to files you added.")
    data = bytearray()
    async for part in request.stream():
        data += part
        if len(data) > thumbs.MAX_UPLOADED_BYTES:
            raise ApiError(413, "PREVIEW_TOO_LARGE", "The preview is too large.")
    await run_in_threadpool(thumbs.save_from_phone, ctx_of(request).require_storage(), item, bytes(data))
    return {"ok": True}


@api.get("/search")
def search(q: str = "", limit: int = 50, user=Depends(current_user), conn=Depends(db)):
    """Files and folders whose name contains q, in every folder this person can open."""
    needle = name_key(q.strip())
    if not needle:
        return {"results": []}
    reachable = {s["id"]: s for s in spaces.accessible(conn, user)}
    if not reachable:
        return {"results": []}
    pattern = "%" + needle.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"
    marks = ",".join("?" * len(reachable))
    rows = conn.execute(
        "SELECT i.*, (SELECT count(*) FROM items c WHERE c.parent_id = i.id AND c.trashed_at IS NULL) AS child_count"
        f" FROM items i WHERE i.space_id IN ({marks}) AND i.parent_id IS NOT NULL AND i.trashed_at IS NULL"
        " AND i.name_key LIKE ? ESCAPE '!' ORDER BY i.kind = 'file', i.modified_at DESC LIMIT ?",
        (*reachable, pattern, max(1, min(limit, 200)) * 2)).fetchall()
    results = []
    for row in rows:
        if not files.is_visible(conn, row["id"]):
            continue
        space = reachable[row["space_id"]]
        path = [c["name"] for c in files.crumbs(conn, row["parent_id"])][1:]
        results.append({**files.to_json(row, user, spaces.can_modify(space["level"], row, user)),
                        "space": {"id": space["id"], "name": space["name"], "kind": space["kind"]},
                        "parent_id": row["parent_id"], "path": path})
        if len(results) >= limit:
            break
    return {"results": results}


def create_lan_app(ctx) -> FastAPI:
    app = FastAPI(title="WiFiDrop", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.ctx = ctx
    install_error_handlers(app)
    app.include_router(api)

    @app.middleware("http")
    async def no_cache_html(request: Request, call_next):
        response = await call_next(request)
        ctx.changes.note_request(request.method, request.url.path, response.status_code)
        if not request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/", StaticFiles(directory=resource_path("web"), html=True), name="web")
    return app
