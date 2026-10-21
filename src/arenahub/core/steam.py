"""Steam through the helper process (see arenahub.steam_helper): one login, keys and game data."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .context import Cancelled, Context, Prompt, PromptKind, TaskError

PROMPT_KINDS = {
    "email_code": (PromptKind.EMAIL_CODE, "Steam sent a Steam Guard code to your email."),
    "two_factor_code": (
        PromptKind.TWO_FACTOR_CODE,
        "Enter the code from your Steam Guard mobile authenticator.",
    ),
}


@dataclass(frozen=True)
class KeyResult:
    app_id: int
    result: str
    key: str

    @property
    def ok(self) -> bool:
        return self.result == "OK" and bool(self.key)


@dataclass(frozen=True)
class Download:
    """Which Steam apps to download into dest, and which top-level folders to keep."""

    dest: Path
    apps: tuple[int, ...]
    include: tuple[str, ...]
    titles: dict[int, str] = field(default_factory=dict)


@dataclass
class SteamResult:
    keys: dict[int, KeyResult] = field(default_factory=dict)
    apps: dict[int, str] = field(default_factory=dict)
    """app id -> "OK" or "NotOwned", for each downloaded app."""

    def owns(self, app_id: int) -> bool:
        return self.apps.get(app_id) == "OK"


def run(
    ctx: Context,
    username: str,
    password: str,
    key_apps: list[int],
    download: Download | None = None,
) -> SteamResult:
    """Log in to Steam once, fetch the CD keys of key_apps and run the download."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.Popen(
        paths.self_command("--steam-helper"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=flags,
    )
    messages: queue.Queue[dict | None] = queue.Queue()
    stderr: deque[str] = deque(maxlen=20)
    threading.Thread(target=_read_messages, args=(proc, messages), daemon=True).start()
    threading.Thread(target=lambda: stderr.extend(proc.stderr), daemon=True).start()

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    request: dict = {"username": username, "password": password, "keys": key_apps}
    titles: dict[int, str] = {}
    if download:
        titles = download.titles
        request["download"] = {
            "dir": str(download.dest),
            "apps": list(download.apps),
            "include": list(download.include),
        }

    result = SteamResult()
    ctx.stage("Signing in to Steam")
    ctx.progress(None, "Waiting for Steam")
    try:
        send(request)
        while True:
            ctx.check()
            try:
                message = messages.get(timeout=0.2)
            except queue.Empty:
                continue
            if message is None:
                raise TaskError(
                    "The Steam helper stopped unexpectedly.\n" + "".join(stderr).strip()
                )
            if _handle(ctx, message, result, titles, send):
                break
    except BaseException:
        # Cancelled or failed: stop the helper at once, even mid-download.
        if proc.poll() is None:
            proc.kill()
        proc.wait()
        raise

    try:
        proc.stdin.close()
        proc.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        proc.kill()
        proc.wait()
    return result


def _handle(ctx: Context, message: dict, result: SteamResult, titles: dict, send) -> bool:
    """Act on one helper message. Returns True once the helper is done."""
    match message.get("type"):
        case "prompt":
            kind, text = PROMPT_KINDS[message["kind"]]
            code = ctx.ask(Prompt(kind, text, retry=message.get("retry", False)))
            if code is None:
                raise Cancelled()
            send({"code": code})
        case "key":
            key = KeyResult(message["app"], message["result"], message.get("key", ""))
            result.keys[key.app_id] = key
        case "app_start":
            app_id = message["app"]
            ctx.stage(f"Downloading {titles.get(app_id, f'Steam app {app_id}')}")
        case "progress":
            total = message.get("total") or 0
            fraction = message["done"] / total if total else None
            ctx.progress(fraction, message.get("text", ""))
        case "app":
            app_id = message["app"]
            result.apps[app_id] = message["result"]
            title = titles.get(app_id, f"Steam app {app_id}")
            if message["result"] == "OK":
                ctx.log(f"{title}: {message.get('written', 0)} files downloaded, the rest verified")
            else:
                ctx.log(f"{title}: not owned by this Steam account")
        case "error":
            raise TaskError(message.get("message") or message.get("result"))
        case "done":
            return True
    return False


def _read_messages(proc: subprocess.Popen, messages: queue.Queue) -> None:
    for line in proc.stdout:
        try:
            messages.put(json.loads(line))
        except json.JSONDecodeError:
            continue
    messages.put(None)
