import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture
def window(tmp_path):
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path / "cfg"))
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("ArenaHubTests")
    from arenahub.gui.main_window import MainWindow

    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()
    app.processEvents()


def test_window_reflects_install_folder(window, tmp_path):
    folder = tmp_path / "q3"
    (folder / "baseq3").mkdir(parents=True)
    (folder / "baseq3" / "pak0.pk3").write_text("")
    (folder / "baseq3" / "q3key").write_text("abcdghjlprstw237\n")

    window.folder.setText(str(folder))
    window.refresh()

    assert window.games.count() == 1
    assert window.install_button.text() == "Update"
    assert not window.use_steam.isChecked()
    # Every installed game has its key, so the CD keys section stays hidden.
    assert window.keys_group.isHidden()


def test_empty_folder_suggests_steam(window, tmp_path):
    window.folder.setText(str(tmp_path / "empty"))
    window.refresh()
    assert window.use_steam.isChecked()
    assert window.install_button.text() == "Install"
    assert not window.play_button.isEnabled()


def test_player_settings_follow_player_cfg(window, tmp_path):
    from arenahub.core import configs

    folder = tmp_path / "q3"
    for game_dir in ("baseq3", "cpma"):
        (folder / game_dir).mkdir(parents=True)
    (folder / "baseq3" / "pak0.pk3").write_text("")
    configs.save_player(folder, configs.Player("FromCfg", 1.5))

    # Opening the folder shows what its player.cfg says.
    window.folder.setText(str(folder))
    window.refresh()
    assert window.player_name.text() == "FromCfg"
    assert window.sensitivity.value() == 1.5

    # Changing the fields writes them back to every player.cfg.
    window.player_name.setText("Ranger")
    window.sensitivity.setValue(4.25)
    assert window.save_player()
    for game_dir in ("baseq3", "cpma"):
        text = (folder / game_dir / "player.cfg").read_text()
        assert configs.read_value(text, "name") == "Ranger"
        assert configs.read_value(text, "sensitivity") == "4.25"


def test_sensitivity_changes_are_saved_after_a_pause(window, tmp_path):
    from PySide6.QtTest import QTest

    from arenahub.core import configs

    folder = tmp_path / "q3"
    (folder / "baseq3").mkdir(parents=True)
    (folder / "baseq3" / "pak0.pk3").write_text("")
    window.folder.setText(str(folder))
    window.refresh()
    window.player_name.setText("Ranger")

    window.sensitivity.setValue(7.5)
    assert window._player_timer.isActive()
    QTest.qWait(window._player_timer.interval() + 200)
    assert configs.read_player(folder) == configs.Player("Ranger", 7.5)


@pytest.mark.parametrize("typed, text, value", [("2,75", "2.75", 2.75), ("1.5", "1.5", 1.5)])
def test_sensitivity_accepts_comma_or_dot(window, typed, text, value):
    from PySide6.QtCore import QLocale
    from PySide6.QtTest import QTest

    # A Spanish system would normally use ',' as the decimal separator.
    previous = QLocale()
    QLocale.setDefault(QLocale(QLocale.Language.Spanish, QLocale.Country.Spain))
    try:
        from arenahub.gui.widgets import DecimalSpinBox

        spin = DecimalSpinBox()
        spin.setRange(0.01, 30.0)
        spin.setDecimals(2)
        spin.lineEdit().selectAll()
        QTest.keyClicks(spin.lineEdit(), typed)
        assert spin.lineEdit().text() == text
        assert spin.value() == value
    finally:
        QLocale.setDefault(previous)

    # The window's own field behaves the same way.
    window.sensitivity.lineEdit().selectAll()
    QTest.keyClicks(window.sensitivity.lineEdit(), typed)
    assert window.sensitivity.lineEdit().text() == text
    assert window.sensitivity.value() == value


def test_every_mod_is_listed_and_installed(window, monkeypatch):
    from PySide6.QtWidgets import QCheckBox, QLabel

    from arenahub.core.catalog import MODS

    texts = [label.text() for label in window.findChildren(QLabel)]
    for mod in MODS:
        assert any(mod.title in text for text in texts), mod.title
    assert not any(
        any(mod.title in box.text() for mod in MODS) for box in window.findChildren(QCheckBox)
    )

    started = {}
    monkeypatch.setattr(window, "_ask_secret", lambda *args: None)  # stop before installing
    window.use_steam.setChecked(False)

    from arenahub.gui import main_window

    def fake_worker(options):
        started["mods"] = options.mods
        raise RuntimeError("stop")

    monkeypatch.setattr(main_window, "InstallWorker", fake_worker)
    try:
        window.start_install()
    except RuntimeError:
        pass
    assert started["mods"] == [mod.id for mod in MODS]


def test_maps_are_listed(window):
    from PySide6.QtWidgets import QAbstractItemView

    from arenahub.core.maps import MAPS

    tree = window.maps_list
    assert tree.topLevelItemCount() == len(MAPS)
    titles = {tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())}
    assert titles == {pack.title for pack in MAPS}
    for i in range(tree.topLevelItemCount()):
        assert not tree.topLevelItem(i).icon(0).isNull(), tree.topLevelItem(i).text(0)
    # Only a list to read: nothing to pick.
    assert tree.selectionMode() == QAbstractItemView.SelectionMode.NoSelection


def install_with_keys(tmp_path, keys):
    folder = tmp_path / "q3"
    for game_dir in ("baseq3", "missionpack"):
        (folder / game_dir).mkdir(parents=True)
        (folder / game_dir / "pak0.pk3").write_text("")
    for game_dir, key in keys.items():
        (folder / game_dir / "q3key").write_text(key + "\n")
    return folder


def test_keys_section_asks_only_for_missing_keys(window, tmp_path):
    folder = install_with_keys(tmp_path, {"baseq3": "abcdghjlprstw237"})
    window.folder.setText(str(folder))
    window.refresh()

    assert not window.keys_group.isHidden()
    assert not window.keys_form.isRowVisible(window.quake3_key)
    assert window.keys_form.isRowVisible(window.team_arena_key)

    # Saving the missing key hides the section again.
    window.team_arena_key.setText("BCDG-HJLP-RSTW-2373-a7")
    window.save_keys()
    assert (folder / "missionpack" / "q3key").read_text()[:16] == "bcdghjlprstw2373"
    assert window.keys_group.isHidden()


def test_keys_section_hidden_without_games(window, tmp_path):
    window.folder.setText(str(tmp_path / "empty"))
    window.refresh()
    assert window.keys_group.isHidden()


def test_invalid_key_file_counts_as_missing(window, tmp_path):
    folder = install_with_keys(tmp_path, {"baseq3": "not a key", "missionpack": "bcdghjlprstw2373"})
    window.folder.setText(str(folder))
    window.refresh()
    assert window.keys_form.isRowVisible(window.quake3_key)
    assert not window.keys_form.isRowVisible(window.team_arena_key)


def server_folder(tmp_path):
    from .conftest import make_zip

    folder = tmp_path / "q3"
    (folder / "baseq3").mkdir(parents=True)
    make_zip(folder / "baseq3" / "pak0.pk3", {"maps/q3dm17.bsp": "", "maps/q3ctf1.bsp": ""})
    (folder / "arena").mkdir()
    (folder / "arena" / "vm.pk3").write_text("")  # Rocket Arena 3 cannot host
    return folder


def wait_until(condition, timeout=5000):
    from PySide6.QtCore import QDeadlineTimer, QEventLoop
    from PySide6.QtWidgets import QApplication

    deadline = QDeadlineTimer(timeout)
    while not condition() and not deadline.hasExpired():
        QApplication.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
    return condition()


def test_server_tab_offers_hostable_games_and_maps(window, tmp_path):
    window.folder.setText(str(server_folder(tmp_path)))
    window.refresh()
    tab = window.server_tab

    assert [tab.game.itemData(i) for i in range(tab.game.count())] == ["baseq3"]
    assert [tab.available.item(i).text() for i in range(tab.available.count())] == [
        "q3ctf1",
        "q3dm17",
    ]
    assert not tab.form.isRowVisible(tab.physics)

    tab.gametype.setCurrentIndex(tab.gametype.findData("ctf"))
    visible = [name for name, box in tab.limits.items() if tab.form.isRowVisible(box)]
    assert visible == ["capturelimit"]


def test_server_needs_a_rotation(window, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    window.folder.setText(str(server_folder(tmp_path)))
    window.refresh()
    window.server_tab.start()
    assert warnings == ["Add at least one map to the rotation."]
    assert not window.server_tab.running


def test_server_runs_and_stops(window, tmp_path, monkeypatch):
    import sys

    from arenahub.core import launcher, server

    # A stand-in for the dedicated server: prints, echoes commands, quits on "quit".
    script = (
        "import sys\n"
        "print('^1Server ^7ready', flush=True)\n"
        "for line in sys.stdin:\n"
        "    if line.strip() == 'quit': break\n"
        "    print('got ' + line.strip(), flush=True)\n"
    )
    monkeypatch.setattr(server, "command", lambda folder, options: [sys.executable, "-c", script])
    folder = server_folder(tmp_path)
    window.folder.setText(str(folder))
    window.refresh()
    tab = window.server_tab
    tab.available.item(1).setSelected(True)
    tab._add_maps()
    joined = []
    monkeypatch.setattr(
        launcher,
        "launch",
        lambda folder, game, renderer, connect: joined.append((game.id, connect)),
    )

    tab.start()
    assert tab.running
    assert (folder / "baseq3" / server.CONFIG_NAME).is_file()
    assert not window.install_button.isEnabled()
    assert not tab.hostname.isEnabled()
    assert wait_until(lambda: "Server ready" in window.log_view.toPlainText())

    tab.console.setText("status")
    tab.send_command()
    assert wait_until(lambda: "got status" in window.log_view.toPlainText())
    tab.join_button.click()
    assert joined == [("baseq3", "127.0.0.1:27960")]

    tab.stop()
    assert wait_until(lambda: not tab.running)
    assert window.install_button.isEnabled()
    assert tab.hostname.isEnabled()
    assert window.settings.value("server/maps/baseq3") in (["q3dm17"], "q3dm17")


def test_rotation_maps_leave_the_installed_list(window, tmp_path):
    window.folder.setText(str(server_folder(tmp_path)))
    window.refresh()
    tab = window.server_tab

    def installed():
        return [tab.available.item(i).text() for i in range(tab.available.count())]

    tab.available.item(0).setSelected(True)
    tab._add_maps()
    assert tab.rotation_maps() == ["q3ctf1"]
    assert installed() == ["q3dm17"]

    # The filter never brings a chosen map back.
    tab.map_filter.setText("q3")
    assert installed() == ["q3dm17"]

    tab.rotation.item(0).setSelected(True)
    tab._remove_maps()
    assert tab.rotation_maps() == []
    assert installed() == ["q3ctf1", "q3dm17"]


def test_shuffle_keeps_every_map(window, tmp_path, monkeypatch):
    import random

    window.folder.setText(str(server_folder(tmp_path)))
    window.refresh()
    tab = window.server_tab
    tab.rotation.addItems(["a", "b", "c", "d"])
    monkeypatch.setattr(random, "shuffle", lambda maps: maps.reverse())
    tab._shuffle_maps()
    assert tab.rotation_maps() == ["d", "c", "b", "a"]


def test_bot_skill_range_follows_the_mod(window, tmp_path):
    folder = server_folder(tmp_path)
    (folder / "cpma").mkdir()
    (folder / "cpma" / "z-cpma-pak153.pk3").write_text("")
    window.folder.setText(str(folder))
    window.refresh()
    tab = window.server_tab

    tab.game.setCurrentIndex(tab.game.findData("baseq3"))
    assert (tab.bot_skill.maximum(), tab.bot_skill.value()) == (5, 3)
    assert tab.bot_skill.text() == "3 - Hurt Me Plenty"
    tab.bot_skill.setValue(5)

    # CPMA starts at its maximum, and each mod keeps its own value.
    tab.game.setCurrentIndex(tab.game.findData("cpma"))
    assert (tab.bot_skill.maximum(), tab.bot_skill.value()) == (100, 100)
    assert tab.bot_skill.text() == "100 (max 100)"
    tab.game.setCurrentIndex(tab.game.findData("baseq3"))
    assert tab.bot_skill.value() == 5


def test_theme_style_sheet_is_complete():
    import re
    from pathlib import Path

    from arenahub.gui import theme

    style = theme.stylesheet()
    assert not re.search(r"@[A-Z]", style)  # every colour and image was filled in
    for path in re.findall(r"url\(([^)]+)\)", style):
        assert Path(path).is_file(), path


def test_activity_panel_follows_the_installation(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    assert window.cancel_button.isHidden()
    window._on_stage("Logging in to Steam")
    window._on_stage("Installing Quake3e")
    assert [item.text() for item in window._stages] == [
        "✓   Logging in to Steam",
        "●   Installing Quake3e",
    ]
    window._on_progress(0.5, "quake3e.zip")
    assert window.progress_text.text() == "quake3e.zip  ·  50%"

    monkeypatch.setattr(QMessageBox, "critical", lambda *args: None)
    window._on_failed("network down")
    assert window._stages[-1].text() == "✕   Installing Quake3e"
    assert window.status.text() == "Installation failed"
