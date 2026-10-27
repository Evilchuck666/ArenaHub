import plistlib
import stat
import sys
from pathlib import Path

import pytest

from arenahub.core import paths, shortcuts
from arenahub.core.catalog import CPMA, GAMES, QUAKE3, TEAM_ARENA
from arenahub.core.engine import Renderer

TEMPLATES = Path(__file__).resolve().parent.parent / "assets" / "links"

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="POSIX paths and modes")


@pytest.fixture
def install_dir(tmp_path):
    folder = tmp_path / "Quake 3 $HOME"  # spaces and shell characters on purpose
    folder.mkdir()
    (folder / "quake3e.x64").write_text("engine")
    (folder / "quake3e.x64.exe").write_text("engine")
    return folder


def test_shortcut_name_is_a_valid_file_name():
    assert shortcuts.shortcut_name(TEAM_ARENA) == "Quake III Team Arena"
    assert shortcuts.shortcut_name(QUAKE3) == "Quake III Arena"


def test_desktop_argument_quoting():
    assert shortcuts.desktop_argument('a "b" $c 100%') == '"a \\\\"b\\\\" \\\\$c 100%%"'


@pytest.mark.parametrize("game", GAMES, ids=lambda g: g.id)
def test_repository_templates_are_complete(game):
    template = (TEMPLATES / f"arenahub-{game.id}.desktop").read_text()
    keys = ("Name", "Comment", "Exec", "TryExec", "Path", "Icon", "Terminal")
    filled = shortcuts.fill_desktop_template(template, {key: "X" for key in keys})
    assert "@" not in filled.split("[Desktop Entry]")[1]


def test_template_problems_are_reported():
    with pytest.raises(OSError, match="lacks Icon"):
        shortcuts.fill_desktop_template("[Desktop Entry]\nName=a\n", {"Name": "b", "Icon": "c"})
    with pytest.raises(OSError, match="twice"):
        shortcuts.fill_desktop_template("[Desktop Entry]\nName=a\nName=b\n", {"Name": "c"})
    # Keys in other groups and comments are left alone.
    text = "# Name=x\n[Desktop Entry]\nName=a\n[Desktop Action play]\nName=b\n"
    assert shortcuts.fill_desktop_template(text, {"Name": "c"}).splitlines() == [
        "# Name=x",
        "[Desktop Entry]",
        "Name=c",
        "[Desktop Action play]",
        "Name=b",
    ]


@posix_only
def test_linux_shortcut(tmp_path, install_dir, monkeypatch):
    monkeypatch.setattr(paths, "system", lambda: "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    path = shortcuts.create(install_dir, CPMA, Renderer.OPENGL)

    assert path == tmp_path / "data" / "applications" / "arenahub-cpma.desktop"
    entry = dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if "=" in line and line[0] != "#"
    )
    assert entry["Name"] == "Challenge ProMode Arena"
    assert entry["Exec"].startswith(
        f'"{install_dir}/quake3e.x64" "+set" "fs_basepath"'.replace("$", "\\\\$")
    )
    assert '"fs_game" "cpma"' in entry["Exec"]
    assert entry["TryExec"] == f"{install_dir}/quake3e.x64"
    assert entry["Icon"] == f"{install_dir}/arenahub.svg"
    assert entry["Terminal"] == "false"
    assert (install_dir / "arenahub.svg").is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o644
    assert [p.name for p in path.parent.iterdir()] == [path.name]  # no staging left behind


def test_linux_shortcut_needs_its_template(tmp_path, install_dir, monkeypatch):
    monkeypatch.setattr(paths, "system", lambda: "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    real = paths.resource

    def resource(*parts):
        return tmp_path / "missing" / parts[-1] if parts[0] == "links" else real(*parts)

    monkeypatch.setattr(paths, "resource", resource)
    with pytest.raises(OSError):
        shortcuts.create(install_dir, QUAKE3, Renderer.OPENGL)
    assert list((tmp_path / "data" / "applications").iterdir()) == []


@pytest.fixture
def macos(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "system", lambda: "macos")
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    stub = tmp_path / "Automator Application Stub"
    stub.write_bytes(b"\xcf\xfa\xed\xfe stub")
    monkeypatch.setattr(shortcuts, "AUTOMATOR_STUB", stub)
    calls = []
    monkeypatch.setattr(shortcuts, "_run", lambda command, env=None: calls.append(command) or "")
    return calls


@posix_only
def test_macos_app(tmp_path, install_dir, macos):
    app = shortcuts.create(install_dir, TEAM_ARENA, Renderer.VULKAN)

    assert app == tmp_path / "home" / "Applications" / "Quake III Team Arena.app"
    contents = app / "Contents"
    assert (contents / "MacOS" / "Automator Application Stub").stat().st_mode & 0o111
    info = plistlib.loads((contents / "Info.plist").read_bytes())
    assert info["CFBundleIdentifier"] == "com.arenahub.missionpack"
    assert info["LSUIElement"] is True
    workflow = plistlib.loads((contents / "document.wflow").read_bytes())
    script = workflow["actions"][0]["action"]["ActionParameters"]["source"]
    assert script.startswith(f"cd '{install_dir}'\nexec '{install_dir}/quake3e.x64'")
    assert "fs_game missionpack" in script
    # The icon and the workflow check run on the staged copy, before publishing.
    assert macos[0][:4] == ["/usr/bin/osascript", "-l", "JavaScript", "-e"]
    assert macos[0][-1] == str(install_dir / "arenahub.png")


def test_macos_app_is_replaced(tmp_path, install_dir, macos):
    first = shortcuts.create(install_dir, QUAKE3, Renderer.OPENGL)
    (first / "Contents" / "old-file").write_text("old")
    second = shortcuts.create(install_dir, QUAKE3, Renderer.OPENGL)
    assert second == first
    assert not (second / "Contents" / "old-file").exists()
    assert sorted(p.name for p in first.parent.iterdir()) == ["Quake III Arena.app"]


def test_windows_shortcut(tmp_path, install_dir, monkeypatch):
    monkeypatch.setattr(paths, "system", lambda: "windows")
    seen = {}
    link = tmp_path / "Desktop" / "Quake III Team Arena.lnk"

    def run(command, env=None):
        seen["command"], seen["env"] = command, env
        link.parent.mkdir()
        link.write_text("lnk")
        return f"{link}\r\n"

    monkeypatch.setattr(shortcuts, "_run", run)
    assert shortcuts.create(install_dir, TEAM_ARENA, Renderer.OPENGL) == link

    assert seen["command"][:4] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-EncodedCommand",
    ]
    env = seen["env"]
    assert env["ARENAHUB_SHORTCUT_NAME"] == "Quake III Team Arena"
    assert env["ARENAHUB_SHORTCUT_TARGET"] == str(install_dir / "quake3e.x64.exe")
    assert "fs_game missionpack" in env["ARENAHUB_SHORTCUT_ARGUMENTS"]
    assert env["ARENAHUB_SHORTCUT_ICON"] == str(install_dir / "arenahub.ico")


def test_windows_shortcut_must_exist(install_dir, monkeypatch):
    monkeypatch.setattr(paths, "system", lambda: "windows")
    monkeypatch.setattr(shortcuts, "_run", lambda command, env=None: "")
    with pytest.raises(OSError, match="did not create"):
        shortcuts.create(install_dir, QUAKE3, Renderer.OPENGL)
