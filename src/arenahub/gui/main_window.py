"""ArenaHub's main window: installation on one tab, playing on the other."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QIcon, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
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
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core import configs, engine, launcher, paths, q3key
from ..core.catalog import MODS, QUAKE3, TEAM_ARENA
from ..core.context import Prompt
from ..core.engine import Renderer
from ..core.installer import InstallOptions, InstallReport
from .widgets import DecimalSpinBox
from .worker import InstallWorker

STEAM_NOTE = (
    "Quake III Arena is downloaded from Steam with a single login, so your account must own "
    "it. Team Arena is downloaded too when your account owns it. Your password and Steam Guard "
    "code are only sent to Steam and are never stored by ArenaHub."
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"ArenaHub {__version__}")
        self.setWindowIcon(QIcon(str(paths.resource("icons", "arenahub.png"))))
        self.resize(820, 720)

        self.settings = QSettings()
        self.thread: QThread | None = None
        self.worker: InstallWorker | None = None
        self._shown_folder: Path | None = None
        self._loading_player = False

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(self._folder_row())

        self.tabs = QTabWidget()
        self.tabs.addTab(self._install_tab(), "Install")
        self.tabs.addTab(self._play_tab(), "Play")
        layout.addWidget(self.tabs, stretch=3)

        self.status = QLabel("Ready")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.log_view = QPlainTextEdit(readOnly=True)
        self.log_view.setMaximumBlockCount(5000)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.log_view, stretch=2)

        self.setCentralWidget(central)
        self._load_settings()
        self.refresh()

    # Layout -------------------------------------------------------------------

    def _folder_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Installation folder:"))
        self.folder = QLineEdit()
        self.folder.editingFinished.connect(self.refresh)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        self.open_folder = QPushButton("Open")
        self.open_folder.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.install_dir())))
        )
        row.addWidget(self.folder, stretch=1)
        row.addWidget(browse)
        row.addWidget(self.open_folder)
        return row

    def _install_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        steam = QGroupBox("Quake III Arena from Steam")
        form = QFormLayout(steam)
        self.use_steam = QCheckBox("Download or verify the game and fetch the CD keys")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Steam account name")
        note = QLabel(STEAM_NOTE)
        note.setWordWrap(True)
        note.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        form.addRow(self.use_steam)
        form.addRow("Steam username:", self.username)
        form.addRow(note)
        self.use_steam.toggled.connect(self.username.setEnabled)
        layout.addWidget(steam)

        mods = QGroupBox("Mods")
        mods_layout = QVBoxLayout(mods)
        self.mod_boxes: dict[str, QCheckBox] = {}
        for mod in MODS:
            box = QCheckBox(f"{mod.title} — {mod.description}")
            if mod.notes:
                box.setToolTip(mod.notes)
            self.mod_boxes[mod.id] = box
            mods_layout.addWidget(box)
        layout.addWidget(mods)

        self.shortcuts = QCheckBox("Create shortcuts for the installed games")
        layout.addWidget(self.shortcuts)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.install_button = QPushButton("Install")
        self.install_button.setDefault(True)
        self.install_button.clicked.connect(self.start_install)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_install)
        buttons.addWidget(self.install_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        return tab

    def _play_tab(self) -> QWidget:
        tab = QWidget()
        layout = QHBoxLayout(tab)

        left = QVBoxLayout()
        left.addWidget(QLabel("Installed games:"))
        self.games = QListWidget()
        self.games.itemDoubleClicked.connect(lambda _item: self.play())
        left.addWidget(self.games)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play)
        left.addWidget(self.play_button)
        layout.addLayout(left, stretch=1)

        right = QVBoxLayout()
        player = QGroupBox("Player")
        form = QFormLayout(player)
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
        form.addRow("Name:", self.player_name)
        form.addRow("Mouse sensitivity:", self.sensitivity)
        form.addRow("Renderer:", self.renderer)
        note = QLabel("Saved to the game's player.cfg files as you change them.")
        note.setWordWrap(True)
        note.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        form.addRow(note)
        right.addWidget(player)

        keys = QGroupBox("CD keys")
        keys_form = QFormLayout(keys)
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
        right.addWidget(keys)
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
        selected = s.value("mods", [m.id for m in MODS]) or []
        for mod_id, box in self.mod_boxes.items():
            box.setChecked(mod_id in selected)

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("install_dir", self.folder.text())
        s.setValue("username", self.username.text().strip())
        s.setValue("player_name", self.player_name.text())
        s.setValue("sensitivity", self.sensitivity.value())
        s.setValue("renderer", self.renderer.currentData())
        s.setValue("shortcuts", "true" if self.shortcuts.isChecked() else "false")
        s.setValue("mods", [mod_id for mod_id, box in self.mod_boxes.items() if box.isChecked()])

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

        for game, field in ((QUAKE3, self.quake3_key), (TEAM_ARENA, self.team_arena_key)):
            key = q3key.read(folder, game.game_dir)
            field.setText(q3key.display(key) if key else "")
            field.setEnabled(game in installed)

    @property
    def busy(self) -> bool:
        return self.thread is not None

    # Installation -----------------------------------------------------------------

    def start_install(self) -> None:
        options = InstallOptions(
            install_dir=self.install_dir(),
            username=self.username.text().strip(),
            steam=self.use_steam.isChecked(),
            mods=[mod_id for mod_id, box in self.mod_boxes.items() if box.isChecked()],
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
        self.worker.cancelled.connect(lambda: self._set_status("Installation cancelled"))
        self.worker.finished.connect(self._on_finished)
        self._set_busy(True)
        self.thread.start()

    def cancel_install(self) -> None:
        if self.worker:
            self._set_status("Cancelling…")
            self.cancel_button.setEnabled(False)
            self.worker.context.cancel()

    def _set_busy(self, busy: bool) -> None:
        self.install_button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.play_button.setEnabled(not busy)
        self.folder.setEnabled(not busy)

    def _set_status(self, text: str) -> None:
        self.status.setText(text)

    def _on_stage(self, title: str) -> None:
        self._set_status(title)
        self.log_view.appendPlainText(f"== {title}")
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)

    def _on_progress(self, fraction: float, detail: str) -> None:
        if fraction < 0:
            self.progress.setRange(0, 0)  # busy indicator
        else:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(fraction * 1000))
        if detail:
            self.progress.setFormat(detail)
            self.progress.setTextVisible(True)

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
        lines = ["Installation complete."]
        if report.keys:
            lines.append("CD keys written for: " + ", ".join(sorted(report.keys)))
        lines += report.warnings
        QMessageBox.information(self, "ArenaHub", "\n\n".join(lines))
        self.tabs.setCurrentIndex(1)

    def _on_failed(self, message: str) -> None:
        self._set_status("Installation failed")
        self.log_view.appendPlainText(f"Error: {message}")
        QMessageBox.critical(self, "ArenaHub", message)

    def _on_finished(self) -> None:
        self.thread.quit()
        self.thread.wait()
        self.thread.deleteLater()
        self.worker.deleteLater()
        self.thread = self.worker = None
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
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
        self._save_settings()
        event.accept()
