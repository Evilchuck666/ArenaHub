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
