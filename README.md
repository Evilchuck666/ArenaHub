# ArenaHub

**Quake III Arena, Team Arena and the classic mods, set up in one window.**

ArenaHub is a desktop installer and launcher for Quake III Arena on GNU/Linux,
Windows and macOS. It downloads your own Steam copy of the game, writes your CD
keys, installs the [Quake3e](https://github.com/ec-/Quake3e) engine and adds
the mods you choose. Then you play from the same window.

## What it installs

| Game | Source |
| --- | --- |
| **Quake III Arena** | Your Steam library (app 2200), through SteamCMD |
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
- **GNU/Linux:** SDL2 for Quake3e. SteamCMD also needs 32-bit glibc
  (Arch/Artix: `sdl2` and `lib32-glibc`; Debian/Ubuntu: `libsdl2-2.0-0` and
  `lib32gcc-s1`). Qt needs `libxkbcommon` and `libxkbcommon-x11`.
- **macOS on Apple Silicon:** Rosetta 2, because SteamCMD is an Intel binary
  (`softwareupdate --install-rosetta --agree-to-license`).

The ArenaHub executable bundles its own Python and Qt. You don't need to install
either one.

## How it works

1. Choose an installation folder, enter your Steam username, pick the mods and
   press **Install**.
2. ArenaHub asks for your Steam password. It logs in to Steam and requests the
   CD keys for Quake III Arena and Team Arena, just like *Manage → CD Keys* in
   the Steam client.
3. SteamCMD downloads Quake III Arena, then Team Arena if your account owns it
   (it is a separate Steam app). Steam may ask for a Steam Guard code a second
   time, because SteamCMD keeps its own session.
4. ArenaHub copies `baseq3` and `missionpack` into the folder, writes the keys to
   `baseq3/q3key` and `missionpack/q3key`, installs Quake3e and extracts the mods.
5. In the **Play** tab, pick a game and press **Play**. Your player name, mouse
   sensitivity and renderer (OpenGL or Vulkan) are applied on every launch.

If Steam returns no key, you can type it into the **CD keys** section yourself.
The keys only matter on servers that enforce authentication (`sv_strictauth 1`).

Everything lives in the installation folder. The engine runs with
`fs_basepath` and `fs_homepath` pointing there, so configs, demos and screenshots
stay in that folder too. SteamCMD is kept for later updates in:

- `~/.local/share/ArenaHub/steamcmd` on Linux
- `%LOCALAPPDATA%\ArenaHub\steamcmd` on Windows
- `~/Library/Application Support/ArenaHub/steamcmd` on macOS

### Your Steam account

ArenaHub never stores or logs your password or Steam Guard codes. The password
goes to Steam through the standard login flow, and to SteamCMD through its
terminal prompt. It is never passed as a command-line argument. SteamCMD may
remember its own login session.

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
  steam_helper.py  Steam client process that fetches CD keys (steam-next + gevent)
  core/            installation logic, no Qt: catalog, downloads, SteamCMD, keys, launcher
  gui/             Qt window and background worker
tests/             pytest suite; no network or Steam account needed
assets/icons/      application icon (regenerate with scripts/make_icons.py)
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
SteamCMD and Quake3e. The CD key request follows
[SteamKit2](https://github.com/SteamRE/SteamKit). Quake III Arena is a trademark of
id Software. The mods belong to their respective authors. ArenaHub is not
affiliated with id Software, Bethesda or Valve.
