"""The Server tab: settings and map rotation for a dedicated server, and the running server."""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QProcess, QProcessEnvironment, QSettings, QTimer, Signal
from PySide6.QtGui import QPalette, QValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core import paths, server
from ..core.server import ServerGame, ServerOptions

BOT_SKILLS = ("I Can Win", "Bring It On", "Hurt Me Plenty", "Hardcore", "Nightmare!")
LIMIT_LABELS = {
    "fraglimit": "Frag limit:",
    "capturelimit": "Capture limit:",
    "roundlimit": "Round limit:",
}
COLOR_CODE = re.compile(r"\^[0-9A-Za-z]")
STOP_TIMEOUT = 3000  # ms to wait for "quit" before terminating, and again before killing
WINDOWS_CONSOLE_NOTE = "On Windows the server shows its console in its own window."


class SkillSpinBox(QSpinBox):
    """Bot skill: Quake III's names for 1 to 5, plain numbers above (CPMA goes up to 100)."""

    def textFromValue(self, value: int) -> str:
        if self.maximum() <= len(BOT_SKILLS) and 1 <= value <= len(BOT_SKILLS):
            return f"{value} - {BOT_SKILLS[value - 1]}"
        return str(value)

    def valueFromText(self, text: str) -> int:
        number = re.match(r"\s*(\d+)", text)
        return int(number[1]) if number else self.value()

    def validate(self, text: str, pos: int) -> object:
        if re.match(r"\s*\d+", text):
            return QValidator.State.Acceptable, text, pos
        return QValidator.State.Intermediate, text, pos


class ServerTab(QWidget):
    """Owns the dedicated server process; only one server runs at a time."""

    log = Signal(str)
    status = Signal(str)
    running_changed = Signal(bool)
    join_requested = Signal(object, str)
    """(Game, "host:port") of the running server."""

    def __init__(self, install_dir: Callable[[], Path], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.install_dir = install_dir
        self.settings = QSettings()
        self.process: QProcess | None = None
        self._options: ServerOptions | None = None
        self._available: list[str] = []
        self._shown_game: ServerGame | None = None
        self._installing = False
        self._loading = False

        layout = QVBoxLayout(self)
        columns = QHBoxLayout()
        columns.addWidget(self._settings_group(), stretch=1)
        columns.addWidget(self._rotation_group(), stretch=1)
        layout.addLayout(columns, stretch=1)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setForegroundRole(QPalette.ColorRole.PlaceholderText)
        layout.addWidget(self.note)
        layout.addLayout(self._control_row())

        self._load_settings()
        self._set_running(False)

    # Layout -------------------------------------------------------------------

    def _settings_group(self) -> QGroupBox:
        group = QGroupBox("Settings")
        form = self.form = QFormLayout(group)

        self.game = QComboBox()
        self.game.currentIndexChanged.connect(self._game_changed)
        self.gametype = QComboBox()
        self.gametype.currentIndexChanged.connect(self._gametype_changed)
        self.physics = QComboBox()
        self.physics.addItems(server.CPMA_PHYSICS)
        self.hostname = QLineEdit()
        self.hostname.setMaxLength(server.MAX_TEXT)
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.max_clients = QSpinBox()
        self.max_clients.setRange(1, 64)
        self.timelimit = self._limit_box(" min")
        self.limits = {name: self._limit_box() for name in LIMIT_LABELS}
        self.bots = QSpinBox()
        self.bots.setRange(0, 64)
        self.bots.setSpecialValueText("None")
        self.bot_skill = SkillSpinBox()
        self.password = QLineEdit()
        self.password.setMaxLength(server.MAX_TEXT)
        self.password.setPlaceholderText("None: anyone can join")
        self.rcon_password = QLineEdit()
        self.rcon_password.setMaxLength(server.MAX_TEXT)
        self.rcon_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.rcon_password.setPlaceholderText("None: remote admin disabled")
        self.public = QCheckBox("List the server on the Internet master servers")
        self.public.toggled.connect(self._update_note)

        form.addRow("Mod:", self.game)
        form.addRow("Game type:", self.gametype)
        form.addRow("CPMA physics:", self.physics)
        form.addRow("Server name:", self.hostname)
        form.addRow("Port (UDP):", self.port)
        form.addRow("Max players:", self.max_clients)
        form.addRow("Time limit:", self.timelimit)
        for name, box in self.limits.items():
            form.addRow(LIMIT_LABELS[name], box)
        form.addRow("Bots:", self.bots)
        form.addRow("Bot skill:", self.bot_skill)
        form.addRow("Password:", self.password)
        form.addRow("RCON password:", self.rcon_password)
        form.addRow(self.public)
        return group

    @staticmethod
    def _limit_box(suffix: str = "") -> QSpinBox:
        box = QSpinBox()
        box.setRange(0, 999)
        box.setSuffix(suffix)
        box.setSpecialValueText("None")
        return box

    def _rotation_group(self) -> QGroupBox:
        group = QGroupBox("Map rotation")
        layout = QVBoxLayout(group)

        self.map_filter = QLineEdit()
        self.map_filter.setPlaceholderText("Filter maps")
        self.map_filter.setClearButtonEnabled(True)
        self.map_filter.textChanged.connect(self._fill_available)
        layout.addWidget(self.map_filter)

        lists = QHBoxLayout()
        self.available = QListWidget()
        self.available.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.available.itemDoubleClicked.connect(lambda _item: self._add_maps())
        self.rotation = QListWidget()
        self.rotation.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.rotation.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.rotation.itemDoubleClicked.connect(lambda _item: self._remove_maps())

        buttons = QVBoxLayout()
        buttons.addStretch()
        self.rotation_buttons = []
        for text, tip, slot in (
            ("→", "Add the selected maps to the rotation", self._add_maps),
            ("←", "Remove the selected maps from the rotation", self._remove_maps),
            ("↑", "Play the selected maps earlier", lambda: self._move_maps(-1)),
            ("↓", "Play the selected maps later", lambda: self._move_maps(1)),
        ):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.setFixedWidth(36)
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.rotation_buttons.append(button)
        buttons.addStretch()

        left = QVBoxLayout()
        left.addWidget(QLabel("Installed maps:"))
        left.addWidget(self.available)
        right = QVBoxLayout()
        right.addWidget(QLabel("Rotation, in order:"))
        right.addWidget(self.rotation)
        shuffle = QPushButton("Shuffle")
        shuffle.setToolTip("Put the rotation in a random order")
        shuffle.clicked.connect(self._shuffle_maps)
        right.addWidget(shuffle)
        self.rotation_buttons.append(shuffle)
        lists.addLayout(left, stretch=1)
        lists.addLayout(buttons)
        lists.addLayout(right, stretch=1)
        layout.addLayout(lists)
        return group

    def _control_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.console = QLineEdit()
        self.console.setPlaceholderText("Server command, e.g. status, map q3dm17, kick <name>")
        self.console.returnPressed.connect(self.send_command)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_command)
        self.start_button = QPushButton("Start server")
        self.start_button.clicked.connect(self.start)
        self.join_button = QPushButton("Join")
        self.join_button.setToolTip("Play on this server")
        self.join_button.clicked.connect(self._join)
        self.stop_button = QPushButton("Stop server")
        self.stop_button.clicked.connect(self.stop)
        if paths.system() == "windows":
            # The Windows server reads commands from its own console window only.
            self.console.hide()
            self.send_button.hide()
        row.addWidget(self.console, stretch=1)
        row.addWidget(self.send_button)
        row.addWidget(self.start_button)
        row.addWidget(self.join_button)
        row.addWidget(self.stop_button)
        return row

    # Settings -----------------------------------------------------------------

    def _load_settings(self) -> None:
        s = self.settings
        defaults = ServerOptions("", "", [])
        self.hostname.setText(s.value("server/hostname", defaults.hostname))
        self.port.setValue(int(s.value("server/port", defaults.port)))
        self.max_clients.setValue(int(s.value("server/max_clients", defaults.max_clients)))
        self.timelimit.setValue(int(s.value("server/timelimit", defaults.timelimit)))
        for name, box in self.limits.items():
            box.setValue(int(s.value(f"server/{name}", getattr(defaults, name))))
        self.bots.setValue(int(s.value("server/bots", defaults.bots)))
        self.password.setText(s.value("server/password", ""))
        self.rcon_password.setText(s.value("server/rcon_password", ""))
        self.public.setChecked(s.value("server/public", "false") == "true")
        self.physics.setCurrentText(s.value("server/physics", defaults.physics))

    def save_settings(self) -> None:
        s = self.settings
        s.setValue("server/hostname", self.hostname.text().strip())
        s.setValue("server/port", self.port.value())
        s.setValue("server/max_clients", self.max_clients.value())
        s.setValue("server/timelimit", self.timelimit.value())
        for name, box in self.limits.items():
            s.setValue(f"server/{name}", box.value())
        s.setValue("server/bots", self.bots.value())
        s.remove("server/bot_skill")  # one value for every mod, in earlier versions
        s.setValue("server/password", self.password.text())
        s.setValue("server/rcon_password", self.rcon_password.text())
        s.setValue("server/public", "true" if self.public.isChecked() else "false")
        s.setValue("server/physics", self.physics.currentText())
        if entry := self.current_game():
            s.setValue("server/game", entry.game.id)
            self._save_game_choices(entry)

    def _save_game_choices(self, entry: ServerGame) -> None:
        """Game type, rotation and bot skill are remembered per mod.

        Each mod has its own maps, and CPMA's bot skills go far beyond Quake III's.
        """
        if self.gametype.currentData():
            self.settings.setValue(f"server/gametype/{entry.game.id}", self.gametype.currentData())
        self.settings.setValue(f"server/maps/{entry.game.id}", self.rotation_maps())
        self.settings.setValue(f"server/bot_skill/{entry.game.id}", self.bot_skill.value())

    def _saved_maps(self, game_id: str) -> list[str]:
        value = self.settings.value(f"server/maps/{game_id}", [])
        if isinstance(value, str):  # QSettings returns a single item as a plain string
            value = [value]
        return [str(name) for name in value or []]

    # State --------------------------------------------------------------------

    def refresh(self) -> None:
        """Offer the mods and maps installed in the current folder."""
        if self.running:
            return
        folder = self.install_dir()
        current = self.current_game()
        wanted = current.game.id if current else self.settings.value("server/game", "baseq3")
        self._loading = True
        try:
            self.game.clear()
            for entry in server.hostable_games(folder):
                self.game.addItem(entry.game.title, entry.game.id)
            self.game.setCurrentIndex(max(self.game.findData(wanted), 0))
        finally:
            self._loading = False
        self._game_changed(remember=False)

    def current_game(self) -> ServerGame | None:
        game_id = self.game.currentData()
        return server.server_game(game_id) if game_id else None

    def _game_changed(self, _index: int = 0, remember: bool = True) -> None:
        if self._loading:
            return
        previous = self._shown_game
        if remember and previous:
            self._save_game_choices(previous)
        entry = self._shown_game = self.current_game()

        self._loading = True
        try:
            self.gametype.clear()
            if entry:
                for kind in entry.gametypes:
                    self.gametype.addItem(kind.title, kind.id)
                saved = self.settings.value(f"server/gametype/{entry.game.id}", "")
                self.gametype.setCurrentIndex(max(self.gametype.findData(saved), 0))
        finally:
            self._loading = False

        self._available = server.available_maps(self.install_dir(), entry.game) if entry else []
        self.rotation.clear()
        if entry:
            self.rotation.addItems(list(dict.fromkeys(self._saved_maps(entry.game.id))))
        self._fill_available()
        self.form.setRowVisible(self.physics, bool(entry) and entry.game.id == "cpma")
        if entry:
            skill = self.settings.value(
                f"server/bot_skill/{entry.game.id}", entry.default_bot_skill
            )
            self.bot_skill.setRange(1, entry.max_bot_skill)
            self.bot_skill.setSuffix(
                f" (max {entry.max_bot_skill})" if entry.max_bot_skill > 5 else ""
            )
            self.bot_skill.setValue(int(skill))
        self._gametype_changed()
        self._set_running(self.running)

    def _gametype_changed(self, _index: int = 0) -> None:
        entry = self.current_game()
        limit = None
        if entry and self.gametype.currentData():
            limit = server.gametype(entry, self.gametype.currentData()).limit
        for name, box in self.limits.items():
            self.form.setRowVisible(box, name == limit)
        self._update_note()

    def _update_note(self) -> None:
        parts = []
        entry = self.current_game()
        if entry is None:
            parts.append(
                "Install Quake III Arena first. Rocket Arena 3 cannot host a server with Quake3e."
            )
        elif entry.notes:
            parts.append(entry.notes)
        if self.public.isChecked():
            parts.append(
                f"Players on the Internet need UDP port {self.port.value()} forwarded "
                "to this computer in your router."
            )
        if paths.system() == "windows":
            parts.append(WINDOWS_CONSOLE_NOTE)
        self.note.setText(" ".join(parts))
        self.note.setVisible(bool(parts))

    def _fill_available(self) -> None:
        """Installed maps matching the filter, without those already in the rotation."""
        text = self.map_filter.text().strip().lower()
        chosen = set(self.rotation_maps())
        self.available.clear()
        self.available.addItems(
            [name for name in self._available if text in name and name not in chosen]
        )

    def rotation_maps(self) -> list[str]:
        return [self.rotation.item(i).text() for i in range(self.rotation.count())]

    def _add_maps(self) -> None:
        for item in self.available.selectedItems():
            self.rotation.addItem(item.text())
        self._fill_available()

    def _remove_maps(self) -> None:
        for item in self.rotation.selectedItems():
            self.rotation.takeItem(self.rotation.row(item))
        self._fill_available()

    def _shuffle_maps(self) -> None:
        maps = self.rotation_maps()
        random.shuffle(maps)
        self.rotation.clear()
        self.rotation.addItems(maps)

    def _move_maps(self, step: int) -> None:
        rows = sorted(
            (self.rotation.row(i) for i in self.rotation.selectedItems()), reverse=step > 0
        )
        for row in rows:
            target = row + step
            if 0 <= target < self.rotation.count() and target not in rows:
                self.rotation.insertItem(target, self.rotation.takeItem(row))
                self.rotation.item(target).setSelected(True)
                rows[rows.index(row)] = target

    def options(self) -> ServerOptions | None:
        entry = self.current_game()
        if entry is None or not self.gametype.currentData():
            return None
        return ServerOptions(
            game_id=entry.game.id,
            gametype_id=self.gametype.currentData(),
            maps=self.rotation_maps(),
            hostname=self.hostname.text().strip(),
            port=self.port.value(),
            max_clients=self.max_clients.value(),
            timelimit=self.timelimit.value(),
            fraglimit=self.limits["fraglimit"].value(),
            capturelimit=self.limits["capturelimit"].value(),
            roundlimit=self.limits["roundlimit"].value(),
            password=self.password.text(),
            rcon_password=self.rcon_password.text(),
            public=self.public.isChecked(),
            bots=self.bots.value(),
            bot_skill=self.bot_skill.value(),
            physics=self.physics.currentText(),
        )

    # Running ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self.process is not None

    def set_enabled_for_install(self, installing: bool) -> None:
        """No server can start while an installation changes the files under it."""
        self._installing = installing
        self._set_running(self.running)

    def _set_running(self, running: bool) -> None:
        settings = (
            self.game, self.gametype, self.physics, self.hostname, self.port, self.max_clients,
            self.timelimit, *self.limits.values(), self.bots, self.bot_skill, self.password,
            self.rcon_password, self.public, self.map_filter, self.available, self.rotation,
            *self.rotation_buttons,
        )  # fmt: skip
        for widget in settings:
            widget.setEnabled(not running)
        can_start = not running and not self._installing and self.current_game() is not None
        self.start_button.setEnabled(can_start)
        self.stop_button.setEnabled(running)
        self.join_button.setEnabled(running)
        self.console.setEnabled(running)
        self.send_button.setEnabled(running)

    def start(self) -> None:
        options = self.options()
        if options is None or self.running:
            return
        try:
            server.validate(options)
        except ValueError as exc:
            QMessageBox.warning(self, "ArenaHub", str(exc))
            return
        missing = [name for name in options.maps if name not in self._available]
        if missing:
            QMessageBox.warning(
                self,
                "ArenaHub",
                "These maps are not installed for this mod:\n" + ", ".join(missing),
            )
            return

        folder = self.install_dir()
        try:
            argv = server.command(folder, options)
            server.write_config(folder, options)
        except (FileNotFoundError, OSError) as exc:
            QMessageBox.critical(self, "ArenaHub", f"Could not start the server: {exc}")
            return
        self.save_settings()

        process = self.process = QProcess(self)
        process.setProgram(argv[0])
        process.setArguments(argv[1:])
        process.setWorkingDirectory(str(folder))
        env = QProcessEnvironment()
        for key, value in paths.child_env().items():
            env.insert(key, value)
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._error)

        self._options = options
        self.log.emit(f"== Starting {options.entry.game.title} server on port {options.port}")
        process.start()
        self._set_running(True)
        self.running_changed.emit(True)
        self.status.emit(
            f"Server running: {options.entry.game.title}, {options.gametype.title}, "
            f"port {options.port}"
        )

    def _read_output(self) -> None:
        if self.process is None:
            return
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        for line in text.splitlines():
            if line := COLOR_CODE.sub("", line).rstrip():
                self.log.emit(line)

    def send_command(self) -> None:
        command = self.console.text().strip()
        if not command or self.process is None:
            return
        self.log.emit(f"] {command}")
        self.process.write((command + "\n").encode())
        self.console.clear()

    def stop(self) -> None:
        """Ask the server to quit, then terminate it, then kill it."""
        process = self.process
        if process is None:
            return
        self.status.emit("Stopping the server…")
        self.stop_button.setEnabled(False)
        process.write(b"quit\n")
        QTimer.singleShot(STOP_TIMEOUT, lambda: self._escalate(process, kill=False))

    def _escalate(self, process: QProcess, kill: bool) -> None:
        if self.process is not process or process.state() == QProcess.ProcessState.NotRunning:
            return
        if kill:
            process.kill()
            return
        process.terminate()
        QTimer.singleShot(STOP_TIMEOUT, lambda: self._escalate(process, kill=True))

    def stop_and_wait(self) -> None:
        """Stop the server before the window closes."""
        process = self.process
        if process is None:
            return
        process.write(b"quit\n")
        if not process.waitForFinished(STOP_TIMEOUT):
            process.terminate()
            if not process.waitForFinished(STOP_TIMEOUT):
                process.kill()
                process.waitForFinished(STOP_TIMEOUT)

    def _error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.log.emit(f"Error: the server could not start: {self.process.errorString()}")
            self._finished()

    def _finished(self, *_args) -> None:
        process = self.process
        if process is None:
            return
        self._read_output()
        self.process = self._options = None
        process.deleteLater()
        self.log.emit("== Server stopped")
        self.status.emit("Server stopped")
        self._set_running(False)
        self.running_changed.emit(False)

    def _join(self) -> None:
        if self._options:
            self.join_requested.emit(self._options.entry.game, f"127.0.0.1:{self._options.port}")
