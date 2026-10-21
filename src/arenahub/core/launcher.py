"""Starting the games."""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import engine, paths
from .catalog import GAMES, Game
from .engine import Renderer


def installed_games(install_dir: Path) -> list[Game]:
    return [game for game in GAMES if (install_dir / game.marker).is_file()]


def arguments(install_dir: Path, game: Game) -> list[str]:
    """Engine arguments that keep everything (configs, keys, demos) inside install_dir.

    The player's settings need no argument: the engine runs autoexec.cfg on
    its own (see configs).
    """
    folder = str(install_dir)
    args = ["+set", "fs_basepath", folder, "+set", "fs_homepath", folder]
    if game.game_dir != "baseq3":
        args += ["+set", "fs_game", game.game_dir]
    return args


def command(install_dir: Path, game: Game, renderer: Renderer) -> list[str]:
    exe = engine.executable(install_dir, renderer)
    if exe is None:
        raise FileNotFoundError("Quake3e is not installed in this folder")
    return [str(exe), *arguments(install_dir, game)]


def launch(install_dir: Path, game: Game, renderer: Renderer) -> subprocess.Popen:
    argv = command(install_dir, game, renderer)
    options: dict = {"cwd": install_dir, "env": paths.child_env(), "stdin": subprocess.DEVNULL}
    if paths.system() == "windows":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
        options["stdout"] = options["stderr"] = subprocess.DEVNULL
    return subprocess.Popen(argv, **options)
