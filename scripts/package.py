"""Verify the PyInstaller build in dist/ and pack it for release.

    uv run python scripts/package.py                   verify, then create the archive
    uv run python scripts/package.py --verify-only     only verify
    uv run python scripts/package.py --qt-platform xcb verify against a real X server

Verification copies the executable to an empty temporary folder, so it cannot
lean on project files, and runs its Steam helper self-test and GUI smoke test.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
TIMEOUT = 120


def system() -> str:
    if sys.platform.startswith("win"):
        return "windows"
    return "macos" if sys.platform == "darwin" else "linux"


def arch() -> str:
    return "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"


def executable() -> Path:
    exe = DIST / ("ArenaHub.exe" if system() == "windows" else "ArenaHub")
    if not exe.is_file():
        sys.exit(f"{exe} not found; build it first with: uv run pyinstaller ArenaHub.spec")
    return exe


def run(argv: list[str], env: dict[str, str], cwd: Path) -> str:
    print("$", " ".join(argv), flush=True)
    result = subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )
    if result.returncode != 0:
        sys.exit(f"Failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
    return result.stdout


def verify(exe: Path, qt_platform: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / exe.name
        shutil.copy2(exe, copy)
        env = {**os.environ, "QT_QPA_PLATFORM": qt_platform}

        output = run([str(copy), "--steam-helper", "--self-test"], env, Path(tmp))
        if '"result": "OK"' not in output:
            sys.exit(f"Unexpected Steam helper self-test output:\n{output}")

        run(
            [str(copy), "--smoke-test", "--screenshot", str(Path(tmp) / "window.png")],
            env,
            Path(tmp),
        )
        if not (Path(tmp) / "window.png").is_file():
            sys.exit("The smoke test did not render the window")
    print(f"Verified {exe} ({qt_platform})")


def pack(exe: Path) -> Path:
    name = f"ArenaHub-{system()}-{arch()}"
    if system() == "linux":
        archive = DIST / f"{name}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(exe, arcname=exe.name)
    else:
        archive = DIST / f"{name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            info = zipfile.ZipInfo.from_file(exe, exe.name)
            info.external_attr = 0o100755 << 16  # keep it executable on macOS
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, exe.read_bytes())
    print(f"Created {archive}")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--qt-platform", default="offscreen")
    args = parser.parse_args()

    exe = executable()
    verify(exe, args.qt_platform)
    if not args.verify_only:
        pack(exe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
