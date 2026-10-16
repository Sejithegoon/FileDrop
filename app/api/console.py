"""Admin API and page for the desktop window. Served on 127.0.0.1 only.

Only the FileDrop window on this PC talks to it. Requests must carry
X-FileDrop: 1 (blocks other websites) and a localhost Host header (blocks DNS
rebinding).
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import threading

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import __version__
from app.api.deps import csrf, ctx_of, db
from app.api.lan import file_response
from app.core.errors import ApiError, install_error_handlers
from app.core.network import primary_ipv4
from app.core.settings import resource_path
from app.services import audit, auth, files, settings_store, spaces, uploads, users

ACTOR = "admin (this PC)"
api = APIRouter(prefix="/api", dependencies=[Depends(csrf)])


class ControlsBody(BaseModel):
    uploads_paused: bool | None = None
    downloads_paused: bool | None = None


class NewUserBody(BaseModel):
    username: str
    password: str
    display_name: str | None = None
    role: str = "user"
    quota_bytes: int | None = None
    must_change_password: bool = True


class EditUserBody(BaseModel):
    display_name: str | None = None
    role: str | None = None
    status: str | None = None
    quota_bytes: int | None = None
    set_quota: bool = False


class PasswordBody(BaseModel):
    password: str
    must_change_password: bool = True


class ConfirmBody(BaseModel):
    confirm: str


class SpaceBody(BaseModel):
    name: str | None = None
    quota_bytes: int | None = None
    set_quota: bool = False


class MemberBody(BaseModel):
    level: str | None = None


class FolderBody(BaseModel):
    parent_id: str
    name: str


class NameBody(BaseModel):
    name: str


def _qr_svg(text: str) -> str:
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError:
        return ""
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, border=1)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode()


# ---- overview and server controls ----------------------------------------------

@api.get("/overview")
def overview(request: Request, conn=Depends(db)):
    ctx = ctx_of(request)
    status = ctx.lan.status()
    url = status["url"] or f"http://{primary_ipv4()}:{ctx.settings.lan_port}/"
    disk = ctx.storage.disk()
    return {
        "version": __version__,
        "server": status, "url": url, "qr": _qr_svg(url),
        "uploads_paused": ctx.uploads_paused, "downloads_paused": ctx.downloads_paused,
        "storage": {"root": str(ctx.storage.root), "disk_total": disk["total"], "disk_free": disk["free"],
                    "files_bytes": conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM items").fetchone()[0]},
        "counts": {
            "users": conn.execute("SELECT count(*) FROM users").fetchone()[0],
            "sessions": len(auth.active_sessions(conn)),
            "uploads": len(uploads.active(conn)),
        },
    }


@api.post("/server/start")
def server_start(request: Request, conn=Depends(db)):
    status = ctx_of(request).lan.start()
    audit.record(conn, "server.start", actor=ACTOR, result="ok" if status["state"] == "running" else "error",
                 details={"error": status["error"]} if status["error"] else None)
    return status


@api.post("/server/stop")
def server_stop(request: Request, conn=Depends(db)):
    audit.record(conn, "server.stop", actor=ACTOR)
    return ctx_of(request).lan.stop()


@api.post("/controls")
def controls(body: ControlsBody, request: Request, conn=Depends(db)):
    ctx = ctx_of(request)
    for key in ("uploads_paused", "downloads_paused"):
        value = getattr(body, key)
        if value is not None and value != getattr(ctx, key):
            settings_store.set_value(conn, key, value)
            setattr(ctx, key, value)
            audit.record(conn, f"{key.split('_')[0]}.{'pause' if value else 'resume'}", actor=ACTOR)
    return {"uploads_paused": ctx.uploads_paused, "downloads_paused": ctx.downloads_paused}


@api.post("/open-storage")
def open_storage(request: Request):
    root = ctx_of(request).storage.root
    if sys.platform == "win32":
        os.startfile(root)  # noqa: S606 - opens Explorer on the storage folder
    else:
        subprocess.Popen(["xdg-open", str(root)])
    return {"ok": True}


@api.post("/quit")
def quit_app(request: Request):
    threading.Timer(0.3, ctx_of(request).request_quit).start()
    return {"quitting": True}


@api.post("/show")
def show_window(request: Request):
    """Called by a second copy of FileDrop: bring this window to the front."""
    ctx = ctx_of(request)
    if ctx.show_window:
        ctx.show_window()
    return {"ok": True}


# ---- users ------------------------------------------------------------------------

@api.get("/users")
def list_users(conn=Depends(db)):
    return {"users": users.list_all(conn)}


@api.post("/users")
def create_user(body: NewUserBody, conn=Depends(db)):
    uid = users.create(conn, body.username, body.password, body.display_name, body.role, body.quota_bytes,
                       body.must_change_password)
    user = users.get(conn, uid)
    audit.record(conn, "user.create", actor=ACTOR, target_type="user", target_id=uid, target_name=user["username"],
                 details={"role": body.role})
    return users.public(user)


@api.patch("/users/{user_id}")
def edit_user(user_id: str, body: EditUserBody, request: Request, conn=Depends(db)):
    before = users.get_required(conn, user_id)
    kwargs = {"display_name": body.display_name, "role": body.role, "status": body.status}
    if body.set_quota:
        kwargs["quota_bytes"] = body.quota_bytes
    users.update(conn, user_id, **kwargs)
    if body.status == "suspended" and before["status"] != "suspended":
        uploads.cancel_for_user(conn, ctx_of(request).storage, user_id)
    changed = {k: v for k, v in kwargs.items() if v is not None}
    audit.record(conn, "user.edit", actor=ACTOR, target_type="user", target_id=user_id,
                 target_name=before["username"], details=changed)
    return users.public(users.get(conn, user_id))


@api.post("/users/{user_id}/password")
def reset_password(user_id: str, body: PasswordBody, conn=Depends(db)):
    user = users.get_required(conn, user_id)
    users.set_password(conn, user_id, body.password, body.must_change_password)
    audit.record(conn, "user.password_reset", actor=ACTOR, target_type="user", target_id=user_id,
                 target_name=user["username"])
    return {"ok": True}


@api.post("/users/{user_id}/delete")
def delete_user(user_id: str, body: ConfirmBody, request: Request, conn=Depends(db)):
    user = users.get_required(conn, user_id)
    if body.confirm.strip().lower() != user["username_key"]:
        raise ApiError(428, "CONFIRMATION_REQUIRED", "Type the username to confirm.")
    users.delete(conn, ctx_of(request).storage, user_id)
    audit.record(conn, "user.delete", actor=ACTOR, target_type="user", target_id=user_id,
                 target_name=user["username"])
    return {"ok": True}


# ---- sessions and transfers -------------------------------------------------------

@api.get("/sessions")
def list_sessions(conn=Depends(db)):
    return {"sessions": auth.active_sessions(conn), "uploads": uploads.active(conn)}


@api.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: str, conn=Depends(db)):
    auth.revoke(conn, session_id)
    audit.record(conn, "session.revoke", actor=ACTOR, target_type="session", target_id=session_id)
    return {"ok": True}


@api.post("/uploads/{upload_id}/cancel")
def cancel_upload(upload_id: str, request: Request, conn=Depends(db)):
    up = uploads.get(conn, upload_id)
    if not up:
        raise ApiError(404, "NOT_FOUND", "Upload not found.")
    uploads.cancel(conn, ctx_of(request).storage, up)
    audit.record(conn, "upload.cancel", actor=ACTOR, target_type="upload", target_id=upload_id,
                 target_name=up["name"])
    return {"ok": True}


@api.get("/audit")
def audit_log(limit: int = 100, conn=Depends(db)):
    return {"entries": audit.recent(conn, min(max(limit, 1), 500))}


# ---- spaces -------------------------------------------------------------------------

@api.get("/spaces")
def list_spaces(conn=Depends(db)):
    return {"spaces": spaces.list_all(conn), "users": [
        {"id": u["id"], "username": u["username"], "display_name": u["display_name"], "role": u["role"]}
        for u in users.list_all(conn)]}


@api.post("/spaces")
def create_space(body: SpaceBody, conn=Depends(db)):
    if not body.name:
        raise ApiError(400, "INVALID_NAME", "Give the shared folder a name.")
    sid = spaces.create_shared(conn, body.name, body.quota_bytes, ACTOR)
    audit.record(conn, "space.create", actor=ACTOR, target_type="space", target_id=sid, target_name=body.name)
    return {"id": sid}


@api.patch("/spaces/{space_id}")
def edit_space(space_id: str, body: SpaceBody, conn=Depends(db)):
    spaces.update_shared(conn, space_id, body.name, body.quota_bytes, body.set_quota)
    audit.record(conn, "space.edit", actor=ACTOR, target_type="space", target_id=space_id,
                 details=body.model_dump(exclude_none=True))
    return {"ok": True}


@api.post("/spaces/{space_id}/delete")
def delete_space(space_id: str, body: ConfirmBody, request: Request, conn=Depends(db)):
    space = spaces.get(conn, space_id)
    if not space or space["kind"] != "shared":
        raise ApiError(404, "NOT_FOUND", "Shared folder not found.")
    if body.confirm.strip() != space["name"]:
        raise ApiError(428, "CONFIRMATION_REQUIRED", "Type the folder name to confirm.")
    spaces.delete_shared(conn, ctx_of(request).storage, space_id)
    audit.record(conn, "space.delete", actor=ACTOR, target_type="space", target_id=space_id,
                 target_name=space["name"])
    return {"ok": True}


@api.put("/spaces/{space_id}/members/{user_id}")
def set_member(space_id: str, user_id: str, body: MemberBody, conn=Depends(db)):
    user = users.get_required(conn, user_id)
    spaces.set_member(conn, space_id, user_id, body.level)
    audit.record(conn, "space.access", actor=ACTOR, target_type="space", target_id=space_id,
                 target_name=user["username"], details={"level": body.level})
    return {"ok": True}


# ---- browse any space -----------------------------------------------------------------

def _admin_item(conn, item_id: str):
    item = files.get(conn, item_id)
    if not item or not files.is_visible(conn, item_id):
        raise ApiError(404, "NOT_FOUND", "That item no longer exists.")
    return item


@api.get("/spaces/{space_id}/items")
def browse(space_id: str, folder: str = "root", conn=Depends(db)):
    space = spaces.get(conn, space_id)
    if not space:
        raise ApiError(404, "NOT_FOUND", "Space not found.")
    folder_id = spaces.root_id(conn, space_id) if folder == "root" else folder
    files.require_folder(conn, folder_id, space_id)
    return {"space": {"id": space_id, "name": space["name"], "kind": space["kind"]}, "folder_id": folder_id,
            "crumbs": files.crumbs(conn, folder_id),
            "items": [files.to_json(i, None, True) for i in files.children(conn, folder_id)]}


@api.post("/spaces/{space_id}/folders")
def admin_new_folder(space_id: str, body: FolderBody, conn=Depends(db)):
    parent = files.require_folder(conn, body.parent_id, space_id)
    iid = files.create_folder(conn, parent, body.name, None, ACTOR)
    return {"id": iid}


@api.patch("/items/{item_id}")
def admin_rename(item_id: str, body: NameBody, conn=Depends(db)):
    item = _admin_item(conn, item_id)
    files.rename(conn, item, body.name)
    audit.record(conn, "item.rename", actor=ACTOR, target_type="item", target_id=item_id, target_name=body.name,
                 details={"from": item["name"]})
    return {"ok": True}


@api.post("/items/{item_id}/delete")
def admin_delete(item_id: str, request: Request, conn=Depends(db)):
    item = _admin_item(conn, item_id)
    files.purge(conn, ctx_of(request).storage, item)
    audit.record(conn, "item.delete", actor=ACTOR, target_type="item", target_id=item_id, target_name=item["name"])
    return {"ok": True}


@api.get("/download/{item_id}")
def admin_download(item_id: str, request: Request, conn=Depends(db)):
    item = _admin_item(conn, item_id)
    if item["kind"] != "file":
        raise ApiError(400, "NOT_A_FILE", "Only files can be downloaded.")
    return file_response(ctx_of(request), item)


def create_console_app(ctx) -> FastAPI:
    app = FastAPI(title="FileDrop admin", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.ctx = ctx
    install_error_handlers(app)
    allowed_hosts = {f"127.0.0.1:{ctx.settings.console_port}", f"localhost:{ctx.settings.console_port}"}

    @app.middleware("http")
    async def localhost_only(request: Request, call_next):
        if request.headers.get("host") not in allowed_hosts:
            return JSONResponse({"error": {"code": "FORBIDDEN", "message": "Wrong host."}}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response

    app.include_router(api)
    app.mount("/shared", StaticFiles(directory=resource_path("web")), name="shared")
    app.mount("/", StaticFiles(directory=resource_path("console"), html=True), name="console")
    return app
