"""Per-user locations and platform detection."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

APP_NAME = "ArenaHub"


def system() -> str:
    """'linux', 'windows' or 'macos'."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def machine() -> str:
    """'x86_64' or 'arm64'."""
    arch = platform.machine().lower()
    if arch in ("arm64", "aarch64"):
        return "arm64"
    return "x86_64"


def data_dir() -> Path:
    """Where ArenaHub keeps its own per-user files."""
    match system():
        case "windows":
            base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        case "macos":
            base = Path.home() / "Library" / "Application Support"
        case _:
            base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


def default_install_dir() -> Path:
    if system() == "windows":
        return Path.home() / "Games" / APP_NAME
    return Path.home() / "Games" / "arenahub"


def resource(*parts: str) -> Path:
    """A file bundled with the application (works from source and from PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    return base.joinpath("assets", *parts)


def self_command(*args: str) -> list[str]:
    """Command line that runs this same application with extra arguments."""
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "arenahub", *args]


def child_env() -> dict[str, str]:
    """Environment for programs we start, without PyInstaller's library path changes.

    A frozen build points LD_LIBRARY_PATH at its own bundled libraries, which
    must not leak into the engine.
    """
    env = os.environ.copy()
    for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        original = env.pop(f"{var}_ORIG", None)
        if original is not None:
            env[var] = original
        elif getattr(sys, "frozen", False):
            env.pop(var, None)
    return env
