"""HTTP downloads with progress, cancellation, mirrors and checksum verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

import certifi
import requests

from .. import __version__
from .context import Context, TaskError

CHUNK = 256 * 1024
TIMEOUT = 30
USER_AGENT = f"ArenaHub/{__version__}"


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    # The bundled CA list works the same on every system, frozen or not.
    s.verify = certifi.where()
    return s


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def fetch(
    ctx: Context,
    urls: tuple[str, ...] | list[str],
    dest: Path,
    sha256: str | None = None,
    label: str = "",
) -> Path:
    """Download the first URL that works into dest and return it.

    An existing dest with the expected checksum is reused without downloading.
    """
    label = label or dest.name

    if sha256 and dest.exists() and sha256_of(dest) == sha256:
        ctx.log(f"Using cached {label}")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".part")
    errors: list[str] = []

    with session() as s:
        for url in urls:
            ctx.check()
            ctx.log(f"Downloading {label} from {url}")
            try:
                _stream(ctx, s, url, partial, label)
            except requests.RequestException as exc:
                errors.append(f"{url}: {exc}")
                ctx.log(f"Download failed: {exc}")
                continue

            if sha256 and (actual := sha256_of(partial)) != sha256:
                errors.append(f"{url}: checksum mismatch ({actual})")
                ctx.log(f"Checksum mismatch for {label}, trying the next mirror")
                partial.unlink(missing_ok=True)
                continue

            partial.replace(dest)
            return dest

    partial.unlink(missing_ok=True)
    raise TaskError(f"Could not download {label}:\n" + "\n".join(errors))


def _stream(ctx: Context, s: requests.Session, url: str, dest: Path, label: str) -> None:
    with s.get(url, stream=True, timeout=TIMEOUT) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        done = 0

        with dest.open("wb") as f:
            for chunk in response.iter_content(CHUNK):
                ctx.check()
                f.write(chunk)
                done += len(chunk)
                if total:
                    ctx.progress(done / total, f"{label}: {_mib(done)} / {_mib(total)}")
                else:
                    ctx.progress(None, f"{label}: {_mib(done)}")


def _mib(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MiB"


def latest_release_asset(repo: str, asset_name: str) -> str:
    """Download URL of an asset in the latest GitHub release of repo."""
    with session() as s:
        response = s.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=TIMEOUT)
        response.raise_for_status()
        for asset in response.json().get("assets", []):
            if asset.get("name") == asset_name:
                return asset["browser_download_url"]
    raise TaskError(f"The latest {repo} release has no {asset_name}")
