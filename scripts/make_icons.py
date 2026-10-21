"""Render assets/icons/arenahub.svg into the PNG, ICO and ICNS files the app and builds use.

Run after changing the SVG:  uv run python scripts/make_icons.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICONS = Path(__file__).resolve().parent.parent / "assets" / "icons"


def render(renderer: QSvgRenderer, size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def main() -> int:
    app = QGuiApplication(sys.argv)  # noqa: F841 - QPainter needs an application
    renderer = QSvgRenderer(str(ICONS / "arenahub.svg"))
    outputs = {"arenahub.png": 256, "arenahub.ico": 256, "arenahub.icns": 512}
    for name, size in outputs.items():
        if not render(renderer, size).save(str(ICONS / name)):
            print(f"Could not write {name}", file=sys.stderr)
            return 1
        print(f"Wrote {ICONS / name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
