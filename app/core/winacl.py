"""Restrict WiFiDrop's folders to the current Windows user, SYSTEM and Administrators.

%ProgramData% lets every local user read new folders by default, which would
expose the database (password hashes) and stored files to other accounts on
the PC. This removes inherited access and grants full control to those three.
"""

from __future__ import annotations

import csv
import io
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

SYSTEM_SID = "S-1-5-18"
ADMINS_SID = "S-1-5-32-544"
_NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: no console flash from the windowed EXE


def _current_user_sid() -> str | None:
    out = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         creationflags=_NO_WINDOW, timeout=10)
    rows = list(csv.reader(io.StringIO(out.stdout.strip())))
    return rows[0][1] if rows and len(rows[0]) > 1 and rows[0][1].startswith("S-1-") else None


def restrict_to_owner(path: Path) -> bool:
    """True if the folder is now private. Never raises: failure is logged and WiFiDrop carries on."""
    if sys.platform != "win32" or not path.is_dir():
        return False
    try:
        sid = _current_user_sid()
        if not sid:
            log.warning("Could not read the current user's SID; leaving permissions on %s unchanged", path)
            return False
        grants = [f"*{s}:(OI)(CI)F" for s in (sid, SYSTEM_SID, ADMINS_SID)]
        result = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", *grants, "/Q"],
                                capture_output=True, text=True, creationflags=_NO_WINDOW, timeout=60)
        if result.returncode != 0:
            log.warning("icacls failed on %s: %s", path, (result.stdout + result.stderr).strip())
            return False
        return True
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("Could not restrict permissions on %s: %s", path, exc)
        return False


MARKER = ".wifidrop-private"
OLD_MARKER = ".filedrop-private"  # FileDrop beta


def ensure_private(path: Path) -> None:
    """Restrict once per folder; a marker file avoids re-walking a large storage tree on every start."""
    if sys.platform != "win32" or (path / MARKER).exists() or (path / OLD_MARKER).exists():
        return
    if restrict_to_owner(path):
        try:
            (path / MARKER).write_text("Access limited to the WiFiDrop user, SYSTEM and Administrators.\n")
        except OSError:
            pass
