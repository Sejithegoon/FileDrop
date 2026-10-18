"""High-quality website screenshots of the demo WiFiDrop (admin window at 2x, phone at 3x)."""
import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "build" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
ADMIN = "http://127.0.0.1:8442/"
lan = json.load(urllib.request.urlopen(urllib.request.Request(ADMIN + "api/overview", headers={"X-WiFiDrop": "1"})))["url"]


def save(png: bytes, name: str, crop_height: int | None = None):
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if crop_height:
        im = im.crop((0, 0, im.width, crop_height))
    im.save(OUT / f"{name}.webp", "WEBP", quality=88, method=6)
    print(name, im.size)


# Neutral demo values so no personal paths appear in public screenshots.
TIDY = """() => {
  const p = document.getElementById('storagePath'); if (p) p.textContent = 'D:\\\\WiFiDrop Files';
  document.querySelectorAll('#statFree').forEach(e => e.textContent = '1.6 TB free on disk');
  document.querySelectorAll('#storageFree').forEach(e => e.textContent = '1.6 TB free on this drive.');
}"""

with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)

    # ---- admin window, 1440x900 at 2x
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="dark")
    page = ctx.new_page()
    for name in ["dashboard", "users", "shared", "files", "activity"]:
        page.goto(ADMIN + "#" + name)
        page.wait_for_timeout(1500)
        if name == "files":
            page.select_option("#spacePick", label="Sam Rivera (@sam)")
            page.wait_for_timeout(800)
        page.evaluate(TIDY)
        page.wait_for_timeout(200)
        save(page.screenshot(), f"admin-{name}")
    # Add-user dialog
    page.goto(ADMIN + "#users")
    page.wait_for_timeout(1200)
    page.click("#addUserBtn")
    page.wait_for_timeout(500)
    save(page.screenshot(), "admin-add-user")
    ctx.close()

    # ---- phone, iPhone-sized 390x844 at 3x
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True,
                              has_touch=True, ignore_https_errors=True, color_scheme="dark",
                              user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1")
    page = ctx.new_page()
    page.goto(lan)
    page.wait_for_timeout(800)
    save(page.screenshot(), "phone-signin")
    page.fill("#loginUser", "sam")
    page.fill("#loginPass", "demo-pass-1")
    page.click("#loginForm button[type=submit]")
    page.wait_for_timeout(1500)
    page.click("#tabs .tab >> nth=0")
    page.wait_for_timeout(900)
    save(page.screenshot(), "phone-files")

    # item menu (action sheet)
    page.click("#list .item:has-text('Banff trip.mov') [data-act=more]")
    page.wait_for_timeout(500)
    save(page.screenshot(), "phone-menu")
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # shared folder with uploader names
    page.click("#tabs .tab >> nth=1")
    page.wait_for_timeout(900)
    page.evaluate("document.querySelector('#list').scrollIntoView({block: 'start'})")
    page.wait_for_timeout(300)
    save(page.screenshot(), "phone-shared")

    # uploads in progress: slow the network so progress is visible
    page.evaluate("window.scrollTo(0, 0)")
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 20, "downloadThroughput": 5_000_000,
                                                  "uploadThroughput": 1_500_000})
    page.evaluate("""() => {
        const mk = (n, mb) => new File([new Uint8Array(mb * 1024 * 1024)], n);
        addFiles([mk('IMG_3021.HEIC', 4), mk('IMG_3022.HEIC', 5), mk('IMG_3023.HEIC', 3), mk('Hiking trip.mov', 60)]);
    }""")
    page.wait_for_timeout(5200)
    save(page.screenshot(), "phone-uploading")
    page.evaluate("jobs.forEach(j => cancelJob(j))")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1,
                                                  "uploadThroughput": -1})
    ctx.close()
    browser.close()
