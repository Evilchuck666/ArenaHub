import shutil

import pytest

from arenahub.core import engine, installer, maps, net, q3key, steam
from arenahub.core.catalog import QUAKE3_APP_ID, TEAM_ARENA_APP_ID
from arenahub.core.context import TaskError
from arenahub.steam_depots import PART_SUFFIX

from .conftest import RecordingContext, make_zip

# Each Steam app brings its own folder, like depots 2201 and 2351.
DEPOT_FILES = {
    QUAKE3_APP_ID: ("baseq3/pak0.pk3",),
    TEAM_ARENA_APP_ID: ("missionpack/pak0.pk3",),
}


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """Replace every network and Steam step with local fakes."""
    calls = {"not_owned": set(), "keys": {}}
    archives = tmp_path / "archives"
    archives.mkdir()
    make_zip(archives / "cpma-1.53-nomaps.zip", {"cpma/z-cpma-pak153.pk3": "cpma"})
    make_zip(archives / "cpma-mappack-full.zip", {"map_cpm1.pk3": "map"})

    def fetch(ctx, urls, dest, sha256=None, label=""):
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archives / dest.name, dest)
        return dest

    def install_engine(ctx, install_dir, download_dir):
        (install_dir / "quake3e.x64").write_text("engine")
        return [install_dir / "quake3e.x64"]

    def run(ctx, username, password, key_apps, download=None):
        calls["steam"] = (username, password, key_apps, download.apps, download.include)
        result = steam.SteamResult(keys=dict(calls["keys"]))
        for app_id in download.apps:
            if app_id in calls["not_owned"]:
                result.apps[app_id] = "NotOwned"
                continue
            for name in DEPOT_FILES[app_id]:
                (download.dest / name).parent.mkdir(parents=True, exist_ok=True)
                (download.dest / name).write_text("data")
            result.apps[app_id] = "OK"
        return result

    calls["keys"] = {
        QUAKE3_APP_ID: steam.KeyResult(QUAKE3_APP_ID, "OK", "ABCD-GHJL-PRST-W237"),
        TEAM_ARENA_APP_ID: steam.KeyResult(TEAM_ARENA_APP_ID, "OK", "BCDG-HJLP-RSTW-2373-a7"),
    }
    monkeypatch.setattr(net, "fetch", fetch)
    monkeypatch.setattr(engine, "install", install_engine)
    monkeypatch.setattr(steam, "run", run)
    monkeypatch.setattr(maps, "MAPS", ())  # covered by test_maps
    return calls


def test_full_install(tmp_path, offline):
    folder = tmp_path / "q3"
    options = installer.InstallOptions(folder, "me", "secret", steam=True, mods=["cpma"])
    report = installer.install(RecordingContext(), options)

    username, password, keys, apps, include = offline["steam"]
    assert (username, password) == ("me", "secret")
    assert keys == [QUAKE3_APP_ID, TEAM_ARENA_APP_ID]
    assert apps == (QUAKE3_APP_ID, TEAM_ARENA_APP_ID)
    assert include == ("baseq3", "missionpack")

    assert (folder / "baseq3" / "pak0.pk3").is_file()
    assert (folder / "missionpack" / "pak0.pk3").is_file()
    assert (folder / "cpma" / "z-cpma-pak153.pk3").is_file()
    assert (folder / "baseq3" / "map_cpm1.pk3").is_file()
    assert q3key.read(folder, "baseq3") == "abcdghjlprstw237"
    # Team Arena keys come with a checksum, which is dropped.
    assert q3key.read(folder, "missionpack") == "bcdghjlprstw2373"
    assert report.keys == {"baseq3": "abcdghjlprstw237", "missionpack": "bcdghjlprstw2373"}
    assert not (folder / installer.STAGING).exists()


def test_team_arena_is_optional(tmp_path, offline):
    offline["not_owned"].add(TEAM_ARENA_APP_ID)
    folder = tmp_path / "q3"
    ctx = RecordingContext()
    installer.install(ctx, installer.InstallOptions(folder, "me", "secret"))
    assert (folder / "baseq3" / "pak0.pk3").is_file()
    assert not (folder / "missionpack").exists()
    assert q3key.read(folder, "missionpack") is None
    assert any("does not own Team Arena" in line for line in ctx.logs)


def test_quake3_is_required(tmp_path, offline):
    offline["not_owned"].add(QUAKE3_APP_ID)
    with pytest.raises(TaskError, match="does not own Quake III Arena"):
        installer.install(RecordingContext(), installer.InstallOptions(tmp_path / "q3", "me", "x"))


def test_unfinished_files_are_removed(tmp_path, offline, monkeypatch):
    folder = tmp_path / "q3"

    def interrupted(ctx, username, password, key_apps, download=None):
        part = download.dest / "baseq3" / f"pak0.pk3{PART_SUFFIX}"
        part.parent.mkdir(parents=True)
        part.write_text("half")
        raise TaskError("network down")

    monkeypatch.setattr(steam, "run", interrupted)
    with pytest.raises(TaskError):
        installer.install(RecordingContext(), installer.InstallOptions(folder, "me", "x"))
    assert not list(folder.rglob(f"*{PART_SUFFIX}"))


def test_update_without_steam_needs_the_game(tmp_path, offline):
    options = installer.InstallOptions(tmp_path / "q3", steam=False, mods=["cpma"])
    with pytest.raises(TaskError, match="not installed"):
        installer.install(RecordingContext(), options)


def test_update_without_steam(tmp_path, offline):
    folder = tmp_path / "q3"
    (folder / "baseq3").mkdir(parents=True)
    (folder / "baseq3" / "pak0.pk3").write_text("data")
    installer.install(RecordingContext(), installer.InstallOptions(folder, steam=False))
    assert "steam" not in offline


def test_steam_requires_username(tmp_path, offline):
    with pytest.raises(TaskError, match="username"):
        installer.install(RecordingContext(), installer.InstallOptions(tmp_path, steam=True))


def test_missing_quake3_key_is_a_warning(tmp_path, offline):
    offline["keys"] = {}
    options = installer.InstallOptions(tmp_path / "q3", "me", "secret")
    report = installer.install(RecordingContext(), options)
    assert any("did not return a CD key" in w for w in report.warnings)


def test_shortcut_failures_are_warnings(tmp_path, offline, monkeypatch):
    from arenahub.core import shortcuts

    created = []

    def create(install_dir, game, renderer):
        if game.id == "missionpack":
            raise OSError("template not found")
        created.append(game.id)
        return install_dir / f"{game.id}.desktop"

    monkeypatch.setattr(shortcuts, "create", create)
    options = installer.InstallOptions(tmp_path / "q3", "me", "secret", shortcuts=True)
    report = installer.install(RecordingContext(), options)
    assert created == ["baseq3"]
    assert any("Quake III: Team Arena: template not found" in w for w in report.warnings)


def test_install_writes_game_configs(tmp_path, offline):
    from arenahub.core import configs

    folder = tmp_path / "q3"
    player = configs.Player("Ranger", 2.5)
    options = installer.InstallOptions(folder, "me", "secret", mods=["cpma"], player=player)
    installer.install(RecordingContext(), options)

    for game_dir in ("baseq3", "missionpack", "cpma"):
        for name in configs.CONFIG_FILES:
            assert (folder / game_dir / name).is_file(), f"{game_dir}/{name}"
    assert configs.read_player(folder) == player
    text = (folder / "cpma" / "player.cfg").read_text()
    assert configs.read_value(text, "sensitivity") == "2.5"


def test_install_adds_the_maps(tmp_path, offline, monkeypatch):
    installed = []

    def install(ctx, folder, downloads):
        installed.append(folder)
        return maps.InstallResult(failed=["Beatbox (ztn3dm2.pk3): 404"])

    monkeypatch.setattr(maps, "install", install)
    folder = tmp_path / "q3"
    ctx = RecordingContext()
    report = installer.install(ctx, installer.InstallOptions(folder, "me", "secret"))
    assert installed == [folder.resolve()]
    assert "Installing maps" in ctx.stages
    # A missing map does not fail the installation.
    assert report.warnings == ["Map not installed: Beatbox (ztn3dm2.pk3): 404"]
