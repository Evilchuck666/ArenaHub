"""What ArenaHub can install: the Steam games and the mods, with pinned downloads."""

from __future__ import annotations

from dataclasses import dataclass, field

QUAKE3_APP_ID = 2200
"""Steam app for Quake III Arena (depot 2201: baseq3)."""

TEAM_ARENA_APP_ID = 2350
"""Steam app for Team Arena (depot 2351: missionpack), installed in the same folder.

Buying Quake III Arena today grants both apps, but each one is downloaded on its own.
"""

QUAKE3_DIRS = ("baseq3", "missionpack")
"""Folders copied from the Steam depot into the installation."""

MIRRORSERVICE = "https://www.mirrorservice.org/sites/quakeunity.com/modifications"


@dataclass(frozen=True)
class Rule:
    """Which members of an archive to extract, and where.

    Patterns are shell-style and matched against lowercase member paths; a pattern
    without '/' matches the file name in any folder.
    """

    target: str = ""
    include: tuple[str, ...] = ("*",)
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class Download:
    filename: str
    urls: tuple[str, ...]
    sha256: str
    size: int
    rule: Rule = Rule()


@dataclass(frozen=True)
class Game:
    id: str
    title: str
    game_dir: str
    description: str
    marker: str
    """File (relative to the installation) whose presence means the game is installed."""
    downloads: tuple[Download, ...] = field(default=())
    requires_team_arena: bool = False
    notes: str = ""

    @property
    def is_mod(self) -> bool:
        return bool(self.downloads)


WINDOWS_ONLY = ("*.exe", "*.bat", "*.dll", "*.so", "thumbs.db")

QUAKE3 = Game(
    id="baseq3",
    title="Quake III Arena",
    game_dir="baseq3",
    description="The original game, from your Steam library.",
    marker="baseq3/pak0.pk3",
)

TEAM_ARENA = Game(
    id="missionpack",
    title="Quake III: Team Arena",
    game_dir="missionpack",
    description="The official expansion, when your Steam copy includes it.",
    marker="missionpack/pak0.pk3",
)

CPMA = Game(
    id="cpma",
    title="Challenge ProMode Arena",
    game_dir="cpma",
    description="CPMA 1.53 with the full CPMA map pack.",
    marker="cpma/z-cpma-pak153.pk3",
    downloads=(
        Download(
            filename="cpma-1.53-nomaps.zip",
            urls=(
                "https://cdn.playmorepromode.com/files/cpma/cpma-1.53-nomaps.zip",
                "https://playmorepromode.com/files/cpma/cpma-1.53-nomaps.zip",
            ),
            sha256="edfffa0c1a0375ba46a5b42257a168fb15086712245733526ab2d9ccdd821ca0",
            size=16946806,
        ),
        Download(
            filename="cpma-mappack-full.zip",
            urls=(
                "https://cdn.playmorepromode.com/files/cpma-mappack-full.zip",
                "https://playmorepromode.com/files/cpma-mappack-full.zip",
            ),
            sha256="5db933fc92c41f2e0941ab65725586d4d0c30fe84727427bb6b265e4d941a226",
            size=122543145,
            rule=Rule(target="baseq3", include=("*.pk3",)),
        ),
    ),
)

OSP = Game(
    id="osp",
    title="OSP Tourney DM/CA/CTF",
    game_dir="osp",
    description="Orange Smoothie Productions 1.03a.",
    marker="osp/zz-osp-pak3.pk3",
    downloads=(
        Download(
            filename="osp-Quake3-1.03a_full.zip",
            urls=(
                "https://osp.dget.cc/orangesmoothie/downloads/osp-Quake3-1.03a_full.zip",
                f"{MIRRORSERVICE}/osp/osp-Quake3-1%5b1%5d.03a_full.zip",
            ),
            sha256="af9a184134733fc24c308b4f8790932d30dc70b6c8a36e050223ba16ba2ac2b3",
            size=55882759,
            rule=Rule(include=("osp/*",), exclude=WINDOWS_ONLY),
        ),
    ),
)

ROCKET_ARENA = Game(
    id="arena",
    title="Rocket Arena 3",
    game_dir="arena",
    description="Rocket Arena 3 1.80 and its arena maps.",
    marker="arena/vm.pk3",
    downloads=(
        Download(
            filename="ra3180.zip",
            urls=(f"{MIRRORSERVICE}/rocketarena3/ra3180.zip",),
            sha256="95d590cb516b01355ef38ccf54427961c69b0a596b41a6137135451891533a29",
            size=182481366,
            rule=Rule(include=("arena/*",), exclude=(*WINDOWS_ONLY, "*.sh")),
        ),
    ),
    notes=(
        "Rocket Arena 3 ships its server code only as 32-bit native libraries, so "
        "Quake3e can join Rocket Arena servers but cannot host local matches."
    ),
)

THREEWAVE = Game(
    id="threewave",
    title="Threewave CTF",
    game_dir="threewave",
    description="Threewave CTF 1.6 with the 1.7 update and its map packs.",
    marker="threewave/pak05.pk3",
    downloads=(
        Download(
            filename="threewave_16_full.zip",
            urls=(f"{MIRRORSERVICE}/threewavectf/threewave_16_full.zip",),
            sha256="c3cb1412cafc61a475ad2f1e93ecf47d7e2f979d973ce82b4a50da3101eca27d",
            size=187896825,
            rule=Rule(exclude=WINDOWS_ONLY),
        ),
        Download(
            filename="threewave_17_update.zip",
            urls=(f"{MIRRORSERVICE}/threewavectf/threewave_17_update.zip",),
            sha256="0fff6a66822c422cb9f6cca0139fa11048fef414c7dd839c50fbcbda80a44433",
            size=6139861,
            rule=Rule(exclude=WINDOWS_ONLY),
        ),
    ),
)

GAMES: tuple[Game, ...] = (QUAKE3, TEAM_ARENA, CPMA, OSP, ROCKET_ARENA, THREEWAVE)
MODS: tuple[Game, ...] = tuple(game for game in GAMES if game.is_mod)


def game_by_id(game_id: str) -> Game:
    for game in GAMES:
        if game.id == game_id:
            return game
    raise KeyError(game_id)
