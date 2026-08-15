"""PySide6 application entry point for GeloTech Tool."""
from __future__ import annotations

import sys

from tech_qt_bootstrap import enable_qt_mode

enable_qt_mode()

from PySide6.QtWidgets import QApplication

from tech_qt_cleaner import install_cleaner_parity
from tech_qt_drivers import install_driver_workflow
from tech_qt_iconsync import install_icon_sync
from tech_qt_mainwindow import MainWindow
from tech_qt_mirror import install_scrcpy
from tech_qt_themes import DEFAULT_THEME, DEFAULT_UI_FONT, apply_theme
from tech_qt_virustotal import install_virustotal


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GeloTech Tool")
    app.setApplicationVersion("1.7.8")
    apply_theme(app, DEFAULT_THEME, True, DEFAULT_UI_FONT)
    install_cleaner_parity(MainWindow)
    install_virustotal(MainWindow)
    install_driver_workflow(MainWindow)
    install_scrcpy(MainWindow)
    install_icon_sync(MainWindow)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
