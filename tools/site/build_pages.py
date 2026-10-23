"""Writes the WiFiDrop website pages into site/ with a shared header and footer.

Run from the repo:  .venv/Scripts/python tools/site/build_pages.py
Then check them:   tools/site/check.py (see README). Edit text here, not in the generated .html files.
"""
import sys
from pathlib import Path

SITE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "site"
UPDATED = "October 17, 2026"
PRIVACY_UPDATED = "October 23, 2026"  # local prices on the Pricing page

PATHS = {
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "users": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    "share": '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/>',
    "home": '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "wifi": '<path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/>',
    "folder": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "phone": '<rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
    "monitor": '<rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
    "refresh": '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    "arrow": '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
    "sun": '<circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>',
    "moon": '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>',
    "menu": '<line x1="3" y1="7" x2="21" y2="7"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="17" x2="21" y2="17"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "search": '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
}


def svg(name, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<svg{c} viewBox="0 0 24 24" aria-hidden="true">{PATHS[name]}</svg>'


def icon(name):
    return f'<span class="icon">{svg(name)}</span>'


def titlebar(title):
    """Windows 11 style title bar: app icon and name on the left, caption buttons on the right."""
    return (f'<div class="titlebar"><img src="assets/img/favicon.svg" alt="" width="16" height="16"><span>{title}</span>'
            '<span class="caps" aria-hidden="true"><i class="min"></i><i class="max"></i><i class="close"></i></span></div>')


def browser(src, alt, title="WiFiDrop Admin", zoom=True, eager=False):
    load = "" if eager else ' loading="lazy"'
    z = ' class="zoomable"' if zoom else ""
    return (f'<div class="browser-frame">{titlebar(title)}'
            f'<div class="screen"><img{z} src="assets/img/{src}" alt="{alt}" width="2880" height="1800"{load} decoding="async"></div></div>')


def phone(src, alt, zoom=True, eager=False):
    load = "" if eager else ' loading="lazy"'
    z = ' class="zoomable"' if zoom else ""
    return (f'<div class="phone-frame"><div class="screen"><img{z} src="assets/img/{src}" alt="{alt}" width="1170" height="2532"{load} decoding="async"></div></div>')


SPAM_FIELDS = ('<div class="hp" aria-hidden="true"><label>Leave this empty<input name="website" tabindex="-1" autocomplete="off"></label></div>'
               '<input type="hidden" name="started" value="">')
STATUS = '<p class="form-status" data-form-status role="status" aria-live="polite" hidden></p>'


def tour(items, kind):
    """items: [(title, text, image, alt)]; kind: 'browser' or 'phone'."""
    tabs = "".join(
        f'<button class="tour-tab" type="button" role="tab" aria-selected="{str(i == 0).lower()}">'
        f'<b>{t}</b><span>{d}</span><span class="bar"><i></i></span></button>'
        for i, (t, d, _, _) in enumerate(items))
    imgs = "".join(
        f'<img class="swap{" active" if i == 0 else ""}" src="assets/img/{src}" alt="{alt}" '
        f'width="{2880 if kind == "browser" else 1170}" height="{1800 if kind == "browser" else 2532}" loading="lazy" decoding="async">'
        for i, (_, _, src, alt) in enumerate(items))
    if kind == "browser":
        frame = f'<div class="browser-frame">{titlebar('WiFiDrop Admin')}<div class="screen">{imgs}</div></div>'
        cls = "tour"
    else:
        frame = f'<div class="phone-frame"><div class="screen">{imgs}</div></div>'
        cls = "tour phone-tour"
    return f'<div class="{cls} reveal"><div class="tour-tabs" role="tablist">{tabs}</div><div>{frame}</div></div>'


HEADER = f"""<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="index.html"><img src="assets/img/favicon.svg" alt="" width="30" height="30">WIFIDROP <span class="beta">BETA</span></a>
    <nav class="nav" id="nav" aria-label="Main">
      <a href="features.html">Features</a>
      <a href="pricing.html">Pricing</a>
      <a href="guide.html">Setup guide</a>
      <a href="faq.html">FAQ</a>
      <a class="btn primary small" href="download.html">Download free</a>
    </nav>
    <button class="icon-btn theme-toggle" type="button" aria-label="Switch theme">{svg("moon", "moon")}{svg("sun", "sun")}</button>
    <button class="icon-btn menu-btn" type="button" aria-expanded="false" aria-controls="nav" aria-label="Menu">{svg("menu", "open")}{svg("x", "close")}</button>
  </div>
</header>"""

FOOTER = """<footer class="site-footer">
  <div class="wrap">
    <div class="cols">
      <div>
        <a class="brand" href="index.html"><img src="assets/img/favicon.svg" alt="" width="30" height="30">WIFIDROP</a>
        <p>Your own private file-sharing space, hosted on your Windows PC.</p>
      </div>
      <div><h4>Product</h4><ul>
        <li><a href="features.html">Features</a></li><li><a href="pricing.html">Pricing</a></li>
        <li><a href="download.html">Download</a></li><li><a href="changelog.html">Changelog</a></li></ul></div>
      <div><h4>Help</h4><ul>
        <li><a href="guide.html">Setup guide</a></li><li><a href="faq.html">FAQ</a></li>
        <li><a href="feedback.html">Send feedback</a></li><li><a href="beta.html">Join the beta</a></li>
        <li><a href="contact.html">Contact</a></li><li><a href="licence.html">Lost your licence?</a></li></ul></div>
      <div><h4>Legal</h4><ul>
        <li><a href="privacy.html">Privacy policy</a></li><li><a href="terms.html">Terms of use</a></li>
        <li><a href="refunds.html">Refund policy</a></li></ul></div>
    </div>
    <div class="legal">
      <span>&copy; <span data-year>2026</span> WiFiDrop. Made in Canada. Beta software.</span>
      <span>Windows is a trademark of Microsoft Corporation.</span>
    </div>
  </div>
</footer>"""


PADDLE_CSP = ("default-src 'self'; img-src 'self' data: https://*.paddle.com; style-src 'self' 'unsafe-inline' https://*.paddle.com; "
              "script-src 'self' https://cdn.paddle.com; frame-src https://buy.paddle.com https://sandbox-buy.paddle.com; "
              "connect-src 'self' https://*.supabase.co https://*.paddle.com; form-action 'self'; base-uri 'self'; object-src 'none'")
BASE_CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self' https://*.supabase.co; "
            "form-action 'self'; base-uri 'self'; object-src 'none'")


def page(filename, title, description, body, csp=None, lang="en-CA"):
    full = f"{title} | WiFiDrop" if title != "WiFiDrop" else "WiFiDrop: your own private file drop, hosted on your PC"
    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
<meta http-equiv="Content-Security-Policy" content="{csp or BASE_CSP}">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{full}</title>
<meta name="description" content="{description}">
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#f7f9fd" media="(prefers-color-scheme: light)">
<meta property="og:type" content="website">
<meta property="og:title" content="{full}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="assets/img/admin-dashboard.webp">
<link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/css/site.css">
<script src="assets/js/theme.js"></script>
<script src="assets/js/config.js" defer></script>
<script src="assets/js/site.js" defer></script>
</head>
<body>
{HEADER}
<main id="main">
{body}
</main>
{FOOTER}
</body>
</html>
"""
    (SITE / filename).write_text(html, encoding="utf-8")


DL = svg("download")
ARROW = svg("arrow", "arrow")

# =================================================================== home
admin_tour = tour([
    ("Dashboard", "Start the server, share the QR code, see who's online.", "admin-dashboard.webp", "WiFiDrop dashboard with the server running, a QR code and live statistics"),
    ("Users", "Add people, set limits, suspend or reset in a click.", "admin-users.webp", "WiFiDrop Users page listing four accounts"),
    ("Shared folders", "Pick who can view, upload or manage each folder.", "admin-shared.webp", "Shared folder permissions with View, Upload and Manage per person"),
    ("Browse files", "See and manage what's stored, for any user.", "admin-files.webp", "Browsing a user's files from the admin window"),
], "browser")

phone_tour = tour([
    ("Your files", "Folders, files and one big upload button.", "phone-files.webp", "A phone showing a user's files in WiFiDrop"),
    ("Uploading", "Many files at once, with speed and time left.", "phone-uploading.webp", "A phone uploading four files with progress bars"),
    ("Shared folders", "See who added what in shared spaces.", "phone-shared.webp", "A shared Family photos folder on a phone"),
    ("Quick actions", "Move, rename or delete from one menu.", "phone-menu.webp", "The move, rename and delete menu on a phone"),
], "phone")

page("index.html", "WiFiDrop",
     "WiFiDrop turns your Windows PC into a private file drop for everyone on your Wi-Fi. Accounts, private and shared folders, and no cloud.",
     f"""<section class="hero">
  <div class="wrap">
    <span class="eyebrow reveal"><span class="dot"></span>Free for Windows 10 and 11 &middot; Public beta</span>
    <h1 class="reveal d1">Your own private file drop,<br><span class="gradient-text">hosted on your PC.</span></h1>
    <p class="lead reveal d2">Everyone on your Wi-Fi can send photos, videos and documents straight to your computer from their phone's browser. No app to install, no cloud, no monthly fee.</p>
    <div class="cta reveal d3">
      <a class="btn primary big" href="download.html">{DL}Download free</a>
      <a class="btn big" href="#tour">See it in action{ARROW}</a>
    </div>
    <p class="fineprint reveal d3">No account with us needed. Your files never leave your network.</p>
    <div class="hero-shots reveal">
      {browser("admin-dashboard.webp", "The WiFiDrop admin window on Windows", eager=True)}
      {phone("phone-files.webp", "WiFiDrop on a phone", eager=True)}
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="section-head reveal"><span class="kicker">How it works</span><h2>Up and running in three steps</h2>
      <p>WiFiDrop runs quietly in your system tray. People connect from any phone or computer on the same network.</p></div>
    <div class="steps">
      <div class="card reveal"><h3>Install and pick a folder</h3><p>Run the installer and choose where uploaded files are saved, like a big second drive.</p></div>
      <div class="card reveal d1"><h3>Add people</h3><p>Create an account for each person. They choose their own password the first time they sign in.</p></div>
      <div class="card reveal d2"><h3>Scan and send</h3><p>They scan the QR code on your screen, sign in and tap <b>Upload files</b>. That's it.</p></div>
    </div>
  </div>
</section>

<section class="alt" id="tour">
  <div class="wrap">
    <div class="section-head reveal"><span class="kicker">On your PC</span><h2>A real Windows app for the person in charge</h2>
      <p>Click through the admin window. Close it any time and WiFiDrop keeps running in the tray.</p></div>
    {admin_tour}
  </div>
</section>

<section>
  <div class="wrap">
    <div class="section-head reveal"><span class="kicker">On their phones</span><h2>Nothing to install for anyone else</h2>
      <p>People open a link in the browser they already have, on iPhone, Android or any computer.</p></div>
    {phone_tour}
  </div>
</section>

<section class="alt">
  <div class="wrap">
    <div class="section-head reveal"><span class="kicker">Features</span><h2>Built for families, classrooms and small teams</h2>
      <p>Everything you need to collect and share files on your own terms.</p></div>
    <div class="grid">
      <div class="card reveal">{icon("home")}<h3>Private folders</h3><p>Every person gets their own space. Nobody else can see it, not even other users.</p></div>
      <div class="card reveal d1">{icon("share")}<h3>Shared folders</h3><p>Make folders like "Family photos" and choose who can view, upload or manage.</p></div>
      <div class="card reveal d2">{icon("upload")}<h3>Uploads that don't give up</h3><p>Send many files at once. Uploads resume by themselves if the Wi-Fi drops.</p></div>
      <div class="card reveal">{icon("users")}<h3>You stay in control</h3><p>Pause uploads or downloads, sign out a device, suspend an account, set storage limits.</p></div>
      <div class="card reveal d1">{icon("lock")}<h3>Encrypted on your network</h3><p>Connections use HTTPS, passwords are hashed and the admin window can be locked with a PIN.</p></div>
      <div class="card reveal d2">{icon("phone")}<h3>Works in any browser</h3><p>iPhone, Android, Windows or Mac. Nothing to install on the devices that connect.</p></div>
    </div>
    <p class="center reveal more"><a class="btn" href="features.html">All features{ARROW}</a></p>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="promise reveal">
      <div>
        <span class="kicker">Privacy</span>
        <h2>Your files stay yours.</h2>
        <p>WiFiDrop runs on your own Windows computer. Files are stored in the folder you choose, and other people reach them over your local network.</p>
        <p>We don't upload your files to our servers, and the app doesn't send us file names, file contents or usage data.</p>
        <p><a href="privacy.html">Read exactly what we do and don't collect &rarr;</a></p>
      </div>
      <div class="facts">
        <div class="fact"><h3>Stays on your PC</h3><ul><li>Every uploaded file</li><li>Accounts and passwords (hashed)</li><li>Activity history and logs</li></ul></div>
        <div class="fact"><h3>We never receive</h3><ul class="no"><li>Your files or file names</li><li>Who uses WiFiDrop or how</li><li>Analytics or crash reports</li></ul></div>
      </div>
    </div>
  </div>
</section>

<section>
  <div class="wrap center">
    <div class="section-head reveal"><h2>Try it free</h2><p>WiFiDrop Free is a complete product, not a trial. Pro adds unlimited accounts and scheduled backups.</p></div>
    <div class="cta reveal"><a class="btn primary big" href="download.html">{DL}Download free</a><a class="btn big" href="pricing.html">Compare Free and Pro</a></div>
  </div>
</section>""")

# =================================================================== features
page("features.html", "Features",
     "What WiFiDrop does today: a desktop admin window, phone-friendly uploads, private and shared folders, HTTPS and admin controls.",
     f"""<div class="wrap page-hero"><h1>Features</h1>
  <p>Everything on this page works in the current beta. Features still in development are marked <span class="soon">Planned</span>. Click any screenshot to see it full size.</p></div>

<section>
  <div class="wrap">
    <div class="split reveal">
      <div><span class="kicker">Admin window</span><h2>Everything in one place on your PC</h2>
        <ul class="checks">
          <li>Start and stop the web server, with a QR code and link to share</li>
          <li>See who's signed in and what's uploading, then sign out a device or cancel an upload</li>
          <li>Pause all uploads or downloads with one switch</li>
          <li>Close the window and WiFiDrop keeps running in the tray</li>
          <li>Optional PIN so nobody else on the PC can manage users or files</li>
        </ul></div>
      {browser("admin-dashboard.webp", "WiFiDrop admin dashboard")}
    </div>

    <div class="split phone-row flip reveal">
      <div><span class="kicker">For everyone else</span><h2>Upload from any phone, no app needed</h2>
        <ul class="checks">
          <li>Open the link or scan the QR code, then sign in</li>
          <li>Upload many files at once, of any type, with progress and time left</li>
          <li>Uploads are sent in pieces and resume by themselves after a dropped connection</li>
          <li>Make folders like "Pics" and "School", then move, rename and delete files</li>
          <li>Deleted items go to the Trash first and can be restored</li>
        </ul></div>
      {phone("phone-uploading.webp", "Uploading several files from a phone")}
    </div>

    <div class="split reveal">
      <div><span class="kicker">Accounts and sharing</span><h2>Private by default, shared on purpose</h2>
        <ul class="checks">
          <li>Each person has a private folder only they can see</li>
          <li>Shared folders with View, Upload or Manage access for each person</li>
          <li>People with Upload access can only change files they added</li>
          <li>Storage limits per person and per shared folder</li>
          <li>Suspend or delete accounts; files someone added to shared folders stay</li>
        </ul></div>
      {browser("admin-shared.webp", "Shared folder permissions in the admin window")}
    </div>

    <div class="split flip reveal">
      <div><span class="kicker">Simple setup</span><h2>Adding people takes seconds</h2>
        <ul class="checks">
          <li>WiFiDrop suggests an easy temporary password</li>
          <li>People choose their own password the first time they sign in</li>
          <li>Give admins the power to manage every shared folder</li>
          <li>Reset a forgotten password from the admin window</li>
        </ul></div>
      {browser("admin-add-user.webp", "The Add user dialog in the admin window")}
    </div>
  </div>
</section>

<section class="alt">
  <div class="wrap">
    <div class="section-head reveal"><span class="kicker">Under the hood</span><h2>Security and reliability</h2></div>
    <div class="grid">
      <div class="card reveal">{icon("lock")}<h3>HTTPS on your network</h3><p>WiFiDrop makes its own certificate. Phones show a one-time warning, then the connection is encrypted.</p></div>
      <div class="card reveal d1">{icon("shield")}<h3>Careful with passwords</h3><p>Passwords are stored with Argon2id. Repeated wrong passwords lock the account and slow down guessing.</p></div>
      <div class="card reveal d2">{icon("folder")}<h3>Files never half-written</h3><p>Uploads are finished and checked before they appear. Rename and move are instant and can't half-fail.</p></div>
      <div class="card reveal">{icon("refresh")}<h3>Safe upgrades</h3><p>Each new version backs up its database first and refuses to damage data from a newer version.</p></div>
      <div class="card reveal d1">{icon("wifi")}<h3>Local network only</h3><p>WiFiDrop only listens on private network addresses. It isn't reachable from the internet.</p></div>
      <div class="card reveal d2">{icon("monitor")}<h3>Your choice of drive</h3><p>Pick where files go during setup, and move everything to a new drive later from the admin window.</p></div>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <div class="section-head reveal"><span class="kicker">WiFiDrop Pro</span><h2>Pro, and what's next</h2><p>Pro adds unlimited accounts and scheduled backups. Items marked Planned aren't available yet. <a href="pricing.html">See plans</a>.</p></div>
    <div class="grid four">
      <div class="card reveal"><h3>Scheduled backups <span class="soon">In Pro</span></h3><p>Automatic daily or weekly copies of every file and account to another drive, such as an external disk.</p></div>
      <div class="card reveal d1"><h3>Guest upload links <span class="soon">Planned</span></h3><p>A link or QR code that lets guests drop files into one folder without an account.</p></div>
      <div class="card reveal d2"><h3>Transfer history <span class="soon">Planned</span></h3><p>Who uploaded and downloaded what, with CSV export.</p></div>
      <div class="card reveal d3"><h3>Your name and logo <span class="soon">Planned</span></h3><p>Custom name, logo and colour on the page people see.</p></div>
    </div>
  </div>
</section>""")

# =================================================================== pricing
CHECK_FREE = ["<b>Up to 5 user accounts</b>", "Private folders and unlimited shared folders", "View, Upload and Manage permissions",
              "Resumable uploads of any file type", "Storage limits you set", "Pause controls, sign-out, suspend accounts",
              "HTTPS and admin window PIN", "Security updates"]
CHECK_PRO = ["<b>Everything in Free</b>", "<b>Unlimited user accounts</b>", "Scheduled backups of files and accounts to another drive",
             "Use your licence on up to 3 PCs", "Works offline, no account with us", "Feature updates for 1 year"]
li = lambda items: "".join(f"<li>{x}</li>" for x in items)
page("pricing.html", "Pricing",
     "WiFiDrop Free is a complete local file-sharing product. WiFiDrop Pro adds unlimited accounts and scheduled backups.",
     f"""<div class="wrap page-hero center"><h1>Simple, honest pricing</h1>
  <p>Free stays free. Pro is a one-time purchase of $29.99 CAD that includes a year of feature updates. No subscription, and no account with us needed to use WiFiDrop.</p></div>

<section>
  <div class="wrap">
    <div class="picker reveal">
      <label for="people">How many people will use WiFiDrop?</label>
      <output id="people-out" for="people">3</output>
      <input id="people" type="range" min="1" max="20" value="3">
      <p class="verdict" id="people-verdict" aria-live="polite"></p>
    </div>
    <div class="plans">
      <div class="plan free reveal">
        <h3>WiFiDrop Free</h3>
        <div class="price">$0 <small>forever</small></div>
        <p class="muted">Everything you need to share files at home.</p>
        <ul class="checks">{li(CHECK_FREE)}</ul>
        <a class="btn primary" href="download.html">{DL}Download free</a>
      </div>
      <div class="plan pro reveal d1">
        <h3>WiFiDrop Pro <span class="soon">Available now</span></h3>
        <div class="price">$29.99 <small>CAD, one-time</small></div>
        <p class="muted small" data-price-note hidden></p>
        <p class="muted">For bigger families, classrooms, clubs and small offices.</p>
        <ul class="checks">{li(CHECK_PRO)}</ul>
        <form class="form" data-api="waitlist" method="post">
          <label for="wl-email">Tell me when Pro launches</label>
          <input id="wl-email" name="email" type="email" placeholder="you@example.com" autocomplete="email" required>
          <label class="consent"><input type="checkbox" name="consent" value="yes" required>
            <span>Yes, email me about the WiFiDrop Pro launch. I can unsubscribe at any time. See the <a href="privacy.html">privacy policy</a>.</span></label>
          {SPAM_FIELDS}
          <button class="btn primary" type="submit">Notify me</button>
          {STATUS}
        </form>
        <p class="form-note" data-waitlist-note>One email when Pro launches. No spam, ever.</p>
        <div class="buy" data-buy hidden>
          <button class="btn primary big" type="button" data-buy-btn>Buy WiFiDrop Pro</button>
          <p class="form-note" data-buy-note>Your licence arrives by email within a minute. Paste it into WiFiDrop to unlock Pro. Taxes are calculated at checkout by our reseller, Paddle.</p>
          <p class="form-note"><a href="licence.html">Lost your licence?</a></p>
        </div>
      </div>
    </div>
  </div>
</section>

<section class="alt">
  <div class="wrap">
    <div class="section-head reveal"><h2>Compare plans</h2><p>Pro is $29.99 CAD, one-time. Features marked "planned" aren't available yet.</p></div>
    <div class="table-wrap reveal"><table class="compare">
      <thead><tr><th scope="col">Feature</th><th scope="col">Free</th><th scope="col">Pro</th></tr></thead>
      <tbody>
        <tr><td>Private folders, subfolders, move, rename, Trash</td><td class="yes">Included</td><td class="yes">Included</td></tr>
        <tr><td>Shared folders with permissions</td><td class="yes">Included</td><td class="yes">Included</td></tr>
        <tr><td>Resumable uploads and downloads</td><td class="yes">Included</td><td class="yes">Included</td></tr>
        <tr><td>Admin window, QR code, pause controls</td><td class="yes">Included</td><td class="yes">Included</td></tr>
        <tr><td>Storage limits you set</td><td class="yes">Included</td><td class="yes">Included</td></tr>
        <tr><td>HTTPS and admin PIN</td><td class="yes">Included</td><td class="yes">Included</td></tr>
        <tr><td>User accounts</td><td>Up to 5</td><td>Unlimited</td></tr>
        <tr><td>Activity log</td><td class="yes">Included</td><td class="yes">Included</td></tr>
        <tr><td>Scheduled backups of files and accounts</td><td class="no">&mdash;</td><td class="yes">Daily or weekly, to another drive</td></tr>
        <tr><td>Transfer history CSV export</td><td class="no">&mdash;</td><td>Planned</td></tr>
        <tr><td>Guest upload links</td><td class="no">&mdash;</td><td>Planned</td></tr>
        <tr><td>Server hours, admin from another PC</td><td class="no">&mdash;</td><td>Planned</td></tr>
        <tr><td>Custom name, logo and colour</td><td class="no">&mdash;</td><td>Planned</td></tr>
        <tr><td>Security updates</td><td class="yes">Always</td><td class="yes">Always</td></tr>
        <tr><td>Feature updates</td><td>Free releases</td><td>1 year included, then optional renewal</td></tr>
      </tbody>
    </table></div>
    <p>If you reach a Free limit, nothing stops working: your files and existing accounts stay available. Prices are in Canadian dollars; sales tax is added at checkout based on where you live.</p>
  </div>
</section>""", csp=PADDLE_CSP)

# =================================================================== download
page("download.html", "Download",
     "Download WiFiDrop for Windows 10 and 11. Version, release notes, checksum and install steps.",
     f"""<div class="wrap page-hero"><h1>Download WiFiDrop</h1>
  <p>Free for Windows 10 and 11. Version <span data-site="version">0.2.0</span> (beta), released <span data-site="releaseDate">2026-10-21</span>.</p></div>

<section>
  <div class="wrap doc">
    <div class="card download-box reveal">
      <div>
        <h3>WiFiDrop for Windows</h3>
        <dl class="meta-list">
          <dt>Version</dt><dd><span data-site="version">0.2.0</span> beta</dd>
          <dt>Size</dt><dd><span data-site="downloadSize">To be announced</span></dd>
          <dt>SHA-256</dt><dd><code data-site="sha256">Published with the download</code></dd>
        </dl>
      </div>
      <a class="btn primary big" href="download.html" data-download>{DL}<span data-label>Download for Windows</span></a>
    </div>
    <p class="callout" data-if-no-download>The public download isn't up yet. Want to try the beta? <a href="contact.html">Get in touch</a>.</p>

    <h2 id="requirements">Requirements</h2>
    <ul>
      <li><b>Host PC:</b> Windows 10 (version 1809 or later) or Windows 11, 64-bit.</li>
      <li><b>Microsoft Edge WebView2:</b> built into Windows 11. On Windows 10 it's usually already installed. If the admin window stays blank, install the <a href="https://developer.microsoft.com/microsoft-edge/webview2/" rel="noopener">WebView2 Runtime</a>.</li>
      <li><b>Disk:</b> about 200 MB for the app, plus space for the files people upload.</li>
      <li><b>Phones and computers that connect:</b> any recent browser (Safari, Chrome, Edge or Firefox) on the same Wi-Fi or hotspot.</li>
    </ul>

    <h2 id="install">Install</h2>
    <ol>
      <li>Run <code>WiFiDrop-Setup-<span data-site="version">0.2.0</span>.exe</code>.</li>
      <li>The beta isn't code-signed yet, so Windows may show <b>"Windows protected your PC"</b>. Click <b>More info</b>, then <b>Run anyway</b>. If you want to be sure first, check the SHA-256 (below).</li>
      <li>Choose whether WiFiDrop starts when you sign in. The installer also adds a Windows Firewall rule so phones can connect.</li>
      <li>WiFiDrop opens and asks where to save uploaded files. Then follow the <a href="guide.html">setup guide</a>.</li>
    </ol>

    <h2 id="verify">Check the download</h2>
    <p>In PowerShell, in your Downloads folder, run:</p>
    <div class="copy-row"><code id="hash-cmd">Get-FileHash .\\WiFiDrop-Setup-0.2.0.exe</code><button class="btn small copy-btn" type="button" data-copy="#hash-cmd">Copy</button></div>
    <p>The result should match the SHA-256 above exactly.</p>

    <h2 id="uninstall">Uninstall</h2>
    <p>Go to <b>Settings &rarr; Apps &rarr; WiFiDrop &rarr; Uninstall</b>. Uninstalling never deletes the files people uploaded or your accounts. They stay in your storage folder and in <code>%ProgramData%\\WiFiDrop</code>, so reinstalling picks up where you left off.</p>

    <h2 id="notes">What's new in this version</h2>
    <p>See the <a href="changelog.html">changelog</a>.</p>
  </div>
</section>""")

# =================================================================== guide
page("guide.html", "Setup guide",
     "How to set up WiFiDrop: choose a storage folder, add users, connect phones over Wi-Fi or a hotspot, and get past the one-time HTTPS warning.",
     f"""<div class="wrap page-hero"><h1>Setup guide</h1>
  <p>From install to the first upload in about five minutes.</p>
  <nav class="toc" aria-label="On this page">
    <a href="#install">1. Install</a><a href="#storage">2. Storage folder</a><a href="#users">3. Add people</a>
    <a href="#connect">4. Connect a phone</a><a href="#warning">5. The one-time warning</a><a href="#shared">6. Shared folders</a>
    <a href="#trouble">Troubleshooting</a></nav></div>

<section>
  <div class="wrap doc">
    <h2 id="install">1. Install WiFiDrop</h2>
    <p>Download and run the installer from the <a href="download.html">download page</a>. WiFiDrop opens its admin window when it's done. Closing that window keeps WiFiDrop running in the system tray; right-click the tray icon and choose <b>Quit WiFiDrop</b> to stop it.</p>

    <h2 id="storage">2. Choose where files are saved</h2>
    <p>The first time, WiFiDrop asks where to store uploaded files. Click <b>Browse</b> and pick a drive with plenty of space. If the folder already has other things in it, WiFiDrop creates a <b>WiFiDrop Files</b> folder inside it so nothing gets mixed up.</p>
    <p class="callout">Files are stored under internal ID names, not their real names, so they can't clash or break. To move everything to another drive later, use <b>Dashboard &rarr; Storage &rarr; Change folder</b>.</p>

    <h2 id="users">3. Add people</h2>
    <p>Go to <b>Users &rarr; Add user</b>. Choose a username and display name; WiFiDrop suggests a temporary password. Give those to the person. They choose their own password the first time they sign in.</p>
    <figure>{browser("admin-add-user.webp", "The Add user dialog in the WiFiDrop admin window")}<figcaption>Adding a user. Click to enlarge.</figcaption></figure>
    <p>WiFiDrop Free includes up to 5 accounts. You can set a storage limit for each person, suspend an account at any time or reset a password.</p>

    <h2 id="connect">4. Connect a phone</h2>
    <ol>
      <li>Make sure the phone and the PC are on the <b>same Wi-Fi</b>, or that the PC is connected to the <b>phone's hotspot</b>.</li>
      <li>On the PC, open the Dashboard. Scan the QR code with the phone's camera, or type the link shown under it (it starts with <code>https://</code>).</li>
      <li>Sign in with the username and temporary password, then choose a new password.</li>
      <li>Tap <b>Upload files</b>.</li>
    </ol>
    <figure>{phone("phone-signin.webp", "The WiFiDrop sign-in page on a phone")}<figcaption>The sign-in page people see.</figcaption></figure>
    <p class="callout"><b>Tip:</b> if someone types just the PC's address without <code>https://</code>, WiFiDrop shows a help page with a button to the secure link.</p>

    <h2 id="warning">5. The one-time "not private" warning</h2>
    <p>WiFiDrop encrypts connections with HTTPS, using a certificate it creates on your PC. Phones don't recognize who made that certificate, so the first time they show a warning. That's expected.</p>
    <ul>
      <li><b>iPhone (Safari):</b> tap <b>Show Details</b>, then <b>visit this website</b>, then <b>Visit Website</b>.</li>
      <li><b>Android (Chrome):</b> tap <b>Advanced</b>, then <b>Proceed</b>.</li>
      <li><b>Windows or Mac browsers:</b> choose <b>Advanced</b>, then <b>Continue</b>.</li>
    </ul>
    <p>The warning only comes back if the PC's network address changes (for example, switching from home Wi-Fi to a hotspot) or about once a year when the certificate renews. The Dashboard shows the certificate fingerprint if you want to compare it with what the phone shows.</p>
    <p class="callout warn"><b>On your own trusted network only</b>, you can turn off HTTPS in the Dashboard to avoid the warning. Without HTTPS, others on the same network could see passwords and files as they travel, so leave it on for shared, school or public Wi-Fi.</p>

    <h2 id="shared">6. Shared folders</h2>
    <p>Go to <b>Shared folders &rarr; New shared folder</b>, then choose each person's access:</p>
    <ul>
      <li><b>View:</b> see and download.</li>
      <li><b>Upload:</b> also add files and folders, and change or delete only what they added.</li>
      <li><b>Manage:</b> change or delete anything in the folder.</li>
    </ul>
    <figure>{browser("admin-shared.webp", "Shared folder access settings")}<figcaption>Access is set per person, per folder.</figcaption></figure>

    <h2 id="trouble">Troubleshooting</h2>
    <h3>The phone can't open the link</h3>
    <ul>
      <li>Check that both devices are on the same network. Guest Wi-Fi networks often block devices from seeing each other.</li>
      <li>Check that the address on the Dashboard matches the one you typed. If the PC changed networks, click <b>Stop web server</b> and then <b>Start web server</b>.</li>
      <li>If you didn't use the installer, Windows may have asked whether to allow WiFiDrop on the network. Allow it for Private and Public networks, or set your network to <b>Private</b> in Windows Settings.</li>
    </ul>
    <h3>Uploads from iPhone take a while to start</h3>
    <p>When you pick many photos, iOS prepares each one first, downloading originals from iCloud or converting formats. WiFiDrop starts uploading as soon as iOS hands the files over. Smaller batches start sooner.</p>
    <h3>I forgot the admin PIN</h3>
    <p>Quit WiFiDrop from the tray, then start it once from a terminal with:</p>
    <div class="copy-row"><code id="pin-cmd">WiFiDrop.exe --reset-admin-pin</code><button class="btn small copy-btn" type="button" data-copy="#pin-cmd">Copy</button></div>
  </div>
</section>""")

# =================================================================== faq
faqs = [
    ("Is WiFiDrop a cloud service?", "No. WiFiDrop runs on your own Windows PC and stores files in the folder you choose. Phones and computers on the same network connect to your PC directly. Nothing is uploaded to our servers."),
    ("Does it need the internet?", "No. WiFiDrop works on a local network with no internet connection, including a phone hotspot. If update checks are turned on, WiFiDrop looks for a newer version about once a day when it can."),
    ("Can people use it from outside my home?", "Not in this version. WiFiDrop only listens on your local network, which keeps it simple and private. Remote access may come later."),
    ("Why do iPhone uploads take a moment to start?", "When you pick many photos on an iPhone, iOS prepares each one first, downloading the original from iCloud or converting the format. WiFiDrop starts uploading as soon as iOS hands the files over. Smaller batches start sooner."),
    ("Do people need to install an app?", "No. They use the browser they already have on their phone or computer."),
    ("Why does my phone say the connection isn't private?", "WiFiDrop encrypts connections with a certificate it creates on your PC. Phones don't recognize who made it, so they warn once. The connection is still encrypted. The setup guide shows how to continue."),
    ("Is there a file size limit?", "There's no built-in limit. You can set storage limits for each person and each shared folder. Uploads are sent in pieces and resume if the connection drops, so large videos work."),
    ("What file types can people upload?", "Any type. Files are always downloaded as attachments, so nothing uploaded can run inside the page."),
    ("Does it work on Mac or Linux?", "The host app is Windows-only for now. People connecting can use any device with a modern browser."),
    ("How much is Pro?", "$29.99 CAD, once. No subscription. That includes a year of feature updates, and Pro keeps working after that. Sales tax is added at checkout. Your licence arrives by email within a minute of buying. Free stays free."),
    ("What data do you collect?", "The app sends us nothing about your files or how you use it. Our website and any forms you fill in receive limited information. The privacy policy explains exactly what."),
    ("Is WiFiDrop available outside Canada?", "Yes. WiFiDrop is made in Canada and anyone can download it. Our privacy policy covers visitors from Canada, the EU, the UK, the US and elsewhere."),
    ("How do I report a bug or suggest a feature?", "Use the feedback page. You can attach a screenshot, and the form asks for the details that help us fix problems quickly."),
]
items = "\n".join(f'<details class="reveal"><summary>{q}</summary><p class="answer">{a}</p></details>' for q, a in faqs)
page("faq.html", "FAQ", "Answers to common questions about WiFiDrop: cloud, internet, phones, the HTTPS warning, file limits, Pro and privacy.",
     f"""<div class="wrap page-hero"><h1>Frequently asked questions</h1><p>Can't find an answer? <a href="contact.html">Ask us</a>.</p></div>
<section><div class="wrap doc faq">
  <div class="search">{svg("search")}<label class="sr" for="faq-search">Search questions</label><input id="faq-search" type="search" placeholder="Search questions, for example 'iPhone' or 'size'" autocomplete="off"></div>
  {items}
  <p class="no-results" hidden>No questions match. Try another word, or <a href="contact.html">ask us</a>.</p>
</div></section>""")

# =================================================================== changelog
page("changelog.html", "Changelog", "What changed in each WiFiDrop release.",
     """<div class="wrap page-hero"><h1>Changelog</h1><p>Every WiFiDrop release, newest first.</p></div>
<section><div class="wrap doc">
  <h2 id="v0-2-0">0.2.0 beta &middot; October 21, 2026</h2>
  <ul>
    <li><b>Picture previews:</b> photos show as small pictures in the file lists, on phones and in the admin window. Tap a photo or video to see it full screen, with a Download button. Don't want them? Turn previews off in your account menu (or with the button in Browse files).</li>
    <li><b>Search:</b> find any file or folder by name, across your files and every shared folder you're in.</li>
  </ul>
  <h2 id="v0-1-5">0.1.5 beta &middot; October 19, 2026</h2>
  <ul>
    <li>The installer no longer fails if WiFiDrop was installed on a drive that's now unplugged. It offers C:\\Program Files instead.</li>
    <li>WiFiDrop can't be installed on a USB stick any more, so it never stops working when the stick is removed. Your shared files can still live on a USB or external drive.</li>
  </ul>
  <h2 id="v0-1-4">0.1.4 beta &middot; October 18, 2026</h2>
  <ul>
    <li>Support is now at <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a>, including in the licence agreement that comes with the app.</li>
  </ul>
  <h2 id="v0-1-3">0.1.3 beta &middot; October 18, 2026</h2>
  <ul>
    <li><b>Live updates:</b> the phone page and the admin window update by themselves within a few seconds when someone uploads, deletes, signs in or changes anything. No more refreshing.</li>
    <li>Downloading a file someone just deleted now says so and refreshes the list, instead of failing.</li>
    <li><b>Restore from a backup:</b> roll back from the Backups page, or bring everything back on a new PC from the first-run screen. Works on Free and Pro; your current state is saved first.</li>
  </ul>
  <h2 id="v0-1-2">0.1.2 beta &middot; October 18, 2026</h2>
  <ul>
    <li>The data folder moves from <code>%ProgramData%\\FileDrop</code> to <code>%ProgramData%\\WiFiDrop</code> automatically the first time WiFiDrop starts. Nothing is lost; if it can't be moved, WiFiDrop keeps using the old folder.</li>
    <li>Tidier internals: the last FileDrop names inside the app are now WiFiDrop.</li>
  </ul>
  <h2 id="v0-1-1">0.1.1 beta &middot; October 18, 2026</h2>
  <ul>
    <li>FileDrop is now <b>WiFiDrop</b>, with a new home at <a href="https://wifidrop.ca">wifidrop.ca</a>.</li>
    <li>Updating keeps your files, accounts, settings and Pro licence. The installer removes the old FileDrop startup entry and firewall rule.</li>
  </ul>
  <h2 id="v0-1-0">0.1.0 beta &middot; October 16, 2026</h2>
  <p>First public beta.</p>
  <ul>
    <li>Desktop admin window with tray icon; closing the window keeps WiFiDrop running.</li>
    <li>Choose the storage folder at first run and move it later.</li>
    <li>User accounts with temporary passwords, suspend, reset and delete.</li>
    <li>Private folders, subfolders, move, rename and Trash with restore.</li>
    <li>Shared folders with View, Upload and Manage access.</li>
    <li>Resumable chunked uploads, several files at once, any file type.</li>
    <li>Storage limits per person and per shared folder.</li>
    <li>Pause uploads or downloads; see signed-in devices and running uploads.</li>
    <li>HTTPS on the local network with a one-time phone warning, plus a help page for plain http:// links.</li>
    <li>Optional admin window PIN; data folders restricted to the Windows account running WiFiDrop.</li>
    <li>Database backup before every upgrade; items in the Trash for over 30 days are removed automatically.</li>
    <li>WiFiDrop Free includes up to 5 accounts. WiFiDrop Pro (in testing) adds unlimited accounts and scheduled backups of files and accounts to another drive.</li>
    <li>Licence screen: paste a Pro licence, see its status, or move it to another PC. Pro works offline.</li>
    <li>"Update available" notice in the admin window when a new version is out, and a Send feedback button that opens the feedback form.</li>
    <li>About page listing every open-source component and its licence; the installer shows the licence agreement.</li>
  </ul>
</div></section>""")

# =================================================================== contact
page("contact.html", "Contact", "Questions, partnerships, press and privacy requests for WiFiDrop.",
     f"""<div class="wrap page-hero"><h1>Contact us</h1><p>Questions, partnerships, press or privacy requests. For bugs and ideas, the <a href="feedback.html">feedback page</a> is faster.</p></div>
<section><div class="wrap form-layout">
  <form class="form-card reveal" data-api="contact" method="post">
    <fieldset class="seg"><legend>What's it about?</legend>
      <label><input type="radio" name="topic" value="general" checked><span>General question</span></label>
      <label><input type="radio" name="topic" value="partnership"><span>Partnership</span></label>
      <label><input type="radio" name="topic" value="press"><span>Press</span></label>
      <label><input type="radio" name="topic" value="privacy"><span>Privacy request</span></label>
    </fieldset>
    <div class="row">
      <div class="field"><label for="c-name">Your name</label><input id="c-name" name="name" autocomplete="name" required maxlength="100"></div>
      <div class="field"><label for="c-email">Email</label><input id="c-email" name="email" type="email" autocomplete="email" required maxlength="254"></div>
    </div>
    <div class="field"><label for="c-subject">Subject <small>(optional)</small></label><input id="c-subject" name="subject" maxlength="200"></div>
    <div class="field"><label for="c-message">Message</label><textarea id="c-message" name="message" required maxlength="5000"></textarea></div>
    {SPAM_FIELDS}
    <p class="form-note">We use your details only to reply. See the <a href="privacy.html">privacy policy</a>.</p>
    <button class="btn primary" type="submit">Send message</button>
    {STATUS}
  </form>
  <div class="side-cards">
    <div class="card reveal d1"><h3>Found a bug?</h3><p>The feedback form asks for the details we need and lets you attach a screenshot.</p><p><a href="feedback.html">Send feedback &rarr;</a></p></div>
    <div class="card reveal d2"><h3>Prefer email?</h3><p>Write to <a data-email href="contact.html">our support address (coming soon)</a>. We usually reply within two business days, in English or French.</p></div>
    <div class="card reveal d3"><h3>Privacy requests</h3><p>Choose "Privacy request" to access, correct or delete information you've sent us. We answer within 30 days.</p></div>
  </div>
</div></section>""")

# =================================================================== feedback
page("feedback.html", "Send feedback", "Report a bug, suggest a feature or ask a question about WiFiDrop.",
     f"""<div class="wrap page-hero"><h1>Send feedback</h1><p>Every bug report and idea is read, especially during the beta. Thank you for helping make WiFiDrop better.</p></div>
<section><div class="wrap form-layout">
  <form class="form-card reveal" data-api="feedback" method="post" enctype="multipart/form-data">
    <fieldset class="seg"><legend>What would you like to send?</legend>
      <label><input type="radio" name="category" value="bug" checked><span>Bug report</span></label>
      <label><input type="radio" name="category" value="idea"><span>Feature idea</span></label>
      <label><input type="radio" name="category" value="question"><span>Question</span></label>
    </fieldset>
    <div class="field"><label for="fb-message" id="fb-message-label">What went wrong?</label>
      <textarea id="fb-message" name="message" required maxlength="5000" placeholder="Describe what happened, or what you'd like"></textarea></div>
    <div class="field" data-for="bug"><label for="fb-steps">Steps to reproduce <small>(optional)</small></label>
      <textarea id="fb-steps" name="steps" maxlength="5000" placeholder="For example: 1. Open the link on my iPhone. 2. Pick 50 photos. 3. ..."></textarea></div>
    <div class="row" data-for="bug question">
      <div class="field"><label for="fb-version">WiFiDrop version</label><input id="fb-version" name="app_version" placeholder="e.g. 0.1.0" maxlength="40">
        <small>Bottom of the admin window's sidebar.</small></div>
      <div class="field"><label for="fb-windows">Windows version</label><input id="fb-windows" name="windows" placeholder="e.g. Windows 11" maxlength="60"></div>
      <div class="field"><label for="fb-device">Phone or browser</label><input id="fb-device" name="device" placeholder="e.g. iPhone 15, Safari" maxlength="100"></div>
    </div>
    <div class="field" data-for="bug"><label for="fb-file">Screenshot or log <small>(optional, up to 5 MB)</small></label>
      <input id="fb-file" name="attachment" type="file" accept=".png,.jpg,.jpeg,.webp,.gif,.txt,.log">
      <small>Check screenshots and logs before attaching. Logs list usernames, device addresses and times, but never file contents or passwords.</small></div>
    <div class="field"><label for="fb-email">Email <small>(optional, if you'd like a reply)</small></label>
      <input id="fb-email" name="email" type="email" autocomplete="email" maxlength="254"></div>
    {SPAM_FIELDS}
    <p class="form-note">We use what you send only to improve WiFiDrop and reply to you. See the <a href="privacy.html">privacy policy</a>.</p>
    <button class="btn primary" type="submit">Send feedback</button>
    {STATUS}
  </form>
  <div class="side-cards">
    <div class="card reveal d1"><h3>Good bug reports</h3><p>Say what you expected and what happened instead. The version, Windows version and phone help us reproduce it fast.</p></div>
    <div class="card reveal d2"><h3>What happens next</h3><p>We review every report within two business days. If you leave an email, we'll tell you when it's fixed or answered.</p></div>
    <div class="card reveal d3"><h3>Want early builds?</h3><p>Beta testers get new versions first and help decide what comes next.</p><p><a href="beta.html">Join the beta &rarr;</a></p></div>
  </div>
</div></section>""")

# =================================================================== beta
page("beta.html", "Join the beta", "Help test WiFiDrop: get early builds and shape what comes next.",
     f"""<div class="wrap page-hero"><h1>Join the WiFiDrop beta</h1><p>We're looking for 10 to 20 people with different PCs and phones to try new versions first and tell us what works and what doesn't.</p></div>
<section><div class="wrap form-layout">
  <form class="form-card reveal" data-api="beta" method="post">
    <div class="row">
      <div class="field"><label for="b-name">Your name</label><input id="b-name" name="name" autocomplete="name" required maxlength="100"></div>
      <div class="field"><label for="b-email">Email</label><input id="b-email" name="email" type="email" autocomplete="email" required maxlength="254"></div>
    </div>
    <div class="field"><label for="b-windows">Windows version on your PC</label><input id="b-windows" name="windows" placeholder="e.g. Windows 11 Home" maxlength="60"></div>
    <fieldset class="field"><legend class="seg-legend">Devices that would connect</legend>
      <div class="checks-inline">
        <label><input type="checkbox" name="phones" value="iphone"> iPhone or iPad</label>
        <label><input type="checkbox" name="phones" value="android"> Android</label>
        <label><input type="checkbox" name="phones" value="windows"> Windows PC</label>
        <label><input type="checkbox" name="phones" value="mac"> Mac</label>
        <label><input type="checkbox" name="phones" value="other"> Other</label>
      </div></fieldset>
    <div class="field"><label for="b-use">How would you use WiFiDrop? <small>(optional)</small></label>
      <textarea id="b-use" name="use_case" maxlength="5000" placeholder="e.g. Family photos at home, collecting assignments in class"></textarea></div>
    <label class="consent"><input type="checkbox" name="consent" value="yes" required>
      <span>Yes, email me about the WiFiDrop beta (new builds and short surveys). I can opt out at any time.</span></label>
    {SPAM_FIELDS}
    <button class="btn primary" type="submit">Join the beta</button>
    {STATUS}
  </form>
  <div class="side-cards">
    <div class="card reveal d1"><h3>What you get</h3><ul class="checks"><li>New builds before anyone else</li><li>A direct line to the developer</li><li>A free WiFiDrop Pro licence when it launches</li></ul></div>
    <div class="card reveal d2"><h3>What we ask</h3><ul class="checks"><li>Use WiFiDrop for real, at home or work</li><li>Report problems with the feedback form</li><li>Answer a short survey about Pro features</li></ul></div>
  </div>
</div></section>""")


# =================================================================== privacy
page("privacy.html", "Privacy policy", "How WiFiDrop handles personal information in the app, on this website, and for purchases and licences.",
     f"""<div class="wrap page-hero"><h1>Privacy policy</h1><p>Last updated {PRIVACY_UPDATED}. <a href="confidentialite.html" lang="fr">Version française</a></p>
  <nav class="toc" aria-label="On this page"><a href="#summary">Summary</a><a href="#app">The app</a><a href="#website">Website</a>
    <a href="#purchases">Purchases</a><a href="#where">Where data is stored</a><a href="#rights">Your rights</a><a href="#contact">Contact</a></nav></div>
<section><div class="wrap doc">
  <div class="callout summary">
    <h2>The short version</h2>
    <ul class="checks">
      <li><b>WiFiDrop runs entirely on your PC.</b> Your files, accounts and settings stay on your computer. We never receive or see them.</li>
      <li><b>No tracking.</b> No analytics, no ads, no usage data, in the app or on this website.</li>
      <li><b>Only two small checks go online:</b> a daily check for new versions, and with Pro, a weekly licence check. Both are explained below, in full.</li>
      <li><b>We keep very little:</b> what you send us through our forms, and for Pro buyers, the email and order needed for the licence.</li>
      <li><b>You're in control:</b> email <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a> and we'll show, fix or delete what we hold about you, within 30 days.</li>
    </ul>
  </div>
  <dl class="legal-meta"><dt>Who we are</dt><dd>WiFiDrop, Winnipeg, Manitoba, Canada</dd>
    <dt>Privacy contact</dt><dd>Privacy Officer, <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a></dd></dl>

  <h2 id="summary">Summary</h2>
  <p>WiFiDrop runs on your own Windows computer. Your files, user accounts and settings are stored on that computer, not with us. The app does not send us your files, file names or usage data. We collect only the limited information needed to run this website, answer you and, once Pro launches, sell and support licences.</p>
  <p>We follow Canada's <i>Personal Information Protection and Electronic Documents Act</i> (PIPEDA). Where they apply, we also respect Quebec's <i>Act respecting the protection of personal information in the private sector</i> (Law 25), the EU and UK General Data Protection Regulation (GDPR), and US state privacy laws such as the California Consumer Privacy Act (CCPA).</p>

  <h2 id="app">Information in the WiFiDrop app</h2>
  <ul>
    <li><b>Files:</b> stored in the folder the administrator chooses on their PC. Other people reach them over the local network. Files are never sent to us.</li>
    <li><b>Accounts:</b> usernames, display names and passwords (stored only as Argon2id hashes) are kept in a database on the PC, in <code>%ProgramData%\\WiFiDrop</code>.</li>
    <li><b>Activity and logs:</b> sign-ins, admin actions and device network addresses are recorded on the PC so the administrator can manage it. They stay on the PC.</li>
    <li><b>Update check:</b> about once a day, WiFiDrop downloads a small version file from our website to see whether a newer version exists. Like any web request, this shows our web host your IP address and the app version. Nothing else is sent.</li>
    <li><b>Pro licence check (Pro only):</b> when you add a Pro licence, and about once a week after that, WiFiDrop sends our licence service the licence (which includes the email address it was issued to), a random ID for that installation and the app version. This lets us limit a licence to three PCs and apply refunds. If the check can't connect, Pro keeps working. WiFiDrop Free never contacts the licence service.</li>
    <li><b>Send feedback:</b> if the administrator clicks Send feedback, WiFiDrop opens our feedback page with the app version and Windows version filled in. Nothing is sent until they submit the form.</li>
    <li><b>No telemetry:</b> the app does not send analytics, crash reports, file names, file contents or usage data.</li>
  </ul>
  <p>The person who runs WiFiDrop on their PC decides how it's used and is responsible for the information of the people they add. We have no access to it.</p>

  <h2 id="website">Information on this website</h2>
  <ul>
    <li><b>Hosting:</b> this website is hosted by GitHub Pages (GitHub, Inc.). GitHub processes basic request information, such as your IP address and browser, to deliver and protect the site, under the GitHub Privacy Statement. We don't receive these logs.</li>
    <li><b>Cookies:</b> we don't use advertising, analytics or tracking cookies. The site stores your light or dark theme choice in your own browser, which is never sent to us. On the Pricing page, the site asks our payment provider Paddle for the Pro price in your currency, so Paddle receives your IP address to work out your country. If you open the checkout to buy Pro, Paddle loads its own checkout, which may use cookies and similar technology needed for payments and fraud prevention, under <a href="https://www.paddle.com/legal/privacy" rel="noopener">Paddle's privacy policy</a>. The site blocks Paddle's optional analytics script.</li>
    <li><b>Pro waitlist:</b> if you sign up, we keep your email address and the date you gave consent, and use them only to tell you when Pro launches. Every email includes our contact details and an unsubscribe link, as Canada's Anti-Spam Legislation (CASL) requires. We delete your address when you unsubscribe or 12 months after launch, whichever comes first.</li>
    <li><b>Feedback, contact and beta forms:</b> we receive what you type and any screenshot or log you attach. We use it only to answer you, fix problems and plan WiFiDrop. Your email is optional on the feedback form. We delete form submissions after 24 months, sooner if you ask.</li>
    <li><b>Abuse protection:</b> to stop spam, our form and licence servers keep a one-way scrambled version (a salted hash) of your IP address with each submission, and count requests per hashed address for up to a day to enforce rate limits. We can't turn the hash back into your IP address.</li>
    <li><b>Emails to us:</b> if you email us, we keep your message and address to reply, for up to 24 months.</li>
  </ul>

  <h2 id="purchases">Purchases and licences</h2>
  <ul>
    <li><b>Payments:</b> purchases are handled by Paddle (Paddle.com Market Ltd), acting as merchant of record. Paddle processes your name, email, billing address and payment details under <a href="https://www.paddle.com/legal/privacy" rel="noopener">its own privacy policy</a>, and sends us your email address and order ID so we can issue your licence. We never see your card details.</li>
    <li><b>Licences:</b> our licence service stores the licence ID, the email address it was issued to, the Paddle order ID, the update period, whether it was refunded, and up to three random installation IDs with the app version and the last time each checked in. This lets licences be activated, recovered and refunded. It never receives file names or contents.</li>
    <li><b>Licence emails:</b> we send your licence, and re-send it if you ask on the <a href="licence.html">licence page</a>, through our email provider Resend, which processes your email address to deliver the message.</li>
    <li>We keep purchase records for as long as tax law requires (in Canada, generally six years).</li>
  </ul>

  <h2 id="why">Why we use information (legal bases)</h2>
  <p>We use information only for the purposes above. For visitors in the EU and UK, our legal bases are: <b>consent</b> (waitlist emails), <b>contract</b> (selling and supporting licences), <b>legal obligation</b> (tax records) and <b>legitimate interests</b> (keeping the website secure and answering messages). We don't sell or rent personal information, and we don't use it for targeted advertising.</p>

  <h2 id="where">Where information is stored</h2>
  <p>This website is hosted by GitHub Pages, on servers outside Canada (mainly in the United States). Form submissions, attachments, the waitlist and licence records are stored by our database provider, Supabase, in its Canada (Central) region. Paddle (United Kingdom, with processing in other countries) and Resend (United States) process information in other countries, where it may be accessible to local authorities under local law. When information leaves Canada or the European Economic Area, we rely on contracts with appropriate safeguards, such as the EU Standard Contractual Clauses.</p>

  <h2 id="security">Security</h2>
  <p>We collect as little as possible, use encrypted connections (HTTPS), limit access to the few people who need it and use reputable providers. If a breach creates a real risk of significant harm, we'll notify affected people and the Office of the Privacy Commissioner of Canada as the law requires.</p>

  <h2 id="rights">Your rights</h2>
  <p>Wherever you live, you can ask us to tell you what information we hold about you, correct it, delete it, or stop using it for emails. Depending on where you live, you may also have the right to data portability, to object to or restrict processing, and to withdraw consent at any time. We answer within 30 days.</p>
  <p>If you're not satisfied with our answer, you can complain to the <a href="https://www.priv.gc.ca/" rel="noopener">Office of the Privacy Commissioner of Canada</a>, the Commission d'accès à l'information du Québec, or your local data protection authority in the EU or UK.</p>

  <h2 id="children">Children</h2>
  <p>This website is not directed at children under 13, and we don't knowingly collect their information. Parents and guardians who run WiFiDrop at home decide who uses it on their own network.</p>

  <h2 id="changes">Changes to this policy</h2>
  <p>If we change this policy, we'll update the date at the top. For important changes, we'll also post a notice on this website.</p>

  <h2 id="contact">Contact</h2>
  <p>Questions or requests: email our Privacy Officer at <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a>. We answer within 30 days.</p>
</div></section>""")

# =================================================================== terms
page("terms.html", "Terms of use", "Terms for using the WiFiDrop website and the WiFiDrop software.",
     f"""<div class="wrap page-hero"><h1>Terms of use</h1><p>Last updated {UPDATED}. <a href="conditions.html" lang="fr">Version française</a></p>
  <nav class="toc" aria-label="On this page"><a href="#agreement">Agreement</a><a href="#licence">Software licence</a><a href="#use">Acceptable use</a>
    <a href="#pro">WiFiDrop Pro</a><a href="#warranty">Warranty</a><a href="#liability">Liability</a><a href="#law">Governing law</a></nav></div>
<section><div class="wrap doc">
  <div class="callout summary">
    <h2>The short version</h2>
    <ul class="checks">
      <li><b>WiFiDrop Free is free</b> for home or business use, with up to 5 accounts. No account with us needed.</li>
      <li><b>Pro is a one-time purchase</b> for up to 3 of your PCs, with a year of feature updates. It keeps working after that, offline too.</li>
      <li><b>Your files are yours.</b> WiFiDrop runs on your PC; we don't host, see or control anything you store.</li>
      <li><b>30-day money-back guarantee</b> on Pro, no questions asked. See the <a href="refunds.html">refund policy</a>.</li>
      <li><b>Please be fair:</b> don't resell WiFiDrop, share your Pro licence publicly, or use it for anything illegal.</li>
    </ul>
    <p>The full terms below are what legally applies. If anything is unclear, email <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a>.</p>
  </div>

  <h2 id="agreement">1. Agreement</h2>
  <p>These terms apply to the WiFiDrop website and the WiFiDrop software (together, "WiFiDrop"), provided by WiFiDrop, based in Winnipeg, Manitoba, Canada ("we" or "us"). By using WiFiDrop, you agree to these terms. If you use WiFiDrop for an organization, you confirm you can accept these terms for it.</p>

  <h2 id="licence">2. Software licence</h2>
  <p>We grant you a personal, non-exclusive, non-transferable licence to install and use WiFiDrop Free on computers you own or control, at no charge, for personal or business use. You may not:</p>
  <ul>
    <li>sell, rent, sublicense or redistribute WiFiDrop, or modified copies of it, without our written permission;</li>
    <li>remove copyright or licence notices; or</li>
    <li>get around licence checks or features reserved for WiFiDrop Pro.</li>
  </ul>
  <p>WiFiDrop includes open-source components that are licensed under their own terms. A list is included with the software. Nothing in these terms limits your rights under those licences.</p>

  <h2 id="beta">3. Beta software</h2>
  <p>WiFiDrop is currently in beta. It may contain bugs, and features may change or be removed. Keep your own backups of anything important.</p>

  <h2 id="use">4. Your responsibilities and acceptable use</h2>
  <ul>
    <li>You control the computer WiFiDrop runs on, the accounts you create and the files stored on it. You're responsible for the people you give access to and for following the laws that apply to you, including privacy laws for other people's information.</li>
    <li>Only store and share files you have the right to share. Don't use WiFiDrop for anything illegal, including sharing content that infringes someone else's rights, exploits children, or harasses or threatens anyone.</li>
    <li>Use WiFiDrop on networks you trust, and keep HTTPS turned on for shared or public networks.</li>
    <li>Don't attempt to disrupt, overload or break into our website or licence service.</li>
  </ul>
  <p>Because WiFiDrop runs on your computer, we do not host, see or control your files.</p>

  <h2 id="pro">5. WiFiDrop Pro</h2>
  <p>Purchases are handled by our reseller Paddle, acting as merchant of record, under <a href="https://www.paddle.com/legal/checkout-buyer-terms" rel="noopener">Paddle's buyer terms</a>. A Pro licence is for your own use on up to three computers at a time, and includes feature updates for one year from purchase; after that, Pro features keep working in the versions released during that year. WiFiDrop checks the licence online when you add it and about once a week, and keeps working offline. If a licence is refunded or charged back, Pro features become read-only, and your files, accounts and Free features keep working. Refunds are covered by our <a href="refunds.html">refund policy</a>.</p>

  <h2 id="ip">6. Our intellectual property</h2>
  <p>WiFiDrop, its name, logo and website content belong to us or our licensors. These terms don't give you any rights to them other than the licence above. If you send us feedback, we may use it to improve WiFiDrop without owing you anything.</p>

  <h2 id="warranty">7. No warranty</h2>
  <p>To the extent permitted by law, WiFiDrop is provided "as is" and "as available", without warranties of any kind, including fitness for a particular purpose and non-infringement. We don't promise that WiFiDrop will be error-free or that files will never be lost.</p>

  <h2 id="liability">8. Limitation of liability</h2>
  <p>To the extent permitted by law, we're not liable for any indirect, incidental, special or consequential damages, or for lost data, profits or revenue, arising from your use of WiFiDrop. Our total liability for any claim is limited to the amount you paid us for WiFiDrop in the 12 months before the claim, or CAD $20 if you paid nothing.</p>
  <p><b>Your consumer rights:</b> nothing in these terms limits rights you have under consumer protection laws that can't be waived, such as Quebec's <i>Consumer Protection Act</i>, or the laws of the country where you live.</p>

  <h2 id="termination">9. Ending these terms</h2>
  <p>You can stop using WiFiDrop at any time by uninstalling it. We may end your licence if you seriously break these terms. Sections 6 to 11 continue to apply after that.</p>

  <h2 id="law">10. Governing law</h2>
  <p>These terms are governed by the laws of Manitoba and the federal laws of Canada that apply there. The courts of Manitoba have jurisdiction, unless the consumer laws of your country give you the right to bring a claim in your local courts.</p>

  <h2 id="changes">11. Changes</h2>
  <p>We may update these terms. We'll change the date at the top and, for important changes, post a notice on this website. Continuing to use WiFiDrop after a change means you accept the new terms.</p>

  <h2 id="contact">Contact</h2>
  <p>Questions about these terms? Use the <a href="contact.html">contact page</a>.</p>
</div></section>""")

# =================================================================== refunds
page("refunds.html", "Refund policy", "Refunds for WiFiDrop Pro.",
     f"""<div class="wrap page-hero"><h1>Refund policy</h1><p>Last updated {UPDATED}. <a href="remboursements.html" lang="fr">Version française</a></p></div>
<section><div class="wrap doc">
  <div class="callout summary">
    <h2>The short version</h2>
    <ul class="checks">
      <li><b>Full refund within 30 days</b> of buying WiFiDrop Pro. No reason needed, no forms, no hassle.</li>
      <li><b>Just email <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a></b> from the address you bought with.</li>
      <li><b>Nothing of yours is lost:</b> your files, accounts and every Free feature keep working.</li>
    </ul>
  </div>

  <h2 id="guarantee">30-day money-back guarantee</h2>
  <p>If WiFiDrop Pro isn't right for you, for any reason, you can have a full refund within 30 days of purchase. You don't need to explain why.</p>

  <h2 id="how">How to get your money back</h2>
  <ol>
    <li>Email <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a> from the address you used to buy Pro. Your order number (it starts with <code>txn_</code> and is on your receipt) helps, but your email address is enough.</li>
    <li>We process refund requests within 2 business days. Our reseller Paddle sends the money back to your original payment method; banks usually take 5 to 10 business days to show it.</li>
  </ol>
  <p>You can also ask Paddle directly through the link in your purchase receipt, or at <a href="https://paddle.net" rel="noopener">paddle.net</a>.</p>
  <p><b>After 30 days?</b> If something is wrong with WiFiDrop Pro, contact us anyway. We'll look at every request fairly.</p>

  <h2 id="after">What happens after a refund</h2>
  <p>Your Pro licence is cancelled, and Pro features turn read-only the next time WiFiDrop checks your licence. Your files, accounts and every WiFiDrop Free feature keep working.</p>

  <h2 id="law">Your legal rights</h2>
  <p>This policy is in addition to any rights you have under the consumer laws where you live.</p>
</div></section>""")

# =================================================================== French legal pages (drafts for review)
UPDATED_FR = "17 octobre 2026"
PRIVACY_UPDATED_FR = "23 octobre 2026"
EMAIL_LINK = '<a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a>'

page("confidentialite.html", "Politique de confidentialité",
     "Comment WiFiDrop traite les renseignements personnels dans l'application, sur ce site Web et pour les achats et licences.",
     f"""<div class="wrap page-hero"><h1>Politique de confidentialité</h1><p>Dernière mise à jour : {PRIVACY_UPDATED_FR}. <a href="privacy.html" lang="en">English version</a></p>
  <nav class="toc" aria-label="Sur cette page"><a href="#resume">Résumé</a><a href="#application">L'application</a><a href="#site">Site Web</a>
    <a href="#achats">Achats</a><a href="#stockage">Lieu de stockage</a><a href="#droits">Vos droits</a><a href="#contact">Contact</a></nav></div>
<section><div class="wrap doc">
  <div class="callout summary">
    <h2>En bref</h2>
    <ul class="checks">
      <li><b>WiFiDrop fonctionne entièrement sur votre ordinateur.</b> Vos fichiers, comptes et paramètres restent chez vous. Nous ne les recevons ni ne les voyons jamais.</li>
      <li><b>Aucun suivi.</b> Ni statistiques, ni publicité, ni données d'utilisation, dans l'application comme sur ce site.</li>
      <li><b>Seulement deux petites vérifications en ligne :</b> une recherche quotidienne de mises à jour et, avec Pro, une vérification hebdomadaire de la licence. Toutes deux sont expliquées en détail ci-dessous.</li>
      <li><b>Nous conservons très peu :</b> ce que vous nous envoyez par nos formulaires et, pour les acheteurs de Pro, le courriel et la commande nécessaires à la licence.</li>
      <li><b>Vous gardez le contrôle :</b> écrivez à {EMAIL_LINK} et nous vous montrerons, corrigerons ou supprimerons ce que nous détenons à votre sujet, dans un délai de 30 jours.</li>
    </ul>
  </div>
  <dl class="legal-meta"><dt>Qui nous sommes</dt><dd>WiFiDrop, Winnipeg (Manitoba), Canada</dd>
    <dt>Responsable de la protection des renseignements personnels</dt><dd>Responsable de la protection de la vie privée, {EMAIL_LINK}</dd></dl>

  <h2 id="resume">Résumé</h2>
  <p>WiFiDrop fonctionne sur votre propre ordinateur Windows. Vos fichiers, vos comptes d'utilisateur et vos paramètres sont stockés sur cet ordinateur, et non chez nous. L'application ne nous envoie ni vos fichiers, ni leurs noms, ni de données d'utilisation. Nous recueillons seulement les renseignements limités nécessaires pour exploiter ce site, vous répondre, et vendre et soutenir les licences.</p>
  <p>Nous respectons la <i>Loi sur la protection des renseignements personnels et les documents électroniques</i> (LPRPDE) du Canada. Lorsqu'elles s'appliquent, nous respectons aussi la <i>Loi sur la protection des renseignements personnels dans le secteur privé</i> du Québec (Loi 25), le Règlement général sur la protection des données (RGPD) de l'UE et du Royaume-Uni, ainsi que les lois des États américains sur la vie privée comme la California Consumer Privacy Act (CCPA).</p>

  <h2 id="application">Renseignements dans l'application WiFiDrop</h2>
  <ul>
    <li><b>Fichiers :</b> stockés dans le dossier choisi par l'administrateur sur son ordinateur. Les autres personnes y accèdent par le réseau local. Les fichiers ne nous sont jamais envoyés.</li>
    <li><b>Comptes :</b> les noms d'utilisateur, noms affichés et mots de passe (conservés uniquement sous forme de hachages Argon2id) sont gardés dans une base de données sur l'ordinateur, dans <code>%ProgramData%\\WiFiDrop</code>.</li>
    <li><b>Activité et journaux :</b> les connexions, les actions d'administration et les adresses réseau des appareils sont enregistrées sur l'ordinateur pour que l'administrateur puisse le gérer. Elles restent sur l'ordinateur.</li>
    <li><b>Recherche de mises à jour :</b> environ une fois par jour, WiFiDrop télécharge un petit fichier de version depuis notre site pour savoir si une nouvelle version existe. Comme toute requête Web, cela révèle à notre hébergeur votre adresse IP et la version de l'application. Rien d'autre n'est envoyé.</li>
    <li><b>Vérification de la licence Pro (Pro seulement) :</b> lorsque vous ajoutez une licence Pro, puis environ une fois par semaine, WiFiDrop envoie à notre service de licences la licence (qui comprend l'adresse courriel à laquelle elle a été émise), un identifiant aléatoire propre à cette installation et la version de l'application. Cela nous permet de limiter une licence à trois ordinateurs et d'appliquer les remboursements. Si la vérification ne peut pas se connecter, Pro continue de fonctionner. WiFiDrop Free ne communique jamais avec le service de licences.</li>
    <li><b>Envoyer des commentaires :</b> si l'administrateur clique sur « Send feedback », WiFiDrop ouvre notre page de commentaires en y inscrivant la version de l'application et de Windows. Rien n'est envoyé avant que le formulaire soit soumis.</li>
    <li><b>Aucune télémétrie :</b> l'application n'envoie ni statistiques, ni rapports de plantage, ni noms ou contenus de fichiers, ni données d'utilisation.</li>
  </ul>
  <p>La personne qui exploite WiFiDrop sur son ordinateur décide de son utilisation et est responsable des renseignements des personnes qu'elle ajoute. Nous n'y avons pas accès.</p>

  <h2 id="site">Renseignements sur ce site Web</h2>
  <ul>
    <li><b>Hébergement :</b> ce site est hébergé par GitHub Pages (GitHub, Inc.). GitHub traite des renseignements de base sur les requêtes, comme votre adresse IP et votre navigateur, pour livrer et protéger le site, conformément à la déclaration de confidentialité de GitHub. Nous ne recevons pas ces journaux.</li>
    <li><b>Témoins (cookies) :</b> nous n'utilisons aucun témoin publicitaire, analytique ou de suivi. Le site enregistre votre choix de thème clair ou sombre dans votre propre navigateur, et ce choix ne nous est jamais envoyé. Sur la page Tarifs, le site demande à notre fournisseur de paiement Paddle le prix de Pro dans votre devise; Paddle reçoit donc votre adresse IP pour déterminer votre pays. Le site bloque le script d'analyse facultatif de Paddle. Si vous ouvrez la caisse pour acheter Pro, Paddle charge sa propre caisse, qui peut utiliser des témoins et des technologies semblables nécessaires aux paiements et à la prévention de la fraude, conformément à la <a href="https://www.paddle.com/legal/privacy" rel="noopener">politique de confidentialité de Paddle</a>.</li>
    <li><b>Liste d'attente Pro :</b> si vous vous inscrivez, nous conservons votre adresse courriel et la date de votre consentement, et nous les utilisons seulement pour vous annoncer le lancement de Pro. Chaque courriel comprend nos coordonnées et un lien de désabonnement, comme l'exige la Loi canadienne anti-pourriel (LCAP). Nous supprimons votre adresse lorsque vous vous désabonnez ou 12 mois après le lancement, selon la première éventualité.</li>
    <li><b>Formulaires de commentaires, de contact et de bêta :</b> nous recevons ce que vous écrivez et toute capture d'écran ou tout journal joint. Nous les utilisons seulement pour vous répondre, corriger des problèmes et planifier WiFiDrop. Votre courriel est facultatif dans le formulaire de commentaires. Nous supprimons les soumissions après 24 mois, ou plus tôt si vous le demandez.</li>
    <li><b>Protection contre les abus :</b> pour bloquer le pourriel, nos serveurs de formulaires et de licences conservent une version brouillée à sens unique (un hachage salé) de votre adresse IP avec chaque soumission, et comptent les requêtes par adresse hachée pendant au plus une journée afin d'appliquer des limites de débit. Nous ne pouvons pas retrouver votre adresse IP à partir du hachage.</li>
    <li><b>Courriels qui nous sont adressés :</b> si vous nous écrivez, nous conservons votre message et votre adresse pour vous répondre, pendant au plus 24 mois.</li>
  </ul>

  <h2 id="achats">Achats et licences</h2>
  <ul>
    <li><b>Paiements :</b> les achats sont traités par Paddle (Paddle.com Market Ltd), qui agit à titre de commerçant officiel (« merchant of record »). Paddle traite votre nom, votre courriel, votre adresse de facturation et vos renseignements de paiement conformément à <a href="https://www.paddle.com/legal/privacy" rel="noopener">sa propre politique de confidentialité</a>, et nous transmet votre adresse courriel et le numéro de commande afin que nous puissions émettre votre licence. Nous ne voyons jamais les détails de votre carte.</li>
    <li><b>Licences :</b> notre service de licences conserve l'identifiant de la licence, l'adresse courriel à laquelle elle a été émise, le numéro de commande Paddle, la période de mises à jour, l'indication d'un éventuel remboursement, et jusqu'à trois identifiants d'installation aléatoires avec la version de l'application et la date de la dernière vérification de chacun. Cela permet d'activer, de récupérer et de rembourser les licences. Il ne reçoit jamais de noms ni de contenus de fichiers.</li>
    <li><b>Courriels de licence :</b> nous vous envoyons votre licence, et la renvoyons si vous le demandez sur la <a href="licence.html">page des licences</a>, par l'intermédiaire de notre fournisseur de courriel Resend, qui traite votre adresse courriel pour livrer le message.</li>
    <li>Nous conservons les dossiers d'achat aussi longtemps que l'exigent les lois fiscales (au Canada, généralement six ans).</li>
  </ul>

  <h2 id="fondements">Pourquoi nous utilisons les renseignements (fondements juridiques)</h2>
  <p>Nous utilisons les renseignements uniquement aux fins décrites ci-dessus. Pour les visiteurs de l'UE et du Royaume-Uni, nos fondements juridiques sont : le <b>consentement</b> (courriels de la liste d'attente), le <b>contrat</b> (vente et soutien des licences), l'<b>obligation légale</b> (dossiers fiscaux) et l'<b>intérêt légitime</b> (sécurité du site et réponses aux messages). Nous ne vendons ni ne louons de renseignements personnels, et nous ne les utilisons pas pour de la publicité ciblée.</p>

  <h2 id="stockage">Où les renseignements sont stockés</h2>
  <p>Ce site est hébergé par GitHub Pages, sur des serveurs situés à l'extérieur du Canada (principalement aux États-Unis). Les soumissions de formulaires, les pièces jointes, la liste d'attente et les dossiers de licences sont stockés par notre fournisseur de base de données, Supabase, dans sa région Canada (Centre). Paddle (Royaume-Uni, avec traitement dans d'autres pays) et Resend (États-Unis) traitent des renseignements dans d'autres pays, où ils peuvent être accessibles aux autorités locales en vertu des lois locales. Lorsque des renseignements quittent le Canada ou l'Espace économique européen, nous nous appuyons sur des contrats comportant des garanties appropriées, comme les clauses contractuelles types de l'UE.</p>

  <h2 id="securite">Sécurité</h2>
  <p>Nous recueillons le moins de renseignements possible, utilisons des connexions chiffrées (HTTPS), limitons l'accès aux quelques personnes qui en ont besoin et faisons appel à des fournisseurs reconnus. Si un incident de confidentialité présente un risque réel de préjudice grave, nous en aviserons les personnes concernées et le Commissariat à la protection de la vie privée du Canada, comme l'exige la loi.</p>

  <h2 id="droits">Vos droits</h2>
  <p>Où que vous habitiez, vous pouvez nous demander quels renseignements nous détenons à votre sujet, de les corriger, de les supprimer ou de cesser de les utiliser pour des courriels. Selon votre lieu de résidence, vous pouvez aussi avoir droit à la portabilité des données, vous opposer au traitement ou le limiter, et retirer votre consentement en tout temps. Nous répondons dans un délai de 30 jours.</p>
  <p>Si notre réponse ne vous satisfait pas, vous pouvez porter plainte auprès du <a href="https://www.priv.gc.ca/fr/" rel="noopener">Commissariat à la protection de la vie privée du Canada</a>, de la Commission d'accès à l'information du Québec ou de l'autorité de protection des données de votre pays dans l'UE ou au Royaume-Uni.</p>

  <h2 id="enfants">Enfants</h2>
  <p>Ce site ne s'adresse pas aux enfants de moins de 13 ans, et nous ne recueillons pas sciemment leurs renseignements. Les parents et tuteurs qui utilisent WiFiDrop à la maison décident qui l'utilise sur leur propre réseau.</p>

  <h2 id="modifications">Modifications de la présente politique</h2>
  <p>Si nous modifions cette politique, nous mettrons à jour la date en haut de la page. Pour les changements importants, nous publierons aussi un avis sur ce site.</p>

  <h2 id="contact">Contact</h2>
  <p>Questions ou demandes : écrivez à notre responsable de la protection de la vie privée à {EMAIL_LINK}. Nous répondons dans un délai de 30 jours.</p>
</div></section>""", lang="fr-CA")

page("conditions.html", "Conditions d'utilisation", "Conditions d'utilisation du site Web et du logiciel WiFiDrop.",
     f"""<div class="wrap page-hero"><h1>Conditions d'utilisation</h1><p>Dernière mise à jour : {UPDATED_FR}. <a href="terms.html" lang="en">English version</a></p>
  <nav class="toc" aria-label="Sur cette page"><a href="#entente">Entente</a><a href="#licence">Licence</a><a href="#utilisation">Utilisation acceptable</a>
    <a href="#pro">WiFiDrop Pro</a><a href="#garantie">Garantie</a><a href="#responsabilite">Responsabilité</a><a href="#droit">Droit applicable</a></nav></div>
<section><div class="wrap doc">
  <div class="callout summary">
    <h2>En bref</h2>
    <ul class="checks">
      <li><b>WiFiDrop Free est gratuit</b> pour un usage personnel ou professionnel, avec jusqu'à 5 comptes. Aucun compte chez nous n'est nécessaire.</li>
      <li><b>Pro s'achète une seule fois</b> pour jusqu'à 3 de vos ordinateurs, avec un an de mises à jour. Il continue de fonctionner ensuite, même hors ligne.</li>
      <li><b>Vos fichiers vous appartiennent.</b> WiFiDrop fonctionne sur votre ordinateur; nous n'hébergeons, ne voyons ni ne contrôlons rien de ce que vous stockez.</li>
      <li><b>Satisfait ou remboursé pendant 30 jours</b> pour Pro, sans questions. Voir la <a href="remboursements.html">politique de remboursement</a>.</li>
      <li><b>Soyez réglo :</b> ne revendez pas WiFiDrop, ne partagez pas votre licence Pro publiquement et ne l'utilisez pas à des fins illégales.</li>
    </ul>
    <p>Les conditions complètes ci-dessous sont celles qui s'appliquent juridiquement. Pour toute question, écrivez à {EMAIL_LINK}.</p>
  </div>

  <h2 id="entente">1. Entente</h2>
  <p>Les présentes conditions s'appliquent au site Web WiFiDrop et au logiciel WiFiDrop (ensemble, « WiFiDrop »), fournis par WiFiDrop, établi à Winnipeg (Manitoba), Canada (« nous »). En utilisant WiFiDrop, vous acceptez ces conditions. Si vous utilisez WiFiDrop pour une organisation, vous confirmez que vous pouvez accepter ces conditions en son nom.</p>

  <h2 id="licence">2. Licence du logiciel</h2>
  <p>Nous vous accordons une licence personnelle, non exclusive et non transférable vous permettant d'installer et d'utiliser WiFiDrop Free sur des ordinateurs que vous possédez ou contrôlez, sans frais, à des fins personnelles ou professionnelles. Vous ne pouvez pas :</p>
  <ul>
    <li>vendre, louer, sous-licencier ou redistribuer WiFiDrop, ou des copies modifiées de celui-ci, sans notre autorisation écrite;</li>
    <li>retirer les avis de droits d'auteur ou de licence;</li>
    <li>contourner les vérifications de licence ou les fonctions réservées à WiFiDrop Pro.</li>
  </ul>
  <p>WiFiDrop comprend des composants libres (open source) visés par leurs propres licences. La liste est fournie avec le logiciel. Rien dans les présentes conditions ne limite vos droits en vertu de ces licences.</p>

  <h2 id="beta">3. Logiciel en version bêta</h2>
  <p>WiFiDrop est actuellement en version bêta. Il peut contenir des bogues, et des fonctions peuvent changer ou disparaître. Faites vos propres copies de sauvegarde de tout ce qui est important.</p>

  <h2 id="utilisation">4. Vos responsabilités et utilisation acceptable</h2>
  <ul>
    <li>Vous contrôlez l'ordinateur sur lequel WiFiDrop fonctionne, les comptes que vous créez et les fichiers qui y sont stockés. Vous êtes responsable des personnes à qui vous donnez accès et du respect des lois qui s'appliquent à vous, y compris les lois sur la protection des renseignements personnels d'autrui.</li>
    <li>Ne stockez et ne partagez que des fichiers que vous avez le droit de partager. N'utilisez pas WiFiDrop à des fins illégales, notamment pour partager du contenu qui porte atteinte aux droits d'autrui, exploite des enfants, ou harcèle ou menace quiconque.</li>
    <li>Utilisez WiFiDrop sur des réseaux de confiance, et gardez HTTPS activé sur les réseaux partagés ou publics.</li>
    <li>N'essayez pas de perturber, de surcharger ou de pirater notre site Web ou notre service de licences.</li>
  </ul>
  <p>Comme WiFiDrop fonctionne sur votre ordinateur, nous n'hébergeons pas vos fichiers, ne les voyons pas et ne les contrôlons pas.</p>

  <h2 id="pro">5. WiFiDrop Pro</h2>
  <p>Les achats sont traités par notre revendeur Paddle, qui agit à titre de commerçant officiel, conformément aux <a href="https://www.paddle.com/legal/checkout-buyer-terms" rel="noopener">conditions d'achat de Paddle</a>. Une licence Pro est destinée à votre propre usage sur au plus trois ordinateurs à la fois et comprend les mises à jour de fonctions pendant un an à compter de l'achat; par la suite, les fonctions Pro continuent de fonctionner dans les versions publiées pendant cette année. WiFiDrop vérifie la licence en ligne lorsque vous l'ajoutez, puis environ une fois par semaine, et continue de fonctionner hors ligne. Si une licence est remboursée ou fait l'objet d'une rétrofacturation, les fonctions Pro passent en lecture seule, et vos fichiers, vos comptes et les fonctions Free continuent de fonctionner. Les remboursements sont régis par notre <a href="remboursements.html">politique de remboursement</a>.</p>

  <h2 id="pi">6. Notre propriété intellectuelle</h2>
  <p>WiFiDrop, son nom, son logo et le contenu de son site nous appartiennent ou appartiennent à nos concédants de licence. Les présentes conditions ne vous accordent aucun droit sur ceux-ci autre que la licence ci-dessus. Si vous nous faites part de commentaires, nous pouvons les utiliser pour améliorer WiFiDrop sans vous devoir quoi que ce soit.</p>

  <h2 id="garantie">7. Absence de garantie</h2>
  <p>Dans la mesure permise par la loi, WiFiDrop est fourni « tel quel » et « selon la disponibilité », sans garantie d'aucune sorte, notamment d'adaptation à un usage particulier et d'absence de contrefaçon. Nous ne promettons pas que WiFiDrop sera exempt d'erreurs ni que des fichiers ne seront jamais perdus.</p>

  <h2 id="responsabilite">8. Limitation de responsabilité</h2>
  <p>Dans la mesure permise par la loi, nous ne sommes pas responsables des dommages indirects, accessoires, spéciaux ou consécutifs, ni de la perte de données, de profits ou de revenus, découlant de votre utilisation de WiFiDrop. Notre responsabilité totale pour toute réclamation est limitée au montant que vous nous avez payé pour WiFiDrop au cours des 12 mois précédant la réclamation, ou à 20 $ CA si vous n'avez rien payé.</p>
  <p><b>Vos droits de consommateur :</b> rien dans les présentes conditions ne limite les droits que vous confèrent les lois sur la protection du consommateur auxquelles on ne peut renoncer, comme la <i>Loi sur la protection du consommateur</i> du Québec, ou les lois du pays où vous habitez.</p>

  <h2 id="fin">9. Fin des présentes conditions</h2>
  <p>Vous pouvez cesser d'utiliser WiFiDrop en tout temps en le désinstallant. Nous pouvons mettre fin à votre licence si vous enfreignez gravement les présentes conditions. Les articles 6 à 11 continuent de s'appliquer par la suite.</p>

  <h2 id="droit">10. Droit applicable</h2>
  <p>Les présentes conditions sont régies par les lois du Manitoba et les lois fédérales du Canada qui s'y appliquent. Les tribunaux du Manitoba sont compétents, sauf si les lois sur la protection du consommateur de votre pays vous donnent le droit d'intenter un recours devant les tribunaux de votre lieu de résidence.</p>

  <h2 id="changements">11. Modifications</h2>
  <p>Nous pouvons modifier les présentes conditions. Nous changerons alors la date en haut de la page et, pour les changements importants, publierons un avis sur ce site. Si vous continuez d'utiliser WiFiDrop après une modification, vous acceptez les nouvelles conditions.</p>

  <h2 id="contact">Contact</h2>
  <p>Des questions sur ces conditions? Écrivez-nous à {EMAIL_LINK} ou utilisez la <a href="contact.html">page de contact</a>.</p>
</div></section>""", lang="fr-CA")

page("remboursements.html", "Politique de remboursement", "Remboursements de WiFiDrop Pro.",
     f"""<div class="wrap page-hero"><h1>Politique de remboursement</h1><p>Dernière mise à jour : {UPDATED_FR}. <a href="refunds.html" lang="en">English version</a></p></div>
<section><div class="wrap doc">
  <div class="callout summary">
    <h2>En bref</h2>
    <ul class="checks">
      <li><b>Remboursement complet dans les 30 jours</b> suivant l'achat de WiFiDrop Pro. Sans raison à donner, sans formulaire, sans tracas.</li>
      <li><b>Écrivez simplement à {EMAIL_LINK}</b> à partir de l'adresse utilisée pour l'achat.</li>
      <li><b>Vous ne perdez rien :</b> vos fichiers, vos comptes et toutes les fonctions Free continuent de fonctionner.</li>
    </ul>
  </div>

  <h2 id="garantie">Satisfait ou remboursé pendant 30 jours</h2>
  <p>Si WiFiDrop Pro ne vous convient pas, pour quelque raison que ce soit, vous pouvez obtenir un remboursement complet dans les 30 jours suivant l'achat. Vous n'avez pas à vous justifier.</p>

  <h2 id="demande">Comment obtenir votre remboursement</h2>
  <ol>
    <li>Écrivez à {EMAIL_LINK} à partir de l'adresse utilisée pour acheter Pro. Votre numéro de commande (il commence par <code>txn_</code> et figure sur votre reçu) est utile, mais votre adresse courriel suffit.</li>
    <li>Nous traitons les demandes de remboursement dans un délai de 2 jours ouvrables. Notre revendeur Paddle rembourse votre mode de paiement d'origine; les banques mettent généralement de 5 à 10 jours ouvrables à l'afficher.</li>
  </ol>
  <p>Vous pouvez aussi vous adresser directement à Paddle au moyen du lien figurant sur votre reçu, ou à <a href="https://paddle.net" rel="noopener">paddle.net</a>.</p>
  <p><b>Après 30 jours?</b> Si WiFiDrop Pro pose problème, écrivez-nous quand même. Nous examinerons chaque demande équitablement.</p>

  <h2 id="apres">Après un remboursement</h2>
  <p>Votre licence Pro est annulée, et les fonctions Pro passent en lecture seule à la prochaine vérification de la licence par WiFiDrop. Vos fichiers, vos comptes et toutes les fonctions de WiFiDrop Free continuent de fonctionner.</p>

  <h2 id="droits">Vos droits</h2>
  <p>Cette politique s'ajoute aux droits que vous confèrent les lois sur la protection du consommateur du lieu où vous habitez.</p>
</div></section>""", lang="fr-CA")

# =================================================================== thank you (after checkout)
page("thanks.html", "Thank you", "Your WiFiDrop Pro licence is on its way.",
     f"""<div class="wrap page-hero center"><h1>Thank you for buying WiFiDrop Pro!</h1>
  <p>Your licence is on its way to your email. Here's how to turn on Pro.</p></div>
<section>
  <div class="wrap">
    <div class="steps">
      <div class="card"><h3>Check your email</h3><p>Look for <b>"Your WiFiDrop Pro licence"</b> from <b>licences@wifidrop.ca</b>. It usually arrives within a minute. Check spam too.</p></div>
      <div class="card"><h3>Open WiFiDrop</h3><p>Double-click the WiFiDrop icon in the system tray, then go to <b>Licence</b>.</p></div>
      <div class="card"><h3>Paste and activate</h3><p>Paste the whole licence, including the BEGIN and END lines, and press <b>Activate Pro</b>. Done.</p></div>
    </div>
    <div class="cta">
      <a class="btn primary" href="download.html">{DL}Don't have WiFiDrop yet? Download it</a>
      <a class="btn" href="licence.html">Didn't get the email?</a>
    </div>
    <p class="muted center-note">Your receipt comes separately from our reseller, Paddle. Questions or a refund within 30 days: <a href="mailto:support@wifidrop.ca">support@wifidrop.ca</a>.</p>
  </div>
</section>""")

# =================================================================== licence help
page("licence.html", "Your licence", "Re-send your WiFiDrop Pro licence, add it to WiFiDrop, or move it to another PC.",
     f"""<div class="wrap page-hero"><h1>Your WiFiDrop Pro licence</h1><p>Get your licence again, add it to WiFiDrop, or move it to a new PC.</p></div>
<section><div class="wrap slim">
  <form class="form-card" data-api="resend" data-api-base="licence" method="post">
    <h2>Re-send my licence</h2>
    <p>Enter the email address you used to buy WiFiDrop Pro. We'll email every licence bought with it.</p>
    <label for="rs-email">Email</label>
    <input id="rs-email" name="email" type="email" autocomplete="email" required>
    {SPAM_FIELDS}
    <button class="btn primary" type="submit">Email my licence</button>
    {STATUS}
  </form>
  <div class="doc">
    <h2>Add your licence to WiFiDrop</h2>
    <ol><li>Open the WiFiDrop window on your PC (double-click the tray icon).</li>
      <li>Go to <b>Licence</b>, paste the whole licence including the BEGIN and END lines, and press <b>Activate Pro</b>.</li></ol>
    <h2>Move Pro to a new PC</h2>
    <p>A licence works on up to 3 PCs. On the PC you no longer use, open <b>Licence</b> and press <b>Remove from this PC</b>, then add the licence on the new one. If the old PC is gone, <a href="contact.html">contact us</a> with your licence ID and we'll free it up.</p>
    <h2>Refunds</h2>
    <p>After a refund, Pro features turn read-only the next time WiFiDrop checks the licence. Your files, accounts and Free features keep working. See the <a href="refunds.html">refund policy</a>.</p>
  </div>
</div></section>""")

# =================================================================== unsubscribe
page("unsubscribe.html", "Unsubscribe", "Stop WiFiDrop launch emails.",
     f"""<div class="wrap page-hero"><h1>Unsubscribe</h1><p>Stop getting WiFiDrop Pro launch emails.</p></div>
<section><div class="wrap slim">
  <form class="form-card" data-api="unsubscribe" method="post">
    <input type="hidden" name="token" value="">
    <p>Press the button and we won't email you again. Your address is kept only as a record that you unsubscribed, and you can ask us to delete it on the <a href="contact.html">contact page</a>.</p>
    <button class="btn primary" type="submit">Unsubscribe</button>
    {STATUS}
  </form>
</div></section>""")

# =================================================================== 404
page("404.html", "Page not found", "This page doesn't exist.",
     """<div class="wrap page-hero"><h1>Page not found</h1><p>That page doesn't exist. Try the <a href="index.html">home page</a> or the <a href="guide.html">setup guide</a>.</p></div>""")

print("pages written:", sorted(p.name for p in SITE.glob("*.html")))
