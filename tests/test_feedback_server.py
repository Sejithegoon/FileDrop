"""Feedback server: forms, spam guards, attachments, waitlist consent, admin access."""

import time

import pytest
from fastapi.testclient import TestClient

from feedback_server.app import create_app
from feedback_server.config import Config


@pytest.fixture
def client(tmp_path):
    cfg = Config(data_dir=tmp_path, admin_password="admin-pass-1", rate_limit=50, min_fill_seconds=2)
    return TestClient(create_app(cfg))


def started():
    return str(int((time.time() - 10) * 1000))  # form opened 10 s ago


def admin(client):
    assert client.post("/admin/api/login", json={"password": "admin-pass-1"}).status_code == 200
    return client


def test_bug_report_with_screenshot(client):
    r = client.post("/api/feedback", data={"category": "bug", "message": "Upload stops at 99%\nOn my iPhone",
                                           "app_version": "0.1.0", "windows": "Windows 11", "device": "iPhone Safari",
                                           "steps": "1. pick 50 photos", "email": "Sam@Example.com", "started": started()},
                    files={"attachment": ("shot.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    admin(client)
    item = client.get(f"/admin/api/submissions/{sid}").json()
    assert item["email"] == "sam@example.com" and item["subject"] == "Upload stops at 99%"
    assert item["details"]["device"] == "iPhone Safari" and len(item["attachments"]) == 1
    att = client.get(f"/admin/api/attachments/{item['attachments'][0]['id']}")
    assert att.content == b"\x89PNG fake" and "attachment" in att.headers["content-disposition"]


def test_attachment_rules(client, tmp_path):
    bad = client.post("/api/feedback", data={"category": "bug", "message": "x", "started": started()},
                      files={"attachment": ("evil.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 400
    small = Config(data_dir=tmp_path / "s", admin_password="x", max_attachment_mb=1)
    c2 = TestClient(create_app(small))
    big = c2.post("/api/feedback", data={"category": "bug", "message": "x", "started": started()},
                  files={"attachment": ("big.png", b"0" * (1024 * 1024 + 10), "image/png")})
    assert big.status_code == 413


def test_spam_guards(client, tmp_path):
    honeypot = client.post("/api/contact", data={"topic": "general", "name": "Bot", "email": "b@x.io", "message": "buy",
                                                 "website": "http://spam", "started": started()})
    assert honeypot.status_code == 400 and honeypot.json()["code"] == "SPAM"
    too_fast = client.post("/api/contact", data={"topic": "general", "name": "Bot", "email": "b@x.io", "message": "hi",
                                                 "started": str(int(time.time() * 1000))})
    assert too_fast.json()["code"] == "TOO_FAST"
    limited = TestClient(create_app(Config(data_dir=tmp_path / "r", admin_password="x", rate_limit=2)))
    codes = [limited.post("/api/contact", data={"topic": "general", "name": "A", "email": "a@x.io", "message": "hi",
                                                "started": started()}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    foreign = client.post("/api/contact", headers={"Origin": "https://evil.example"},
                          data={"topic": "general", "name": "A", "email": "a@x.io", "message": "hi", "started": started()})
    assert foreign.status_code == 403


def test_validation(client):
    r = client.post("/api/contact", data={"topic": "general", "name": "A", "email": "not-an-email", "message": "hi",
                                          "started": started()})
    assert r.status_code == 400 and "valid email" in r.json()["message"]
    r = client.post("/api/feedback", data={"category": "rant", "message": "x", "started": started()})
    assert r.status_code == 400


def test_beta_needs_consent(client):
    data = {"name": "Mia", "email": "mia@example.com", "windows": "Windows 11", "phones": ["iphone", "android", "toaster"],
            "use_case": "Classroom", "started": started()}
    assert client.post("/api/beta", data=data).status_code == 400
    r = client.post("/api/beta", data=data | {"consent": "yes"})
    assert r.status_code == 200
    admin(client)
    item = client.get(f"/admin/api/submissions/{r.json()['id']}").json()
    assert item["details"]["phones"] == ["iphone", "android"] and item["details"]["consent_at"]


def test_waitlist_consent_and_unsubscribe(client):
    assert client.post("/api/waitlist", data={"email": "a@b.co", "started": started()}).status_code == 400
    assert client.post("/api/waitlist", data={"email": "a@b.co", "consent": "yes", "started": started()}).status_code == 200
    assert client.post("/api/waitlist", data={"email": "A@B.co", "consent": "yes", "started": started()}).status_code == 200
    admin(client)
    items = client.get("/admin/api/waitlist").json()["items"]
    assert len(items) == 1 and items[0]["consent_at"]
    token = items[0]["unsubscribe_url"].split("token=")[1]
    page = client.get(f"/api/unsubscribe?token={token}")
    assert "unsubscribed" in page.text
    assert client.get("/admin/api/waitlist").json()["items"][0]["unsubscribed_at"]
    csv_text = client.get("/admin/api/export.csv?kind=waitlist").text
    assert "consent_text" in csv_text and "a@b.co" in csv_text


def test_admin_is_protected_and_triage_works(client):
    r = client.post("/api/feedback", data={"category": "idea", "message": "=HYPERLINK(\"evil\")", "started": started()})
    sid = r.json()["id"]
    assert client.get("/admin/api/submissions").status_code == 401
    assert client.post("/admin/api/login", json={"password": "nope"}).status_code == 401
    admin(client)
    assert client.patch(f"/admin/api/submissions/{sid}", json={"status": "closed", "admin_note": "Planned for 0.2"}).status_code == 200
    item = client.get(f"/admin/api/submissions/{sid}").json()
    assert item["status"] == "closed" and item["admin_note"] == "Planned for 0.2"
    assert "ip_hash" not in item
    exported = client.get("/admin/api/export.csv?kind=feedback").text
    assert "'=HYPERLINK" in exported  # formulas are neutralised
    assert client.delete(f"/admin/api/submissions/{sid}").status_code == 200
    assert client.get(f"/admin/api/submissions/{sid}").status_code == 404


def test_old_submissions_are_purged(tmp_path):
    cfg = Config(data_dir=tmp_path, admin_password="x", retention_days=30)
    c = TestClient(create_app(cfg))
    sid = c.post("/api/feedback", data={"category": "bug", "message": "old", "started": started()}).json()["id"]
    from feedback_server import db
    conn = db.connect(cfg.db_path)
    conn.execute("UPDATE submissions SET created_at = created_at - 31 * 86400 WHERE id = ?", (sid,))
    conn.close()
    TestClient(create_app(cfg))  # restart runs the purge
    conn = db.connect(cfg.db_path)
    assert conn.execute("SELECT count(*) FROM submissions").fetchone()[0] == 0
    conn.close()
