# WiFiDrop

WiFiDrop is a LAN file server for Windows. The PC running it gets a desktop **admin window** and a tray icon. People on the same Wi-Fi open a **web page** on their phone or computer, sign in, and manage their files.

## Try it

1. Run `build/out/WiFiDrop/WiFiDrop.exe` (or `.venv/Scripts/python -m app` from source).
2. The **WiFiDrop Admin** window opens. The first time, it asks where to save uploaded files (type a path or click **Browse…**). You can change it later with **Dashboard → Storage → Change folder**; WiFiDrop moves the existing files for you.
3. Go to **Users → Add user** and create an account.
4. Optional: **Shared folders → New shared folder**, then give users View, Upload or Manage access.
5. On a phone on the same Wi-Fi, scan the QR code on the Dashboard (or type the link), then sign in. The link is **https://**. The first time, the phone warns that the connection isn't private, because WiFiDrop made its own certificate. On iPhone tap **Show Details → visit this website**; on Android **Advanced → Proceed**. The Dashboard shows the certificate fingerprint so you can compare. Anyone who types just `http://<PC address>` gets a help page with a button to the secure link. On a trusted home network you can turn HTTPS off in the Dashboard.

Closing the admin window keeps WiFiDrop running in the tray. Click the tray icon to reopen it. **Quit WiFiDrop** (tray menu or the window's sidebar) stops everything.

## What works

| Admin window (this PC) | User web page (any device) |
| --- | --- |
| Start/stop the web server, link + QR code | Sign in, forced password change on first sign-in |
| Allow/pause uploads and downloads for everyone | Private "My files" plus shared folders they're added to |
| Add, edit, suspend, enable, delete users, reset passwords | Upload many files at once: 8 MB chunks, 3 in parallel, auto-retry and resume |
| Storage limits per user and per shared folder | Download, rename, new folder, delete to Trash, restore, delete forever |
| Shared folders with per-user View / Upload / Manage | Drag and drop on desktop, iPhone photo hint |
| See signed-in devices and uploads, sign out or cancel them | Live banner when the admin pauses uploads or downloads |
| Browse, download, rename, delete any user's files | Picture previews, full-screen viewer for photos and videos |
| Activity log of sign-ins and admin actions | Search across your files and every shared folder you're in |
| Picture previews and viewer in Browse files | Live updates: lists refresh by themselves |
| Backups and restore; licence page | Works at phone width, light and dark mode |

**Free and Pro:** Free allows 5 accounts. Pro (CA$29.99, one-time, licence checked by `supabase/functions/licence`) unlocks unlimited accounts and scheduled backups.

**Previews:** the PC makes thumbnails for JPEG, PNG, GIF, WebP, BMP and TIFF (`app/services/thumbs.py`, stored in the storage folder's `thumbs\`). iPhone photos (HEIC) and videos show an icon unless the phone app sent a preview. Each person can turn previews off (account menu, or the button in Browse files).

## How it runs

One process, two listeners:

| Listener | Address | Purpose |
| --- | --- | --- |
| Admin | `http://127.0.0.1:8442` | Shown inside the desktop window. Only this PC can reach it. |
| Web server | `https://<this PC's LAN IP>:8443` | What users open (self-signed HTTPS). Start/Stop controls only this one. |

- Only one copy runs at a time. Launching it again brings the window to the front.
- Optional **admin PIN** (Dashboard): the window then needs the PIN to open, and locks when closed or after 30 idle minutes. Forgot it? Quit WiFiDrop and start it once with `--reset-admin-pin`.
- WiFiDrop's data folder and storage folder are limited to the Windows account that runs it (plus SYSTEM and Administrators).
- Every hour it removes items that have been in a Trash for over 30 days, and expired unfinished uploads.
- The web server binds only to a private address (192.168.x, 10.x, 172.16-31.x), never a public one.
- App data lives in `%ProgramData%\WiFiDrop\`: `wifidrop.db` (accounts, folders), `backups\`, `logs\`. Uploaded files go in the folder the admin chose, under ID names.

## Development

You need Python 3.12 or newer.

```bash
py -3 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

Run with the window and tray, using a throwaway data folder:

```bash
.venv/Scripts/python -m app --data-dir .devdata
```

Run without window or tray (Ctrl+C quits):

```bash
.venv/Scripts/python -m app --headless --data-dir .devdata
```

Run the tests:

```bash
.venv/Scripts/python -m pytest
```

Other flags: `--background` (start hidden in the tray), `--no-server`, `--reset-admin-pin`. Environment overrides: `WIFIDROP_WEBSITE=<https://your-site>` (shows **Send feedback** in the admin window), `WIFIDROP_CONSOLE_PORT`, `WIFIDROP_LAN_HOST`, `WIFIDROP_LAN_PORT`, `WIFIDROP_DATA_DIR`, `WIFIDROP_STORAGE_DIR`, `WIFIDROP_START_SERVER=0|1`, `WIFIDROP_HTTPS=0|1`, `WIFIDROP_UPDATE_FEED=<url>` (JSON `{"version", "url", "notes"}`; the admin window shows an "update available" banner), `WIFIDROP_LICENCE_URL=<url>` (licence server; empty turns licence checks off). The FileDrop beta's `FILEDROP_*` names still work.

Dependencies are pinned in `requirements.txt`. Upgrade one on purpose, run the tests, rebuild.

## Database and upgrades

Each new EXE upgrades the database on startup:

- Migrations are in `app/db/migrations.py`, numbered and forward-only. **Never edit a released migration.** Add a new one at the end. `tests/test_database.py` pins each released checksum.
- A backup goes to `backups\` before any upgrade (the last 10 are kept).
- A failed upgrade changes nothing and keeps the web server stopped. The admin window shows why.
- A database from a newer WiFiDrop is refused, never modified.

## Build the EXE and installer

```bash
powershell -ExecutionPolicy Bypass -File build/build.ps1
```

This runs the tests, builds `build/out/WiFiDrop/WiFiDrop.exe`, and, if [Inno Setup 6](https://jrsoftware.org/isdl.php) is installed, `build/out/WiFiDrop-Setup-<version>.exe` with its SHA-256. The installer (`build/installer.iss`) installs to Program Files, adds a Start menu entry, optional "start when I sign in", and a Windows Firewall rule; uninstalling keeps users' files.

Before a release, go through `tests/manual/CHECKLIST.md`.

## Layout

| Path | Contents |
| --- | --- |
| `app/main.py` | Entry point: single instance, database, listeners, admin window, tray |
| `app/api/` | `lan.py` (user API), `console.py` (admin API), `deps.py` |
| `app/services/` | Users, sign-in, spaces, files, uploads, settings, audit |
| `app/core/` | Settings, storage, names, networking, listener threads, Free/Pro edition (`edition.py`), beta upgrade (`legacy.py`) |
| `app/db/` | SQLite connection, backups, migrations, IDs |
| `web/` | User page plus the shared styles and helpers |
| `console/` | Admin window page |
| `tests/` | pytest suites, plus `tests/manual/CHECKLIST.md` |
| `site/` | The website at https://wifidrop.ca (generated; see **Website** below) |
| `tools/site/` | Website generator, self-checks, demo data and screenshot scripts |
| `supabase/` | Database migrations and Edge Functions: website forms, Pro licences, Paddle payments. See `supabase/README.md` |
| `mobile/` | Phone app (Expo), **on hold**. The PC side it needs (app sign-in tokens, network announcement, QR pairing) is in the app and tested. See `mobile/README.md` |
| `build/` | PyInstaller spec, installer script, build and publish scripts, open-source notices, icon |

## Website

The site lives in `site/` and is published to https://wifidrop.ca (GitHub Pages, from the public `filedrop-website` repo, which receives only `site/`).

- **Edit text in `tools/site/build_pages.py`**, not in the `.html` files, then regenerate: `.venv/Scripts/python tools/site/build_pages.py`.
- Settings such as the download link, checksum, support email, Supabase and Paddle live in `site/assets/js/config.js`.
- Check every page (layout at phone/tablet/desktop, contrast, console errors, spelling): serve `site/` with `.venv/Scripts/python -m http.server 8090 --directory site`, then run `.venv/Scripts/python tools/site/check.py`.
- Publish: commit, then `powershell -ExecutionPolicy Bypass -File build/publish-site.ps1`. It refuses to publish if any app file would leak.
- Screenshots: run a demo copy with sample data (`tools/site/demo_seed.py`), then `tools/site/screenshots.py`, and copy the `.webp` files to `site/assets/img/`.

## Releasing a new version

1. Bump `__version__` and `BUILD_DATE` in `app/__init__.py`, then run `build/build.ps1`.
2. Go through `tests/manual/CHECKLIST.md`.
3. Upload `build/out/WiFiDrop-Setup-<version>.exe` as a GitHub release on the website repo.
4. In `site/assets/js/config.js` set `version`, `releaseDate`, `downloadUrl` and `sha256`; in `site/update.json` set `version` and `notes` so existing installs see "Update available"; add a changelog entry in `tools/site/build_pages.py`.
5. Regenerate, check and publish the site.

## Not built yet

Code signing (needs a certificate), Windows shutdown handling, ZIP download of folders, guest upload links, the phone app (on hold).
