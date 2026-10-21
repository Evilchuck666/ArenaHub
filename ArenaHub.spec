# -*- mode: python ; coding: utf-8 -*-
# Build a single-file executable for the current system:
#   uv run pyinstaller ArenaHub.spec --clean --noconfirm
# PyInstaller does not cross-compile: build on each target OS/architecture.
import importlib
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules, copy_metadata

ROOT = Path(SPECPATH)
ICONS = ROOT / "assets" / "icons"

# Everything the app imports at runtime, including what only the Steam helper
# process or a single platform uses. The build stops if any of it is missing
# from the environment, instead of producing a binary that fails later.
REQUIRED = ["PySide6.QtWidgets", "requests", "certifi", "gevent", "steam.client", "websocket"]
if sys.platform == "win32":
    REQUIRED.append("winpty")

missing = []
for name in REQUIRED:
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        missing.append(f"{name}: {exc}")
if missing:
    raise SystemExit("Missing build dependencies (run the setup script):\n  " + "\n  ".join(missing))

hiddenimports = [
    "arenahub.steam_helper",
    # steam-next loads its protobuf modules by name.
    *collect_submodules("steam"),
]
datas = [(str(ICONS / "arenahub.png"), "assets/icons")]
datas += copy_metadata("steam-next")
binaries = []

if sys.platform == "win32":
    hiddenimports += collect_submodules("winpty")
    binaries += collect_dynamic_libs("winpty")

if sys.platform == "win32":
    ICON = str(ICONS / "arenahub.ico")
elif sys.platform == "darwin":
    ICON = str(ICONS / "arenahub.icns")
else:
    ICON = None

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.Qt3DCore",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ArenaHub",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon=ICON,
)
