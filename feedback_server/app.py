"""FileDrop feedback server: website forms in, a private admin page to review them.

Public endpoints (same origin as the website, under /api):
    POST /api/feedback    bug reports, feature ideas, questions (optional attachment)
    POST /api/contact     general, partnership, press and privacy messages
    POST /api/beta        beta programme sign-ups
    POST /api/waitlist    Pro launch emails (CASL express consent recorded)
    GET  /api/unsubscribe?token=...
Admin (password protected): /admin and /admin/api/...
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import html
import io
import json
import logging
import re
import secrets
import smtplib
import threading
import time
import urllib.parse
import urllib.request
from collections import deque
from email.message import EmailMessage
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from .config import Config

log = logging.getLogger("feedback")
STATIC = Path(__file__).parent / "static"
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
ATTACH_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
                ".gif": "image/gif", ".txt": "text/plain", ".log": "text/plain"}
WAITLIST_CONSENT = ("Yes, email me about the FileDrop Pro launch. I can unsubscribe at any time.")
LIMITS = {"name": 100, "email": 254, "subject": 200, "message": 5000, "short": 200}


class Login(BaseModel):
    password: str


class Update(BaseModel):
    status: str | None = None
    admin_note: str | None = None


class FormError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "INVALID"):
        super().__init__(message)
        self.message, self.status, self.code = message, status, code


# ---------------------------------------------------------------- helpers

class RateLimiter:
    def __init__(self, limit: int, window_s: int):
        self.limit, self.window = limit, window_s
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] < now - self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise FormError("Too many submissions from your network. Please try again in a few minutes.", 429, "RATE_LIMITED")
            q.append(now)


def clean(value: str | None, limit: int, required: bool = False, label: str = "This field") -> str:
    value = (value or "").replace("\x00", "").replace("\r\n", "\n").strip()
    if required and not value:
        raise FormError(f"{label} is required.")
    if len(value) > limit:
        raise FormError(f"{label} is too long (maximum {limit} characters).")
    return value


def clean_email(value: str | None, required: bool) -> str:
    value = clean(value, LIMITS["email"], required, "Email")
    if value and not EMAIL_RE.match(value):
        raise FormError("Please enter a valid email address.")
    return value.lower()


def choice(value: str | None, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise FormError(f"Please choose a {label}.")
    return value


class Server:
    def __init__(self, config: Config):
        self.c = config
        db.init(config.db_path)
        config.attachment_dir.mkdir(parents=True, exist_ok=True)
        self.limiter = RateLimiter(config.rate_limit, config.rate_window_s)
        self.admin_tokens: dict[str, float] = {}
        self.admin_fails: deque = deque()
        self.lock = threading.Lock()
        self.purge_old()

    def conn(self):
        return db.connect(self.c.db_path)

    def client_ip(self, request: Request) -> str:
        if self.c.trust_proxy:
            fwd = request.headers.get("x-forwarded-for", "")
            if fwd:
                return fwd.split(",")[0].strip()
        return request.client.host if request.client else ""

    def ip_hash(self, ip: str) -> str:
        return hashlib.sha256((self.c.ip_salt + ip).encode()).hexdigest()[:16]

    def guard(self, request: Request, form_name: str, honeypot: str | None, started: str | None,
              turnstile: str | None) -> str:
        """Spam checks shared by every form. Returns the IP hash."""
        if honeypot:  # real people never see this field
            raise FormError("Submission rejected.", 400, "SPAM")
        try:
            if started and time.time() - float(started) / 1000 < self.c.min_fill_seconds:
                raise FormError("That was quick! Please take a moment and send the form again.", 400, "TOO_FAST")
        except ValueError:
            pass
        ip = self.client_ip(request)
        self.limiter.check(f"{form_name}:{ip}")
        if self.c.turnstile_secret and not self.verify_turnstile(turnstile, ip):
            raise FormError("Please complete the check that you're human.", 400, "CAPTCHA")
        return self.ip_hash(ip)

    def verify_turnstile(self, token: str | None, ip: str) -> bool:
        if not token:
            return False
        body = urllib.parse.urlencode({"secret": self.c.turnstile_secret, "response": token, "remoteip": ip}).encode()
        try:
            with urllib.request.urlopen("https://challenges.cloudflare.com/turnstile/v0/siteverify", body, timeout=8) as r:
                return bool(json.loads(r.read()).get("success"))
        except OSError as exc:
            log.warning("Turnstile check failed: %s", exc)
            return False

    def notify(self, subject: str, text: str) -> None:
        if not (self.c.smtp_host and self.c.notify_to):
            return

        def send():
            try:
                msg = EmailMessage()
                msg["Subject"], msg["From"], msg["To"] = subject, self.c.notify_from or self.c.notify_to, self.c.notify_to
                msg.set_content(text)
                with smtplib.SMTP(self.c.smtp_host, self.c.smtp_port, timeout=15) as s:
                    s.starttls()
                    if self.c.smtp_user:
                        s.login(self.c.smtp_user, self.c.smtp_password)
                    s.send_message(msg)
            except Exception as exc:  # never lose a submission over an email problem
                log.warning("Notification email failed: %s", exc)
        threading.Thread(target=send, daemon=True).start()

    def save_submission(self, kind: str, category: str, *, name="", email="", subject="", message="",
                        details=None, ip_hash="", attachment: tuple[str, str, bytes] | None = None) -> int:
        t = db.now()
        conn = self.conn()
        try:
            with db.transaction(conn):
                cur = conn.execute(
                    "INSERT INTO submissions (kind, category, name, email, subject, message, details_json, ip_hash,"
                    " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (kind, category, name, email, subject, message, json.dumps(details or {}), ip_hash, t, t))
                sid = cur.lastrowid
                if attachment:
                    filename, ctype, data = attachment
                    stored = secrets.token_hex(16)
                    (self.c.attachment_dir / stored).write_bytes(data)
                    conn.execute("INSERT INTO attachments (submission_id, filename, content_type, size_bytes, stored_name)"
                                 " VALUES (?, ?, ?, ?, ?)", (sid, filename, ctype, len(data), stored))
        finally:
            conn.close()
        self.notify(f"[FileDrop] New {kind}: {category}", f"{subject or message[:80]}\n\nFrom: {name} <{email}>\n\n{message}")
        return sid

    def purge_old(self) -> None:
        cutoff = db.now() - self.c.retention_days * 86400
        conn = self.conn()
        try:
            old = conn.execute("SELECT a.stored_name FROM attachments a JOIN submissions s ON s.id = a.submission_id"
                               " WHERE s.created_at < ?", (cutoff,)).fetchall()
            for row in old:
                (self.c.attachment_dir / row[0]).unlink(missing_ok=True)
            conn.execute("DELETE FROM submissions WHERE created_at < ?", (cutoff,))
        finally:
            conn.close()

    # ---- admin sessions (in memory; restart signs everyone out)
    def admin_login(self, password: str) -> str:
        now = time.monotonic()
        with self.lock:
            while self.admin_fails and self.admin_fails[0] < now - 900:
                self.admin_fails.popleft()
            if len(self.admin_fails) >= 10:
                raise FormError("Too many wrong passwords. Try again in 15 minutes.", 429, "LOCKED")
        if not self.c.admin_password or not hmac.compare_digest(password.encode(), self.c.admin_password.encode()):
            with self.lock:
                self.admin_fails.append(now)
            raise FormError("Wrong password.", 401, "WRONG_PASSWORD")
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.admin_tokens[token] = now + 8 * 3600
        return token

    def admin_ok(self, request: Request) -> bool:
        token = request.cookies.get("fd_feedback_admin", "")
        with self.lock:
            exp = self.admin_tokens.get(token)
            if not exp or exp < time.monotonic():
                self.admin_tokens.pop(token, None)
                return False
            return True


# ---------------------------------------------------------------- app

def create_app(config: Config) -> FastAPI:
    srv = Server(config)
    app = FastAPI(title="FileDrop feedback", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.server = srv

    @app.exception_handler(FormError)
    async def form_error(request: Request, exc: FormError):
        return JSONResponse({"ok": False, "code": exc.code, "message": exc.message}, status_code=exc.status)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        path = request.url.path
        # Forms are posted from our own pages only.
        if request.method == "POST" and path.startswith(("/api/", "/admin/api/")):
            origin = request.headers.get("origin")
            if origin and urllib.parse.urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"ok": False, "code": "ORIGIN", "message": "Request blocked."}, status_code=403)
        if path.startswith("/admin/api/") and path != "/admin/api/login" and not srv.admin_ok(request):
            return JSONResponse({"ok": False, "code": "UNAUTHENTICATED", "message": "Please sign in."}, status_code=401)
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if path.startswith(("/api/", "/admin")):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Frame-Options"] = "DENY"
        return response

    # ---------------- public forms

    @app.get("/api/health")
    def health():
        return {"ok": True}

    @app.post("/api/feedback")
    async def feedback(request: Request,
                       category: str = Form(...), message: str = Form(...), email: str = Form(""),
                       steps: str = Form(""), app_version: str = Form(""), windows: str = Form(""),
                       device: str = Form(""), attachment: UploadFile | None = None,
                       website: str = Form(""), started: str = Form(""), turnstile: str = Form("")):
        ip_hash = srv.guard(request, "feedback", website, started, turnstile)
        category = choice(category, {"bug", "idea", "question"}, "type of feedback")
        message = clean(message, LIMITS["message"], True, "Your message")
        details = {"steps": clean(steps, LIMITS["message"], False, "Steps"),
                   "app_version": clean(app_version, LIMITS["short"], False, "Version"),
                   "windows": clean(windows, LIMITS["short"], False, "Windows version"),
                   "device": clean(device, LIMITS["short"], False, "Phone or browser")}
        file = None
        if attachment is not None and attachment.filename:
            ext = Path(attachment.filename).suffix.lower()
            if ext not in ATTACH_TYPES:
                raise FormError("Attach a screenshot (PNG, JPG, WebP, GIF) or a log file (TXT, LOG).")
            data = await attachment.read(config.max_attachment_mb * 1024 * 1024 + 1)
            if len(data) > config.max_attachment_mb * 1024 * 1024:
                raise FormError(f"The attachment is larger than {config.max_attachment_mb} MB.", 413, "TOO_LARGE")
            name = re.sub(r"[^\w.\- ]", "_", Path(attachment.filename).name)[:120] or "attachment" + ext
            file = (name, ATTACH_TYPES[ext], data)
        sid = srv.save_submission("feedback", category, email=clean_email(email, False), message=message,
                                  subject=message.splitlines()[0][:120], details=details, ip_hash=ip_hash, attachment=file)
        return {"ok": True, "id": sid, "message": "Thanks! Your feedback has been received."}

    @app.post("/api/contact")
    async def contact(request: Request, topic: str = Form(...), name: str = Form(...), email: str = Form(...),
                      message: str = Form(...), subject: str = Form(""),
                      website: str = Form(""), started: str = Form(""), turnstile: str = Form("")):
        ip_hash = srv.guard(request, "contact", website, started, turnstile)
        topic = choice(topic, {"general", "partnership", "press", "privacy"}, "topic")
        sid = srv.save_submission("contact", topic, name=clean(name, LIMITS["name"], True, "Your name"),
                                  email=clean_email(email, True), subject=clean(subject, LIMITS["subject"], False, "Subject"),
                                  message=clean(message, LIMITS["message"], True, "Your message"), ip_hash=ip_hash)
        return {"ok": True, "id": sid, "message": "Thanks! We'll reply by email, usually within two business days."}

    @app.post("/api/beta")
    async def beta(request: Request, name: str = Form(...), email: str = Form(...), windows: str = Form(""),
                   phones: list[str] = Form([]), use_case: str = Form(""), consent: str = Form(""),
                   website: str = Form(""), started: str = Form(""), turnstile: str = Form("")):
        ip_hash = srv.guard(request, "beta", website, started, turnstile)
        if consent != "yes":
            raise FormError("Please agree to be contacted about the beta.")
        allowed = {"iphone", "android", "windows", "mac", "other"}
        details = {"windows": clean(windows, LIMITS["short"], False, "Windows version"),
                   "phones": [p for p in phones if p in allowed][:5], "consent_at": db.now()}
        sid = srv.save_submission("beta", "signup", name=clean(name, LIMITS["name"], True, "Your name"),
                                  email=clean_email(email, True), message=clean(use_case, LIMITS["message"], False, "Use case"),
                                  details=details, ip_hash=ip_hash)
        return {"ok": True, "id": sid, "message": "You're on the list! We'll email you when the next beta build is ready."}

    @app.post("/api/waitlist")
    async def waitlist(request: Request, email: str = Form(...), consent: str = Form(""),
                       website: str = Form(""), started: str = Form(""), turnstile: str = Form("")):
        ip_hash = srv.guard(request, "waitlist", website, started, turnstile)
        if consent != "yes":
            raise FormError("Please tick the box to agree to the launch email.")
        email = clean_email(email, True)
        conn = srv.conn()
        try:
            conn.execute(
                "INSERT INTO waitlist (email, consent_text, consent_at, ip_hash, unsubscribe_token) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(email) DO UPDATE SET consent_text = excluded.consent_text, consent_at = excluded.consent_at,"
                " unsubscribed_at = NULL",
                (email, WAITLIST_CONSENT, db.now(), ip_hash, secrets.token_urlsafe(24)))
        finally:
            conn.close()
        return {"ok": True, "message": "You're on the list. We'll send one email when Pro launches."}

    @app.get("/api/unsubscribe", response_class=HTMLResponse)
    def unsubscribe(token: str = ""):
        conn = srv.conn()
        try:
            hit = conn.execute("UPDATE waitlist SET unsubscribed_at = ? WHERE unsubscribe_token = ? AND unsubscribed_at IS NULL",
                               (db.now(), token)).rowcount if token else 0
        finally:
            conn.close()
        text = "You've been unsubscribed. We won't email you again." if hit else "This link has already been used or isn't valid."
        return HTMLResponse(f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                            f"<title>Unsubscribe | FileDrop</title><body style='font:17px system-ui;margin:15vh auto;max-width:520px;padding:0 20px'>"
                            f"<h1>FileDrop</h1><p>{html.escape(text)}</p><p><a href='/'>Back to the website</a></p>")

    # ---------------- admin

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page():
        return FileResponse(STATIC / "admin.html", headers={"Cache-Control": "no-store"})

    @app.post("/admin/api/login")
    def login(body: Login, request: Request, response: Response):
        token = srv.admin_login(body.password)
        response.set_cookie("fd_feedback_admin", token, httponly=True, samesite="strict", path="/admin",
                            secure=request.url.scheme == "https" or config.trust_proxy, max_age=8 * 3600)
        return {"ok": True}

    @app.post("/admin/api/logout")
    def logout(request: Request, response: Response):
        srv.admin_tokens.pop(request.cookies.get("fd_feedback_admin", ""), None)
        response.delete_cookie("fd_feedback_admin", path="/admin")
        return {"ok": True}

    def row_json(row, attachments=None):
        d = dict(row)
        d["details"] = json.loads(d.pop("details_json") or "{}")
        d.pop("ip_hash", None)
        if attachments is not None:
            d["attachments"] = [dict(a) for a in attachments]
        return d

    @app.get("/admin/api/summary")
    def summary():
        conn = srv.conn()
        try:
            counts = {f"{r['kind']}:{r['status']}": r["n"] for r in
                      conn.execute("SELECT kind, status, count(*) AS n FROM submissions GROUP BY kind, status")}
            waiting = conn.execute("SELECT count(*) FROM waitlist WHERE unsubscribed_at IS NULL").fetchone()[0]
        finally:
            conn.close()
        return {"counts": counts, "waitlist": waiting}

    @app.get("/admin/api/submissions")
    def submissions(kind: str = "", status: str = "", q: str = ""):
        sql, args = "SELECT * FROM submissions WHERE 1 = 1", []
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        if status:
            sql += " AND status = ?"
            args.append(status)
        if q:
            sql += " AND (message LIKE ? OR email LIKE ? OR name LIKE ? OR subject LIKE ?)"
            args += [f"%{q}%"] * 4
        conn = srv.conn()
        try:
            rows = conn.execute(sql + " ORDER BY created_at DESC LIMIT 500", args).fetchall()
            att = {r["submission_id"]: r["n"] for r in conn.execute("SELECT submission_id, count(*) AS n FROM attachments GROUP BY submission_id")}
        finally:
            conn.close()
        return {"items": [row_json(r) | {"attachment_count": att.get(r["id"], 0)} for r in rows]}

    @app.get("/admin/api/submissions/{sid}")
    def submission(sid: int):
        conn = srv.conn()
        try:
            row = conn.execute("SELECT * FROM submissions WHERE id = ?", (sid,)).fetchone()
            if not row:
                raise FormError("Not found.", 404, "NOT_FOUND")
            atts = conn.execute("SELECT id, filename, content_type, size_bytes FROM attachments WHERE submission_id = ?", (sid,)).fetchall()
        finally:
            conn.close()
        return row_json(row, atts)

    @app.patch("/admin/api/submissions/{sid}")
    def update(sid: int, body: Update):
        conn = srv.conn()
        try:
            if body.status is not None:
                choice(body.status, {"new", "in_progress", "closed"}, "status")
                conn.execute("UPDATE submissions SET status = ?, updated_at = ? WHERE id = ?", (body.status, db.now(), sid))
            if body.admin_note is not None:
                conn.execute("UPDATE submissions SET admin_note = ?, updated_at = ? WHERE id = ?",
                             (clean(body.admin_note, LIMITS["message"]), db.now(), sid))
        finally:
            conn.close()
        return {"ok": True}

    @app.delete("/admin/api/submissions/{sid}")
    def delete(sid: int):
        """For privacy requests: removes the submission and its attachments for good."""
        conn = srv.conn()
        try:
            for r in conn.execute("SELECT stored_name FROM attachments WHERE submission_id = ?", (sid,)).fetchall():
                (config.attachment_dir / r[0]).unlink(missing_ok=True)
            conn.execute("DELETE FROM submissions WHERE id = ?", (sid,))
        finally:
            conn.close()
        return {"ok": True}

    @app.get("/admin/api/attachments/{aid}")
    def attachment(aid: int):
        conn = srv.conn()
        try:
            a = conn.execute("SELECT * FROM attachments WHERE id = ?", (aid,)).fetchone()
        finally:
            conn.close()
        if not a:
            raise FormError("Not found.", 404, "NOT_FOUND")
        return FileResponse(config.attachment_dir / a["stored_name"], media_type=a["content_type"], filename=a["filename"],
                            content_disposition_type="attachment", headers={"X-Content-Type-Options": "nosniff"})

    @app.get("/admin/api/waitlist")
    def waitlist_list():
        conn = srv.conn()
        try:
            rows = conn.execute("SELECT id, email, consent_at, unsubscribed_at, unsubscribe_token FROM waitlist ORDER BY consent_at DESC").fetchall()
        finally:
            conn.close()
        base = config.public_url or ""
        return {"items": [dict(r) | {"unsubscribe_url": f"{base}/api/unsubscribe?token={r['unsubscribe_token']}"} for r in rows]}

    @app.delete("/admin/api/waitlist/{wid}")
    def waitlist_delete(wid: int):
        conn = srv.conn()
        try:
            conn.execute("DELETE FROM waitlist WHERE id = ?", (wid,))
        finally:
            conn.close()
        return {"ok": True}

    @app.get("/admin/api/export.csv")
    def export(kind: str = "feedback"):
        conn = srv.conn()
        try:
            if kind == "waitlist":
                rows = conn.execute("SELECT email, consent_text, consent_at, unsubscribed_at FROM waitlist").fetchall()
                head = ["email", "consent_text", "consent_at", "unsubscribed_at"]
            else:
                rows = conn.execute("SELECT id, kind, category, status, name, email, subject, message, details_json, admin_note,"
                                    " created_at FROM submissions WHERE kind = ? ORDER BY created_at DESC", (kind,)).fetchall()
                head = ["id", "kind", "category", "status", "name", "email", "subject", "message", "details", "admin_note", "created_at"]
        finally:
            conn.close()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(head)
        for r in rows:
            # neutralise spreadsheet formulas in user-supplied text
            w.writerow([("'" + v) if isinstance(v, str) and v[:1] in "=+-@" else v for v in tuple(r)])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="filedrop-{kind}.csv"'})

    app.mount("/admin/static", StaticFiles(directory=STATIC), name="admin-static")
    if config.site_dir:
        app.mount("/", StaticFiles(directory=config.site_dir, html=True), name="site")
    return app
