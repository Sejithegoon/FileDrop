# FileDrop

FileDrop is a LAN file server for Windows that runs in the system tray. People on the same network sign in from a phone or computer browser and manage their own folder. The Windows PC stores the files.

The full spec is in the requirements doc (permissions, state diagrams, API outline, acceptance criteria). This repo is a **scaffold**: it starts the app, shows the tray icon and runs both listeners. No features are built yet.

## How it runs

FileDrop is one process with two listeners:

| Listener | Address | Purpose |
| --- | --- | --- |
| Console | `http://127.0.0.1:8442` | Host-only control page: start/stop the web server, quit. Always on while FileDrop runs. |
| LAN web server | `http://<this PC's LAN IP>:8443` | What users open. Start/Stop controls only this listener. |

- Closing the console page or browser does **not** stop FileDrop. It keeps running in the tray.
- FileDrop stops only when you pick **Quit FileDrop** (tray menu or console) or Windows shuts down.
- Only one copy runs at a time. Launching it again opens the console.
- The LAN server binds only to a private address (192.168.x, 10.x, 172.16-31.x). It refuses public addresses and `0.0.0.0`.

## Development

You need Python 3.12 or newer.

```bash
py -3 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```

Run with the tray icon:

```bash
.venv/Scripts/python -m app
```

Run without a tray (Ctrl+C quits), and start the LAN server right away:

```bash
.venv/Scripts/python -m app --headless --start-server
```

Run the tests:

```bash
.venv/Scripts/python -m pytest
```

Environment overrides: `FILEDROP_CONSOLE_PORT`, `FILEDROP_LAN_HOST`, `FILEDROP_LAN_PORT`, `FILEDROP_DATA_DIR`, `FILEDROP_START_SERVER=1`.

Logs go to `%ProgramData%\FileDrop\logs\filedrop.log`.

## Build the EXE

```bash
.venv/Scripts/pyinstaller build/filedrop.spec --distpath build/out --workpath build/work
```

The output is `build/out/FileDrop/FileDrop.exe` (a one-folder build). An Inno Setup installer and a "Start with Windows" entry come later.

## Layout

| Path | Contents |
| --- | --- |
| `app/main.py` | Entry point: single-instance check, tray, both listeners |
| `app/tray.py` | Tray icon and menu |
| `app/api/` | FastAPI apps: `lan.py` (users), `console.py` (localhost only) |
| `app/core/` | Settings, LAN address checks, listener threads. Later: permissions, storage, transfers, audit |
| `app/db/` | SQLite schema and queries (not started) |
| `web/` | User and admin pages (placeholder) |
| `console/` | Host console page |
| `tests/` | pytest suites |
| `build/` | PyInstaller spec |

## Not built yet

HTTPS/TLS, accounts and sign-in, SQLite, file browsing, uploads and downloads, admin pages, upload/download pauses, drain-mode stop, Windows shutdown handling, Start with Windows, and the installer.
