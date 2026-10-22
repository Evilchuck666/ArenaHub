"""Dedicated servers: game types per mod, the maps on disk and the server config.

ArenaHub writes one config per start (arenahub-server.cfg in the mod folder)
and runs Quake3e's dedicated build with it. Map rotation uses the usual
"vstr" chain through nextmap, except where the mod ignores nextmap: OSP gets
its own map queue file and CPMA a custom mode and map lists (see _write_osp
and _write_cpma).
"""

from __future__ import annotations

import re
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

from . import engine, launcher
from .catalog import CPMA, OSP, QUAKE3, TEAM_ARENA, THREEWAVE, Game

CONFIG_NAME = "arenahub-server.cfg"
OSP_MAP_FILE = "arenahub-maps.txt"
CPMA_MODE = "ARENAHUB"
CPMA_CFGDIR = "cfg-arenahub"
CPMA_MAPLISTS = (
    "1v1maps.txt",
    "2v2maps.txt",
    "camaps.txt",
    "ctfmaps.txt",
    "ffamaps.txt",
    "mamaps.txt",
    "teammaps.txt",
)
"""Every map list CPMA reads; each mode reads one of them, and all get the rotation."""

BOT_NAMES = (
    "sarge", "visor", "ranger", "anarki", "xaero", "klesk", "hunter", "major", "doom", "orbb",
    "slash", "razor", "mynx", "keel", "lucy", "grunt", "bitterman", "uriel", "sorlag", "phobos",
    "tankjr", "wrack", "stripe", "bones", "crash", "daemia", "gorre", "hossman", "patriot",
    "angel", "cadavre", "biker",
)  # fmt: skip
"""The bots of Quake III Arena, which every mod here also has."""

DEFAULT_PORT = 27960
MAX_TEXT = 64


@dataclass(frozen=True)
class GameType:
    id: str
    """Stable key, used to remember the choice."""
    title: str
    value: int
    """g_gametype, or the "type" of a CPMA mode."""
    limit: str = "fraglimit"
    """Which score ends the match: fraglimit, capturelimit or roundlimit."""
    teams: bool = False
    """Played red against blue, so bots are split between the teams."""


FFA = GameType("ffa", "Free For All", 0)
TOURNEY = GameType("tourney", "Tournament (1v1)", 1)
TDM = GameType("tdm", "Team Deathmatch", 3, teams=True)
CTF = GameType("ctf", "Capture The Flag", 4, "capturelimit", teams=True)


@dataclass(frozen=True)
class ServerGame:
    game: Game
    gametypes: tuple[GameType, ...]
    notes: str = ""
    roundlimit_cvar: str = "roundlimit"
    max_bot_skill: int = 5
    """Quake III's bots go from 1 (I Can Win) to 5 (Nightmare!)."""
    default_bot_skill: int = 3


SERVER_GAMES: tuple[ServerGame, ...] = (
    ServerGame(QUAKE3, (FFA, TOURNEY, TDM, CTF)),
    ServerGame(
        TEAM_ARENA,
        (
            FFA,
            TOURNEY,
            TDM,
            CTF,
            GameType("oneflag", "One Flag CTF", 5, "capturelimit", teams=True),
            GameType("overload", "Overload", 6, "capturelimit", teams=True),
            GameType("harvester", "Harvester", 7, "capturelimit", teams=True),
        ),
    ),
    ServerGame(
        CPMA,
        (
            FFA,
            GameType("1v1", "1v1", 1),
            GameType("2v2", "2v2", 9, teams=True),
            TDM,
            CTF,
            GameType("ca", "Clan Arena", 5, "roundlimit", teams=True),
            GameType("ft", "Freeze Tag", 6, "roundlimit", teams=True),
            GameType("ctfs", "Capture Strike", 7, "roundlimit", teams=True),
            GameType("ntf", "NTF (classes)", 8, "capturelimit", teams=True),
        ),
        notes="CPMA does not rotate maps in 1v1: players change them by vote.",
        # CPMA's bots accept skills up to 100 (higher values are clamped to it).
        max_bot_skill=100,
        default_bot_skill=100,
    ),
    ServerGame(
        OSP,
        (
            FFA,
            GameType("1v1", "1v1", 1),
            TDM,
            CTF,
            GameType("ca", "Clan Arena", 5, "roundlimit", teams=True),
        ),
    ),
    ServerGame(
        THREEWAVE,
        (
            FFA,
            TOURNEY,
            TDM,
            GameType("ctf", "Threewave CTF", 4, "capturelimit", teams=True),
            GameType("oneflag", "One Flag CTF", 5, "capturelimit", teams=True),
            GameType("ctfs", "Capture Strike", 9, "capturelimit", teams=True),
            GameType("cctf", "Classic CTF", 10, "capturelimit", teams=True),
            GameType("arena", "Threewave Arena", 11, "roundlimit", teams=True),
        ),
        roundlimit_cvar="g_roundlimit",
    ),
)
"""Games that can host a server. Rocket Arena 3 cannot: its server code is a 32-bit library."""

CPMA_PHYSICS = ("CPM", "VQ3")


def server_game(game_id: str) -> ServerGame:
    for entry in SERVER_GAMES:
        if entry.game.id == game_id:
            return entry
    raise KeyError(game_id)


def gametype(entry: ServerGame, gametype_id: str) -> GameType:
    for item in entry.gametypes:
        if item.id == gametype_id:
            return item
    raise KeyError(gametype_id)


def hostable_games(install_dir: Path) -> list[ServerGame]:
    installed = launcher.installed_games(install_dir)
    return [entry for entry in SERVER_GAMES if entry.game in installed]


@dataclass
class ServerOptions:
    game_id: str
    gametype_id: str
    maps: list[str]
    hostname: str = "ArenaHub server"
    port: int = DEFAULT_PORT
    max_clients: int = 16
    timelimit: int = 15
    """Minutes; 0 means no time limit."""
    fraglimit: int = 30
    capturelimit: int = 8
    roundlimit: int = 7
    password: str = ""
    rcon_password: str = ""
    public: bool = False
    """Announce the server to the master servers (dedicated 2) instead of LAN only."""
    bots: int = 0
    """Bots added when the server starts; they stay when people join."""
    bot_skill: int = 3
    physics: str = "CPM"
    """CPMA only: CPM or VQ3 movement."""

    @property
    def entry(self) -> ServerGame:
        return server_game(self.game_id)

    @property
    def gametype(self) -> GameType:
        return gametype(self.entry, self.gametype_id)

    @property
    def score_limit(self) -> int:
        return getattr(self, self.gametype.limit)


_MAP_NAME = re.compile(r"[A-Za-z0-9_\-.+]+")


def validate(options: ServerOptions) -> None:
    """Raise ValueError with a message for the user if the server cannot start like this."""
    options.gametype  # noqa: B018 - raises KeyError for an unknown game or game type
    if not options.maps:
        raise ValueError("Add at least one map to the rotation.")
    for name in options.maps:
        if not _MAP_NAME.fullmatch(name):
            raise ValueError(f"Invalid map name: {name}")
    for label, text in (
        ("server name", options.hostname),
        ("password", options.password),
        ("RCON password", options.rcon_password),
    ):
        if len(text) > MAX_TEXT:
            raise ValueError(f"The {label} can have at most {MAX_TEXT} characters.")
        if any(ord(ch) < 32 or ch in '"\\;' for ch in text):
            raise ValueError(f"The {label} cannot contain quotes, backslashes or semicolons.")
    if not options.hostname.strip():
        raise ValueError("Enter a server name.")
    if not 1024 <= options.port <= 65535:
        raise ValueError("The port must be between 1024 and 65535.")
    if not 1 <= options.max_clients <= 64:
        raise ValueError("Max players must be between 1 and 64.")
    if options.bots > options.max_clients:
        raise ValueError("There cannot be more bots than player slots.")
    if not 1 <= options.bot_skill <= options.entry.max_bot_skill:
        raise ValueError(f"Bot skill must be between 1 and {options.entry.max_bot_skill}.")
    if options.physics not in CPMA_PHYSICS:
        raise ValueError(f"Unknown CPMA physics: {options.physics}")


def config_text(options: ServerOptions) -> str:
    """The console lines of arenahub-server.cfg; the last one loads the first map."""
    validate(options)
    entry, kind = options.entry, options.gametype
    cpma = entry.game is CPMA
    lines = [
        "// Written by ArenaHub each time the server starts: changes here are lost.",
        f'set sv_hostname "{options.hostname}"',
        f"set sv_maxclients {options.max_clients}",
        f'set g_password "{options.password}"',
        f'set rconpassword "{options.rcon_password}"',
        f"set bot_enable {1 if options.bots else 0}",
        # bot_minplayers would fill the server up to that many players, so bots
        # would leave as people join: the bots are added one by one below instead.
        "set bot_minplayers 0",
        f"set g_spSkill {options.bot_skill}",
    ]
    if cpma:
        lines += [
            f"set server_gameplay {options.physics}",
            f"set mode_start {CPMA_MODE}",
            f"set map_cfgdir {CPMA_CFGDIR}",
            "set map_rotate 1",
        ]
    else:
        limit_cvar = entry.roundlimit_cvar if kind.limit == "roundlimit" else kind.limit
        lines += [
            f"set g_gametype {kind.value}",
            f"set timelimit {options.timelimit}",
            f"set {limit_cvar} {options.score_limit}",
        ]
    if entry.game is OSP:
        lines += [
            f"set map_file {OSP_MAP_FILE}",
            "set map_queue 1",
            "set map_rotate 1",
            "set map_random 0",
            "set map_autoload 0",
            "set map_nocount 1",
        ]
    if entry.game is THREEWAVE:
        lines.append("set p_enablePortal 0")  # no voting portal between maps

    maps = options.maps
    if cpma or entry.game is OSP:
        lines.append(f"map {maps[0]}")
    else:
        for index, name in enumerate(maps):
            following = (index + 1) % len(maps)
            lines.append(
                f'set arenahub_map{index} "map {name}; set nextmap vstr arenahub_map{following}"'
            )
        lines.append("vstr arenahub_map0")
    # Run once the first map is loaded; bots stay connected across map changes.
    # In team modes each bot gets its team: the game would put them all in one,
    # because none has joined a team yet when the next one is added. Red gets the
    # odd one, so the first person to join (sent to the smaller team) evens them.
    for index in range(options.bots):
        bot = f"addbot {BOT_NAMES[index % len(BOT_NAMES)]} {options.bot_skill}"
        if kind.teams:
            bot += " red" if index % 2 == 0 else " blue"
        lines.append(bot)
    return "\n".join(lines) + "\n"


def write_config(install_dir: Path, options: ServerOptions) -> Path:
    """Write the server config (and CPMA's mode and map lists) into the installation."""
    text = config_text(options)
    folder = install_dir / options.entry.game.game_dir
    folder.mkdir(parents=True, exist_ok=True)
    if options.entry.game is CPMA:
        _write_cpma(folder, options)
    elif options.entry.game is OSP:
        _write_osp(folder, options)
    path = folder / CONFIG_NAME
    path.write_text(text, encoding="utf-8")
    return path


def _write_osp(folder: Path, options: ServerOptions) -> None:
    """OSP loads the next map from its map queue, not from nextmap.

    Each line is "map min_players max_players fraglimit capturelimit timelimit
    roundlimit"; -1 keeps the server's limits.
    """
    lines = [f"{name} 0 99 -1 -1 -1 -1" for name in options.maps]
    (folder / OSP_MAP_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_cpma(folder: Path, options: ServerOptions) -> None:
    """CPMA ignores nextmap and g_gametype: it plays modes and rotates through map lists.

    The custom mode sets the game type and limits. The map lists live in their own
    map_cfgdir, copied from cfg-maps so per-map settings keep working, with every
    list replaced by the rotation and no mapmodes.txt entries that would switch the
    mode on some maps.
    """
    kind = options.gametype
    mode = [f"type {kind.value}", f"timelimit {options.timelimit}", f"limit {options.score_limit}"]
    (folder / "modes").mkdir(exist_ok=True)
    (folder / "modes" / f"{CPMA_MODE}.cfg").write_text("\n".join(mode) + "\n", encoding="utf-8")

    cfgdir = folder / CPMA_CFGDIR
    if cfgdir.exists():
        shutil.rmtree(cfgdir)
    if (folder / "cfg-maps").is_dir():
        shutil.copytree(folder / "cfg-maps", cfgdir)
    cfgdir.mkdir(exist_ok=True)
    (cfgdir / "mapmodes.txt").write_text("[maps]\n", encoding="utf-8")
    rotation = "\n".join(options.maps) + "\n"
    for name in CPMA_MAPLISTS:
        (cfgdir / name).write_text(rotation, encoding="utf-8")


def search_dirs(game: Game) -> list[str]:
    """Game folders the engine reads for this game, like its own search path."""
    dirs = ["baseq3"]
    if game.game_dir != "baseq3":
        dirs.append(game.game_dir)
    return dirs


def available_maps(install_dir: Path, game: Game) -> list[str]:
    """Names of the maps the server can load for game, from .pk3 files and loose .bsp files."""
    found: set[str] = set()
    for game_dir in search_dirs(game):
        folder = install_dir / game_dir
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if path.suffix.lower() == ".pk3" and path.is_file():
                found.update(pk3_maps(path))
        maps_dir = folder / "maps"
        if maps_dir.is_dir():
            found.update(p.stem.lower() for p in maps_dir.glob("*.bsp"))
    return sorted(found)


def pk3_maps(path: Path) -> set[str]:
    """Map names inside a .pk3, read from its ZIP central directory.

    Some old .pk3 files have extra fields that Python's zipfile rejects but the
    engine ignores, so only the member names are read here, by hand.
    """
    maps = set()
    for name in _zip_names(path):
        lower = name.lower().replace("\\", "/")
        if lower.startswith("maps/") and lower.endswith(".bsp") and lower.count("/") == 1:
            maps.add(lower[5:-4])
    return maps


def _zip_names(path: Path) -> list[str]:
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 65557))
            tail = f.read()
            end = tail.rfind(b"PK\x05\x06")
            if end < 0:
                return []
            count, cd_size, cd_offset = struct.unpack_from("<HII", tail, end + 10)
            f.seek(cd_offset)
            directory = f.read(cd_size)
    except OSError:
        return []

    names, pos = [], 0
    for _ in range(count):
        if directory[pos : pos + 4] != b"PK\x01\x02":
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", directory, pos + 28)
        names.append(directory[pos + 46 : pos + 46 + name_len].decode("cp437"))
        pos += 46 + name_len + extra_len + comment_len
    return names


def command(install_dir: Path, options: ServerOptions) -> list[str]:
    """Command line of the dedicated server; the config written by write_config does the rest."""
    exe = engine.server_executable(install_dir)
    if exe is None:
        raise FileNotFoundError("The Quake3e dedicated server is not installed in this folder")
    return [
        str(exe),
        *launcher.arguments(install_dir, options.entry.game),
        "+set",
        "dedicated",
        "2" if options.public else "1",
        "+set",
        "net_port",
        str(options.port),
        "+exec",
        CONFIG_NAME,
    ]
