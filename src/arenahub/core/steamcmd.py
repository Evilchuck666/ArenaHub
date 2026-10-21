"""Installing SteamCMD and downloading Quake III Arena with it."""

from __future__ import annotations

import re
import subprocess
import tarfile
import tempfile
import zipfile
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from . import net, paths
from .archive import make_executable
from .console import Console
from .context import Cancelled, Context, Prompt, PromptKind, TaskError

URLS = {
    "linux": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz",
    "windows": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip",
    "macos": "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_osx.tar.gz",
}

SELF_UPDATE_RE = re.compile(r"^\[\s*(\d+)%\]\s*(.*)")
PROGRESS_RE = re.compile(
    r"Update state \(0x[0-9a-f]+\) ([a-z ]+), progress: ([\d.]+) \((\d+) / (\d+)\)"
)
SUCCESS_RE = re.compile(r"Success! App '(\d+)' fully installed")
ERROR_RE = re.compile(r"(?:ERROR! (.+)|FAILED \((.+)\))")

PROMPTS = (
    (re.compile(r"password:\s*$", re.IGNORECASE), PromptKind.PASSWORD),
    (re.compile(r"steam guard code:\s*$", re.IGNORECASE), PromptKind.EMAIL_CODE),
    (re.compile(r"two-factor code:\s*$", re.IGNORECASE), PromptKind.TWO_FACTOR_CODE),
)

HINTS = {
    "no subscription": "This Steam account does not own Quake III Arena.",
    "invalid password": "Steam rejected the username or password.",
    "rate limit exceeded": "Steam is limiting login attempts. Wait a while and try again.",
    "two-factor code mismatch": "The Steam Guard code was not accepted.",
    "invalid login auth code": "The Steam Guard code was not accepted.",
}

TAIL_LINES = 15


def executable() -> Path:
    name = "steamcmd.exe" if paths.system() == "windows" else "steamcmd.sh"
    return paths.steamcmd_dir() / name


def install(ctx: Context) -> Path:
    """Install SteamCMD in ArenaHub's data folder unless it is already there."""
    exe = executable()
    if exe.exists():
        ctx.log(f"SteamCMD found in {exe.parent}")
        return exe

    check_rosetta()
    url = URLS[paths.system()]
    exe.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        download = net.fetch(ctx, (url,), Path(tmp) / Path(url).name, label="SteamCMD")
        if download.suffix == ".zip":
            with zipfile.ZipFile(download) as archive:
                archive.extractall(exe.parent)
        else:
            with tarfile.open(download, mode="r:gz") as archive:
                archive.extractall(exe.parent, filter="tar")

    if not exe.exists():
        raise TaskError(f"{exe.name} was not found after extracting SteamCMD")
    if paths.system() != "windows":
        make_executable(exe)
    return exe


def check_rosetta() -> None:
    """SteamCMD for macOS is an Intel binary; Apple Silicon needs Rosetta 2 for it."""
    if paths.system() != "macos" or paths.machine() != "arm64":
        return
    result = subprocess.run(["arch", "-x86_64", "/usr/bin/true"], check=False, capture_output=True)
    if result.returncode != 0:
        raise TaskError(
            "SteamCMD needs Rosetta 2 on Apple Silicon. Install it with:\n"
            "softwareupdate --install-rosetta --agree-to-license"
        )


@dataclass
class Event:
    kind: str  # "line", "prompt", "progress"
    text: str = ""
    prompt: PromptKind | None = None
    fraction: float | None = None


class OutputParser:
    """Turns SteamCMD's terminal output into lines, prompts and progress."""

    def __init__(self) -> None:
        self._pending = ""

    def feed(self, chunk: str) -> list[Event]:
        events: list[Event] = []
        *lines, self._pending = re.split(r"[\r\n]", self._pending + chunk)
        for line in lines:
            events.extend(self._line(line))

        # Prompts do not end in a newline: look for them in the unfinished line.
        for pattern, kind in PROMPTS:
            if pattern.search(self._pending):
                events.append(Event("prompt", self._pending.strip(), prompt=kind))
                self._pending = ""
                break
        return events

    def flush(self) -> list[Event]:
        pending, self._pending = self._pending, ""
        return self._line(pending)

    @staticmethod
    def _line(line: str) -> list[Event]:
        line = line.strip()
        if not line:
            return []
        if match := PROGRESS_RE.search(line):
            phase, percent = match.group(1), float(match.group(2))
            return [Event("progress", phase.strip().capitalize(), fraction=percent / 100)]
        if match := SELF_UPDATE_RE.match(line):
            return [Event("progress", "Updating SteamCMD", fraction=int(match.group(1)) / 100)]
        return [Event("line", line)]


def explain(lines: list[str]) -> str:
    """The most useful explanation of a failure found in SteamCMD's last lines."""
    for line in reversed(lines):
        if match := ERROR_RE.search(line):
            reason = (match.group(1) or match.group(2)).strip()
            for needle, hint in HINTS.items():
                if needle in reason.lower():
                    return f"{hint} (SteamCMD: {reason})"
            return f"SteamCMD: {reason}"
    return "SteamCMD did not finish the download."


def download_app(
    ctx: Context,
    steamcmd: Path,
    app_id: int,
    install_dir: Path,
    username: str,
    password: str | None,
) -> None:
    """Download a Steam app with SteamCMD, answering its prompts through ctx.

    password answers the first password prompt; later ones (a rejected password)
    are asked to the user. SteamCMD skips the prompt when it remembers the login.
    """
    argv = [
        str(steamcmd),
        "+@ShutdownOnFailedCommand", "1",
        "+@sSteamCmdForcePlatformType", "windows",  # Quake III only has Windows depots
        "+force_install_dir", str(install_dir),
        "+login", username,
        "+app_update", str(app_id), "validate",
        "+quit",
    ]  # fmt: skip

    ctx.log(f"Starting SteamCMD for app {app_id}")
    console = Console(argv, cwd=steamcmd.parent)
    parser = OutputParser()
    tail: deque[str] = deque(maxlen=TAIL_LINES)
    asked: set[PromptKind] = set()
    succeeded = False

    try:
        while True:
            if ctx.cancelled:
                raise Cancelled()
            chunk = console.read(timeout=0.2)
            if chunk is None:
                break
            for event in parser.feed(chunk):
                match event.kind:
                    case "line":
                        tail.append(event.text)
                        ctx.log(event.text)
                        if SUCCESS_RE.search(event.text):
                            succeeded = True
                        elif "Steam Mobile app" in event.text:
                            ctx.progress(None, "Confirm the login in the Steam Mobile app")
                    case "progress":
                        ctx.progress(event.fraction, event.text)
                    case "prompt":
                        answer = _answer(ctx, event.prompt, asked, password)
                        if answer is None:
                            raise Cancelled()
                        console.write_line(answer)
        for event in parser.flush():
            tail.append(event.text)
            ctx.log(event.text)
    except BaseException:
        console.kill()
        console.wait()
        raise

    code = console.wait()
    if code != 0 or not succeeded:
        raise TaskError(explain(list(tail)))


def _answer(
    ctx: Context, kind: PromptKind, asked: set[PromptKind], password: str | None
) -> str | None:
    retry = kind in asked
    asked.add(kind)

    if kind is PromptKind.PASSWORD and password and not retry:
        return password

    messages = {
        PromptKind.PASSWORD: "SteamCMD needs your Steam password.",
        PromptKind.EMAIL_CODE: "SteamCMD sent a Steam Guard code to your email.",
        PromptKind.TWO_FACTOR_CODE: "Enter the code from your Steam Guard mobile authenticator.",
    }
    return ctx.ask(Prompt(kind, messages[kind], retry=retry))
