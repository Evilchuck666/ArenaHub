"""Safe extraction and merging of game files."""

from __future__ import annotations

import fnmatch
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from .catalog import Rule
from .context import Context, TaskError


def _matches(path: str, pattern: str) -> bool:
    """Like .gitignore: a pattern without '/' matches the file name in any folder."""
    if "/" not in pattern:
        path = path.rsplit("/", 1)[-1]
    return fnmatch.fnmatch(path, pattern)


def selected(name: str, rule: Rule) -> bool:
    lower = name.lower().replace("\\", "/")
    if not any(_matches(lower, pattern) for pattern in rule.include):
        return False
    return not any(_matches(lower, pattern) for pattern in rule.exclude)


def safe_member_path(name: str) -> PurePosixPath:
    """Reject archive members that would land outside the destination."""
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or (path.parts and ":" in path.parts[0]):
        raise TaskError(f"Unsafe path in archive: {name}")
    return path


def extract(ctx: Context, archive: Path, dest: Path, rule: Rule | None = None) -> list[Path]:
    """Extract the members of archive selected by rule (all by default) into dest/rule.target."""
    rule = rule or Rule()
    root = dest / rule.target if rule.target else dest
    written: list[Path] = []

    try:
        with zipfile.ZipFile(archive) as zf:
            members = [m for m in zf.infolist() if not m.is_dir() and selected(m.filename, rule)]
            for index, member in enumerate(members, 1):
                ctx.check()
                target = root / safe_member_path(member.filename)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)
                written.append(target)
                ctx.progress(index / len(members), f"Extracting {archive.name}")
    except zipfile.BadZipFile as exc:
        raise TaskError(f"{archive.name} is not a valid ZIP archive: {exc}") from exc

    return written


def make_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def merge_tree(src: Path, dest: Path) -> None:
    """Move every file of src into dest, replacing files that already exist."""
    for path in sorted(src.rglob("*")):
        if path.is_dir():
            continue
        target = dest / path.relative_to(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        shutil.move(path, target)
