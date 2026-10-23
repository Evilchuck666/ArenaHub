"""Quake III colour codes in player names.

A '^' followed by any character other than '^' switches the colour of the text
after it. The game picks one of eight colours from the character's code, so
^0-^7 are the usual ones and every other character repeats them (^8 is black
again, ^a is red). A '^' with nothing after it is drawn as it is.
"""

from __future__ import annotations

ESCAPE = "^"
WHITE = 7
COLORS = (
    ("Black", "#000000"),
    ("Red", "#ff0000"),
    ("Green", "#00ff00"),
    ("Yellow", "#ffff00"),
    ("Blue", "#0000ff"),
    ("Cyan", "#00ffff"),
    ("Magenta", "#ff00ff"),
    ("White", "#ffffff"),
)
"""Name and RGB of each colour, indexed by the number after the '^'."""


def code(color: int) -> str:
    return f"{ESCAPE}{color}"


def _parse(name: str) -> tuple[list[tuple[int, str]], int]:
    pieces: list[tuple[int, str]] = []
    color, text, i = WHITE, "", 0
    while i < len(name):
        if name[i] == ESCAPE and i + 1 < len(name) and name[i + 1] != ESCAPE:
            if text:
                pieces.append((color, text))
                text = ""
            color = (ord(name[i + 1]) - ord("0")) & 7
            i += 2
        else:
            text += name[i]
            i += 1
    if text:
        pieces.append((color, text))
    return pieces, color


def pieces(name: str) -> list[tuple[int, str]]:
    """The name as the game draws it: (colour index, text) runs."""
    return _parse(name)[0]


def plain(name: str) -> str:
    """The name without colour codes."""
    return "".join(text for _color, text in pieces(name))


def for_game(name: str) -> str:
    """The name to write to the configs, switched back to white at the end.

    Otherwise the colour, or a trailing '^', runs into whatever the game
    prints after the name, such as kill messages.
    """
    if _parse(name)[1] != WHITE or name.endswith(ESCAPE):
        return name + code(WHITE)
    return name


def from_game(name: str) -> str:
    """Undo for_game, so the white it added does not show up in the window."""
    rest = name.removesuffix(code(WHITE))
    return rest if rest != name and for_game(rest) == name else name
