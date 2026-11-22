#!/usr/bin/env python3
"""Start ArenaHub, from source or from its single-file executable (scripts/ArenaHub.spec)."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def main(argv=None):
    try:
        from arenahub.__main__ import main as start
    except ModuleNotFoundError:
        if getattr(sys, "frozen", False) or os.environ.get("ARENAHUB_REEXEC"):
            raise
        # Started by an interpreter outside the project environment (such as the
        # system python3): hand over to the one in .venv, or explain how to make it.
        root = Path(__file__).resolve().parent
        venv = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not venv.exists():
            setup = {"win32": r"scripts\setup_windows.bat", "darwin": "./scripts/setup_macos.sh"}
            sys.exit(
                "ArenaHub's environment is not set up yet. Run "
                f"{setup.get(sys.platform, './scripts/setup_linux.sh')} and then: uv run arenahub"
            )
        os.environ["ARENAHUB_REEXEC"] = "1"
        args = sys.argv[1:] if argv is None else argv
        os.execv(venv, [str(venv), str(Path(__file__).resolve()), *args])
    return start(argv)


def run(argv=None):
    """Report startup failures even when the Windows executable has no console."""
    try:
        return main(argv)
    except Exception as error:  # noqa: BLE001 - surface startup failures when no console exists.
        message = "ArenaHub could not start.\n\n" + traceback.format_exc()
        if isinstance(error, ImportError) and not getattr(sys, "frozen", False):
            message += (
                "\nThis is the source code. To use ArenaHub without installing "
                "Python or Qt, extract the standalone package for your system "
                "and open ArenaHub.exe (Windows) or ArenaHub (Linux/macOS).\n"
            )
        if sys.stderr is not None:
            print(message, file=sys.stderr)
        elif sys.platform == "win32":
            # Qt itself may have failed to import, so use a native dialog.
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, "ArenaHub", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
