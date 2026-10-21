import shutil

import pytest

from arenahub.core import engine, installer, net, q3key, steam_keys, steamcmd
from arenahub.core.catalog import QUAKE3_APP_ID, TEAM_ARENA_APP_ID
from arenahub.core.context import TaskError

from .conftest import RecordingContext, make_zip


@pytest.fixture
def offline(tmp_path, monkeypatch):
    """Replace every network and Steam step with local fakes."""
    calls = {}
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

    def fetch_keys(ctx, username, password, app_ids):
        calls["keys"] = (username, password, app_ids)
        return {
            QUAKE3_APP_ID: steam_keys.KeyResult(QUAKE3_APP_ID, "OK", "ABCD-GHJL-PRST-W237"),
            TEAM_ARENA_APP_ID: steam_keys.KeyResult(TEAM_ARENA_APP_ID, "AccessDenied", ""),
        }

    # Each Steam app brings its own folder, like depots 2201 and 2351.
    depot_files = {
        QUAKE3_APP_ID: ("baseq3/pak0.pk3", "quake3.exe"),
        TEAM_ARENA_APP_ID: ("missionpack/pak0.pk3",),
    }
    calls["not_owned"] = set()

    def download_app(ctx, exe, app_id, depot, username, password):
        calls.setdefault("steamcmd", []).append((app_id, username, password))
        if app_id in calls["not_owned"]:
            raise steamcmd.NotOwned(app_id, "This Steam account does not own this game.")
        for name in depot_files[app_id]:
            (depot / name).parent.mkdir(parents=True, exist_ok=True)
            (depot / name).write_text("data")

    monkeypatch.setattr(net, "fetch", fetch)
    monkeypatch.setattr(engine, "install", install_engine)
    monkeypatch.setattr(steam_keys, "fetch", fetch_keys)
    monkeypatch.setattr(steamcmd, "install", lambda ctx: tmp_path / "steamcmd.sh")
    monkeypatch.setattr(steamcmd, "download_app", download_app)
    return calls


def test_full_install(tmp_path, offline):
    folder = tmp_path / "q3"
    options = installer.InstallOptions(folder, "me", "secret", steam=True, mods=["cpma"])
    report = installer.install(RecordingContext(), options)

    assert offline["keys"] == ("me", "secret", [QUAKE3_APP_ID, TEAM_ARENA_APP_ID])
    assert offline["steamcmd"] == [
        (QUAKE3_APP_ID, "me", "secret"),
        (TEAM_ARENA_APP_ID, "me", "secret"),
    ]
    assert (folder / "baseq3" / "pak0.pk3").is_file()
    assert (folder / "missionpack" / "pak0.pk3").is_file()
    assert not (folder / "quake3.exe").exists()
    assert (folder / "cpma" / "z-cpma-pak153.pk3").is_file()
    assert (folder / "baseq3" / "map_cpm1.pk3").is_file()
    assert q3key.read(folder, "baseq3") == "abcdghjlprstw237"
    assert q3key.read(folder, "missionpack") is None
    assert report.keys == {"baseq3": "abcdghjlprstw237"}
    assert not (folder / installer.STAGING).exists()


def test_update_without_steam_needs_the_game(tmp_path, offline):
    options = installer.InstallOptions(tmp_path / "q3", steam=False, mods=["cpma"])
    with pytest.raises(TaskError, match="not installed"):
        installer.install(RecordingContext(), options)


def test_update_without_steam(tmp_path, offline):
    folder = tmp_path / "q3"
    (folder / "baseq3").mkdir(parents=True)
    (folder / "baseq3" / "pak0.pk3").write_text("data")
    installer.install(RecordingContext(), installer.InstallOptions(folder, steam=False))
    assert "keys" not in offline and "steamcmd" not in offline


def test_team_arena_is_optional(tmp_path, offline):
    offline["not_owned"].add(TEAM_ARENA_APP_ID)
    folder = tmp_path / "q3"
    ctx = RecordingContext()
    installer.install(ctx, installer.InstallOptions(folder, "me", "secret"))
    assert (folder / "baseq3" / "pak0.pk3").is_file()
    assert not (folder / "missionpack").exists()
    assert any("does not own Team Arena" in line for line in ctx.logs)


def test_quake3_is_required(tmp_path, offline):
    offline["not_owned"].add(QUAKE3_APP_ID)
    with pytest.raises(TaskError, match="does not own Quake III Arena"):
        installer.install(RecordingContext(), installer.InstallOptions(tmp_path / "q3", "me", "x"))
    assert [call[0] for call in offline["steamcmd"]] == [QUAKE3_APP_ID]


def test_steam_requires_username(tmp_path, offline):
    with pytest.raises(TaskError, match="username"):
        installer.install(RecordingContext(), installer.InstallOptions(tmp_path, steam=True))


def test_missing_quake3_key_is_a_warning(tmp_path, offline, monkeypatch):
    monkeypatch.setattr(steam_keys, "fetch", lambda *args: {})
    options = installer.InstallOptions(tmp_path / "q3", "me", "secret")
    report = installer.install(RecordingContext(), options)
    assert any("did not return a CD key" in w for w in report.warnings)
