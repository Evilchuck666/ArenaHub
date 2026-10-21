# Entry point for PyInstaller (see ArenaHub.spec) and for `python run.py`.
import os
import sys
from pathlib import Path

try:
    from arenahub.__main__ import main
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
    os.execv(venv, [str(venv), str(Path(__file__).resolve()), *sys.argv[1:]])

if __name__ == "__main__":
    sys.exit(main())
