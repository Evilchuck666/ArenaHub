"""Small widgets shared by the window."""

from __future__ import annotations

from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QDoubleSpinBox, QWidget


class DecimalSpinBox(QDoubleSpinBox):
    """A number field that always uses '.' as the decimal separator.

    Quake configs write numbers with a dot, so the field shows them the same
    way whatever the system language, and a ',' typed by the user turns into
    '.' as it is typed.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # The C locale uses '.' and never adds thousands separators.
        self.setLocale(QLocale.c())

    def validate(self, text: str, pos: int) -> object:
        return super().validate(text.replace(",", "."), pos)
