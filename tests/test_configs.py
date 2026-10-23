import re
from pathlib import Path

import pytest

from arenahub.core import configs

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "cfg"
GAME_DIRS = ["arena", "baseq3", "cpma", "missionpack", "osp", "threewave"]


def make_install(tmp_path, *game_dirs):
    for game_dir in game_dirs:
        (tmp_path / game_dir).mkdir(parents=True)
    return tmp_path


# The bundled files ------------------------------------------------------------------


def test_bundled_game_dirs():
    assert configs.bundled_game_dirs() == GAME_DIRS


@pytest.mark.parametrize("game_dir", GAME_DIRS)
def test_autoexec_only_runs_game_then_player(game_dir):
    text = (ASSETS / game_dir / "autoexec.cfg").read_text()
    commands = [line.split("//")[0].split() for line in text.splitlines()]
    commands = [c for c in commands if c]
    assert commands == [["exec", "game.cfg"], ["exec", "player.cfg"]]


@pytest.mark.parametrize("game_dir", GAME_DIRS)
def test_player_settings_live_only_in_player_cfg(game_dir):
    game = (ASSETS / game_dir / "game.cfg").read_text()
    player = (ASSETS / game_dir / "player.cfg").read_text()
    for key in ("name", "sensitivity", "model"):
        assert configs.read_value(game, key) is None
        assert configs.read_value(player, key)
    assert "{quake_3" not in game + player  # no template placeholders left


@pytest.mark.parametrize("game_dir", GAME_DIRS)
def test_every_setting_is_explained(game_dir):
    """Each binding and variable carries a comment saying what it does."""
    for name in configs.CONFIG_FILES:
        for line in (ASSETS / game_dir / name).read_text().splitlines():
            if re.match(r"^(bind|seta|exec|unbindall)\b", line):
                assert "//" in line, f"{game_dir}/{name}: {line}"


# Reading and writing values ---------------------------------------------------------

PLAYER = """// header
seta    name            "Player"    // your player name
seta    sensitivity     "3"         // mouse sensitivity
seta    model           "sarge"     // your player model
"""


def test_read_value():
    assert configs.read_value(PLAYER, "name") == "Player"
    assert configs.read_value(PLAYER, "sensitivity") == "3"
    assert configs.read_value(PLAYER, "headmodel") is None
    assert configs.read_value("name Bare\n", "name") == "Bare"


def test_set_value_keeps_alignment_and_comments():
    text = configs.set_value(PLAYER, "sensitivity", "2.75")
    assert 'seta    sensitivity     "2.75"      // mouse sensitivity\n' in text
    text = configs.set_value(text, "name", "A much longer name")
    assert 'seta    name            "A much longer name" // your player name\n' in text
    # Other lines are untouched.
    assert 'seta    model           "sarge"     // your player model\n' in text


def test_set_value_appends_missing_keys():
    text = configs.set_value("// empty", "name", "Ranger")
    assert text == '// empty\nseta    name            "Ranger"\n'


@pytest.mark.parametrize(
    "player, message",
    [
        (configs.Player("", 3), "Enter a player name"),
        (configs.Player("^1^2", 3), "Now type your name"),  # colours only
        (configs.Player('Bad"Name', 3), "quotes"),
        (configs.Player("x;quit", 3), "semicolons"),
        (configs.Player("x" * 33, 3), "at most"),
        (configs.Player("Ranger", 0), "positive"),
        (configs.Player("Ranger", float("nan")), "positive"),
    ],
)
def test_validate(player, message):
    with pytest.raises(ValueError, match=message):
        configs.validate(player)


# Installing and saving ------------------------------------------------------------


def test_install_copies_only_missing_files(tmp_path):
    folder = make_install(tmp_path, "baseq3", "cpma")
    (folder / "baseq3" / "game.cfg").write_text("// my own game.cfg\n")
    (folder / "baseq3" / "arenahub.cfg").write_text("// from an older ArenaHub\n")

    written = configs.install(folder)

    assert sorted(p.relative_to(folder).as_posix() for p in written) == [
        "baseq3/autoexec.cfg",
        "baseq3/player.cfg",
        "cpma/autoexec.cfg",
        "cpma/game.cfg",
        "cpma/player.cfg",
    ]
    assert (folder / "baseq3" / "game.cfg").read_text() == "// my own game.cfg\n"
    assert not (folder / "baseq3" / "arenahub.cfg").exists()
    assert not (folder / "missionpack").exists()  # only installed games get configs


def test_save_and_read_player(tmp_path):
    folder = make_install(tmp_path, "baseq3", "missionpack", "osp")
    updated = configs.save_player(folder, configs.Player(" Ranger ", 2.75))

    assert len(updated) == 3
    for game_dir in ("baseq3", "missionpack", "osp"):
        text = (folder / game_dir / "player.cfg").read_text()
        assert configs.read_value(text, "name") == "Ranger"
        assert configs.read_value(text, "sensitivity") == "2.75"
        # The model and the comments are kept.
        assert configs.read_value(text, "model")
        assert "// your player name" in text
    assert configs.read_player(folder) == configs.Player("Ranger", 2.75)


def test_save_player_rejects_invalid_values(tmp_path):
    folder = make_install(tmp_path, "baseq3")
    with pytest.raises(ValueError):
        configs.save_player(folder, configs.Player("", 3))
    assert not (folder / "baseq3" / "player.cfg").exists()


def test_read_player_without_configs(tmp_path):
    assert configs.read_player(tmp_path) is None


def test_format_sensitivity():
    assert configs.format_sensitivity(3.0) == "3"
    assert configs.format_sensitivity(2.75) == "2.75"
    assert configs.format_sensitivity(0.1234567) == "0.1235"


@pytest.mark.parametrize(
    "game_dir, expected",
    [
        ("cpma", {"cg_forceModel": "1", "cg_enemyModel": "tankjr/pm"}),
        ("osp", {"cg_forceModel": "1", "cg_enemyModel": "tankjr/pm"}),
        (
            "arena",
            {
                "cg_forceModel": "1",
                "cg_teamModel": "ranger",
                "cg_enemyModel": "tankjr",
                "cg_customColors": "1",
            },
        ),
        (
            "threewave",
            {"cg_forceModel": "1", "cg_usepromodeskins": "1", "cg_enemymodel": "tankjr/pm"},
        ),
        ("baseq3", {"cg_forceModel": "0"}),
    ],
)
def test_team_and_enemy_models(game_dir, expected):
    text = (ASSETS / game_dir / "game.cfg").read_text()
    for key, value in expected.items():
        assert configs.read_value(text, key) == value, key


def test_coloured_name_ends_in_white(tmp_path):
    folder = make_install(tmp_path, "baseq3")
    configs.save_player(folder, configs.Player("^1Evil^4Chuck", 3))

    text = (folder / "baseq3" / "player.cfg").read_text()
    assert configs.read_value(text, "name") == "^1Evil^4Chuck^7"
    # The window gets the name back as it was typed.
    assert configs.read_player(folder).name == "^1Evil^4Chuck"
