"""Previews (thumbnails and in-page viewing) and search."""

import io

from PIL import Image

from tests.test_api import login, make_user, my_space, upload


def picture(fmt="PNG", size=(1200, 800), color=(200, 30, 30)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, fmt)
    return out.getvalue()


def root_of(c, space):
    return c.get(f"/api/v1/spaces/{space['id']}/items").json()["folder_id"]


def test_pc_makes_a_small_jpeg_thumbnail_and_deletes_it_with_the_file(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    item = upload(c, space["id"], root_of(c, space), "beach.png", picture())
    r = c.get(f"/api/v1/thumb/{item['id']}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert "max-age" in r.headers["cache-control"]
    thumb = Image.open(io.BytesIO(r.content))
    assert thumb.format == "JPEG" and max(thumb.size) == 400
    conn = ctx.connect()
    blob = conn.execute("SELECT blob_id FROM items WHERE id = ?", (item["id"],)).fetchone()[0]
    conn.close()
    assert ctx.storage.thumb_path(blob).exists()
    c.delete(f"/api/v1/items/{item['id']}")
    assert c.get(f"/api/v1/thumb/{item['id']}").status_code == 404  # in the trash: no preview
    c.delete(f"/api/v1/items/{item['id']}/purge")
    assert not ctx.storage.thumb_path(blob).exists()


def test_broken_pictures_and_other_files_just_have_no_preview(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    root = root_of(c, space)
    broken = upload(c, space["id"], root, "broken.jpg", b"not really a jpeg")
    notes = upload(c, space["id"], root, "notes.txt", b"hello")
    for item in (broken, notes, broken):  # asking twice uses the remembered "no preview"
        r = c.get(f"/api/v1/thumb/{item['id']}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "NO_PREVIEW"


def test_phone_app_adds_previews_for_iphone_photos_and_videos(ctx, admin):
    make_user(admin, "sam")
    make_user(admin, "alex")
    c = login(ctx, "sam")
    space = my_space(c)
    root = root_of(c, space)
    heic = upload(c, space["id"], root, "IMG_0001.HEIC", b"heic bytes the PC can't read")
    assert c.get(f"/api/v1/thumb/{heic['id']}").status_code == 404
    small = picture("JPEG", (400, 300))
    assert c.put(f"/api/v1/items/{heic['id']}/thumb", content=small).status_code == 200
    r = c.get(f"/api/v1/thumb/{heic['id']}")
    assert r.status_code == 200 and Image.open(io.BytesIO(r.content)).format == "JPEG"

    assert c.put(f"/api/v1/items/{heic['id']}/thumb", content=b"<svg/>").status_code == 400
    assert c.put(f"/api/v1/items/{heic['id']}/thumb", content=b"x" * (600 * 1024)).status_code == 413
    notes = upload(c, space["id"], root, "notes.txt", b"hello")
    assert c.put(f"/api/v1/items/{notes['id']}/thumb", content=small).status_code == 400
    other = login(ctx, "alex")
    assert other.put(f"/api/v1/items/{heic['id']}/thumb", content=small).status_code == 404  # not their folder


def test_previews_open_in_the_page_only_for_safe_types(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    root = root_of(c, space)
    png = upload(c, space["id"], root, "pic.png", picture())
    svg = upload(c, space["id"], root, "logo.svg", b"<svg onload='alert(1)'/>")
    shown = c.get(f"/api/v1/download/{png['id']}?inline=1")
    assert shown.headers["content-disposition"].startswith("inline")
    assert "sandbox" in shown.headers["content-security-policy"]
    assert c.get(f"/api/v1/download/{png['id']}").headers["content-disposition"].startswith("attachment")
    assert c.get(f"/api/v1/download/{svg['id']}?inline=1").headers["content-disposition"].startswith("attachment")


def test_admin_window_sees_previews(ctx, admin):
    make_user(admin, "sam")
    c = login(ctx, "sam")
    space = my_space(c)
    item = upload(c, space["id"], root_of(c, space), "pic.png", picture())
    assert admin.get(f"/api/thumb/{item['id']}").status_code == 200
    assert admin.get(f"/api/download/{item['id']}?inline=1").headers["content-disposition"].startswith("inline")


def test_search_finds_names_in_every_folder_you_can_open_and_nothing_else(ctx, admin):
    sam_id = make_user(admin, "sam")
    make_user(admin, "alex")
    sid = admin.post("/api/spaces", json={"name": "Family"}).json()["id"]
    admin.put(f"/api/spaces/{sid}/members/{sam_id}", json={"level": "upload"})
    sam, alex = login(ctx, "sam"), login(ctx, "alex")
    mine = my_space(sam)
    sam_root = root_of(sam, mine)
    folder = sam.post(f"/api/v1/spaces/{mine['id']}/folders", json={"parent_id": sam_root, "name": "Trips"}).json()
    upload(sam, mine["id"], folder["id"], "Beach Day.jpg", b"1")
    upload(sam, mine["id"], sam_root, "100%_beach.txt", b"2")
    gone = upload(sam, mine["id"], sam_root, "beach-old.jpg", b"3")
    sam.delete(f"/api/v1/items/{gone['id']}")
    family_root = sam.get(f"/api/v1/spaces/{sid}/items").json()["folder_id"]
    upload(sam, sid, family_root, "BEACH group.png", b"4")
    alex_space = my_space(alex)
    upload(alex, alex_space["id"], root_of(alex, alex_space), "alex beach.jpg", b"5")

    found = sam.get("/api/v1/search", params={"q": "beach"}).json()["results"]
    names = sorted(r["name"] for r in found)
    assert names == ["100%_beach.txt", "BEACH group.png", "Beach Day.jpg"]  # not trashed, not alex's
    day = next(r for r in found if r["name"] == "Beach Day.jpg")
    assert day["path"] == ["Trips"] and day["space"]["kind"] == "private" and day["parent_id"] == folder["id"]
    assert [r["name"] for r in sam.get("/api/v1/search", params={"q": "%_"}).json()["results"]] == ["100%_beach.txt"]
    assert sam.get("/api/v1/search", params={"q": "   "}).json()["results"] == []
    assert [r["name"] for r in sam.get("/api/v1/search", params={"q": "trip"}).json()["results"]] == ["Trips"]
