"""Starting the games."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import engine, paths
from .catalog import GAMES, Game
from .engine import Renderer

PLAYER_CFG = "arenahub.cfg"


@dataclass(frozen=True)
class PlayerSettings:
    name: str = ""
    sensitivity: float | None = None
    renderer: Renderer = Renderer.OPENGL


def installed_games(install_dir: Path) -> list[Game]:
    return [game for game in GAMES if (install_dir / game.marker).is_file()]


def _cfg_string(value: str) -> str:
    """Quake config strings cannot contain quotes, semicolons or line breaks."""
    return "".join(ch for ch in value if ch not in '";\r\n').strip()


def write_player_cfg(install_dir: Path, game: Game, settings: PlayerSettings) -> Path | None:
    """Write the player's settings to <game_dir>/arenahub.cfg, run at startup."""
    lines = []
    if name := _cfg_string(settings.name):
        lines.append(f'seta name "{name}"')
    if settings.sensitivity is not None:
        lines.append(f'seta sensitivity "{settings.sensitivity:g}"')
    path = install_dir / game.game_dir / PLAYER_CFG
    if not lines:
        path.unlink(missing_ok=True)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("// Written by ArenaHub on every launch\n" + "\n".join(lines) + "\n")
    return path


def arguments(install_dir: Path, game: Game, with_cfg: bool = True) -> list[str]:
    """Engine arguments that keep everything (configs, keys, demos) inside install_dir."""
    folder = str(install_dir)
    args = ["+set", "fs_basepath", folder, "+set", "fs_homepath", folder]
    if game.game_dir != "baseq3":
        args += ["+set", "fs_game", game.game_dir]
    if with_cfg:
        args += ["+exec", PLAYER_CFG]
    return args


def command(install_dir: Path, game: Game, renderer: Renderer) -> list[str]:
    exe = engine.executable(install_dir, renderer)
    if exe is None:
        raise FileNotFoundError("Quake3e is not installed in this folder")
    return [str(exe), *arguments(install_dir, game)]


def launch(install_dir: Path, game: Game, settings: PlayerSettings) -> subprocess.Popen:
    write_player_cfg(install_dir, game, settings)
    argv = command(install_dir, game, settings.renderer)
    options: dict = {"cwd": install_dir, "env": paths.child_env(), "stdin": subprocess.DEVNULL}
    if paths.system() == "windows":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
        options["stdout"] = options["stderr"] = subprocess.DEVNULL
    return subprocess.Popen(argv, **options)
