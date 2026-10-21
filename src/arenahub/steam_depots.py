"""Downloading Steam depots from the content network (runs inside the Steam helper).

This replaces SteamCMD: the helper's single login is enough to request each
depot's manifest and decryption key, and to download its chunks. Only the
folders ArenaHub needs are written, straight into the installation, and files
whose SHA-1 already matches the manifest are kept, so an update only verifies.
"""

from __future__ import annotations

import hashlib
import io
import lzma
import os
import struct
import time
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path, PurePosixPath

PARALLEL_CHUNKS = 8
PART_SUFFIX = ".arenahub-part"
KEEP_EXISTING = (".cfg",)
"""Files the user may have edited: written only when they are missing."""

Progress = Callable[[int, int, str], None]


class NotOwned(Exception):
    """The account has no license for the app."""


class DepotError(Exception):
    """A download that cannot go on, with a message for the user."""


def relative_path(filename_raw: str, include: tuple[str, ...]) -> PurePosixPath | None:
    """Where a depot file goes inside the installation, or None to skip it.

    Depots use Windows paths. Only files under one of the include folders are
    kept, and nothing may escape the installation folder.
    """
    path = PurePosixPath(*filename_raw.replace("\\", "/").split("/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        return None
    if path.parts[0].lower() not in include:
        return None
    return path


def decode_chunk(data: bytes) -> bytes:
    """Decompress a decrypted depot chunk.

    Steam uses three formats: zstd ("VSZa", current uploads), LZMA ("VZa",
    older ones) and a plain ZIP holding one file (the oldest). steam-next only
    knows the last two, so ArenaHub decodes chunks itself, following SteamKit2.
    """
    if data[:4] == b"VSZa":
        import zstandard

        if len(data) < 8 + 15 or data[-3:] != b"zsv":
            raise ValueError("VSZa chunk: bad footer")
        crc, size = struct.unpack_from("<Ii", data, len(data) - 15)
        out = zstandard.ZstdDecompressor().decompress(data[8:-15], max_output_size=size)
    elif data[:3] == b"VZa":
        if len(data) < 12 + 10 or data[-2:] != b"zv":
            raise ValueError("VZa chunk: bad footer")
        lzma_filter = lzma._decode_filter_properties(lzma.FILTER_LZMA1, data[7:12])
        decompressor = lzma.LZMADecompressor(lzma.FORMAT_RAW, filters=[lzma_filter])
        crc, size = struct.unpack_from("<II", data, len(data) - 10)
        # The raw LZMA stream may decode a few bytes past the real end.
        out = decompressor.decompress(data[12:-9])[:size]
    else:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            return zf.read(zf.filelist[0])

    if len(out) != size or zlib.crc32(out) != crc:
        raise ValueError("chunk checksum does not match its contents")
    return out


def fetch_chunk(cdn, app_id: int, depot_id: int, chunk) -> bytes:
    """Download, decrypt and decompress one chunk with steam-next's CDN client."""
    from steam.core.crypto import symmetric_decrypt

    response = cdn.cdn_cmd("depot", f"{depot_id}/chunk/{chunk.sha.hex()}")
    data = decode_chunk(symmetric_decrypt(response.content, cdn.get_depot_key(app_id, depot_id)))
    if len(data) != chunk.cb_original:
        raise ValueError(f"chunk {chunk.sha.hex()} has the wrong size")
    return data


def sha1_of(path: Path) -> bytes:
    digest = hashlib.sha1()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.digest()


def is_current(target: Path, depot_file) -> bool:
    if not target.is_file():
        return False
    if target.suffix.lower() in KEEP_EXISTING:
        return True
    return target.stat().st_size == depot_file.size and sha1_of(target) == depot_file.sha_content


class Throttle:
    """Calls progress at most a few times per second, plus once at the end."""

    def __init__(self, progress: Progress, interval: float = 0.25) -> None:
        self._progress = progress
        self._interval = interval
        self._last = 0.0

    def __call__(self, done: int, total: int, text: str, force: bool = False) -> None:
        now = time.monotonic()
        if force or now - self._last >= self._interval:
            self._last = now
            self._progress(done, total, text)


def download_app(
    cdn,
    app_id: int,
    dest: Path,
    include: tuple[str, ...],
    skip_depots: set[int],
    progress: Progress,
) -> list[str]:
    """Download the included files of every depot of app_id into dest.

    Depots in skip_depots (already handled for another app) are left out and the
    ones handled here are added to it. Returns the paths written.
    """
    from gevent.pool import Pool

    if app_id not in cdn.licensed_app_ids:
        raise NotOwned(app_id)

    try:
        manifests = cdn.get_manifests(
            app_id, filter_func=lambda depot_id, info: int(depot_id) not in skip_depots
        )
    except Exception as exc:  # noqa: BLE001 - steam-next raises several error types
        raise DepotError(f"Could not get the file list of Steam app {app_id}: {exc}") from exc

    files = []
    for manifest in manifests:
        skip_depots.add(manifest.depot_id)
        for depot_file in manifest.iter_files():
            if depot_file.is_directory:
                continue
            rel = relative_path(depot_file.filename_raw, include)
            if rel is not None:
                files.append((rel, depot_file))

    total = sum(depot_file.size for _rel, depot_file in files)
    done = 0
    written: list[str] = []
    report = Throttle(progress)
    pool = Pool(PARALLEL_CHUNKS)

    for rel, depot_file in files:
        target = dest.joinpath(*rel.parts)
        if is_current(target, depot_file):
            done += depot_file.size
            report(done, total, f"Verified {rel}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + PART_SUFFIX)
        chunks = sorted(depot_file.file_mapping.chunks, key=lambda c: c.offset)

        def fetch(chunk, depot_id=depot_file.manifest.depot_id):
            return fetch_chunk(cdn, app_id, depot_id, chunk)

        try:
            with part.open("wb") as out:
                for chunk, data in zip(chunks, pool.imap(fetch, chunks), strict=True):
                    out.seek(chunk.offset)
                    out.write(data)
                    done += len(data)
                    report(done, total, f"Downloading {rel}")
                out.truncate(depot_file.size)
        except OSError as exc:
            raise DepotError(f"Could not write {target}: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - network and decryption errors from steam-next
            part.unlink(missing_ok=True)
            raise DepotError(f"Downloading {rel} failed: {exc}") from exc

        if sha1_of(part) != depot_file.sha_content:
            part.unlink(missing_ok=True)
            raise DepotError(f"{rel} was corrupted while downloading; try again.")
        os.replace(part, target)
        written.append(str(rel))

    report(done, total, "Done", force=True)
    return written
