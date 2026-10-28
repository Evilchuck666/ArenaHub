# 🎮 ArenaHub

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20GNU%2FLinux%20%7C%20macOS-blue)
![Python](https://img.shields.io/badge/python-3.13-blue)
![PySide6](https://img.shields.io/badge/PySide6-%3E%3D6.8-blue)
![Requires](https://img.shields.io/badge/requires-Quake%20III%20Arena%20on%20Steam-blue)
[![License](https://img.shields.io/badge/license-GPLv3-green)](LICENSE)
[![Latest release](https://img.shields.io/github/v/release/Evilchuck666/ArenaHub?label=download&sort=semver)](https://github.com/Evilchuck666/ArenaHub/releases/latest)
[![Build and tests](https://github.com/Evilchuck666/ArenaHub/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/Evilchuck666/ArenaHub/actions/workflows/release.yml)

**Quake III Arena, Team Arena and the classic mods, set up in one window.**

ArenaHub is a desktop installer and launcher for Quake III Arena. It downloads
your own Steam copy of the game, installs the [Quake3e](https://github.com/ec-/Quake3e)
engine with four classic mods and a collection of community maps, and lets you
play or run your own server on Windows, GNU/Linux or macOS.

## 🧩 Why ArenaHub?

Getting Quake III Arena ready to play takes several separate jobs: downloading
the game from Steam, finding your CD keys, choosing a modern engine, tracking
down mods and maps that are scattered across old websites, and editing config
files.

ArenaHub does all of that for you. Choose a folder, sign in to Steam once and
press **Install**. Then set your player name, pick a game and play, or start a
dedicated server, from the same window.

## ⚔️ What you can play

| Game | What it is |
| --- | --- |
| **Quake III Arena** | The original game, from your Steam library. |
| **Quake III: Team Arena** | The official expansion, when your account owns it. |
| **Challenge ProMode Arena** 1.53 | The competitive mod, with its full map pack. |
| **OSP Tourney DM/CA/CTF** 1.03a | The classic tournament mod. |
| **Rocket Arena 3** 1.80 | Round-based arena play. You can join servers, but not host them. |
| **Threewave CTF** 1.6 + 1.7 | The classic Capture the Flag mod. |

ArenaHub also adds **47 community map packs** that every mod can load, most of
them from [lvlworld.com](https://lvlworld.com).

## ✨ What it does

- Downloads the game straight from Steam, with a single login and Steam Guard
  support in the window.
- Requests your CD keys from Steam and writes them for you.
- Installs Quake3e, the mods and the map packs, each download checked against a
  SHA-256 checksum.
- Lets you set your player name, with Quake III colour codes and a live
  preview, and your mouse sensitivity.
- Plays with the OpenGL or Vulkan renderer.
- Runs a dedicated server with game type, limits, bots and a map rotation you
  build from the installed maps.
- Shows installation progress and an activity log.
- Keeps your own config edits when you update.
- Creates shortcuts that start each game without opening ArenaHub.

## 🚀 Getting started

1. Download the package for your system from the
   [latest release](https://github.com/Evilchuck666/ArenaHub/releases/latest).
2. Extract the package and open **ArenaHub** (`ArenaHub.exe` on Windows).
3. In the **Install** tab, choose a folder, enter your Steam username and press
   **Install**.
4. Enter your Steam password and, if asked, your Steam Guard code.
5. Once installation finishes, open the **Play** tab, pick a game and press
   **Play**.

## 📥 Download

| Platform | Latest stable release |
| --- | --- |
| GNU/Linux x64 | [Download](https://github.com/Evilchuck666/ArenaHub/releases/latest/download/ArenaHub-linux-x64.tar.gz) |
| Windows x64 | [Download](https://github.com/Evilchuck666/ArenaHub/releases/latest/download/ArenaHub-windows-x64.zip) |
| macOS Intel | [Download](https://github.com/Evilchuck666/ArenaHub/releases/latest/download/ArenaHub-macos-x64.zip) |
| macOS Apple Silicon | [Download](https://github.com/Evilchuck666/ArenaHub/releases/latest/download/ArenaHub-macos-arm64.zip) |

[Release notes](https://github.com/Evilchuck666/ArenaHub/releases/latest)

The packages are not signed, so macOS Gatekeeper and Windows SmartScreen warn
the first time you open them.

## 📋 What you need

- A **Steam account that owns Quake III Arena**. Team Arena is optional.
- An **Internet connection** and about **3 GB** of free space.
- A **Windows, GNU/Linux or macOS** system. On GNU/Linux, Quake3e needs SDL2;
  see the [technical guide](TECHNICAL_GUIDE.md#system-requirements).

The application bundles its own Python and Qt, so you don't need to install
them. The game, the engine, the mods and the maps are downloaded during
installation.

## 🔐 Your Steam account

ArenaHub never stores or logs your password or Steam Guard codes. They only go
to Steam, through its standard login flow. ArenaHub does not keep a Steam
session, so every installation or update asks you to log in again.

## 📚 Learn more

To develop from a source checkout, run the setup script for your system. It
installs [uv](https://docs.astral.sh/uv/) if needed, a uv-managed Python and
every dependency, without touching the system Python:

```sh
./scripts/setup_linux.sh      # or ./scripts/setup_macos.sh, scripts\setup_windows.bat
uv run arenahub
```

- [Technical guide](TECHNICAL_GUIDE.md): how the installation works, game
  configs, shortcuts, the dedicated server, map sources, building from source,
  releases and verification.

Built with **Qt6 / PySide6**, [steam-next](https://github.com/fabieu/steam-next)
and **Quake3e**. Quake III Arena is a trademark of id Software. The mods and
maps belong to their respective authors. ArenaHub is not affiliated with id
Software, Bethesda or Valve.
