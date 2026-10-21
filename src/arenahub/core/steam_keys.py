"""Fetching CD keys through the Steam helper process (see arenahub.steam_helper)."""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from collections import deque
from dataclasses import dataclass

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


def fetch(ctx: Context, username: str, password: str, app_ids: list[int]) -> dict[int, KeyResult]:
    """Log in to Steam and return the CD key result for each app."""
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

    results: dict[int, KeyResult] = {}
    try:
        send({"username": username, "password": password, "apps": app_ids})
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

            match message.get("type"):
                case "prompt":
                    kind, text = PROMPT_KINDS[message["kind"]]
                    code = ctx.ask(Prompt(kind, text, retry=message.get("retry", False)))
                    if code is None:
                        raise Cancelled()
                    send({"code": code})
                case "key":
                    result = KeyResult(message["app"], message["result"], message.get("key", ""))
                    results[result.app_id] = result
                case "error":
                    raise TaskError(message.get("message") or message.get("result"))
                case "done":
                    break
    finally:
        if proc.poll() is None:
            try:
                proc.stdin.close()
                proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                proc.kill()
                proc.wait()

    return results


def _read_messages(proc: subprocess.Popen, messages: queue.Queue) -> None:
    for line in proc.stdout:
        try:
            messages.put(json.loads(line))
        except json.JSONDecodeError:
            continue
    messages.put(None)
