import pytest

from arenahub.core import names


@pytest.mark.parametrize(
    "name, pieces",
    [
        ("Ranger", [(7, "Ranger")]),
        ("^1Evil^7Chuck", [(1, "Evil"), (7, "Chuck")]),
        ("^8^aX", [(1, "X")]),  # any character picks a colour: ^8 is black, ^a red
        ("a^^1b", [(7, "a^"), (1, "b")]),  # '^^' is a '^' followed by the next code
        ("Evil^", [(7, "Evil^")]),  # a trailing '^' is drawn as it is
    ],
)
def test_pieces(name, pieces):
    assert names.pieces(name) == pieces


def test_plain():
    assert names.plain("^1Evil^4Chuck") == "EvilChuck"
    assert names.plain("^1^2") == ""


@pytest.mark.parametrize(
    "name, in_game",
    [
        ("Ranger", "Ranger"),
        ("^1Evil", "^1Evil^7"),
        ("^1Evil^7Chuck", "^1Evil^7Chuck"),  # already back to white
        ("^1Evil^7", "^1Evil^7"),
        ("Evil^", "Evil^^7"),  # the '^' would take the next character as a colour
    ],
)
def test_for_game_ends_in_white(name, in_game):
    assert names.for_game(name) == in_game
    color, text = names.pieces(in_game + " fragged")[-1]
    assert color == names.WHITE and text.endswith(" fragged")


@pytest.mark.parametrize("name", ["Ranger", "^1Evil", "^1Evil^7Chuck", "Chuck^7", "Evil^", ""])
def test_from_game_undoes_for_game(name):
    assert names.for_game(names.from_game(names.for_game(name))) == names.for_game(name)
    if names.for_game(name) != name:
        assert names.from_game(names.for_game(name)) == name
