# -*- mode: python ; coding: utf-8 -*-
# Compilar con:  uv run pyinstaller ArenaHub.spec --clean --noconfirm
import sys
from pathlib import Path

ROOT = Path(SPECPATH)
ICON = None
if sys.platform == "win32" and (ROOT / "assets/icon.ico").exists():
    ICON = str(ROOT / "assets/icon.ico")
elif sys.platform == "darwin" and (ROOT / "assets/icon.icns").exists():
    ICON = str(ROOT / "assets/icon.icns")

a = Analysis(
    [str(ROOT / "run.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[(str(ROOT / "assets"), "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # Excluir módulos Qt pesados que no se usan (reduce tamaño)
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore"],
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

if sys.platform == "darwin":
    app = BUNDLE(exe, name="ArenaHub.app", icon=ICON, bundle_identifier="com.evilchuck.arenahub")
