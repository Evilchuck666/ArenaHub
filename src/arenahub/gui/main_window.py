"""ArenaHub's main window, laid out like QuakeBundle: tabs on the left, activity on the right."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core import configs, engine, launcher, maps, paths, q3key
from ..core.catalog import MODS, QUAKE3, TEAM_ARENA, Game
from ..core.context import Prompt
from ..core.engine import Renderer
from ..core.installer import InstallOptions, InstallReport
from . import theme
from .server_tab import ServerTab
from .theme import COLORS, label, panel
from .widgets import DecimalSpinBox
from .worker import InstallWorker

STEAM_NOTE = (
    "Quake III Arena is downloaded from Steam with a single login, so your account must own "
    "it. Team Arena is downloaded too when your account owns it. Your password and Steam Guard "
    "code are only sent to Steam and are never stored by ArenaHub."
)
MAX_STAGES = 7
"""Installation steps listed in the activity panel; older ones scroll away."""


class Emblem(QSvgWidget):
    """ArenaHub's crosshair emblem, drawn as a vector at any display scale."""

    def __init__(self) -> None:
        super().__init__(str(paths.resource("icons", "arenahub-emblem.svg")))
        self.setFixedSize(200, 120)
        self.setAccessibleName("ArenaHub emblem")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"ArenaHub {__version__}")
        self.setWindowIcon(QIcon(str(paths.resource("icons", "arenahub.png"))))
        self.resize(1120, 850)
        self.setMinimumSize(960, 700)
        theme.apply(self)

        self.settings = QSettings()
        self.thread: QThread | None = None
        self.worker: InstallWorker | None = None
        self._shown_folder: Path | None = None
        self._loading_player = False
        self._stages: list[QLabel] = []

        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(28, 22, 28, 16)
        outer.setSpacing(18)
        header = QHBoxLayout()
        header.addWidget(label("A  /  ARENAHUB", "eyebrow"))
        header.addStretch()
        header.addWidget(label("YOUR GATEWAY TO THE ARENA", "muted"))
        outer.addLayout(header)

        columns = QHBoxLayout()
        columns.setSpacing(24)
        columns.addWidget(self._main_column(), stretch=1)
        columns.addWidget(self._activity_panel())
        outer.addLayout(columns, stretch=1)

        footer = QHBoxLayout()
        footer.addWidget(label("QUAKE III ARENA  /  1999 → TODAY", "muted"))
        footer.addStretch()
        footer.addWidget(label(f"ArenaHub {__version__}  ·  Qt6  ·  Quake3e", "muted"))
        outer.addLayout(footer)

        self.setCentralWidget(central)
        theme.indent_spin_boxes(self)
        self.server_tab.log.connect(self.log_view.appendPlainText)
        self.server_tab.status.connect(self._set_status)
        self.server_tab.running_changed.connect(lambda _running: self._set_busy(self.busy))
        self.server_tab.join_requested.connect(self.join)
        self._load_settings()
        self.refresh()

    # Layout -------------------------------------------------------------------

    def _main_column(self) -> QWidget:
        content = QWidget()
        column = QVBoxLayout(content)
        column.setContentsMargins(0, 0, 10, 0)
        column.setSpacing(16)

        hero = QHBoxLayout()
        words = QVBoxLayout()
        words.addWidget(label("QUAKE III ARENA  ·  TEAM ARENA  ·  CLASSIC MODS", "eyebrow"))
        words.addWidget(label("Enter the arena.", "heading"))
        words.addWidget(
            label("Install it from your Steam library, play, or host your own server.", "muted")
        )
        hero.addLayout(words, stretch=1)
        hero.addWidget(Emblem())
        column.addLayout(hero)

        column.addWidget(label("Installation folder", "muted"))
        row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setAccessibleName("Installation folder")
        self.folder.editingFinished.connect(self.refresh)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder, stretch=1)
        row.addWidget(browse)
        column.addLayout(row)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)  # the pane's own top border is the base line
        self.tabs.addTab(self._install_tab(), "Install")
        self.tabs.addTab(self._play_tab(), "Play")
        self.server_tab = ServerTab(self.install_dir)
        self.tabs.addTab(self.server_tab, "Server")
        self.tabs.addTab(self._maps_tab(), "Maps")
        column.addWidget(self.tabs, stretch=1)
        return theme.scrollable(content)

    def _activity_panel(self) -> QWidget:
        side, layout = panel()
        side.setFixedWidth(300)
        layout.setContentsMargins(20, 22, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(label("ACTIVITY CENTER", "eyebrow"))
        self.status = label("Ready", "section", wrap=True)
        layout.addWidget(self.status)
        self.stage_list = QVBoxLayout()
        self.stage_list.setSpacing(8)
        layout.addLayout(self.stage_list)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.progress_text = label("Waiting for a task", "muted", wrap=True)
        layout.addWidget(self.progress_text)
        self.cancel_button = QPushButton("Cancel installation")
        self.cancel_button.clicked.connect(self.cancel_install)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)
        layout.addSpacing(6)
        layout.addWidget(label("Activity log", "section"))
        self.log_view = QPlainTextEdit(readOnly=True)
        self.log_view.setMaximumBlockCount(5000)
        layout.addWidget(self.log_view, stretch=1)
        self.open_folder = QPushButton("Open game folder")
        self.open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.install_dir())))
        )
        layout.addWidget(self.open_folder)
        return side

    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(14)
        return page, layout

    def _install_tab(self) -> QWidget:
        tab, layout = self._page()

        steam, form = panel("01   Quake III Arena from Steam")
        self.use_steam = QCheckBox("Download or verify the game and fetch the CD keys")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Your Steam account")
        self.username.setAccessibleName("Steam username")
        self.use_steam.toggled.connect(self.username.setEnabled)
        form.addWidget(self.use_steam)
        form.addWidget(label("Steam username", "muted"))
        form.addWidget(self.username)
        form.addWidget(label(STEAM_NOTE, "muted", wrap=True))
        layout.addWidget(steam)

        mods, mods_layout = panel("02   Mods installed with the game")
        for mod in MODS:
            entry = QVBoxLayout()
            entry.setSpacing(2)
            entry.addWidget(label(mod.title, wrap=True))
            entry.addWidget(label(mod.description, "muted", wrap=True))
            if mod.notes:
                entry.addWidget(label(mod.notes, "muted", wrap=True))
            mods_layout.addLayout(entry)
        layout.addWidget(mods)

        self.shortcuts = QCheckBox("Create shortcuts for the installed games")
        layout.addWidget(self.shortcuts)
        self.install_button = QPushButton("Install")
        self.install_button.setDefault(True)
        self.install_button.clicked.connect(self.start_install)
        theme.set_primary(self.install_button)
        layout.addWidget(self.install_button)
        layout.addStretch()
        return tab

    def _maps_tab(self) -> QWidget:
        """The map packs every installation gets; only a list to read."""
        tab, layout = self._page()
        box, box_layout = panel(f"{len(maps.MAPS)} map packs come with the game")
        box_layout.addWidget(
            label(
                "Installed into baseq3, so every mod can load them. They are downloaded from "
                "lvlworld.com, or from ArenaHub's own backup copy when that fails.",
                "muted",
                wrap=True,
            )
        )

        self.maps_list = QTreeWidget()
        self.maps_list.setHeaderLabels(["Title", "Author", "Maps", "Modes"])
        self.maps_list.setRootIsDecorated(False)
        self.maps_list.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.maps_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.maps_list.setIconSize(QSize(*maps.THUMBNAIL_SIZE))
        self.maps_list.setMinimumHeight(420)
        for pack in maps.MAPS:
            names = ", ".join(pack.maps)
            if len(pack.maps) > 3:
                names = f"{pack.maps[0]} … {pack.maps[-1]} ({len(pack.maps)} maps)"
            item = QTreeWidgetItem([pack.title, pack.author, names, ", ".join(pack.modes)])
            tooltip = (
                f"{pack.filename}, {pack.size / 1024**2:.1f} MiB\n"
                f"Maps: {', '.join(pack.maps)}\n{pack.url}"
            )
            for column in range(item.columnCount()):
                item.setToolTip(column, tooltip)
            if (levelshot := maps.thumbnail(pack)).is_file():
                item.setIcon(0, QIcon(str(levelshot)))
            self.maps_list.addTopLevelItem(item)
        self.maps_list.setSortingEnabled(True)
        self.maps_list.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        for column in range(self.maps_list.columnCount() - 1):
            self.maps_list.resizeColumnToContents(column)
        box_layout.addWidget(self.maps_list, stretch=1)
        layout.addWidget(box, stretch=1)
        return tab

    def _play_tab(self) -> QWidget:
        tab, page = self._page()
        layout = QHBoxLayout()
        layout.setSpacing(14)
        page.addLayout(layout)
        page.addStretch()

        games, left = panel("Installed games")
        self.games = QListWidget()
        self.games.setMinimumHeight(180)
        self.games.itemDoubleClicked.connect(lambda _item: self.play())
        left.addWidget(self.games)
        self.play_button = QPushButton("▶  Play")
        self.play_button.clicked.connect(self.play)
        theme.set_primary(self.play_button)
        left.addWidget(self.play_button)
        layout.addWidget(games, stretch=1)

        right = QVBoxLayout()
        right.setSpacing(14)
        player, player_layout = panel("Player")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.player_name = QLineEdit()
        self.player_name.setMaxLength(configs.MAX_NAME_LENGTH)
        self.player_name.setPlaceholderText("Your name in game")
        self.sensitivity = DecimalSpinBox()
        self.sensitivity.setRange(0.01, 30.0)
        self.sensitivity.setDecimals(2)
        self.sensitivity.setSingleStep(0.1)
        # Both are written to every player.cfg as soon as they change (see save_player).
        self._player_timer = QTimer(self, singleShot=True, interval=600)
        self._player_timer.timeout.connect(self.save_player)
        self.player_name.editingFinished.connect(self.save_player)
        self.sensitivity.valueChanged.connect(self._player_changed)
        self.renderer = QComboBox()
        self.renderer.addItem("OpenGL", Renderer.OPENGL.value)
        self.renderer.addItem("Vulkan", Renderer.VULKAN.value)
        grid.addWidget(label("Name", "muted"), 0, 0, 1, 2)
        grid.addWidget(self.player_name, 1, 0, 1, 2)
        grid.addWidget(label("Mouse sensitivity", "muted"), 2, 0)
        grid.addWidget(label("Renderer", "muted"), 2, 1)
        grid.addWidget(self.sensitivity, 3, 0)
        grid.addWidget(self.renderer, 3, 1)
        player_layout.addLayout(grid)
        player_layout.addWidget(
            label("Saved to the game's player.cfg files as you change them.", "muted", wrap=True)
        )
        right.addWidget(player)

        # Only shown when an installed game has no q3key (see refresh).
        self.keys_group, keys_layout = panel("CD keys")
        keys_form = self.keys_form = QFormLayout()
        keys_form.addRow(
            label(
                "Steam did not provide these keys. Copy them from the Steam client "
                "(Manage → CD Keys) and save them here.",
                "muted",
                wrap=True,
            )
        )
        self.quake3_key = QLineEdit()
        self.team_arena_key = QLineEdit()
        for field in (self.quake3_key, self.team_arena_key):
            field.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
            field.setMaxLength(24)  # Team Arena keys come with a checksum: ...-XXXX-XX
        save_keys = QPushButton("Save keys")
        save_keys.clicked.connect(self.save_keys)
        keys_form.addRow(f"{QUAKE3.title}:", self.quake3_key)
        keys_form.addRow(f"{TEAM_ARENA.title}:", self.team_arena_key)
        keys_form.addRow(save_keys)
        keys_layout.addLayout(keys_form)
        right.addWidget(self.keys_group)
        right.addStretch()
        layout.addLayout(right, stretch=1)
        return tab

    # Settings -------------------------------------------------------------------

    def _load_settings(self) -> None:
        s = self.settings
        self.folder.setText(s.value("install_dir", str(paths.default_install_dir())))
        self.username.setText(s.value("username", ""))
        self._show_player(
            configs.Player(
                s.value("player_name", "") or configs.Player.name,
                float(s.value("sensitivity", configs.Player.sensitivity)),
            )
        )
        index = self.renderer.findData(s.value("renderer", Renderer.OPENGL.value))
        self.renderer.setCurrentIndex(max(index, 0))
        self.shortcuts.setChecked(s.value("shortcuts", "false") == "true")

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("install_dir", self.folder.text())
        s.setValue("username", self.username.text().strip())
        s.setValue("player_name", self.player_name.text())
        s.setValue("sensitivity", self.sensitivity.value())
        s.setValue("renderer", self.renderer.currentData())
        s.setValue("shortcuts", "true" if self.shortcuts.isChecked() else "false")
        s.remove("mods")  # the mod selection of earlier versions
        self.server_tab.save_settings()

    # State ------------------------------------------------------------------------

    def install_dir(self) -> Path:
        return Path(self.folder.text().strip() or paths.default_install_dir()).expanduser()

    def _browse(self) -> None:
        start = str(self.install_dir())
        folder = QFileDialog.getExistingDirectory(self, "Installation folder", start)
        if folder:
            self.folder.setText(folder)
            self.refresh()

    def refresh(self) -> None:
        """Update the window to what is installed in the chosen folder."""
        folder = self.install_dir()
        installed = launcher.installed_games(folder)
        has_quake3 = QUAKE3 in installed

        self.games.clear()
        for game in installed:
            item = QListWidgetItem(game.title)
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setToolTip(game.notes or game.description)
            self.games.addItem(item)
        if self.games.count():
            self.games.setCurrentRow(0)

        has_engine = engine.executable(folder) is not None
        self.play_button.setEnabled(bool(installed) and has_engine and not self.busy)
        if folder != self._shown_folder:
            # A new folder: suggest Steam only when the game is not there yet, and
            # show the player settings saved in its configs.
            self._shown_folder = folder
            self.use_steam.setChecked(not has_quake3)
            if player := configs.read_player(folder):
                self._show_player(player)
        self.username.setEnabled(self.use_steam.isChecked())
        self.install_button.setText("Update" if has_quake3 else "Install")
        self.open_folder.setEnabled(folder.is_dir())
        self.server_tab.refresh()

        # Ask for a key only for installed games whose q3key is missing or invalid.
        missing = False
        for game, field in ((QUAKE3, self.quake3_key), (TEAM_ARENA, self.team_arena_key)):
            needed = game in installed and q3key.read(folder, game.game_dir) is None
            self.keys_form.setRowVisible(field, needed)
            field.setEnabled(needed)
            if not needed:
                field.clear()
            missing = missing or needed
        self.keys_group.setVisible(missing)

    @property
    def busy(self) -> bool:
        return self.thread is not None

    # Installation -----------------------------------------------------------------

    def start_install(self) -> None:
        options = InstallOptions(
            install_dir=self.install_dir(),
            username=self.username.text().strip(),
            steam=self.use_steam.isChecked(),
            mods=[mod.id for mod in MODS],  # every mod is always installed
            shortcuts=self.shortcuts.isChecked(),
            renderer=Renderer(self.renderer.currentData()),
            player=self._valid_player(),
        )
        if options.steam:
            if not options.username:
                QMessageBox.warning(self, "ArenaHub", "Enter your Steam username first.")
                return
            password = self._ask_secret(
                "Steam password", f"Password for the Steam account {options.username}:"
            )
            if not password:
                return
            options.password = password

        self._save_settings()
        self.log_view.clear()
        self._clear_stages()
        self.worker = InstallWorker(options)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.log_view.appendPlainText)
        self.worker.stage.connect(self._on_stage)
        self.worker.progress.connect(self._on_progress)
        self.worker.prompt.connect(self._on_prompt)
        self.worker.succeeded.connect(self._on_succeeded)
        self.worker.failed.connect(self._on_failed)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.finished.connect(self._on_finished)
        self._set_busy(True)
        self.thread.start()

    def cancel_install(self) -> None:
        if self.worker:
            self._set_status("Cancelling…")
            self.cancel_button.setEnabled(False)
            self.worker.context.cancel()

    def _set_busy(self, busy: bool) -> None:
        # A running server keeps the folder and its files as they are.
        serving = self.server_tab.running
        self.install_button.setEnabled(not busy and not serving)
        self.cancel_button.setEnabled(busy)
        self.cancel_button.setVisible(busy)
        self.play_button.setEnabled(not busy)
        self.folder.setEnabled(not busy and not serving)
        self.server_tab.set_enabled_for_install(busy)

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def _clear_stages(self) -> None:
        for item in self._stages:
            item.deleteLater()
        self._stages.clear()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress_text.setText("Waiting for a task")

    def _mark_stage(self, item: QLabel, mark: str, color: str) -> None:
        item.setText(f"{mark}   {item.text()[4:]}")
        item.setStyleSheet(f"color: {COLORS[color]};")

    def _on_stage(self, title: str) -> None:
        """List the installation steps: done ones ticked, the current one highlighted."""
        self._set_status(title)
        self.log_view.appendPlainText(f"== {title}")
        if self._stages:
            self._mark_stage(self._stages[-1], "✓", "OK")
        item = label(f"●   {title}", wrap=True)
        item.setStyleSheet(f"color: {COLORS['GOLD']};")
        self._stages.append(item)
        self.stage_list.addWidget(item)
        while len(self._stages) > MAX_STAGES:
            self._stages.pop(0).deleteLater()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress_text.setText("Working…")

    def _on_progress(self, fraction: float, detail: str) -> None:
        if fraction < 0:
            self.progress.setRange(0, 0)  # busy indicator
            text = detail
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(fraction * 1000))
            text = f"{detail}  ·  {fraction:.0%}" if detail else f"{fraction:.0%}"
        if text:
            self.progress_text.setText(text)

    def _on_cancelled(self) -> None:
        self._set_status("Installation cancelled")
        if self._stages:
            self._mark_stage(self._stages[-1], "○", "MUTED")
        self.progress_text.setText("You can start again whenever you like.")

    def _on_prompt(self, prompt: Prompt) -> None:
        message = prompt.message
        if prompt.retry:
            message = "The previous code was not accepted.\n" + message
        answer, ok = QInputDialog.getText(self, "Steam Guard", message)
        self.worker.context.answer(answer.strip() if ok and answer.strip() else None)

    def _ask_secret(self, title: str, message: str) -> str | None:
        text, ok = QInputDialog.getText(self, title, message, QLineEdit.EchoMode.Password)
        return text if ok and text else None

    def _on_succeeded(self, report: InstallReport) -> None:
        self._set_status("Installation complete")
        for item in self._stages:
            self._mark_stage(item, "✓", "OK")
        self.progress_text.setText("Your next match awaits.")
        lines = ["Installation complete."]
        if report.keys:
            lines.append("CD keys written for: " + ", ".join(sorted(report.keys)))
        lines += report.warnings
        QMessageBox.information(self, "ArenaHub", "\n\n".join(lines))
        self.tabs.setCurrentIndex(1)

    def _on_failed(self, message: str) -> None:
        self._set_status("Installation failed")
        if self._stages:
            self._mark_stage(self._stages[-1], "✕", "ERROR")
        self.progress_text.setText("See the activity log, then try again.")
        self.log_view.appendPlainText(f"Error: {message}")
        QMessageBox.critical(self, "ArenaHub", message)

    def _on_finished(self) -> None:
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.worker.deleteLater()
        self.thread = self.worker = None
        self.progress.setRange(0, 1000)
        self.progress.setValue(1000 if self.status.text() == "Installation complete" else 0)
        self._set_busy(False)
        self.refresh()

    # Playing ----------------------------------------------------------------------

    def _player(self) -> configs.Player:
        return configs.Player(self.player_name.text().strip(), self.sensitivity.value())

    def _valid_player(self) -> configs.Player | None:
        player = self._player()
        try:
            configs.validate(player)
        except ValueError:
            return None
        return player

    def _show_player(self, player: configs.Player) -> None:
        """Fill in the fields without saving them back."""
        self._loading_player = True
        try:
            self.player_name.setText(player.name)
            self.sensitivity.setValue(player.sensitivity)
        finally:
            self._loading_player = False

    def _player_changed(self) -> None:
        if not self._loading_player:
            self._player_timer.start()

    def save_player(self) -> bool:
        """Write name and sensitivity into the player.cfg files of the installation."""
        self._player_timer.stop()
        if self._loading_player:
            return True
        player = self._player()
        try:
            configs.validate(player)
        except ValueError as exc:
            QMessageBox.warning(self, "ArenaHub", str(exc))
            return False
        self._save_settings()
        try:
            updated = configs.save_player(self.install_dir(), player)
        except OSError as exc:
            QMessageBox.warning(self, "ArenaHub", f"Could not save the player settings: {exc}")
            return False
        if updated:
            self._set_status(f"Player settings saved to {len(updated)} config files")
        return True

    def play(self) -> None:
        item = self.games.currentItem()
        if item is None or not self.save_player():
            return
        game = item.data(Qt.ItemDataRole.UserRole)
        try:
            launcher.launch(self.install_dir(), game, Renderer(self.renderer.currentData()))
        except OSError as exc:
            QMessageBox.critical(self, "ArenaHub", f"Could not start {game.title}: {exc}")
            return
        self._set_status(f"Started {game.title}")

    def join(self, game: Game, address: str) -> None:
        """Play on the server started from the Server tab."""
        if not self.save_player():
            return
        renderer = Renderer(self.renderer.currentData())
        try:
            launcher.launch(self.install_dir(), game, renderer, connect=address)
        except OSError as exc:
            QMessageBox.critical(self, "ArenaHub", f"Could not start {game.title}: {exc}")
            return
        self._set_status(f"Joining the server at {address}")

    def save_keys(self) -> None:
        folder = self.install_dir()
        problems = []
        for game, field in ((QUAKE3, self.quake3_key), (TEAM_ARENA, self.team_arena_key)):
            text = field.text().strip()
            if not text or not field.isEnabled():
                continue
            if not q3key.is_valid(text):
                problems.append(f"The {game.title} key is not a valid Quake III CD key.")
                continue
            q3key.write(folder, game.game_dir, text)
        if problems:
            QMessageBox.warning(self, "ArenaHub", "\n".join(problems))
        else:
            self._set_status("CD keys saved")
        self.refresh()

    # Closing ------------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.busy:
            answer = QMessageBox.question(
                self, "ArenaHub", "An installation is running. Cancel it and quit?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.worker.context.cancel()
            self.thread.quit()
            self.thread.wait()
        if self.server_tab.running:
            answer = QMessageBox.question(
                self, "ArenaHub", "A server is running. Stop it and quit?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.server_tab.stop_and_wait()
        self._save_settings()
        event.accept()
