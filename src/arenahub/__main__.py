"""Entry point.

arenahub                         the application
arenahub --smoke-test [--screenshot FILE]
                                 open the window, optionally save it as an image, and quit
arenahub --steam-helper [--self-test]
                                 internal: the Steam client process (see steam_helper)
"""

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    # The helper must start before anything imports sockets: it monkey-patches them.
    if argv[:1] == ["--steam-helper"]:
        from arenahub.steam_helper import main as helper_main

        return helper_main(argv[1:])

    return run_gui(argv)


def run_gui(argv: list[str]) -> int:
    import tempfile

    from PySide6.QtCore import QSettings, QTimer
    from PySide6.QtWidgets import QApplication

    from arenahub.gui.main_window import MainWindow

    if "--smoke-test" in argv:
        # Keep the user's real settings out of smoke tests.
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp())

    app = QApplication([sys.argv[0], *argv])
    app.setApplicationName("ArenaHub")
    app.setOrganizationName("ArenaHub")
    window = MainWindow()
    window.show()

    if "--smoke-test" in argv:
        screenshot = None
        if "--screenshot" in argv and argv.index("--screenshot") + 1 < len(argv):
            screenshot = argv[argv.index("--screenshot") + 1]

        def finish() -> None:
            if screenshot:
                window.grab().save(screenshot)
            window.close()
            app.quit()

        QTimer.singleShot(500, finish)

    code = app.exec()
    # Destroy Qt objects in order while the interpreter is still alive; leaving
    # it to interpreter teardown can crash on exit.
    window.deleteLater()
    app.processEvents()
    app.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
