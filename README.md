# ArenaHub

**Quake III Arena, Team Arena and the classic mods, set up in one window.**

ArenaHub is a desktop installer and launcher for Quake III Arena on GNU/Linux,
Windows and macOS. It downloads your own Steam copy of the game, writes your CD
keys, installs the [Quake3e](https://github.com/ec-/Quake3e) engine and adds
four classic mods. Then you play from the same window.

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

## What you need

- A **Steam account that owns Quake III Arena**. Team Arena is optional.
- An Internet connection and about 2 GB of free space.
- **GNU/Linux:** SDL2 for Quake3e (Arch/Artix: `sdl2`; Debian/Ubuntu:
  `libsdl2-2.0-0`). Qt needs `libxkbcommon` and `libxkbcommon-x11`.

The ArenaHub executable bundles its own Python and Qt. You don't need to install
either one.

## How it works

1. Choose an installation folder, enter your Steam username and press
   **Install**. All the mods in the table above are always installed.
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
   Quake3e, extracts the mods and adds the game configs (see below).
6. In the **Play** tab, pick a game and press **Play**, with the OpenGL or
   Vulkan renderer.

If Steam returns no key, you can type it into the **CD keys** section yourself.
The keys only matter on servers that enforce authentication (`sv_strictauth 1`).

Everything lives in the installation folder. The engine runs with
`fs_basepath` and `fs_homepath` pointing there, so configs, demos and screenshots
stay in that folder too.

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

### Your Steam account

ArenaHub never stores or logs your password or Steam Guard codes. They only go
to Steam, through its standard login flow, and are never passed as
command-line arguments. ArenaHub does not keep a Steam session, so every
installation or update asks you to log in again.

## Development

You need nothing but this repository. The setup script installs
[uv](https://docs.astral.sh/uv/) if it is missing, then a uv-managed Python and
every dependency into `.venv/`. It never uses the system Python.

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
  gui/             Qt window and background worker
tests/             pytest suite; no network or Steam account needed
assets/icons/      application icon (regenerate with scripts/make_icons.py)
assets/links/      .desktop templates for the GNU/Linux shortcuts
assets/cfg/        game configs copied into each game folder
```

The Steam helper runs as a separate process, which is the same executable
started with `--steam-helper`. steam-next needs gevent's monkey-patching, and
that does not mix with Qt in a single process.

### Building

```bash
uv run pyinstaller ArenaHub.spec --clean --noconfirm
uv run python scripts/package.py   # verify the binary from an empty folder, then archive it
```

`scripts/package.py` copies the executable to a temporary folder and runs its
Steam helper self-test and a GUI smoke test there. It then packs the
executable as `dist/ArenaHub-<system>-<arch>.tar.gz` (Linux) or `.zip`
(Windows, macOS).

PyInstaller does not cross-compile, so build on each target system and
architecture. The result is a single executable (`dist/ArenaHub` or
`dist/ArenaHub.exe`) that needs no Python on the target machine.

### GitHub Actions

`.github/workflows/build.yml` builds, tests and packages ArenaHub for Linux
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

## Credits

Built with Qt6 / PySide6, [steam-next](https://github.com/fabieu/steam-next),
zstandard and Quake3e. The CD key request and the depot chunk formats follow
[SteamKit2](https://github.com/SteamRE/SteamKit). Quake III Arena is a trademark of
id Software. The mods belong to their respective authors. ArenaHub is not
affiliated with id Software, Bethesda or Valve.
