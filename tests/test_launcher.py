import sys

import pytest

from arenahub.core import engine, launcher, paths
from arenahub.core.catalog import CPMA, QUAKE3, TEAM_ARENA
from arenahub.core.engine import Renderer


def fake_install(tmp_path, names):
    for name in names:
        (tmp_path / name).write_text("binary")
    return tmp_path


def test_arguments_keep_everything_in_the_folder(tmp_path):
    args = launcher.arguments(tmp_path, QUAKE3)
    assert args == ["+set", "fs_basepath", str(tmp_path), "+set", "fs_homepath", str(tmp_path)]
    assert launcher.arguments(tmp_path, CPMA)[6:] == ["+set", "fs_game", "cpma"]
    assert launcher.arguments(tmp_path, TEAM_ARENA)[6:] == ["+set", "fs_game", "missionpack"]


def test_installed_games(tmp_path):
    (tmp_path / "baseq3").mkdir()
    (tmp_path / "baseq3" / "pak0.pk3").write_text("")
    assert launcher.installed_games(tmp_path) == [QUAKE3]


@pytest.mark.skipif(sys.platform == "win32", reason="unix executable names")
def test_engine_executable_selection(tmp_path):
    fake_install(tmp_path, ["quake3e.x64", "quake3e-vulkan.x64", "quake3e.ded.x64"])
    assert engine.executable(tmp_path, Renderer.OPENGL).name == "quake3e.x64"
    assert engine.executable(tmp_path, Renderer.VULKAN).name == "quake3e-vulkan.x64"


def test_engine_falls_back_to_other_renderer(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "system", lambda: "linux")
    fake_install(tmp_path, ["quake3e.aarch64", "libSDL2-2.0.0.dylib"])
    assert engine.executable(tmp_path, Renderer.VULKAN).name == "quake3e.aarch64"
    assert engine.executable(tmp_path / "missing") is None


def test_asset_names():
    assert engine.asset_name("linux", "x86_64") == "quake3e-linux-x86_64.zip"
    assert engine.asset_name("macos", "arm64") == "quake3e-macos-aarch64.zip"
    assert engine.asset_name("windows", "x86_64") == "quake3e-windows-mingw-x86_64.zip"


def test_child_env_restores_library_path(monkeypatch):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/tmp/_MEI1234")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib/custom")
    env = paths.child_env()
    assert env["LD_LIBRARY_PATH"] == "/usr/lib/custom"
    assert "LD_LIBRARY_PATH_ORIG" not in env
