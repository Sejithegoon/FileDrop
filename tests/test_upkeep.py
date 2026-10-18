"""Background upkeep: trash older than 30 days is removed; update feed parsing."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.db.ids import now_ms
from app.services import upkeep
from tests.test_api import login, make_user, my_space, upload



def test_old_trash_is_purged_recent_trash_kept(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    old = upload(c, space["id"], space["root_id"], "old.txt", b"old")
    new = upload(c, space["id"], space["root_id"], "new.txt", b"new")
    c.delete(f"/api/v1/items/{old['id']}")
    c.delete(f"/api/v1/items/{new['id']}")
    conn = ctx.connect()
    conn.execute("UPDATE items SET trashed_at = ? WHERE id = ?", (now_ms() - 31 * 24 * 3600 * 1000, old["id"]))
    assert upkeep.purge_old_trash(conn, ctx.storage) == 1
    names = [r[0] for r in conn.execute("SELECT name FROM items WHERE trashed_at IS NOT NULL")]
    conn.close()
    assert names == ["new.txt"]


def _serve(payload):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}/feed.json"


def test_update_check_reports_only_newer_https_versions():
    srv, url = _serve({"version": "9.0.0", "url": "https://example.com/dl", "notes": "Faster uploads"})
    try:
        assert upkeep.check_for_update(url, current="0.1.0")["version"] == "9.0.0"
        assert upkeep.check_for_update(url, current="9.0.0") is None
    finally:
        srv.shutdown()
    srv, url = _serve({"version": "9.0.0", "url": "http://insecure.example/dl"})
    try:
        assert upkeep.check_for_update(url, current="0.1.0") is None
    finally:
        srv.shutdown()
