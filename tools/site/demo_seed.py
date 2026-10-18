"""Fill a running demo WiFiDrop with realistic users, folders and files for website screenshots."""
import http.cookiejar
import json
import ssl
import sys
import urllib.request

ADMIN = "http://127.0.0.1:8442/api"
H = {"X-WiFiDrop": "1", "Content-Type": "application/json"}
CTX = ssl.create_default_context()
CTX.check_hostname, CTX.verify_mode = False, ssl.CERT_NONE


def call(opener, url, body=None, method=None, raw=None, headers=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method or ("POST" if data is not None else "GET"),
                                 headers=headers or H)
    with opener.open(req) as r:
        return json.loads(r.read() or b"null")


admin = urllib.request.build_opener()
lan = call(admin, ADMIN + "/overview")["url"].rstrip("/") + "/api/v1"
people = [("sam", "Sam Rivera"), ("alex", "Alex Chen"), ("jordan", "Jordan Lee"), ("mia", "Mia Patel")]
ids = {}
for u, name in people:
    ids[u] = call(admin, ADMIN + "/users", {"username": u, "display_name": name, "password": "demo-pass-1",
                                            "must_change_password": False,
                                            "quota_bytes": 50 * 1024**3 if u != "mia" else None})["id"]
fam = call(admin, ADMIN + "/spaces", {"name": "Family photos", "quota_bytes": 200 * 1024**3})["id"]
school = call(admin, ADMIN + "/spaces", {"name": "School projects"})["id"]
for sid, u, lvl in [(fam, "sam", "upload"), (fam, "alex", "view"), (fam, "jordan", "upload"), (fam, "mia", "manage"),
                    (school, "mia", "manage"), (school, "sam", "upload")]:
    call(admin, f"{ADMIN}/spaces/{sid}/members/{ids[u]}", {"level": lvl}, method="PUT")


def session(user):
    o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                                    urllib.request.HTTPSHandler(context=CTX))
    call(o, lan + "/auth/login", {"username": user, "password": "demo-pass-1"})
    return o


def upload(o, space_id, parent_id, name, size):
    up = call(o, lan + "/uploads", {"space_id": space_id, "parent_id": parent_id, "name": name, "size": size})
    chunk, sent, i = up["chunk_size"], 0, 0
    while sent < size:
        n = min(chunk, size - sent)
        call(o, f"{lan}/uploads/{up['id']}/chunks/{i}", raw=bytes(n), method="PUT",
             headers={"X-WiFiDrop": "1", "Content-Type": "application/octet-stream"})
        sent, i = sent + n, i + 1
    call(o, f"{lan}/uploads/{up['id']}/complete", {})


def folder(o, space_id, parent_id, name):
    return call(o, f"{lan}/spaces/{space_id}/folders", {"parent_id": parent_id, "name": name})["id"]


MB = 1024 * 1024
sam = session("sam")
spaces = {s["name"] if s["kind"] == "shared" else "mine": s for s in call(sam, lan + "/spaces")["spaces"]}
mine = spaces["mine"]
pics = folder(sam, mine["id"], mine["root_id"], "Pics")
school_f = folder(sam, mine["id"], mine["root_id"], "School")
for name, size in [("IMG_2406.HEIC", 3 * MB), ("IMG_2407.HEIC", int(2.7 * MB)), ("IMG_2411.HEIC", int(3.4 * MB))]:
    upload(sam, mine["id"], pics, name, size)
for name, size in [("Essay draft.docx", 240_000), ("Chem lab notes.pdf", int(1.2 * MB))]:
    upload(sam, mine["id"], school_f, name, size)
for name, size in [("Banff trip.mov", 48 * MB), ("Resume 2026.pdf", 180_000), ("Spotify Wrapped.png", int(1.6 * MB))]:
    upload(sam, mine["id"], mine["root_id"], name, size)
famroot = spaces["Family photos"]["root_id"]
for name, size in [("Thanksgiving 2026.jpg", int(4.1 * MB)), ("Grandma's birthday.mov", 22 * MB)]:
    upload(sam, fam, famroot, name, size)
jordan = session("jordan")
for name, size in [("Lake day.jpg", int(3.8 * MB)), ("Dog at the park.jpg", int(2.2 * MB))]:
    upload(jordan, fam, famroot, name, size)
session("alex")
session("mia")
print("demo data ready:", lan)
sys.exit(0)
