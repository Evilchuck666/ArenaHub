"""The look of the window: a dark theme in Quake III Arena's colours, laid out like QuakeBundle.

Blood red is the accent for the main actions, ember gold marks focus and
highlights, on warm near-black panels.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core import paths

COLORS = {
    "BG": "#0d0a0a",
    "PANEL": "#171111",
    "PANEL_BORDER": "#2e2220",
    "INPUT": "#0b0808",
    "INPUT_BORDER": "#3b2b28",
    "RAISED": "#231817",
    "RAISED_HOVER": "#2f201e",
    "TEXT": "#f2e8e2",
    "MUTED": "#a8938b",
    "DISABLED": "#6a5a55",
    "ACCENT": "#c8321e",
    "ACCENT_HOVER": "#e2452b",
    "ACCENT_PRESSED": "#9c2514",
    "ON_ACCENT": "#fff3ea",
    "GOLD": "#f0a43a",
    "OK": "#a9c96b",
    "ERROR": "#ff6b57",
    "SELECTION": "#6e1f14",
}

STYLE = """
QWidget { color: @TEXT; font-family: 'Inter', 'Segoe UI', 'Noto Sans', sans-serif; font-size: 13px; }
QMainWindow, QDialog { background: @BG; }
QMessageBox, QInputDialog { background: @PANEL; }
QLabel, QCheckBox { background: transparent; }
QLabel#eyebrow { color: @GOLD; font-size: 11px; font-weight: 700; letter-spacing: 3px; }
QLabel#heading { font-size: 32px; font-weight: 750; letter-spacing: -1px; }
QLabel#muted { color: @MUTED; }
QLabel#section { font-size: 14px; font-weight: 650; }
QFrame#panel { background: @PANEL; border: 1px solid @PANEL_BORDER; border-radius: 14px; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }

QPushButton { border: 1px solid @INPUT_BORDER; border-radius: 8px; background: @RAISED; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: @RAISED_HOVER; border-color: #6b4a42; }
QPushButton:pressed { background: #140e0d; }
QPushButton:focus { border-color: @GOLD; }
QPushButton:disabled { color: @DISABLED; background: #191211; border-color: #2a1f1d; }
QPushButton#primary { background: @ACCENT; border-color: @ACCENT; color: @ON_ACCENT; padding: 11px 22px; }
QPushButton#primary:hover { background: @ACCENT_HOVER; border-color: @ACCENT_HOVER; }
QPushButton#primary:pressed { background: @ACCENT_PRESSED; border-color: @ACCENT_PRESSED; }
QPushButton#primary:focus { border-color: @GOLD; }
QPushButton#primary:disabled { background: #4a2620; border-color: #4a2620; color: #a07e74; }

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: @INPUT; border: 1px solid @INPUT_BORDER; border-radius: 7px;
    padding: 6px 10px; selection-background-color: @SELECTION; selection-color: @TEXT;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color: @GOLD; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: @DISABLED; border-color: #261c1a; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url(@CHEVRON_DOWN); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: @RAISED; border: 1px solid @INPUT_BORDER; selection-background-color: @SELECTION; outline: none; padding: 4px; }
QSpinBox, QDoubleSpinBox { padding: 6px 24px 6px 10px; }
QSpinBox QLineEdit, QDoubleSpinBox QLineEdit { background: transparent; border: none; padding: 0; }
QSpinBox::up-button, QDoubleSpinBox::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 22px; border: none; background: transparent; }
QSpinBox::down-button, QDoubleSpinBox::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 22px; border: none; background: transparent; }
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow { image: url(@CHEVRON_UP); width: 10px; height: 10px; }
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { image: url(@CHEVRON_DOWN); width: 10px; height: 10px; }

QCheckBox { spacing: 8px; }
QCheckBox:disabled { color: @DISABLED; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid @INPUT_BORDER; border-radius: 4px; background: @INPUT; }
QCheckBox::indicator:hover { border-color: @GOLD; }
QCheckBox::indicator:checked { background: @ACCENT; border-color: @ACCENT; image: url(@CHECK); }
QCheckBox::indicator:checked:disabled { background: #4a2620; border-color: #4a2620; }

QListWidget, QTreeWidget { background: @INPUT; border: 1px solid @INPUT_BORDER; border-radius: 8px; padding: 4px; outline: none; }
QListWidget:disabled, QTreeWidget:disabled { color: @DISABLED; }
QListWidget::item, QTreeWidget::item { padding: 4px 6px; border-radius: 5px; }
QListWidget::item:hover, QTreeWidget::item:hover { background: #1f1615; }
QListWidget::item:selected, QTreeWidget::item:selected { background: @SELECTION; color: @TEXT; }
QHeaderView { background: transparent; }
QHeaderView::section { background: @PANEL; color: @MUTED; border: none; border-bottom: 1px solid @PANEL_BORDER; padding: 6px 8px; font-weight: 600; }

QTabWidget::pane { border: none; border-top: 1px solid @PANEL_BORDER; top: -1px; }
QTabWidget::tab-bar { left: 0; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; color: @MUTED; padding: 8px 18px 10px 18px; margin-right: 4px; border: none; border-bottom: 2px solid transparent; font-weight: 650; }
QTabBar::tab:hover { color: @TEXT; }
QTabBar::tab:selected { color: @TEXT; border-bottom: 2px solid @ACCENT; }

QProgressBar { background: #2a1f1d; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { border-radius: 3px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @ACCENT, stop:1 @GOLD); }
QPlainTextEdit { background: @INPUT; border: 1px solid @PANEL_BORDER; border-radius: 8px; padding: 6px; color: #c4b2aa; font-family: monospace; font-size: 11px; }

QScrollBar:vertical { background: transparent; width: 8px; margin: 2px 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0 2px; }
QScrollBar#page:vertical { width: 18px; margin: 2px 0 2px 10px; }
QScrollBar::handle:vertical { background: #3e2c29; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:horizontal { background: #3e2c29; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:hover { background: #5a3d37; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }

QMenu { background: @RAISED; border: 1px solid @INPUT_BORDER; padding: 4px; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: @SELECTION; }
QToolTip { background: #241917; color: @TEXT; border: 1px solid #5a3d37; padding: 6px; }
"""


def stylesheet() -> str:
    images = {
        "CHEVRON_DOWN": paths.resource("icons", "ui", "chevron-down.svg"),
        "CHEVRON_UP": paths.resource("icons", "ui", "chevron-up.svg"),
        "CHECK": paths.resource("icons", "ui", "check.svg"),
    }
    text = STYLE
    for name, path in images.items():
        text = text.replace(f"@{name}", path.as_posix())
    # Longest names first, so that @PANEL does not eat the start of @PANEL_BORDER.
    for name in sorted(COLORS, key=len, reverse=True):
        text = text.replace(f"@{name}", COLORS[name])
    return text


def palette() -> QPalette:
    """For what style sheets do not reach, such as placeholder text and highlights."""
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: "BG",
        QPalette.ColorRole.WindowText: "TEXT",
        QPalette.ColorRole.Base: "INPUT",
        QPalette.ColorRole.AlternateBase: "PANEL",
        QPalette.ColorRole.Text: "TEXT",
        QPalette.ColorRole.Button: "RAISED",
        QPalette.ColorRole.ButtonText: "TEXT",
        QPalette.ColorRole.Highlight: "SELECTION",
        QPalette.ColorRole.HighlightedText: "TEXT",
        QPalette.ColorRole.PlaceholderText: "MUTED",
        QPalette.ColorRole.ToolTipBase: "RAISED",
        QPalette.ColorRole.ToolTipText: "TEXT",
        QPalette.ColorRole.Link: "GOLD",
    }
    for role, name in roles.items():
        pal.setColor(role, QColor(COLORS[name]))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(COLORS["DISABLED"]))
    return pal


def apply(window: QWidget) -> None:
    window.setPalette(palette())
    window.setStyleSheet(stylesheet())


def indent_spin_boxes(root: QWidget) -> None:
    """Line the text of spin boxes up with other fields; their padding does not reach it."""
    for box in root.findChildren(QAbstractSpinBox):
        if editor := box.findChild(QLineEdit):
            editor.setTextMargins(6, 0, 0, 0)


def icon(name: str) -> QIcon:
    """One of the small SVG icons in assets/icons/ui."""
    return QIcon(str(paths.resource("icons", "ui", f"{name}.svg")))


def label(text: str = "", kind: str | None = None, wrap: bool = False) -> QLabel:
    """A label with one of the theme's roles: eyebrow, heading, section or muted."""
    widget = QLabel(text)
    widget.setWordWrap(wrap)
    if kind:
        widget.setObjectName(kind)
    return widget


def panel(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    """A rounded panel, optionally headed by a section title."""
    frame = QFrame()
    frame.setObjectName("panel")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    if title:
        layout.addWidget(label(title, "section"))
    return frame, layout


def set_primary(*buttons: QWidget) -> None:
    for button in buttons:
        button.setObjectName("primary")
        button.style().unpolish(button)
        button.style().polish(button)


def scrollable(content: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.verticalScrollBar().setObjectName("page")  # keeps a gap between bar and content
    area.setWidget(content)
    return area
