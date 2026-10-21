import re

from arenahub.core.catalog import GAMES, MODS, game_by_id


def test_ids_and_dirs_are_unique():
    assert len({g.id for g in GAMES}) == len(GAMES)
    assert len({g.game_dir for g in GAMES}) == len(GAMES)


def test_downloads_are_pinned():
    for mod in MODS:
        for item in mod.downloads:
            assert re.fullmatch(r"[0-9a-f]{64}", item.sha256), item.filename
            assert item.size > 0
            assert item.urls and all(url.startswith("https://") for url in item.urls)


def test_markers_belong_to_the_game_dir():
    for game in GAMES:
        assert game.marker.startswith(game.game_dir + "/")


def test_game_by_id():
    assert game_by_id("cpma").title == "Challenge ProMode Arena"
