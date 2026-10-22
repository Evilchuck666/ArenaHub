"""The installation as a whole: Steam data, CD keys, engine, mods and maps."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ..steam_depots import PART_SUFFIX
from . import configs, engine, launcher, maps, net, q3key, shortcuts, steam
from .archive import extract
from .catalog import QUAKE3, QUAKE3_APP_ID, QUAKE3_DIRS, TEAM_ARENA, TEAM_ARENA_APP_ID, game_by_id
from .context import Context, TaskError

STAGING = ".arenahub-staging"
REQUIRED_SPACE = 3 * 1024**3  # game ~500 MiB, mod archives ~570 MiB + extracted, maps ~360 MiB


@dataclass
class InstallOptions:
    install_dir: Path
    username: str = ""
    password: str = ""
    steam: bool = True
    """Download (or verify) Quake III Arena from Steam and fetch the CD keys."""
    mods: list[str] = field(default_factory=list)
    player: configs.Player | None = None
    """Name and sensitivity to write into the game configs."""
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
    # Mod downloads stay in staging until everything succeeded, so a retry reuses them.
    staging = install_dir / STAGING
    downloads = staging / "downloads"

    if options.steam:
        result = _steam(ctx, options, install_dir)
        _write_keys(ctx, install_dir, result.keys, report)
    elif not (install_dir / QUAKE3.marker).is_file():
        raise TaskError("Quake III Arena is not installed in this folder yet.")

    ctx.stage("Installing Quake3e")
    engine.install(ctx, install_dir, downloads)

    for mod_id in options.mods:
        _install_mod(ctx, install_dir, downloads, mod_id)

    ctx.stage("Installing maps")
    result = maps.install(ctx, install_dir, downloads)
    ctx.log(f"Added {len(result.added)} map packs; the others were already up to date.")
    report.warnings += [f"Map not installed: {failure}" for failure in result.failed]

    shutil.rmtree(staging, ignore_errors=True)

    ctx.stage("Writing game configs")
    for path in configs.install(install_dir):
        ctx.log(f"Added {path.relative_to(install_dir)}")
    if options.player:
        try:
            configs.save_player(install_dir, options.player)
        except ValueError as exc:
            report.warnings.append(f"Player settings not saved: {exc}")

    if options.shortcuts:
        ctx.stage("Creating shortcuts")
        for game in launcher.installed_games(install_dir):
            try:
                shortcut = shortcuts.create(install_dir, game, options.renderer)
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


def _steam(ctx: Context, options: InstallOptions, install_dir: Path) -> steam.SteamResult:
    """One Steam login: the CD keys, then Quake III Arena and Team Arena from the depots.

    Only baseq3 and missionpack are downloaded, straight into the installation;
    files that already match Steam's are kept, so an update just verifies them.
    """
    download = steam.Download(
        dest=install_dir,
        apps=(QUAKE3_APP_ID, TEAM_ARENA_APP_ID),
        include=QUAKE3_DIRS,
        titles={QUAKE3_APP_ID: QUAKE3.title, TEAM_ARENA_APP_ID: TEAM_ARENA.title},
    )
    keys = [QUAKE3_APP_ID, TEAM_ARENA_APP_ID]
    try:
        result = steam.run(ctx, options.username, options.password, keys, download)
    finally:
        # A cancelled or failed download leaves unfinished files behind.
        for name in QUAKE3_DIRS:
            for part in (install_dir / name).glob(f"**/*{PART_SUFFIX}"):
                part.unlink(missing_ok=True)

    if not result.owns(QUAKE3_APP_ID):
        raise TaskError("This Steam account does not own Quake III Arena.")
    if not result.owns(TEAM_ARENA_APP_ID):
        ctx.log("This Steam account does not own Team Arena; skipping it (it is optional).")
    if not (install_dir / QUAKE3.marker).is_file():
        raise TaskError("The Steam download did not contain Quake III Arena's baseq3/pak0.pk3.")
    return result


def _write_keys(
    ctx: Context,
    install_dir: Path,
    keys: dict[int, steam.KeyResult],
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
