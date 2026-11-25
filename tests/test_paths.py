import sys

from arenahub.core import paths


def fake_module(root):
    """Where core/paths.py would live inside `root` (a site-packages or src folder)."""
    module = root / "arenahub" / "core" / "paths.py"
    module.parent.mkdir(parents=True)
    module.touch()
    return module


def test_source_checkout_uses_the_repository_assets():
    assert paths.resource("cfg").is_dir()
    assert paths.resource("icons", "arenahub.png").is_file()


def test_installed_wheel_uses_the_package_assets(tmp_path, monkeypatch):
    site = tmp_path / "site-packages"
    monkeypatch.setattr(paths, "__file__", str(fake_module(site)))
    (site / "arenahub" / "assets").mkdir()
    assert paths.resource("cfg") == site / "arenahub" / "assets" / "cfg"


def test_without_package_assets_falls_back_to_the_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "__file__", str(fake_module(tmp_path / "repo" / "src")))
    assert paths.resource("cfg") == tmp_path / "repo" / "assets" / "cfg"


def test_frozen_build_uses_its_bundle(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.resource("links") == tmp_path / "assets" / "links"
