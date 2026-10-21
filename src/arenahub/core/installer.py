"""The installation as a whole: Steam data, CD keys, engine and mods."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import engine, launcher, net, q3key, steam_keys, steamcmd
from .archive import extract, merge_tree
from .catalog import QUAKE3, QUAKE3_APP_ID, QUAKE3_DIRS, TEAM_ARENA, TEAM_ARENA_APP_ID, game_by_id
from .context import Context, TaskError

STAGING = ".arenahub-staging"
REQUIRED_SPACE = 2 * 1024**3  # game ~500 MiB + mod archives ~570 MiB + extracted mods


@dataclass
class InstallOptions:
    install_dir: Path
    username: str = ""
    password: str = ""
    steam: bool = True
    """Download (or verify) Quake III Arena from Steam and fetch the CD keys."""
    mods: list[str] = field(default_factory=list)
    shortcuts: bool = False
    renderer: engine.Renderer = engine.Renderer.OPENGL


@dataclass
class InstallReport:
    keys: dict[str, str] = field(default_factory=dict)
    """game_dir -> key written to its q3key."""
    warnings: list[str] = field(default_factory=list)
    shortcuts: list[Path] = field(default_factory=list)


def install(ctx: Context, options: InstallOptions) -> InstallReport:
    install_dir = options.install_dir.expanduser().resolve()
    report = InstallReport()

    _prepare(install_dir, options)
    # Downloads stay in staging until everything succeeded, so a retry reuses them.
    staging = install_dir / STAGING
    downloads = staging / "downloads"

    if options.steam:
        keys = _fetch_keys(ctx, options)
        _download_quake3(ctx, options, staging)
        _write_keys(ctx, install_dir, keys, report)
    elif not (install_dir / QUAKE3.marker).is_file():
        raise TaskError("Quake III Arena is not installed in this folder yet.")

    ctx.stage("Installing Quake3e")
    engine.install(ctx, install_dir, downloads)

    for mod_id in options.mods:
        _install_mod(ctx, install_dir, downloads, mod_id)

    shutil.rmtree(staging, ignore_errors=True)

    if options.shortcuts:
        ctx.stage("Creating shortcuts")
        for game in launcher.installed_games(install_dir):
            try:
                shortcut = launcher.create_shortcut(install_dir, game, options.renderer)
                report.shortcuts.append(shortcut)
            except Exception as exc:  # noqa: BLE001 - a shortcut must not fail the install
                report.warnings.append(f"Could not create a shortcut for {game.title}: {exc}")

    for warning in report.warnings:
        ctx.log(f"Warning: {warning}")
    ctx.stage("Done")
    ctx.progress(1.0, "Installation complete")
    return report


def _prepare(install_dir: Path, options: InstallOptions) -> None:
    if options.steam and not options.username:
        raise TaskError("Enter your Steam username.")
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        probe = install_dir / ".arenahub-write-test"
        probe.write_text("")
        probe.unlink()
    except OSError as exc:
        raise TaskError(f"Cannot write to {install_dir}: {exc}") from exc

    free = shutil.disk_usage(install_dir).free
    if free < REQUIRED_SPACE:
        raise TaskError(
            f"Not enough free space in {install_dir}: {free / 1024**3:.1f} GiB available, "
            f"at least {REQUIRED_SPACE / 1024**3:.0f} GiB needed."
        )


def _fetch_keys(ctx: Context, options: InstallOptions) -> dict[int, steam_keys.KeyResult]:
    ctx.stage("Signing in to Steam")
    ctx.progress(None, "Requesting your CD keys from Steam")
    return steam_keys.fetch(
        ctx, options.username, options.password, [QUAKE3_APP_ID, TEAM_ARENA_APP_ID]
    )


def _download_quake3(ctx: Context, options: InstallOptions, staging: Path) -> None:
    ctx.stage("Installing SteamCMD")
    exe = steamcmd.install(ctx)

    ctx.stage("Downloading Quake III Arena")
    depot = staging / "steam"
    depot.mkdir(parents=True, exist_ok=True)
    steamcmd.download_app(ctx, exe, QUAKE3_APP_ID, depot, options.username, options.password)

    ctx.stage("Copying game data")
    install_dir = staging.parent
    found = {child.name.lower(): child for child in depot.iterdir() if child.is_dir()}
    for name in QUAKE3_DIRS:
        if name in found:
            merge_tree(found[name], install_dir / name)
            ctx.log(f"Copied {name}")

    if not (install_dir / QUAKE3.marker).is_file():
        raise TaskError("The Steam download did not contain Quake III Arena's baseq3/pak0.pk3.")


def _write_keys(
    ctx: Context,
    install_dir: Path,
    keys: dict[int, steam_keys.KeyResult],
    report: InstallReport,
) -> None:
    ctx.stage("Writing CD keys")
    for app_id, game in ((QUAKE3_APP_ID, QUAKE3), (TEAM_ARENA_APP_ID, TEAM_ARENA)):
        result = keys.get(app_id)
        if result is None or not result.ok:
            reason = result.result if result else "no answer"
            if game is QUAKE3:
                report.warnings.append(
                    f"Steam did not return a CD key for {game.title} ({reason}). "
                    "You can enter it by hand in the CD keys section."
                )
            else:
                ctx.log(f"No CD key for {game.title} on this account ({reason}); it is optional.")
            continue
        if not q3key.is_valid(result.key):
            report.warnings.append(f"Steam returned an unexpected CD key for {game.title}.")
            continue
        if game is TEAM_ARENA and not (install_dir / TEAM_ARENA.marker).is_file():
            ctx.log(f"Skipping the {game.title} key: its data is not installed.")
            continue
        q3key.write(install_dir, game.game_dir, result.key)
        report.keys[game.game_dir] = q3key.normalize(result.key)
        ctx.log(f"Wrote the CD key for {game.title}")


def _install_mod(ctx: Context, install_dir: Path, downloads: Path, mod_id: str) -> None:
    mod = game_by_id(mod_id)
    ctx.stage(f"Installing {mod.title}")
    for item in mod.downloads:
        archive = net.fetch(ctx, item.urls, downloads / item.filename, item.sha256, item.filename)
        extract(ctx, archive, install_dir, item.rule)
    if mod.notes:
        ctx.log(f"Note: {mod.notes}")
