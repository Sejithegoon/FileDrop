# PyInstaller spec. Build from the repo root:
#   .venv/Scripts/pyinstaller build/filedrop.spec --distpath build/out --workpath build/work --noconfirm
import glob
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# Python 3.15 keeps python3t.dll (needed by abi3t wheels such as cryptography) in an
# "abi3t-compat" folder that PyInstaller doesn't collect on its own.
EXTRA_BINARIES = [(dll, ".") for dll in glob.glob(os.path.join(sys.base_prefix, "abi3t-compat", "*.dll"))]

a = Analysis(
    [os.path.join(ROOT, "app", "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "web"), "web"), (os.path.join(ROOT, "console"), "console")],
    binaries=EXTRA_BINARIES,
    hiddenimports=collect_submodules("uvicorn") + collect_submodules("app") + ["qrcode.image.svg"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WiFiDrop", console=False,
          icon=os.path.join(SPECPATH, "filedrop.ico"))
coll = COLLECT(exe, a.binaries, a.datas, name="WiFiDrop")
