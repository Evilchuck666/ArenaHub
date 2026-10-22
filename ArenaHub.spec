# -*- mode: python ; coding: utf-8 -*-
# Build a single-file executable for the current system:
#   uv run pyinstaller ArenaHub.spec --clean --noconfirm
# PyInstaller does not cross-compile: build on each target OS/architecture.
import importlib
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH)
ICONS = ROOT / "assets" / "icons"

# Everything the app imports at runtime, including what only the Steam helper
# process or a single platform uses. The build stops if any of it is missing
# from the environment, instead of producing a binary that fails later.
REQUIRED = [
    "PySide6.QtWidgets",
    "PySide6.QtSvgWidgets",
    "requests",
    "certifi",
    "gevent",
    "steam.client",
    "steam.client.cdn",
    "websocket",
    "zstandard",
]

missing = []
for name in REQUIRED:
    try:
        importlib.import_module(name)
    except Exception as exc:  # noqa: BLE001
        missing.append(f"{name}: {exc}")
if missing:
    raise SystemExit("Missing build dependencies (run the setup script):\n  " + "\n  ".join(missing))

hiddenimports = [
    # Only imported inside the Steam helper process.
    "arenahub.steam_helper",
    "arenahub.steam_depots",
    *collect_submodules("zstandard"),
    # steam-next loads its protobuf modules by name.
    *collect_submodules("steam"),
]
# The window uses the PNG; shortcuts use the SVG (Linux), PNG (macOS) or ICO (Windows).
datas = [(str(ICONS / name), "assets/icons") for name in ("arenahub.png", "arenahub.svg", "arenahub.ico")]
# The emblem in the window's header and the theme's small icons (arrows, check mark).
datas += [(str(ICONS / "arenahub-emblem.svg"), "assets/icons")]
datas += [(str(svg), "assets/icons/ui") for svg in sorted((ICONS / "ui").glob("*.svg"))]
# Templates for the GNU/Linux shortcuts.
datas += [(str(link), "assets/links") for link in sorted((ROOT / "assets" / "links").glob("*.desktop"))]
# Game configs copied into the installation (autoexec.cfg, game.cfg, player.cfg per game).
datas += [
    (str(cfg), str(cfg.parent.relative_to(ROOT)))
    for cfg in sorted((ROOT / "assets" / "cfg").glob("*/*.cfg"))
]
# Levelshot thumbnails for the Maps tab (the map packs themselves are downloaded).
datas += [(str(jpg), "assets/levelshots") for jpg in sorted((ROOT / "assets" / "levelshots").glob("*.jpg"))]
datas += copy_metadata("steam-next")
binaries = []

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
