import pytest

from arenahub.core import engine, launcher, server
from arenahub.core.catalog import QUAKE3, ROCKET_ARENA, THREEWAVE
from arenahub.core.server import ServerOptions

from .conftest import make_zip


def options(game_id="baseq3", gametype_id="ffa", maps=("q3dm17", "q3dm1"), **kwargs):
    return ServerOptions(game_id, gametype_id, list(maps), **kwargs)


def test_game_types_are_unique():
    for entry in server.SERVER_GAMES:
        ids = [kind.id for kind in entry.gametypes]
        assert len(ids) == len(set(ids)), entry.game.id
        assert all(
            kind.limit in ("fraglimit", "capturelimit", "roundlimit") for kind in entry.gametypes
        )


def test_rocket_arena_cannot_host():
    # Its server code is a 32-bit native library that Quake3e cannot load.
    assert ROCKET_ARENA not in [entry.game for entry in server.SERVER_GAMES]


def test_rotation_is_a_vstr_chain():
    text = server.config_text(
        options(maps=["q3dm17", "q3dm1", "q3dm6"], timelimit=10, fraglimit=25)
    )
    lines = text.splitlines()
    assert "set g_gametype 0" in lines
    assert "set timelimit 10" in lines
    assert "set fraglimit 25" in lines
    assert 'set arenahub_map0 "map q3dm17; set nextmap vstr arenahub_map1"' in lines
    assert 'set arenahub_map2 "map q3dm6; set nextmap vstr arenahub_map0"' in lines
    assert lines[-1] == "vstr arenahub_map0"


def test_limits_follow_the_game_type():
    ctf = server.config_text(options(gametype_id="ctf", maps=["q3ctf1"], capturelimit=5))
    assert "set capturelimit 5" in ctf.splitlines()
    assert "fraglimit" not in ctf

    arena = server.config_text(options("threewave", "arena", ["q3dm17"], roundlimit=9))
    assert "set g_gametype 11" in arena.splitlines()
    assert "set g_roundlimit 9" in arena.splitlines()
    assert "set p_enablePortal 0" in arena.splitlines()

    ca = server.config_text(options("osp", "ca", ["q3dm17"], roundlimit=4))
    assert "set roundlimit 4" in ca.splitlines()


def test_server_settings():
    text = server.config_text(
        options(hostname="My Server", password="pw", rcon_password="admin", bots=4, bot_skill=5)
    )
    lines = text.splitlines()
    assert 'set sv_hostname "My Server"' in lines
    assert 'set g_password "pw"' in lines
    assert 'set rconpassword "admin"' in lines
    assert "set bot_enable 1" in lines
    assert "set bot_minplayers 4" in lines
    assert "set g_spSkill 5" in lines


def test_osp_uses_its_map_queue(tmp_path):
    opts = options("osp", "ffa", ["q3dm17", "ztn3dm2"])
    path = server.write_config(tmp_path, opts)
    lines = path.read_text().splitlines()
    assert path == tmp_path / "osp" / server.CONFIG_NAME
    assert f"set map_file {server.OSP_MAP_FILE}" in lines
    assert "set map_queue 1" in lines
    assert lines[-1] == "map q3dm17"
    queue = (tmp_path / "osp" / server.OSP_MAP_FILE).read_text().splitlines()
    assert queue == ["q3dm17 0 99 -1 -1 -1 -1", "ztn3dm2 0 99 -1 -1 -1 -1"]


def test_cpma_gets_a_mode_and_map_lists(tmp_path):
    cpma = tmp_path / "cpma"
    (cpma / "cfg-maps").mkdir(parents=True)
    (cpma / "cfg-maps" / "cpm22.cfg").write_text("per-map settings")
    (cpma / "cfg-maps" / "mapmodes.txt").write_text("[maps]\nq3ctf1 ctfs\n")
    (cpma / server.CPMA_CFGDIR).mkdir()
    (cpma / server.CPMA_CFGDIR / "stale.txt").write_text("old")

    opts = options("cpma", "ctf", ["q3ctf1", "q3ctf2"], timelimit=20, capturelimit=6, physics="VQ3")
    lines = server.write_config(tmp_path, opts).read_text().splitlines()

    assert "set mode_start ARENAHUB" in lines
    assert f"set map_cfgdir {server.CPMA_CFGDIR}" in lines
    assert "set map_rotate 1" in lines
    assert "set server_gameplay VQ3" in lines
    assert not any(line.startswith("set g_gametype") for line in lines)
    assert lines[-1] == "map q3ctf1"

    mode = (cpma / "modes" / "ARENAHUB.cfg").read_text().splitlines()
    assert mode == ["type 4", "timelimit 20", "limit 6"]
    cfgdir = cpma / server.CPMA_CFGDIR
    assert (cfgdir / "cpm22.cfg").read_text() == "per-map settings"
    assert not (cfgdir / "stale.txt").exists()
    # No map may switch the mode away from the one chosen.
    assert (cfgdir / "mapmodes.txt").read_text() == "[maps]\n"
    for name in server.CPMA_MAPLISTS:
        assert (cfgdir / name).read_text() == "q3ctf1\nq3ctf2\n"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"maps": []}, "at least one map"),
        ({"maps": ["q3dm17; quit"]}, "Invalid map name"),
        ({"hostname": 'bad "name"'}, "server name cannot contain"),
        ({"hostname": " "}, "Enter a server name"),
        ({"password": "x" * 65}, "at most"),
        ({"port": 80}, "port"),
        ({"bots": 20, "max_clients": 8}, "more bots"),
        ({"bot_skill": 6}, "between 1 and 5"),
    ],
)
def test_validation(changes, message):
    opts = options()
    for key, value in changes.items():
        setattr(opts, key, value)
    with pytest.raises(ValueError, match=message):
        server.validate(opts)


def test_pk3_maps(tmp_path):
    pk3 = make_zip(
        tmp_path / "maps.pk3",
        {
            "maps/MyMap.bsp": "bsp",
            "maps/MyMap.aas": "aas",
            "maps/sub/hidden.bsp": "bsp",
            "levelshots/mymap.jpg": "jpg",
        },
    )
    assert server.pk3_maps(pk3) == {"mymap"}
    (tmp_path / "broken.pk3").write_bytes(b"not a zip")
    assert server.pk3_maps(tmp_path / "broken.pk3") == set()


def test_available_maps_follow_the_search_path(tmp_path):
    for game_dir in ("baseq3", "threewave/maps", "cpma"):
        (tmp_path / game_dir).mkdir(parents=True)
    make_zip(tmp_path / "baseq3" / "pak0.pk3", {"maps/q3dm17.bsp": ""})
    make_zip(tmp_path / "threewave" / "pak00.pk3", {"maps/q3wc1.bsp": ""})
    (tmp_path / "threewave" / "maps" / "loose.bsp").write_text("")
    make_zip(tmp_path / "cpma" / "other.pk3", {"maps/cpmonly.bsp": ""})

    assert server.available_maps(tmp_path, QUAKE3) == ["q3dm17"]
    assert server.available_maps(tmp_path, THREEWAVE) == ["loose", "q3dm17", "q3wc1"]


def test_command(tmp_path, monkeypatch):
    monkeypatch.setattr(engine.paths, "system", lambda: "linux")
    with pytest.raises(FileNotFoundError):
        server.command(tmp_path, options())
    (tmp_path / "quake3e.ded.x64").write_text("")
    (tmp_path / "quake3e.x64").write_text("")

    argv = server.command(tmp_path, options("cpma", "ffa", port=27999))
    assert argv[0] == str(tmp_path / "quake3e.ded.x64")
    assert argv[argv.index("fs_game") + 1] == "cpma"
    assert argv[argv.index("dedicated") + 1] == "1"
    assert argv[argv.index("net_port") + 1] == "27999"
    assert argv[-2:] == ["+exec", server.CONFIG_NAME]

    public = server.command(tmp_path, options(public=True))
    assert public[public.index("dedicated") + 1] == "2"
    assert "fs_game" not in public


def test_launcher_can_join_a_server(tmp_path, monkeypatch):
    monkeypatch.setattr(engine.paths, "system", lambda: "linux")
    (tmp_path / "quake3e.x64").write_text("")
    argv = launcher.command(tmp_path, QUAKE3, engine.Renderer.OPENGL, connect="127.0.0.1:27960")
    assert argv[-2:] == ["+connect", "127.0.0.1:27960"]


def test_cpma_bots_go_up_to_skill_100():
    cpma = server.server_game("cpma")
    assert (cpma.max_bot_skill, cpma.default_bot_skill) == (100, 100)
    text = server.config_text(options("cpma", "ffa", bots=2, bot_skill=100))
    assert "set g_spSkill 100" in text.splitlines()
    with pytest.raises(ValueError, match="between 1 and 100"):
        server.validate(options("cpma", "ffa", bot_skill=101))
