"""The licence agreement and open-source notices ship with the app and cover every dependency."""

import json
import re
from pathlib import Path

from tests.test_api import admin, ctx  # noqa: F401 (fixtures)

ROOT = Path(__file__).resolve().parents[1]


def test_every_runtime_requirement_is_listed():
    listed = {re.sub(r"[-_. ]+", "-", c["name"]).lower() for c in json.loads((ROOT / "console/licences.json").read_text())}
    required = {re.sub(r"[-_.]+", "-", l.split("==")[0].strip()).lower()
                for l in (ROOT / "requirements.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
    assert required <= listed, f"run build/notices.py; missing: {required - listed}"
    assert {"python", "pyinstaller-bootloader"} <= listed


def test_admin_window_serves_agreement_and_notices(admin):
    assert "END USER LICENCE AGREEMENT" in admin.get("/EULA.txt").text
    assert "pystray" in admin.get("/THIRD-PARTY-NOTICES.txt").text
    assert any(c["name"] == "fastapi" for c in admin.get("/licences.json").json())
