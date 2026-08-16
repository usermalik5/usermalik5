"""PySide6 application entry point for GeloTech Tool."""
from __future__ import annotations

import sys

from tech_qt_bootstrap import enable_qt_mode

enable_qt_mode()

from PySide6.QtWidgets import QApplication

from tech_qt_auto_refresh import install_auto_refresh
from tech_qt_backup import install_backup_restore
from tech_qt_bezel import install_bezel_alias
from tech_qt_cleaner import install_cleaner_parity
from tech_qt_compat import install_qt_compat
from tech_qt_drivers import install_driver_workflow
from tech_qt_final_fixes import install_final_qt_fixes
from tech_qt_help_pages import install_help_pages
from tech_qt_iconfix import install_icon_cache_lookup
from tech_qt_iconsync import install_icon_sync
from tech_qt_mainwindow import LoginDialog, MainWindow
from tech_qt_mirror import install_scrcpy
from tech_qt_phone import install_phone_frame
from tech_qt_sidebar_compact import install_sidebar_compact
from tech_qt_themes import DEFAULT_THEME, DEFAULT_UI_FONT, apply_theme, install_appearance_controls
from tech_qt_ui import install_visual_parity
from tech_qt_virustotal import install_virustotal
from tech_qt_visual_polish import install_visual_polish


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GeloTech Tool")
    app.setApplicationVersion("1.7.8")
    apply_theme(app, DEFAULT_THEME, True, DEFAULT_UI_FONT)
    install_cleaner_parity(MainWindow)
    install_icon_cache_lookup(MainWindow)
    install_backup_restore(MainWindow)
    install_virustotal(MainWindow)
    install_driver_workflow(MainWindow)
    install_scrcpy(MainWindow)
    install_icon_sync(MainWindow)
    install_visual_parity(MainWindow)
    install_phone_frame(MainWindow)
    install_qt_compat(MainWindow)
    install_final_qt_fixes(MainWindow)
    install_help_pages(MainWindow)
    install_bezel_alias(MainWindow)
    install_sidebar_compact(MainWindow)
    install_auto_refresh(MainWindow)
    install_appearance_controls(MainWindow)
    install_visual_polish(MainWindow, LoginDialog)
    window = MainWindow()
    window.hide()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
