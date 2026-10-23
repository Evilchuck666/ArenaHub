"""The bundled game configs (assets/cfg) and the player settings inside them.

Each game folder with configs gets three files, as in QuakeBundle:

- autoexec.cfg: Quake3e runs it at every start; it only runs the other two.
- game.cfg:     bindings, HUD, graphics, sound and server settings.
- player.cfg:   name, sensitivity and model; ArenaHub edits name and sensitivity.
                The name may hold colour codes (see names).

Every game ArenaHub installs has its own set. A folder without them would
still use baseq3's, because the engine looks for autoexec.cfg in the mod
folder first and then in baseq3.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from . import names, paths

CONFIG_FILES = ("autoexec.cfg", "game.cfg", "player.cfg")
PLAYER_CFG = "player.cfg"
OBSOLETE = ("arenahub.cfg",)
"""Files earlier versions of ArenaHub wrote; the configs above replace them."""

MAX_NAME_LENGTH = 32
"""Colour codes included. The game keeps 35 characters, which leaves room for
the ^7 that names.for_game adds."""


@dataclass(frozen=True)
class Player:
    name: str = "Player"
    sensitivity: float = 3.0


def validate(player: Player) -> None:
    """Raise ValueError with a message for the user if the settings cannot be saved."""
    name = player.name.strip()
    if not names.plain(name).strip():
        raise ValueError("Enter a player name.")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"The player name can have at most {MAX_NAME_LENGTH} characters.")
    if any(ord(ch) < 32 or ch in '"\\;' for ch in name):
        raise ValueError("The player name cannot contain quotes, backslashes or semicolons.")
    if not math.isfinite(player.sensitivity) or player.sensitivity <= 0:
        raise ValueError("Mouse sensitivity must be a positive number.")


def bundled_game_dirs() -> list[str]:
    """Game folders that ArenaHub has configs for."""
    root = paths.resource("cfg")
    if not root.is_dir():
        return []
    return sorted(
        folder.name
        for folder in root.iterdir()
        if all((folder / name).is_file() for name in CONFIG_FILES)
    )


def install(install_dir: Path) -> list[Path]:
    """Copy the configs that are missing into each installed game folder.

    Existing files are never replaced: they may hold the player's own changes.
    """
    written = []
    for game_dir in bundled_game_dirs():
        folder = install_dir / game_dir
        if not folder.is_dir():
            continue
        for name in CONFIG_FILES:
            target = folder / name
            if not target.exists():
                target.write_bytes(paths.resource("cfg", game_dir, name).read_bytes())
                written.append(target)
        for name in OBSOLETE:
            (folder / name).unlink(missing_ok=True)
    return written


def player_files(install_dir: Path) -> list[Path]:
    return [
        install_dir / game_dir / PLAYER_CFG
        for game_dir in bundled_game_dirs()
        if (install_dir / game_dir / PLAYER_CFG).is_file()
    ]


_ENTRY = r'^(\s*(?:seta?\s+)?{key}\s+)("[^"\r\n]*"|[^\s"/]+)([ \t]*)'


def read_value(text: str, key: str) -> str | None:
    """The value of a cvar in a config file, or None if it is not set there."""
    match = re.search(_ENTRY.format(key=re.escape(key)), text, re.IGNORECASE | re.MULTILINE)
    return match.group(2).strip('"') if match else None


def set_value(text: str, key: str, value: str) -> str:
    """Change a cvar's value in place, keeping alignment and comments; append it if missing."""
    pattern = re.compile(_ENTRY.format(key=re.escape(key)), re.IGNORECASE | re.MULTILINE)
    replacement = f'"{value}"'

    def replace(match: re.Match) -> str:
        old_value, padding = match.group(2), match.group(3)
        if padding:  # keep a trailing comment in its column
            padding = " " * max(1, len(old_value) + len(padding) - len(replacement))
        return match.group(1) + replacement + padding

    if pattern.search(text):
        return pattern.sub(replace, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + f"seta    {key:<16}{replacement}\n"


def format_sensitivity(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def read_player(install_dir: Path) -> Player | None:
    """The player settings saved in the installation (baseq3 first), if any."""
    for path in player_files(install_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        name = names.from_game(read_value(text, "name") or "")
        sensitivity = read_value(text, "sensitivity")
        try:
            return Player(name or Player.name, float(sensitivity or Player.sensitivity))
        except ValueError:
            return Player(name or Player.name)
    return None


def save_player(install_dir: Path, player: Player) -> list[Path]:
    """Write name and sensitivity into every player.cfg of the installation."""
    validate(player)
    install(install_dir)
    updated = []
    for path in player_files(install_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        new = set_value(text, "name", names.for_game(player.name.strip()))
        new = set_value(new, "sensitivity", format_sensitivity(player.sensitivity))
        if new != text:
            staged = path.with_name(path.name + ".tmp")
            staged.write_text(new, encoding="utf-8", newline="\n")
            staged.replace(path)
            updated.append(path)
    return updated
