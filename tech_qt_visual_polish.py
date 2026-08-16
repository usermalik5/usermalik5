"""Reference-style Qt visual polish: gray surfaces, compact controls, icons."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from tech_qt_icons import ICONS, load_icon, tinted_icon


# (tabler icon name, accent colour) per sidebar action. Short labels keep the
# sidebar compact while the colour + tinted icon make each action lively.
SIDEBAR_STYLE = {
    "DASHBOARD": ("dashboard", "#1a8cff"),
    "MONITOR": ("search", "#22d3ee"),
    "AD BLOCK": ("globe", "#22c55e"),
    "VT SCAN": ("virus", "#a855f7"),
    "RECOVERY": ("refresh", "#f97316"),
    "FASTBOOT": ("power", "#fb923c"),
    "AUTH ADB": ("plug-connected", "#14b8a6"),
    "ADB DRIVERS": ("tool", "#06b6d4"),
    "ADMIN": ("key", "#6366f1"),
    "LOGOUT": ("logout", "#ef4444"),
}
THEME_STYLE = ("settings", "#eab308")


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
    theme = getattr(self, "theme_btn", None)
    for button in sidebar.findChildren(QPushButton):
        if button is theme:
            icon_name, color = THEME_STYLE
            button.setIcon(tinted_icon(icon_name, color, 18))
            is_dark = bool(getattr(self, "dark_mode", True))
            button.setCheckable(True)
            button.setChecked(is_dark)
            button.setText("Dark Mode" if is_dark else "Light Mode")
        else:
            spec = SIDEBAR_STYLE.get(button.text().strip().upper())
            if spec is None:
                button.setMinimumHeight(28)
                button.setMaximumHeight(32)
                button.setContentsMargins(4, 2, 4, 2)
                continue
            icon_name, color = spec
            button.setIcon(tinted_icon(icon_name, color, 18))
        button.setMinimumHeight(28)
        button.setMaximumHeight(32)
        button.setContentsMargins(4, 2, 4, 2)
        button.setStyleSheet(
            "QPushButton { background:#171b20; color:#e6edf3; border:1px solid #2c3340; "
            f"border-left:3px solid {color}; border-radius:8px; padding:6px 10px 6px 13px; "
            "min-height:30px; font-weight:700; text-align:left; }"
            f"QPushButton:hover {{ background:{color}24; color:#ffffff; border-color:{color}; }}"
            f"QPushButton:pressed, QPushButton:checked {{ background:{color}; color:#ffffff; }}"
        )


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

        # The supplied reference screenshot measures about RGB 71,71,71 for
        # the main dark surface. Keep the whole dark UI in that restrained gray
        # family instead of the previous near-black presentation.
        if dark:
            bg = "#474747"
            panel = "#454545"
            panel2 = "#3f3f3f"
            button = "#3e3e3e"
            button_hover = "#555555"
            input_bg = "#3f3f3f"
            fg = "#ffffff"
            muted = "#bdbdbd"
            border = "#646464"
            grid = "#616161"
            header_bg = "#d0d0d0"
            log_text = "#7CFF00"
        else:
            bg = "#ffffff"
            panel = "#f4f4f4"
            panel2 = "#eeeeee"
            button = "#f2f2f2"
            button_hover = "#e2e2e2"
            input_bg = "#ffffff"
            fg = "#000000"
            muted = "#666666"
            border = "#c9c9c9"
            grid = "#d0d0d0"
            header_bg = "#d9d9d9"
            log_text = "#1a7f37"
        accent = "#2388ff"

        app = QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(
            f"""
            * {{ font-size: 10pt; }}
            QWidget, QMainWindow, QDialog {{ background: {bg}; color: {fg}; }}
            QFrame, QStackedWidget, QScrollArea, QAbstractScrollArea::viewport {{ background: {bg}; color: {fg}; }}
            QFrame#sidebar {{ background: {bg}; border-right: 1px solid {border}; }}
            QPushButton {{ background: {button}; color: {fg}; border: 1px solid {border}; border-radius: 2px; padding: 4px 9px; min-height: 29px; font-weight: 700; margin: 0px; }}
            QPushButton:hover {{ background: {button_hover}; color: {fg}; border-color: {accent}; }}
            QPushButton:pressed, QPushButton:checked {{ background: {button_hover}; color: {accent}; border-color: {accent}; }}
            QPushButton:disabled {{ background: {panel2}; color: #888888; border-color: {border}; }}
            QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{ background: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 2px; }}
            QTableWidget, QListWidget {{ background: {panel2}; color: {fg}; alternate-background-color: {panel2}; border: 1px solid {border}; gridline-color: {grid}; selection-background-color: {accent}; selection-color: white; }}
            QHeaderView::section {{ background: {header_bg}; color: #202020; border: 1px solid {grid}; padding: 6px 7px; font-weight: 800; }}
            QPlainTextEdit#liveLog {{ background: {panel2}; color: {log_text}; border: 1px solid {border}; border-radius: 2px; }}
            QFrame#guidePanel, QFrame#sidebarGuide {{ background: {panel}; color: {fg}; border: 1px solid {border}; border-radius: 2px; }}
            QLabel#guideTitle {{ color: {fg}; font-weight: 800; }}
            QLabel#guideText, QLabel#muted {{ color: {muted}; }}
            QLabel#brandTitle, QLabel#sidebarBrandHeader {{ background: transparent; color: {accent}; }}
            QLabel#brandVersion {{ background: transparent; color: {fg}; }}
            QLabel#brandCopyright {{ background: transparent; color: {muted}; }}
            QLabel#brandLink {{ background: transparent; color: #7fb7ff; }}
            QListWidget#sidebarNav {{ background: transparent; border: 0; outline: 0; spacing: 0px; }}
            QListWidget#sidebarNav::item {{ min-height: 29px; padding: 4px 9px; border: 1px solid {border}; border-radius: 2px; background: {button}; font-weight: 700; margin: 0px; }}
            QListWidget#sidebarNav::item:hover {{ background: {button_hover}; color: {fg}; }}
            QListWidget#sidebarNav::item:selected {{ background: {button_hover}; color: {accent}; border-color: {accent}; }}
            QScrollBar:vertical {{ background: {bg}; width: 10px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 24px; border-radius: 3px; }}
            QScrollBar:horizontal {{ background: {bg}; height: 10px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 28px; border-radius: 3px; }}
            QMenu {{ background: {panel}; color: {fg}; border: 1px solid {border}; }}
            QMenu::item {{ padding: 6px 14px; }}
            QMenu::item:selected {{ background: {button_hover}; color: {accent}; }}
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
