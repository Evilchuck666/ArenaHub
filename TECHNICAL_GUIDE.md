# ArenaHub technical guide

[Back to the project overview](README.md)

ArenaHub is a Quake III Arena installer and launcher built with **Qt6 /
PySide6**. It downloads the game from Steam, writes the CD keys, installs the
[Quake3e](https://github.com/ec-/Quake3e) engine, four classic mods and 47
community map packs, and plays or hosts them from one window.

## Standalone application

The release package holds a **single executable** with Python, Qt6, the icons,
the game configs and the map thumbnails inside. Users don't need to install
Python or Qt. Extract the package and open `ArenaHub` (GNU/Linux, macOS) or
`ArenaHub.exe` (Windows).

PyInstaller builds it in `onefile` mode. At startup it extracts its libraries
and resources to a temporary folder and removes them when it closes, which adds
some startup time. On GNU/Linux that folder must allow the extracted libraries
to run. Each operating system and architecture needs its own build. See the
[PyInstaller documentation](https://pyinstaller.org/en/stable/operating-mode.html).

**Code → Download ZIP** downloads the source code, not the application.

### System requirements

- A Steam account that owns Quake III Arena. Team Arena is optional.
- An Internet connection and about 3 GB of free space.
- **GNU/Linux:** SDL2 for Quake3e (Arch/Artix: `sdl2`; Debian/Ubuntu:
  `libsdl2-2.0-0`). Qt needs `libxkbcommon` and `libxkbcommon-x11`.

## What it installs

| Game | Source |
| --- | --- |
| **Quake III Arena** | Your Steam library (app 2200) |
| **Quake III: Team Arena** | Your Steam library (app 2350), when your account owns it |
| **Challenge ProMode Arena** 1.53 + full map pack | [playmorepromode.com](https://playmorepromode.com/downloads) |
| **OSP Tourney DM/CA/CTF** 1.03a | [osp.dget.cc](https://osp.dget.cc/), mirrored by mirrorservice.org |
| **Rocket Arena 3** 1.80 | mirrorservice.org (QuakeUnity archive) |
| **Threewave CTF** 1.6 + 1.7 update | mirrorservice.org (QuakeUnity archive) |

Every mod download is pinned to a SHA-256 checksum. Windows-only executables in
the archives (old engines, server tools) are not installed.

Rocket Arena 3 only ships its server code as 32-bit native libraries. With
Quake3e you can join Rocket Arena servers, but you cannot host local matches.

### Maps

ArenaHub also adds 47 community map packs (about 360 MB) to `baseq3`, so every
mod can load them. The **Maps** tab lists them with a levelshot thumbnail,
their authors and map names. They are defined in `src/arenahub/core/maps.py`,
each one pinned to a SHA-256 checksum:

- 44 come from [lvlworld.com](https://lvlworld.com). Its downloads need a
  short-lived token, which ArenaHub requests the same way the site's download
  page does. It then takes the `.pk3` out of the release archive.
- The original *OverWhelming Hostility* (`auh3dm1`) and the Dreamcast map pack
  (`dc-mappack`) are not on lvlworld in this exact version, and neither is
  [High Quality Quake](https://www.moddb.com/mods/high-quality-quake) 3.7, a
  graphics pack. They come from the backup copy only.
- `assets/maps/` holds a backup copy of every pack. ArenaHub downloads it from
  this repository's `main` branch when lvlworld fails or serves another version.
  These files are not bundled into the executable.

A map pack that cannot be downloaded is reported as a warning at the end of the
installation. It does not stop the installation.

The thumbnails in `assets/levelshots/` are bundled into the executable, so the
list shows them before anything is installed. After adding a map pack to
`maps.py` and `assets/maps/`, regenerate them with
`uv run python scripts/make_thumbnails.py`.

The `map_cpm*` packs come with the CPMA map pack, and `q3wpak0-4` and
`derean01` come with Threewave CTF.

## How it works

The window follows the layout of
[QuakeBundle](https://github.com/Evilchuck666/QuakeBundle) in Quake III
Arena's colours: blood red for the main actions and ember gold for highlights.
The **Install**, **Play**, **Server** and **Maps** tabs are on the left. The
**Activity Center** on the right shows the installation steps, the progress,
the activity log and a button to open the game folder.

1. In the **Install** tab, choose an installation folder, enter your Steam
   username and press **Install**. All the mods in the table above are always
   installed. The other tabs work on the folder chosen there.
2. ArenaHub asks for your Steam password and, if your account uses Steam Guard,
   for its code. That single login is all it needs.
3. It requests the CD keys for Quake III Arena and Team Arena, just like
   *Manage → CD Keys* in the Steam client.
4. It downloads `baseq3` from Quake III Arena and `missionpack` from Team Arena,
   if your account owns it (it is a separate Steam app), straight from Steam's
   content servers into the folder. Every file is checked against Steam's
   SHA-1, and files that already match are not downloaded again, so **Update**
   only verifies the game. Existing `.cfg` files are never replaced.
5. It writes the keys to `baseq3/q3key` and `missionpack/q3key`, installs
   Quake3e, extracts the mods, adds the maps and writes the game configs (see
   below). Map packs that are already in place and intact are not downloaded
   again.
6. In the **Play** tab, pick a game and press **Play**, with the OpenGL or
   Vulkan renderer.

If Steam returns no key, the **Play** tab shows a **CD keys** section where you
can type it yourself. It only appears while an installed game lacks its key.
The keys only matter on servers that enforce authentication (`sv_strictauth 1`).

Everything lives in the installation folder. The engine runs with
`fs_basepath` and `fs_homepath` pointing there, so configs, demos and screenshots
stay in that folder too.

### Your Steam account

ArenaHub never stores or logs your password or Steam Guard codes. They only go
to Steam, through its standard login flow, and are never passed as
command-line arguments. ArenaHub does not keep a Steam session, so every
installation or update asks you to log in again.

There is no SteamCMD. The Steam client runs in a helper process, which is the
same executable started with `--steam-helper`. steam-next needs gevent's
monkey-patching, and that does not mix with Qt in a single process. The CD key
request and the depot chunk formats follow
[SteamKit2](https://github.com/SteamRE/SteamKit).

### Game configs

Every game gets three config files in its folder, as in QuakeBundle:

| File | What it holds |
| --- | --- |
| `autoexec.cfg` | Quake3e runs it at every start. It only runs the two files below. |
| `game.cfg` | Key bindings, HUD, graphics, sound and server settings, in commented sections. |
| `player.cfg` | Your name, mouse sensitivity and player model. |

When you change your name or sensitivity in the **Play** tab, ArenaHub writes
them straight into every `player.cfg` and leaves the rest of each file as it is.
It only adds config files that are missing, so your own edits survive updates.
The originals live in [`assets/cfg/`](assets/cfg/).

Names can use Quake III colour codes: `^` followed by a digit colours the text
after it (`^1` red, `^2` green, `^3` yellow, `^4` blue, `^5` cyan, `^6` magenta,
`^7` white, `^0` black). The buttons next to the name insert them, and the
preview shows the name as the game draws it. If the name doesn't end in white,
ArenaHub adds `^7` to the end of the name it saves in `player.cfg`. That way kill
messages and other text after the name don't take its colour.

In the mods, teammates and enemies get fixed, easy-to-spot models: teammates
look like Ranger and enemies like a bright Tank Jr. CPMA, OSP and Threewave use
CPMA's bright "pm" skins. Rocket Arena 3 has no such skins, so it paints its own
with colors instead (white teammates, green enemies). Each mod's `game.cfg` has
these settings in its last section.

### Shortcuts

With **Create shortcuts** checked, ArenaHub adds one shortcut per installed
game. Each one starts Quake3e directly, with the renderer chosen at install
time, so ArenaHub does not need to be running:

| System | Shortcut |
| --- | --- |
| GNU/Linux | `~/.local/share/applications/arenahub-<game>.desktop`, in the application menu. It is made from the template in [`assets/links/`](assets/links/), which ships inside ArenaHub as in QuakeBundle, so no download is needed. The templates also explain how to install a shortcut by hand. |
| macOS | `~/Applications/<Game>.app`, a small application built on Automator's application stub, with the ArenaHub icon. It opens without Terminal. |
| Windows | `<Game>.lnk` on your Desktop, including a Desktop redirected to OneDrive. |

Installing again replaces the shortcuts. If one cannot be created, the
installation still finishes and reports a warning.

## Running a server

The **Server** tab starts Quake3e's dedicated server (`quake3e.ded`) for
Quake III Arena, Team Arena, CPMA, OSP or Threewave. Choose the mod, the game
type, the time limit and the frag, capture or round limit (whichever the game
type uses), the server name, port, player slots, bots, passwords, and whether
to list the server on the Internet master servers. Then build the map rotation
from the maps installed for that mod, in the order they should be played, or
press **Shuffle** for a random order. A map added to the rotation leaves the
list of installed maps, so it cannot be added twice.

| Mod | Game types |
| --- | --- |
| Quake III Arena | Free For All, Tournament, Team Deathmatch, CTF |
| Team Arena | the above, plus One Flag CTF, Overload and Harvester |
| CPMA | FFA, 1v1, 2v2, TDM, CTF, Clan Arena, Freeze Tag, Capture Strike, NTF; CPM or VQ3 physics |
| OSP | FFA, 1v1, TDM, CTF, Clan Arena |
| Threewave CTF | FFA, Tournament, TDM, Threewave CTF, One Flag CTF, Capture Strike, Classic CTF, Threewave Arena |

Rocket Arena 3 is missing because Quake3e cannot load its 32-bit server code.

The bots are added when the server starts and stay when people join, also
across map changes. ArenaHub does not use `bot_minplayers`, which removes bots
as players arrive. In team modes the bots are split between red and blue, with
the odd one on red, so the first person to join evens the teams. With **Humans
vs bots**, a team-mode option, every bot plays on red and people on blue: they
join blue automatically, and anyone who joins red is moved to blue
(`forceteam`, or `putblue` in CPMA) while the server runs. On Windows, where
ArenaHub cannot send commands to the server, nobody is moved. Bot skill goes
from 1 (*I Can Win*) to 5 (*Nightmare!*), except in CPMA, whose bots accept
skills up to 100. CPMA starts at 100, and each mod remembers its own value.

**Start server** writes `arenahub-server.cfg` into the mod folder and runs the
server with it. Each mod rotates maps its own way:

- Quake III Arena, Team Arena and Threewave use the usual `nextmap` chain.
  Threewave's voting portal is turned off.
- OSP gets its own map queue, `osp/arenahub-maps.txt`.
- CPMA ignores `nextmap` and `g_gametype`. ArenaHub writes a custom mode,
  `cpma/modes/ARENAHUB.cfg`, and map lists in `cpma/cfg-arenahub/`, a copy of
  `cfg-maps/` whose map lists hold the rotation. CPMA does not rotate maps in
  1v1: players change them by vote.

As in any Quake III server, the next map loads when the intermission ends. In
Quake III Arena and Team Arena that takes a human player pressing fire
(ready); bots alone never end it. OSP and CPMA move on by themselves.

The server's console output goes to the activity log on the right. You
can type server commands such as `status`, `map q3dm17` or `kick <name>`.
**Join** starts the game connected to your server. **Stop server** sends
`quit`, and the server is closed if it does not stop. Installing and changing
the folder are disabled while the server runs, and closing ArenaHub stops it.
On Windows the server shows its console in its own window, so its output does
not reach the activity log and the command field is hidden. For players on the
Internet, forward the UDP port to your computer in your router.

## Development and builds

### Development environment

You need nothing but this repository. The setup script installs
[uv](https://docs.astral.sh/uv/) if it is missing, then a uv-managed Python
3.13 and every dependency into `.venv/`. It never uses the system Python.

| System | Command |
| --- | --- |
| GNU/Linux | `./scripts/setup_linux.sh` |
| macOS | `./scripts/setup_macos.sh` |
| Windows | `scripts\setup_windows.bat` |

```bash
uv run arenahub                                        # run from source
python3 run.py                                         # same; any Python hands over to .venv
uv run pytest                                          # tests
uv run ruff check src tests scripts                    # lint
uv run pyinstaller ArenaHub.spec --clean --noconfirm   # single-file build in dist/
```

Open `ArenaHub.code-workspace` in VS Code. The workspace already points at
`.venv`, includes a debug configuration (F5) and has tasks for running, testing
and building.

Add dependencies with `uv add <package>` so that `pyproject.toml` and `uv.lock`
stay in sync. If a new package is loaded dynamically, declare it in
`ArenaHub.spec`: list it in `REQUIRED` and add it to `hiddenimports` or `datas`.
The build stops if something in `REQUIRED` cannot be imported.

### Project layout

```text
src/arenahub/
  __main__.py      entry point (GUI, --smoke-test, --steam-helper)
  steam_helper.py  Steam client process: login, CD keys, downloads (steam-next + gevent)
  steam_depots.py  depot download from Steam's content servers (runs in the helper)
  core/            installation logic, no Qt: catalog, downloads, Steam, keys, launcher
  gui/             Qt window, theme and background worker
tests/             pytest suite; no network or Steam account needed
assets/icons/      application icon (regenerate with scripts/make_icons.py), header emblem, ui/ theme icons
assets/links/      .desktop templates for the GNU/Linux shortcuts
assets/cfg/        game configs copied into each game folder
assets/maps/       backup copy of the map packs (downloaded, not bundled)
assets/levelshots/ map thumbnails for the Maps tab (regenerate with scripts/make_thumbnails.py)
```

### Building

```bash
uv run pyinstaller ArenaHub.spec --clean --noconfirm
uv run python scripts/package.py   # verify the binary from an empty folder, then archive it
```

`scripts/package.py` copies the executable to a temporary folder and runs its
Steam helper self-test and a GUI smoke test there. It then packs the
executable as `dist/ArenaHub-<system>-<arch>.tar.gz` (GNU/Linux) or `.zip`
(Windows, macOS). `--verify-only` runs the checks without creating the archive.

PyInstaller does not cross-compile, so build on each target system and
architecture. The result is a single executable (`dist/ArenaHub` or
`dist/ArenaHub.exe`) that needs no Python on the target machine. On macOS it is
a standalone binary, not an `.app`.

### GitHub Actions

`.github/workflows/release.yml` builds, tests and packages ArenaHub for GNU/Linux
x64, Windows x64, macOS Intel and macOS Apple Silicon. It is **disabled by
default**:

- **Pushes to `main` and pull requests** only build when the repository variable
  `ARENAHUB_CI` is `true` (*Settings → Secrets and variables → Actions →
  Variables*). Otherwise the run is skipped and uses no minutes.
- **Actions → Build desktop app → Run workflow** always works. Leave the version
  empty to just build; the packages are attached to the run as artifacts.
  Enter a version such as `1.0.0` to also publish a GitHub release with the
  four packages and a `SHA256SUMS.txt`.

To release, bump `__version__` in `src/arenahub/__init__.py` first: the
workflow refuses a version that doesn't match it, or one whose tag already
exists. The packages are not signed, so macOS Gatekeeper and Windows
SmartScreen will warn on first launch.

## Verification

```bash
uv run ruff check src tests scripts && uv run ruff format --check src tests scripts
uv run pytest
uv run arenahub --smoke-test
uv run python scripts/package.py --verify-only   # checks the frozen binary
```

On headless GNU/Linux, prefix the GUI commands with `QT_QPA_PLATFORM=offscreen`.
To save a window preview, run `uv run arenahub --smoke-test --screenshot preview.png`.

The tests use synthetic files and processes, with no network access, credentials
or game downloads. A real Steam login (including Steam Guard), the native
libraries and an actual game session need to be checked by hand on each
platform.

## Credits

Built with Qt6 / PySide6, [steam-next](https://github.com/fabieu/steam-next),
zstandard and Quake3e. The CD key request and the depot chunk formats follow
[SteamKit2](https://github.com/SteamRE/SteamKit). Quake III Arena is a trademark of
id Software. The mods and maps belong to their respective authors; most maps
are downloaded from [lvlworld.com](https://lvlworld.com). ArenaHub is not
affiliated with id Software, Bethesda or Valve.
