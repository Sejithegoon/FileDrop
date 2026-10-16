# PyInstaller spec. Build from the repo root:
#   pyinstaller build/filedrop.spec --distpath build/out --workpath build/work
import os

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(ROOT, "app", "main.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "web"), "web"), (os.path.join(ROOT, "console"), "console")],
    hiddenimports=collect_submodules("uvicorn"),
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FileDrop", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="FileDrop")
