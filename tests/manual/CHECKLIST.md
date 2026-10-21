# WiFiDrop release checklist (manual)

Run this on a release candidate before giving it to anyone. Note the date, build version, PC, and phones used. Mark each line **Pass**, **Fail** (file a bug with steps) or **Skip** (say why).

Build: `________`  Date: `________`  Host PC / Windows version: `________`

## Install and first run (clean Windows 11 PC or VM)

- [ ] Run `WiFiDrop-Setup-<version>.exe`. The publisher shows as expected (unsigned builds show "Unknown publisher" until signing is set up).
- [ ] Installer finishes; "Start WiFiDrop now" opens the admin window.
- [ ] First run asks where to save files. **Browse…** opens the Windows folder picker and fills in the path.
- [ ] No Windows Firewall prompt appears (the installer added a rule).
- [ ] Start menu entry works. Desktop icon appears only if ticked.
- [ ] With "Start WiFiDrop when I sign in" ticked: sign out and back in; WiFiDrop is in the tray and the window is **not** open.

## Tray and window

- [ ] Clicking **X** hides the window; a one-time notification says WiFiDrop is still running.
- [ ] Tray icon → **Open WiFiDrop** brings the window back.
- [ ] Tray icon → **Quit WiFiDrop** with the window hidden quits within a few seconds (check Task Manager).
- [ ] Launching WiFiDrop again while it runs brings the existing window forward (no second copy).

## Phones over HTTPS

- [ ] Scan the Dashboard QR code with an **iPhone** (Safari). The "not private" warning appears once; Show Details → visit this website works.
- [ ] The certificate fingerprint on the warning page matches the start of the one on the Dashboard.
- [ ] Same with an **Android** phone (Chrome): Advanced → Proceed.
- [ ] Sign in, change temporary password, see "My files".
- [ ] Restart WiFiDrop: phones reconnect **without** a new warning.
- [ ] Switch the PC to a different network (new IP): the Dashboard link changes after Stop/Start, and phones warn once more.

## Uploads and downloads

- [ ] iPhone: pick **50 photos** at once. Note how long iOS takes to "prepare" before uploads start: `____`
- [ ] Upload a **5 GB** file from a PC browser. It finishes and the download is byte-identical (compare SHA-256).
- [ ] Turn Wi-Fi off for 30 s in the middle of a large upload; it resumes by itself.
- [ ] **10 devices or browser tabs** uploading at the same time; the admin window stays responsive.
- [ ] Download a large file on a phone and open it.
- [ ] Make folders "Pics" and "School", move files into them, rename, delete to Trash, restore.
- [ ] Photos show previews in the list (phone page and admin Browse files); tap one to view it full screen; a video plays.
- [ ] Previews off in the account menu hides them; on again brings them back.
- [ ] Search finds a file inside a subfolder and in a shared folder; tapping a folder result opens it.

## Admin controls

- [ ] Turn off **Allow uploads**: phones show the banner within 15 s and can't start uploads.
- [ ] Suspend a signed-in user: their phone is signed out right away.
- [ ] Shared folder: View user can download but not upload; Upload user can't delete others' files.
- [ ] Set an **admin PIN**. Close the window, reopen from tray: PIN required. Wrong PIN 5 times pauses for a minute.
- [ ] Quit, start with `--reset-admin-pin` (from a terminal): the PIN is gone.
- [ ] **Change folder** to another drive with a few GB stored: progress shows, files still download afterwards.

## Failure and recovery

- [ ] Kill `WiFiDrop.exe` in Task Manager during an upload. Start it again: no half-finished file appears, the phone's upload restarts or resumes.
- [ ] Unplug the drive holding the storage folder while WiFiDrop runs: phones get a clear error, nothing crashes. Plug it back and restart WiFiDrop: everything is there.
- [ ] Pull the power (or force shutdown) while idle. On restart the database opens and files are intact.
- [ ] Check `%ProgramData%\WiFiDrop\logs\wifidrop.log` has no unexpected errors.

## Privacy and permissions

- [ ] Sign in to the PC as a **different Windows user**: they can't open `%ProgramData%\WiFiDrop` or the storage folder.
- [ ] With a network monitor (e.g. Resource Monitor → Network), confirm WiFiDrop makes no outgoing internet connections except the update check (if a feed is configured).

## Uninstall

- [ ] Uninstall from Settings → Apps. WiFiDrop stops, the Start menu entry and firewall rule are gone.
- [ ] `%ProgramData%\WiFiDrop` and the storage folder are **kept** (users' files are never deleted by uninstalling).
- [ ] Reinstall: accounts and files are all still there.
