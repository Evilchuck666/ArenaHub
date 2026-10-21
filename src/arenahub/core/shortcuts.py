"""Per-user shortcuts to the installed games, with each platform's own facilities.

- GNU/Linux: a .desktop entry in the application menu, made from the template
  in assets/links/ that ships inside ArenaHub, as QuakeBundle does.
- macOS: a small application in ~/Applications built on Automator's
  application stub, so it opens like any app, with its icon and no Terminal.
- Windows: a .lnk on the user's Desktop, made by PowerShell.

Every shortcut runs Quake3e directly; ArenaHub does not need to be running.
"""

from __future__ import annotations

import base64
import os
import plistlib
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import launcher, paths
from .catalog import Game
from .engine import Renderer

AUTOMATOR_STUB = Path(
    "/System/Library/CoreServices/Automator Application Stub.app/Contents/MacOS/"
    "Automator Application Stub"
)

ICONS = {"linux": "arenahub.svg", "macos": "arenahub.png", "windows": "arenahub.ico"}


def create(install_dir: Path, game: Game, renderer: Renderer) -> Path:
    """Create or replace the shortcut for game and return where it was written."""
    argv = launcher.command(install_dir, game, renderer)
    icon = _copy_icon(install_dir)
    match paths.system():
        case "windows":
            return _windows(install_dir, game, argv, icon)
        case "macos":
            return _macos(install_dir, game, argv, icon)
        case _:
            return _linux(install_dir, game, argv, icon)


def shortcut_name(game: Game) -> str:
    """A file name for the shortcut: Windows forbids ':' and Finder shows it as '/'."""
    return " ".join(game.title.replace(":", " ").split())


def _copy_icon(install_dir: Path) -> Path:
    name = ICONS[paths.system()]
    icon = install_dir / name
    shutil.copyfile(paths.resource("icons", name), icon)
    return icon


def _run(command: list[str], env: dict[str, str] | None = None) -> str:
    """Run a native tool, turning a failure into an OSError with its output."""
    options = {}
    if paths.system() == "windows":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env or paths.child_env(),
            **options,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise OSError(f"{Path(command[0]).name} failed: {detail}") from exc
    return result.stdout


# GNU/Linux -----------------------------------------------------------------------


def desktop_value(value: object) -> str:
    """Escape a string value of a .desktop file."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def desktop_argument(value: object) -> str:
    """Quote one argument of the Exec key (its quoting rules come before value escaping)."""
    value = str(value).replace("%", "%%")
    for character in ("\\", '"', "`", "$"):
        value = value.replace(character, "\\" + character)
    return desktop_value(f'"{value}"')


def fill_desktop_template(template: str, replacements: dict[str, str]) -> str:
    """Set the given keys of the [Desktop Entry] group; each must appear exactly once."""
    lines, found, group = [], set(), ""
    for line in template.splitlines():
        if line.startswith("["):
            group = line.strip()
        key = line.partition("=")[0].strip()
        if group == "[Desktop Entry]" and key in replacements and not line.startswith("#"):
            if key in found:
                raise OSError(f"The shortcut template sets {key} twice")
            found.add(key)
            lines.append(f"{key}={replacements[key]}")
        else:
            lines.append(line)
    if missing := replacements.keys() - found:
        raise OSError(f"The shortcut template lacks {', '.join(sorted(missing))}")
    return "\n".join(lines) + "\n"


def _linux(install_dir: Path, game: Game, argv: list[str], icon: Path) -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    directory = data_home / "applications"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"arenahub-{game.id}.desktop"

    with tempfile.TemporaryDirectory(prefix=".arenahub-shortcut-", dir=directory) as tmp:
        staged = Path(tmp) / destination.name
        template = paths.resource("links", destination.name)
        content = fill_desktop_template(
            template.read_text(encoding="utf-8"),
            {
                "Name": desktop_value(game.title),
                "Comment": desktop_value(game.description),
                "Exec": " ".join(desktop_argument(arg) for arg in argv),
                "TryExec": desktop_value(argv[0]),
                "Path": desktop_value(install_dir),
                "Icon": desktop_value(icon),
                "Terminal": "false",
            },
        )
        staged.write_text(content, encoding="utf-8")
        staged.chmod(0o644)
        staged.replace(destination)
    return destination


# macOS ---------------------------------------------------------------------------

# Loads the workflow the way Automator will (so a broken one fails here, not
# when the user clicks it) and gives the application its icon.
MACOS_CHECK_AND_ICON = """
ObjC.import('Automator');
ObjC.import('AppKit');
function run(argv) {
    var error = Ref();
    var workflow = $.AMWorkflow.alloc.initWithContentsOfURLError(
        $.NSURL.fileURLWithPath(argv[0] + '/Contents/document.wflow'), error);
    if (workflow.isNil()) {
        throw Error('Invalid Automator workflow: ' + ObjC.unwrap(error[0].localizedDescription));
    }
    if (Number(workflow.actions.count) !== 1) {
        throw Error('Automator could not load the launch action');
    }
    var icon = $.NSImage.alloc.initWithContentsOfFile(argv[1]);
    if (icon.isNil() || !$.NSWorkspace.sharedWorkspace.setIconForFileOptions(icon, argv[0], 0)) {
        throw Error('Could not set the application icon');
    }
}
"""


def macos_workflow(install_dir: Path, argv: list[str]) -> dict:
    """An Automator workflow with one "Run Shell Script" action that starts the game."""
    script = f"cd {shlex.quote(str(install_dir))}\nexec {shlex.join(argv)}\n"
    return {
        "AMDocumentVersion": "2",
        "actions": [
            {
                "action": {
                    "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                    "ActionName": "Run Shell Script",
                    "BundleIdentifier": "com.apple.RunShellScript",
                    "ActionParameters": {
                        "shell": "/bin/sh",
                        "source": script,
                        "inputMethod": 0,
                        "CheckedForUserDefaultShell": True,
                    },
                }
            }
        ],
        "connectors": [],
        "workflowMetaData": {"workflowTypeIdentifier": "com.apple.Automator.application"},
    }


def build_macos_app(app: Path, install_dir: Path, game: Game, argv: list[str]) -> None:
    contents = app / "Contents"
    executable = contents / "MacOS" / AUTOMATOR_STUB.name
    executable.parent.mkdir(parents=True)
    shutil.copyfile(AUTOMATOR_STUB, executable)
    executable.chmod(0o755)
    info = {
        "CFBundleExecutable": executable.name,
        "CFBundleIdentifier": f"com.arenahub.{game.id}",
        "CFBundleName": shortcut_name(game),
        "CFBundleDisplayName": shortcut_name(game),
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "LSUIElement": True,  # the stub only starts the game; keep it out of the Dock
    }
    for name, data in (("Info.plist", info), ("document.wflow", macos_workflow(install_dir, argv))):
        with (contents / name).open("wb") as out:
            plistlib.dump(data, out)


def _publish_app(staged: Path, destination: Path) -> None:
    """Replace destination with staged, restoring the old app if that fails."""
    # A non-empty .app directory cannot be replaced by a single rename.
    backup = staged.parent / "previous.app"
    had_previous = destination.exists() or destination.is_symlink()
    if had_previous:
        destination.rename(backup)
    try:
        staged.rename(destination)
    except OSError:
        if had_previous:
            backup.rename(destination)
        raise


def _macos(install_dir: Path, game: Game, argv: list[str], icon: Path) -> Path:
    directory = Path.home() / "Applications"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{shortcut_name(game)}.app"
    with tempfile.TemporaryDirectory(prefix=".arenahub-shortcut-", dir=directory) as tmp:
        staged = Path(tmp) / destination.name
        build_macos_app(staged, install_dir, game, argv)
        _run(
            ["/usr/bin/osascript", "-l", "JavaScript", "-e", MACOS_CHECK_AND_ICON]
            + [str(staged), str(icon)]
        )
        _publish_app(staged, destination)
    return destination


# Windows -------------------------------------------------------------------------

# The values arrive in environment variables, so nothing needs quoting for
# PowerShell. The link is saved under a temporary name and then swapped in.
WINDOWS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$shell = New-Object -ComObject WScript.Shell
$desktop = $shell.SpecialFolders.Item('Desktop')
if (-not $desktop) { throw 'Could not find the Desktop folder' }
$destination = Join-Path $desktop ($env:ARENAHUB_SHORTCUT_NAME + '.lnk')
$staged = Join-Path $desktop (([guid]::NewGuid().ToString()) + '.lnk')
try {
    $link = $shell.CreateShortcut($staged)
    $link.TargetPath = $env:ARENAHUB_SHORTCUT_TARGET
    $link.Arguments = $env:ARENAHUB_SHORTCUT_ARGUMENTS
    $link.WorkingDirectory = $env:ARENAHUB_SHORTCUT_DIR
    $link.IconLocation = $env:ARENAHUB_SHORTCUT_ICON + ',0'
    $link.Description = $env:ARENAHUB_SHORTCUT_DESCRIPTION
    $link.Save()
    if (Test-Path -LiteralPath $destination) {
        # PowerShell would turn $null into '' here; NullString means "no backup file".
        $noBackup = [System.Management.Automation.Language.NullString]::Value
        [System.IO.File]::Replace($staged, $destination, $noBackup)
    } else {
        [System.IO.File]::Move($staged, $destination)
    }
    [Console]::WriteLine($destination)
} finally {
    if (Test-Path -LiteralPath $staged) { Remove-Item -LiteralPath $staged }
}
"""


def _windows(install_dir: Path, game: Game, argv: list[str], icon: Path) -> Path:
    encoded = base64.b64encode(WINDOWS_SCRIPT.encode("utf-16le")).decode("ascii")
    env = {
        **paths.child_env(),
        "ARENAHUB_SHORTCUT_NAME": shortcut_name(game),
        "ARENAHUB_SHORTCUT_TARGET": argv[0],
        "ARENAHUB_SHORTCUT_ARGUMENTS": subprocess.list2cmdline(argv[1:]),
        "ARENAHUB_SHORTCUT_DIR": str(install_dir),
        "ARENAHUB_SHORTCUT_ICON": str(icon),
        "ARENAHUB_SHORTCUT_DESCRIPTION": game.description,
    }
    output = _run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], env
    ).strip()
    destination = Path(output)
    if not output or not destination.is_file():
        raise OSError("Windows did not create the shortcut")
    return destination
