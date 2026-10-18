"""Self-checks for the WiFiDrop website: layout, images, contrast, console, interactivity, spelling."""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from spellchecker import SpellChecker

BASE = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8090/"
ROOT = Path(__file__).resolve().parents[2]
SITE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
SHOTS = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "build" / "site-check"
SHOTS.mkdir(parents=True, exist_ok=True)
PAGES = sorted(p.name for p in SITE.glob("*.html"))
VIEWPORTS = {"phone": (375, 812), "tablet": (768, 1024), "desktop": (1440, 900)}

PAGE_CHECK = r"""() => {
  const out = {overflow: 0, images: [], contrast: []};
  out.overflow = document.documentElement.scrollWidth - window.innerWidth;
  for (const img of document.images) {
    if (!img.getAttribute('src')) continue;
    const r = img.getBoundingClientRect();
    const fit = getComputedStyle(img).objectFit;
    const info = {src: img.getAttribute('src'), loaded: img.complete && img.naturalWidth > 0};
    if (info.loaded && r.width > 0 && r.height > 0 && !['cover', 'contain'].includes(fit)) {
      const natural = img.naturalWidth / img.naturalHeight, shown = r.width / r.height;
      info.stretch = Math.abs(shown / natural - 1);
    }
    out.images.push(info);
  }
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = ({r, g, b}) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = el => { let stack = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { stack.push(c); if (c.a >= 0.99) break; } }
    let base = {r: 0, g: 0, b: 0}; const body = parse(getComputedStyle(document.body).backgroundColor); if (body) base = body;
    for (const c of stack.reverse()) base = {r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a)};
    return base; };
  const seen = new Set();
  for (const el of document.querySelectorAll('h1,h2,h3,h4,p,li,a,button,label,td,th,summary,span,small,code,dd,dt,figcaption,output')) {
    const st = getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || el.closest('[hidden]') || el.closest('.screen') || el.closest('.lightbox')) continue;
    if (st.backgroundClip === 'text' || st.webkitBackgroundClip === 'text' || el.closest('.gradient-text')) continue;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    if (el.closest('[aria-disabled="true"]') || el.disabled) continue;
    const fg = parse(st.color); if (!fg) continue;
    const bg = bgOf(el);
    const L1 = lum(fg), L2 = lum(bg); const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const size = parseFloat(st.fontSize), bold = parseInt(st.fontWeight) >= 700;
    const need = (size >= 24 || (bold && size >= 18.66)) ? 3 : 4.5;
    if (ratio < need) { const key = el.tagName + ':' + el.textContent.trim().slice(0, 40); if (!seen.has(key)) { seen.add(key); out.contrast.push({el: key, ratio: +ratio.toFixed(2), need}); } }
  }
  return out;
}"""

problems = []
texts = {}
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    for theme in ["dark", "light"]:
        for vname, (w, h) in VIEWPORTS.items():
            ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=theme, reduced_motion="reduce",
                                      is_mobile=vname == "phone", has_touch=vname == "phone", device_scale_factor=1)
            for name in PAGES:
                page = ctx.new_page()
                errors = []
                page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(BASE + name, wait_until="networkidle")
                page.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
                page.wait_for_timeout(250)
                res = page.evaluate(PAGE_CHECK)
                tag = f"{name} [{theme}/{vname}]"
                if errors:
                    problems.append(f"{tag} console: {errors[:2]}")
                if res["overflow"] > 1:
                    problems.append(f"{tag} scrolls sideways by {res['overflow']}px")
                for im in res["images"]:
                    if not im["loaded"]:
                        problems.append(f"{tag} image not loaded: {im['src']}")
                    elif im.get("stretch", 0) > 0.02:
                        problems.append(f"{tag} image stretched {im['stretch']:.0%}: {im['src']}")
                for c in res["contrast"]:
                    problems.append(f"{tag} low contrast {c['ratio']} (needs {c['need']}): {c['el']}")
                if theme == "dark" and vname == "desktop":
                    texts[name] = page.inner_text("main")
                page.close()
            ctx.close()

    # ---- interactivity
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme="dark")
    page = ctx.new_page()
    page.goto(BASE + "index.html", wait_until="networkidle")
    before = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.click(".theme-toggle")
    after = page.evaluate("document.documentElement.getAttribute('data-theme')")
    page.reload(wait_until="networkidle")
    persisted = page.evaluate("document.documentElement.getAttribute('data-theme')")
    if not (after == "light" and persisted == "light"):
        problems.append(f"theme toggle: before={before} after={after} after reload={persisted}")
    page.click(".theme-toggle")
    page.locator("#tour").scroll_into_view_if_needed()
    page.click("#tour .tour-tab >> nth=2")
    active = page.evaluate("[...document.querySelectorAll('#tour .screen img.swap')].findIndex(i => i.classList.contains('active'))")
    if active != 2:
        problems.append(f"tour tab click: active image {active}, expected 2")
    page.click(".hero-shots img.zoomable >> nth=0")
    page.wait_for_timeout(300)
    if not page.evaluate("document.querySelector('dialog.lightbox').open"):
        problems.append("lightbox did not open")
    page.keyboard.press("Escape")
    page.goto(BASE + "faq.html", wait_until="networkidle")
    page.fill("#faq-search", "iphone")
    visible = page.evaluate("[...document.querySelectorAll('.faq details')].filter(d => !d.hidden).length")
    page.fill("#faq-search", "zzzz")
    none_shown = page.evaluate("!document.querySelector('.no-results').hidden")
    if not (0 < visible < 13 and none_shown):
        problems.append(f"faq search: visible={visible} no-results shown={none_shown}")
    page.goto(BASE + "pricing.html", wait_until="networkidle")
    page.fill("#people", "12")
    page.dispatch_event("#people", "input")
    verdict = page.inner_text("#people-verdict")
    if "Pro" not in verdict:
        problems.append(f"pricing picker: {verdict!r}")
    ctx.close()

    m = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True, color_scheme="dark")
    page = m.new_page()
    page.goto(BASE + "index.html", wait_until="networkidle")
    page.click(".menu-btn")
    page.wait_for_timeout(300)
    if not page.is_visible(".nav a[href='pricing.html']"):
        problems.append("mobile menu did not open")
    m.close()

    # ---- review screenshots
    for theme in ["dark", "light"]:
        for vname, (w, h) in [("desktop", (1440, 900)), ("phone", (390, 844))]:
            ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=theme, reduced_motion="reduce",
                                      device_scale_factor=1 if vname == "desktop" else 2, is_mobile=vname == "phone")
            page = ctx.new_page()
            for name in ["index", "pricing", "features"]:
                page.goto(BASE + name + ".html", wait_until="networkidle")
                page.evaluate("document.querySelectorAll('img[loading=lazy]').forEach(i => i.loading = 'eager')")
                page.wait_for_timeout(400)
                page.screenshot(path=str(SHOTS / f"{name}-{theme}-{vname}.png"), full_page=True)
            ctx.close()
    browser.close()

# ---- spelling
spell = SpellChecker()
allow = set("""wifidrop filedrop changelog chunked dac française get-filehash github gmail progressclosed screenshot screenshots statusesnew subfolders supabase txn usernames waitlist else's https http wi-fi wifi iphone ipad icloud android webview runtime powershell sha argon2id pipeda casl ccpa gdpr
quebec québec qr csv tba cad os ios macos windows microsoft edge safari chrome firefox mac linux exe programdata gethash
admin admins pc pcs usb faq url urls id ids html sms app apps beta pro pin unsubscribe hotspot hotspots login signin
reupload checksum checksums ttl dns wan lan nas uploads uploader downloads lifecycle iso utc fileDrop
licence licences licensors colour colours organization organizations recognize behaviour favourite centre
cookie cookies telemetry analytics hashed hashes zip mov heic jpg png pdf docx webp ui api apis tos eula
sublicense non-exclusive non-transferable non-infringement commission d'accès l'information québec privacy-request
pics gb mb tb kb mins inc""".split())
unknown = {}
for name, text in texts.items():
    for word in re.findall(r"[A-Za-zÀ-ÿ'][A-Za-zÀ-ÿ'\-]+", text):
        w = word.strip("'-").lower()
        if len(w) < 3 or w in allow or any(ch.isdigit() for ch in w):
            continue
        parts = w.split("-")
        if all(part in allow or not spell.unknown([part]) for part in parts if part):
            continue
        unknown.setdefault(w, set()).add(name)

print(json.dumps({"problems": problems, "possible_misspellings": {k: sorted(v) for k, v in sorted(unknown.items())}}, indent=1))
