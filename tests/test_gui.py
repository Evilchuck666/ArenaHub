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
