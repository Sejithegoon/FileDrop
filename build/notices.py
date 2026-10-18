"""Writes the open-source notices for everything FileDrop ships.

Follows requirements.txt through each package's own dependencies (as installed in .venv),
then adds Python itself and the PyInstaller launcher. Outputs:
  console/licences.json             the list shown on the admin window's About page
  console/THIRD-PARTY-NOTICES.txt   the full licence texts (also copied into the installer)
Run: .venv/Scripts/python build/notices.py   (build.ps1 runs it before every build)
"""

from __future__ import annotations

import json
import re
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]
LICENCE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|AUTHORS)[^/]*$", re.I)


def licence_of(meta) -> str:
    if meta.get("License-Expression"):
        return meta["License-Expression"]
    text = (meta.get("License") or "").strip()
    if text and "\n" not in text and len(text) <= 60:
        return text
    found = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return "; ".join(found) or "See licence text"


def homepage(meta) -> str:
    urls = dict(u.split(",", 1) for u in meta.get_all("Project-URL") or [] if "," in u)
    for key in ("Homepage", "homepage", "Source", "Source Code", "Repository", "repository", "Documentation"):
        if key in urls:
            return urls[key].strip()
    return (meta.get("Home-page") or "").strip()


def runtime_closure(names: list[str]) -> list:
    seen, order, todo = set(), [], list(names)
    while todo:
        name = todo.pop(0)
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in seen:
            continue
        try:
            dist = distribution(name)
        except PackageNotFoundError:
            continue
        seen.add(key)
        order.append(dist)
        for raw in dist.requires or []:
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate({"extra": ""}):
                continue  # optional extra or another platform
            todo.append(req.name)
    return sorted(order, key=lambda d: d.metadata["Name"].lower())


def licence_texts(dist) -> str:
    parts = []
    for f in dist.files or []:
        if LICENCE_FILE.search(str(f)) and not str(f).endswith((".py", ".pyc")):
            try:
                parts.append(Path(dist.locate_file(f)).read_text(encoding="utf-8", errors="replace").strip())
            except OSError:
                pass
    if not parts and dist.metadata.get("License") and "\n" in dist.metadata["License"]:
        parts.append(dist.metadata["License"].strip())
    return "\n\n".join(parts) or "No licence file is included in this package. See the project's website."


def main() -> None:
    names = [l.split("==")[0].strip() for l in (ROOT / "requirements.txt").read_text().splitlines()
             if l.strip() and not l.startswith("#")]
    items, blocks = [], []
    for dist in runtime_closure(names):
        m = dist.metadata
        item = {"name": m["Name"], "version": dist.version, "license": licence_of(m), "url": homepage(m)}
        items.append(item)
        blocks.append((item, licence_texts(dist)))

    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_licence = Path(sys.base_prefix, "LICENSE.txt")
    extra = [({"name": "Python", "version": py, "license": "PSF-2.0", "url": "https://www.python.org/"},
              py_licence.read_text(encoding="utf-8", errors="replace") if py_licence.exists() else "")]
    try:
        pi = distribution("pyinstaller")
        extra.append(({"name": "PyInstaller bootloader", "version": pi.version,
                       "license": "GPL-2.0-or-later WITH Bootloader-exception", "url": "https://pyinstaller.org/"},
                      licence_texts(pi)))
    except PackageNotFoundError:
        pass
    for item, text in extra:
        items.append(item)
        blocks.append((item, text))

    (ROOT / "console" / "licences.json").write_text(json.dumps(items, indent=1) + "\n", encoding="utf-8")
    out = ["FileDrop includes the open-source software listed below. Each is used under its own licence,",
           "reproduced in full. Thank you to everyone who builds and maintains these projects.", ""]
    out += [f"  {i['name']} {i['version']}  ({i['license']})" for i in items]
    for item, text in blocks:
        out += ["", "=" * 78, f"{item['name']} {item['version']}", f"Licence: {item['license']}",
                f"Website: {item['url'] or 'n/a'}", "=" * 78, "", text.strip()]
    (ROOT / "console" / "THIRD-PARTY-NOTICES.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(items)} components written to console/licences.json and console/THIRD-PARTY-NOTICES.txt")


if __name__ == "__main__":
    main()
