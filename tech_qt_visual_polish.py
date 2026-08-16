"""Final Qt visual polish: monochrome surfaces, compact sidebar, app icon and button icons."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from tech_qt_icons import ICONS, load_icon


def _asset_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))))
    return root / name


def _set_app_icon() -> QIcon:
    icon_path = _asset_path("gelotech_icon.ico")
    icon = QIcon(str(icon_path)) if icon_path.is_file() else QIcon()
    app = QApplication.instance()
    if app is not None and not icon.isNull():
        app.setWindowIcon(icon)
    return icon


def _apply_sidebar_icons(self) -> None:
    sidebar = getattr(self, "sidebar", None)
    if sidebar is None:
        return
    mapping = {
        "Dashboard": "Dashboard",
        "Monitor Apps": "Monitor Apps",
        "Block Ads DNS": "Block Ads DNS",
        "VirusTotal": "VirusTotal",
        "Reboot to Recovery": "Reboot",
        "Reboot to Fastboot": "Power",
        "Re-authorize ADB": "Re-authorize ADB",
        "Fix / DL ADB Drivers": "Fix Drivers",
        "Fix/DL ADB Drivers": "Fix Drivers",
        "Accounts": "Accounts",
        "Logout": "Logout",
        "LOGOUT": "Logout",
        "DASHBOARD": "Dashboard",
        "MONITOR APPS": "Monitor Apps",
        "BLOCK ADS DNS": "Block Ads DNS",
        "VIRUSTOTAL": "VirusTotal",
    }
    for button in sidebar.findChildren(QPushButton):
        key = mapping.get(button.text().strip())
        if key:
            icon_name = ICONS.get(key)
            if icon_name:
                button.setIcon(load_icon(icon_name))
        button.setMinimumHeight(28)
        button.setMaximumHeight(32)
        button.setContentsMargins(4, 2, 4, 2)

    theme = getattr(self, "theme_btn", None)
    if isinstance(theme, QPushButton):
        theme.setCheckable(True)
        theme.setChecked(bool(getattr(self, "dark_mode", True)))
        theme.setText("Dark Mode" if getattr(self, "dark_mode", True) else "Light Mode")
        theme.setIcon(load_icon("moon" if getattr(self, "dark_mode", True) else "sun"))


def _apply_all_button_icons(self) -> None:
    mapping = {
        "Refresh": "refresh",
        "Screen Mirror": "device-mobile",
        "Stop Mirror": "x",
        "Scan Bloatware": "scan",
        "Restore/Backup": "restore",
        "Restore / Backup": "restore",
        "Load Apps": "apps",
        "Advanced Filter": "adjustments-horizontal",
        "Select All": "check",
        "Apply DNS": "shield-check",
        "Disable": "x",
        "Scan Phone": "scan",
        "Scan Running": "activity",
        "Pull + Upload": "upload",
        "Scan Package": "scan",
        "Load Packages": "packages",
        "Start monitoring": "antenna",
        "Stop": "x",
        "Clear History": "trash",
        "Refresh Accounts": "refresh",
        "Change password": "password",
    }
    for button in self.findChildren(QPushButton):
        if button is getattr(self, "theme_btn", None):
            continue
        text = button.text().replace("…", "").replace("▾", "").strip()
        key = mapping.get(text)
        if key:
            button.setIcon(load_icon(key))


def _wrap_apply_theme(self):
    original = self.__class__._apply_theme
    if getattr(self, "_visual_theme_wrapped", False):
        return
    self._visual_theme_wrapped = True

    def apply():
        original(self)
        dark = bool(getattr(self, "dark_mode", True))
        bg = "#000000" if dark else "#ffffff"
        fg = "#ffffff" if dark else "#000000"
        border = "#222222" if dark else "#d0d0d0"
        accent = "#1a8cff"
        QApplication.instance().setStyleSheet(
            QApplication.instance().styleSheet()
            + f"""
            QWidget, QMainWindow, QDialog {{ background: {bg}; color: {fg}; }}
            QFrame, QStackedWidget, QScrollArea, QAbstractScrollArea::viewport {{ background: {bg}; color: {fg}; }}
            QPushButton {{ background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 3px 8px; }}
            QPushButton:hover, QPushButton:pressed, QPushButton:checked {{ background: {bg}; color: {accent}; border-color: {accent}; }}
            QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{ background: {bg}; color: {fg}; border: 1px solid {border}; }}
            QTableWidget, QListWidget {{ background: {bg}; color: {fg}; alternate-background-color: {bg}; border: 1px solid {border}; }}
            QHeaderView::section {{ background: {bg}; color: {fg}; border: 1px solid {border}; }}
            QMenu {{ background: {bg}; color: {fg}; border: 1px solid {border}; }}
            QMenu::item:selected {{ background: {bg}; color: {accent}; }}
            QLabel#brandTitle {{ background: transparent; color: {accent}; font-size: 20px; font-weight: 800; }}
            QLabel#brandVersion {{ background: transparent; color: {fg}; font-size: 10px; font-weight: 700; }}
            QLabel#brandCopyright {{ background: transparent; color: {'#777777' if dark else '#666666'}; font-size: 9px; }}
            QLabel#brandLink {{ background: transparent; color: {accent}; font-size: 9px; }}
            QFrame#sidebar {{ background: {bg}; border-right: 1px solid {border}; }}
            """
        )
        _apply_sidebar_icons(self)
        _apply_all_button_icons(self)

    self._apply_theme = apply
    apply()


def install_visual_polish(MainWindow, LoginDialog=None) -> None:
    icon = _set_app_icon()
    original_init = MainWindow.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if not icon.isNull():
            self.setWindowIcon(icon)
        _apply_sidebar_icons(self)
        _apply_all_button_icons(self)
        _wrap_apply_theme(self)

    MainWindow.__init__ = init

    if LoginDialog is not None:
        login_icon = icon
        original_login_init = LoginDialog.__init__

        def login_init(self, *args, **kwargs):
            original_login_init(self, *args, **kwargs)
            if not login_icon.isNull():
                self.setWindowIcon(login_icon)

        LoginDialog.__init__ = login_init
