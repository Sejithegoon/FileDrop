"""The LAN-facing app: the user web page plus the /api/v1 JSON API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import __version__
from app.api.deps import client_ip, csrf, ctx_of, current_user, db, session_and_user
from app.core.errors import ApiError, install_error_handlers
from app.core.settings import resource_path
from app.services import audit, auth, files, spaces, uploads, users

api = APIRouter(prefix="/api/v1", dependencies=[Depends(csrf)])


class LoginBody(BaseModel):
    username: str
    password: str


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


@api.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response, conn=Depends(db)):
    token, user = auth.login(conn, body.username, body.password, client_ip(request),
                             request.headers.get("user-agent", ""))
    response.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_MAX_MS // 1000, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https",
                        path="/")
    return _me(user, ctx_of(request))


@api.post("/auth/logout")
def logout(request: Request, response: Response, conn=Depends(db)):
    found = auth.resolve(conn, request.cookies.get(auth.COOKIE))
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


def file_response(ctx, item) -> FileResponse:
    path = ctx.require_storage().blob_path(item["blob_id"])
    if not path.exists():
        raise ApiError(404, "MISSING", "This file is missing on the server.")
    return FileResponse(path, filename=item["name"], media_type=item["content_type"] or "application/octet-stream",
                        content_disposition_type="attachment",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@api.get("/changes")
def changes(request: Request, user=Depends(current_user)):
    """A number that goes up when anything changes; the page reloads what it shows when it moves."""
    return {"version": ctx_of(request).changes.version}


@api.get("/download/{item_id}")
def download(item_id: str, request: Request, user=Depends(current_user), conn=Depends(db)):
    ctx = ctx_of(request)
    if ctx.downloads_paused:
        raise ApiError(503, "DOWNLOADS_PAUSED", "Downloads are paused by the administrator.")
    item, space, level = _item_access(conn, user, item_id)
    if item["kind"] != "file":
        raise ApiError(400, "NOT_A_FILE", "Only files can be downloaded.")
    return file_response(ctx, item)


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
