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
    assert window.quake3_key.text() == "ABCD-GHJL-PRST-W237"
    assert not window.team_arena_key.isEnabled()


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
