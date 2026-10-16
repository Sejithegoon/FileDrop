# FileDrop

FileDrop is a LAN file server for Windows. The PC running it gets a desktop **admin window** and a tray icon. People on the same Wi-Fi open a **web page** on their phone or computer, sign in, and manage their files.

## Try it

1. Run `build/out/FileDrop/FileDrop.exe` (or `.venv/Scripts/python -m app` from source).
2. The **FileDrop Admin** window opens. The first time, it asks where to save uploaded files (type a path or click **Browse…**). You can change it later with **Dashboard → Storage → Change folder**; FileDrop moves the existing files for you.
3. Go to **Users → Add user** and create an account.
4. Optional: **Shared folders → New shared folder**, then give users View, Upload or Manage access.
5. On a phone on the same Wi-Fi, scan the QR code on the Dashboard (or type the link), then sign in.

Closing the admin window keeps FileDrop running in the tray. Click the tray icon to reopen it. **Quit FileDrop** (tray menu or the window's sidebar) stops everything.

## What works

| Admin window (this PC) | User web page (any device) |
| --- | --- |
| Start/stop the web server, link + QR code | Sign in, forced password change on first sign-in |
| Allow/pause uploads and downloads for everyone | Private "My files" plus shared folders they're added to |
| Add, edit, suspend, enable, delete users, reset passwords | Upload many files at once: 8 MB chunks, 3 in parallel, auto-retry and resume |
| Storage limits per user and per shared folder | Download, rename, new folder, delete to Trash, restore, delete forever |
| Shared folders with per-user View / Upload / Manage | Drag and drop on desktop, iPhone photo hint |
| See signed-in devices and uploads, sign out or cancel them | Live banner when the admin pauses uploads or downloads |
| Browse, download, rename, delete any user's files | Works at phone width, light and dark mode |
| Activity log of sign-ins and admin actions | |

## How it runs

One process, two listeners:

| Listener | Address | Purpose |
| --- | --- | --- |
| Admin | `http://127.0.0.1:8442` | Shown inside the desktop window. Only this PC can reach it. |
| Web server | `http://<this PC's LAN IP>:8443` | What users open. Start/Stop controls only this one. |

- Only one copy runs at a time. Launching it again brings the window to the front.
- The web server binds only to a private address (192.168.x, 10.x, 172.16-31.x), never a public one.
- App data lives in `%ProgramData%\FileDrop\`: `filedrop.db` (accounts, folders), `backups\`, `logs\`. Uploaded files go in the folder the admin chose, under ID names.

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

Other flags: `--background` (start hidden in the tray), `--no-server`. Environment overrides: `FILEDROP_CONSOLE_PORT`, `FILEDROP_LAN_HOST`, `FILEDROP_LAN_PORT`, `FILEDROP_DATA_DIR`, `FILEDROP_STORAGE_DIR`, `FILEDROP_START_SERVER=0|1`.

## Database and upgrades

Each new EXE upgrades the database on startup:

- Migrations are in `app/db/migrations.py`, numbered and forward-only. **Never edit a released migration.** Add a new one at the end. `tests/test_database.py` pins each released checksum.
- A backup goes to `backups\` before any upgrade (the last 10 are kept).
- A failed upgrade changes nothing and keeps the web server stopped. The admin window shows why.
- A database from a newer FileDrop is refused, never modified.

## Build the EXE

```bash
.venv/Scripts/pyinstaller build/filedrop.spec --distpath build/out --workpath build/work --noconfirm
```

The output is `build/out/FileDrop/` (run `FileDrop.exe` inside it; keep the `_internal` folder next to it).

## Layout

| Path | Contents |
| --- | --- |
| `app/main.py` | Entry point: single instance, database, listeners, admin window, tray |
| `app/api/` | `lan.py` (user API), `console.py` (admin API), `deps.py` |
| `app/services/` | Users, sign-in, spaces, files, uploads, settings, audit |
| `app/core/` | Settings, storage, names, networking, listener threads |
| `app/db/` | SQLite connection, backups, migrations, IDs |
| `web/` | User page plus the shared styles and helpers |
| `console/` | Admin window page |
| `tests/` | pytest suites |
| `build/` | PyInstaller spec and icon |

## Not built yet

HTTPS, Windows shutdown handling, Start with Windows, moving files between folders, ZIP download of folders, thumbnails, an installer.
