"""The Quake3e engine: picking the right build, installing it and finding its executable."""

from __future__ import annotations

import zipfile
from enum import Enum
from pathlib import Path

from . import net, paths
from .archive import extract, make_executable
from .context import Context, TaskError

REPO = "ec-/Quake3e"

ASSETS = {
    ("linux", "x86_64"): "quake3e-linux-x86_64.zip",
    ("linux", "arm64"): "quake3e-linux-arm64.zip",
    ("windows", "x86_64"): "quake3e-windows-mingw-x86_64.zip",
    ("windows", "arm64"): "quake3e-windows-msvc-arm64.zip",
    ("macos", "x86_64"): "quake3e-macos-x86_64.zip",
    ("macos", "arm64"): "quake3e-macos-aarch64.zip",
}


class Renderer(Enum):
    OPENGL = "opengl"
    VULKAN = "vulkan"


def asset_name(system: str | None = None, machine: str | None = None) -> str:
    key = (system or paths.system(), machine or paths.machine())
    try:
        return ASSETS[key]
    except KeyError:
        raise TaskError(f"Quake3e has no build for {key[0]} {key[1]}") from None


def is_client(name: str) -> bool:
    """Client executables are named quake3e[-vulkan].<arch>[.exe]; '.ded.' is the server."""
    name = Path(name).name.lower()
    return name.startswith("quake3e") and ".ded." not in name and not name.endswith(".dylib")


def install(ctx: Context, install_dir: Path, download_dir: Path) -> list[Path]:
    """Download the latest Quake3e build for this system into install_dir."""
    name = asset_name()
    url = net.latest_release_asset(REPO, name)
    archive = net.fetch(ctx, (url,), download_dir / name, label="Quake3e")

    with zipfile.ZipFile(archive) as zf:
        names = [Path(n).name for n in zf.namelist() if not n.endswith("/")]
    if not any(is_client(n) for n in names):
        raise TaskError(f"{name} does not contain a Quake3e client")

    written = extract(ctx, archive, install_dir)
    if paths.system() != "windows":
        for path in written:
            if is_client(path.name) or ".ded." in path.name:
                make_executable(path)
    return written


def executable(install_dir: Path, renderer: Renderer = Renderer.OPENGL) -> Path | None:
    """The Quake3e client in install_dir for the chosen renderer, if installed."""
    candidates = sorted(
        p for p in install_dir.glob("quake3e*") if p.is_file() and is_client(p.name)
    )
    if paths.system() == "windows":
        candidates = [p for p in candidates if p.suffix.lower() == ".exe"]
    vulkan = [p for p in candidates if "vulkan" in p.name.lower()]
    opengl = [p for p in candidates if "vulkan" not in p.name.lower()]

    preferred, fallback = (vulkan, opengl) if renderer is Renderer.VULKAN else (opengl, vulkan)
    return (preferred or fallback or [None])[0]
