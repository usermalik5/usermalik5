"""Final user-facing Qt6 parity pass for GeloTech.

Keeps the migrated feature modules intact while normalizing the shell to the
legacy/reference layout, global surface colors, icons, application icon, and
feature-help styling. This module is intentionally kept small for PyArmor
trial builds.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton, QFrame

from tech_qt_icons import load_icon, tinted_icon
from tech_qt_themes import palette_profile


REFERENCE_DARK = {
    "bg": "#474747",
    "panel": "#444444",
    "panel2": "#3e3e3e",
    "button": "#3f3f3f",
    "button_hover": "#555555",
    "input": "#3d3d3d",
    "border": "#686868",
    "text": "#ffffff",
    "muted": "#c2c2c2",
    "log": "#252525",
    "log_text": "#7CFF00",
    "header": "#d2d2d2",
    "header_text": "#202020",
}

REFERENCE_LIGHT = {
    "bg": "#ffffff",
    "panel": "#ffffff",
    "panel2": "#ffffff",
    "button": "#ffffff",
    "button_hover": "#f0f0f0",
    "input": "#ffffff",
    "border": "#cfcfcf",
    "text": "#000000",
    "muted": "#5f5f5f",
    "log": "#ffffff",
    "log_text": "#1a7f37",
    "header": "#eeeeee",
    "header_text": "#202020",
}

SIDEBAR_LABELS = {
    "DASHBOARD": ("Dashboard", "dashboard"),
    "MONITOR": ("Monitor Apps", "search"),
    "MONITOR APPS": ("Monitor Apps", "search"),
    "AD BLOCK": ("Block Ads DNS", "globe"),
    "BLOCK ADS DNS": ("Block Ads DNS", "globe"),
    "VT SCAN": ("VirusTotal", "virus"),
    "VIRUSTOTAL": ("VirusTotal", "virus"),
    "RECOVERY": ("Reboot to Recovery", "refresh"),
    "FASTBOOT": ("Reboot to Fastboot", "power"),
    "AUTH ADB": ("Re-authorize ADB", "plug-connected"),
    "ADB DRIVERS": ("Fix / DL ADB Drivers", "tool"),
    "ADMIN": ("Accounts", "key"),
    "ACCOUNTS": ("Accounts", "key"),
    "LOGOUT": ("Logout", "logout"),
}

ACTION_ICONS = {
    "Refresh": "refresh",
    "Refresh now": "refresh",
    "Screen Mirror": "device-mobile",
    "Stop Mirror": "x",
    "Scan Bloatware": "search",
    "Restore/Backup": "restore",
    "Restore / Backup": "restore",
    "Load Apps": "apps",
    "Advanced Filter": "filter",
    "Select All": "check",
    "Apply DNS": "shield-check",
    "Disable DNS": "x",
    "Disable": "x",
    "DNS Guide": "info-circle",
    "How it works": "info-circle",
    "Start monitoring": "antenna",
    "Stop monitoring": "x",
    "Clear history": "trash",
    "Scan Phone": "scan",
    "Scan Running": "activity",
    "Pull + Upload": "upload",
    "Scan Package": "scan",
    "Load Packages": "packages",
    "Stop": "x",
    "Refresh Accounts": "refresh",
    "Change password": "password",
}


def _asset(name: str):
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, name)


def _app_icon() -> QIcon:
    path = _asset("gelotech_icon.ico")
    icon = QIcon(path) if os.path.isfile(path) else QIcon()
    app = QApplication.instance()
    if app is not None and not icon.isNull():
        app.setWindowIcon(icon)
    return icon


def _normalise_sidebar(window) -> None:
    sidebar = getattr(window, "sidebar", None)
    if sidebar is None:
        return
    sidebar.setMinimumWidth(264)
    sidebar.setMaximumWidth(264)
    sidebar.setFixedWidth(264)
    layout = sidebar.layout()
    if layout is not None:
        layout.setContentsMargins(10, 7, 10, 8)
        layout.setSpacing(0)

    nav = getattr(window, "nav", None)
    if isinstance(nav, QListWidget):
        # Final shell uses direct push-buttons. If an older installer left a
        # QListWidget behind, hide it so there is only one navigation surface.
        nav.hide()
        nav.setSpacing(0)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    theme = getattr(window, "theme_btn", None)
    buttons = sidebar.findChildren(QPushButton)
    for button in buttons:
        raw = button.text().strip().upper()
        if button is theme:
            continue
        mapped = SIDEBAR_LABELS.get(raw)
        if mapped:
            text, icon_name = mapped
            button.setText(text)
            button.setIcon(load_icon(icon_name))
        button.setMinimumHeight(30)
        button.setMaximumHeight(30)
        button.setContentsMargins(0, 0, 0, 0)
        button.setProperty("sidebarButton", True)
        button.setStyleSheet(
            "QPushButton { margin:0; padding:4px 10px; min-height:30px; max-height:30px; "
            "border-radius:2px; font-weight:700; text-align:left; }"
            "QPushButton:hover { margin:0; } QPushButton:pressed { margin:0; }"
        )

    if theme is not None:
        theme.setText("Theme - Dark" if getattr(window, "dark_mode", True) else "Theme - Light")
        theme.setIcon(load_icon("moon" if getattr(window, "dark_mode", True) else "sun"))
        theme.setCheckable(True)
        theme.setChecked(bool(getattr(window, "dark_mode", True)))
        theme.setMinimumHeight(30)
        theme.setMaximumHeight(30)

    # The reference puts one compact branding block at the top and quiet help
    # text at the bottom. Keep only one copy of each guide.
    usb_seen = False
    how_seen = False
    for label in sidebar.findChildren(QLabel):
        text = label.text()
        if "USB debugging" in text:
            if usb_seen:
                label.hide()
            else:
                usb_seen = True
                label.setObjectName("guideText")
        elif "How to use" in text:
            if how_seen:
                label.hide()
            else:
                how_seen = True
                label.setObjectName("guideText")

    header = None
    for label in sidebar.findChildren(QLabel):
        if "GELOTECH" in label.text() and ("Gsmcodeph" in label.text() or "© 2026" in label.text()):
            header = label
            break
    if header is not None:
        version = getattr(window, "_qt_sidebar_version", "1.7.8")
        header.setText(
            f'<span style="color:#2388ff;font-size:20pt;font-weight:800;">GELOTECH</span>'
            f'<span style="color:#d8d8d8;font-size:10pt;font-weight:800;"> TOOL</span><br>'
            f'<span style="color:#d0d0d0;font-size:8pt;font-weight:700;">v{version} - Angelo Estrada Espinosa</span><br>'
            f'<span style="color:#9a9a9a;font-size:8pt;">© 2026 GeloTech</span><br>'
            f'<a href="https://gsmcodeph.com" style="color:#7fb7ff;font-size:8pt;">Gsmcodeph.com</a><br>'
            f'<a href="https://facebook.com/gelotechxyz" style="color:#7fb7ff;font-size:8pt;">facebook.com/gelotechxyz</a>'
        )
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setOpenExternalLinks(True)
        header.setMaximumHeight(94)
        header.setContentsMargins(0, 0, 0, 0)


def _apply_action_icons(window) -> None:
    for button in window.findChildren(QPushButton):
        if button is getattr(window, "theme_btn", None):
            continue
        key = button.text().replace("▾", "").replace("…", "").strip()
        icon_name = ACTION_ICONS.get(key)
        if icon_name:
            button.setIcon(load_icon(icon_name))


def _style_help_and_feature_pages(app) -> None:
    # These object names are created by tech_qt_help_pages.py. Styling them
    # here keeps the pages useful while matching the compact reference theme.
    app.setStyleSheet(app.styleSheet() + """
        QFrame#featureHeader, QFrame#helpHeader, QFrame#helpCard,
        QFrame#statusPanel, QFrame#contentPanel {
            border: 1px solid palette(mid);
            border-radius: 4px;
        }
        QLabel#helpHeading { font-weight: 800; font-size: 10pt; }
        QLabel#helpText { font-size: 9pt; }
        QLabel#pageTitle { padding: 3px 0 7px 8px; margin: 0; }
        QFrame#providerCard { border-radius: 4px; }
        QPushButton#providerHeader { border-radius: 4px; }
    """)


def _wrap_theme(window) -> None:
    original = getattr(window.__class__, "_apply_theme", None)
    if original is None or getattr(window, "_user_finish_theme_wrapped", False):
        return
    window._user_finish_theme_wrapped = True

    def apply():
        try:
            original(window)
        except TypeError:
            original()
        dark = bool(getattr(window, "dark_mode", True))
        profile = palette_profile(getattr(window, "theme_name", "orange"), dark)
        accent = profile.get("accent", "#f97316")
        c = REFERENCE_DARK if dark else REFERENCE_LIGHT
        app = QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(f"""
            * {{ font-family:'Segoe UI',sans-serif; font-size:10pt; }}
            QWidget, QMainWindow, QDialog, QStackedWidget, QScrollArea,
            QAbstractScrollArea::viewport {{ background:{c['bg']}; color:{c['text']}; }}
            QFrame#sidebar {{ background:{c['bg']}; border-right:1px solid {c['border']}; }}
            QPushButton {{ background:{c['button']}; color:{c['text']}; border:1px solid {c['border']};
                border-radius:2px; padding:4px 9px; min-height:30px; max-height:30px; margin:0; font-weight:700; }}
            QPushButton:hover {{ background:{c['button_hover']}; border-color:{accent}; color:{c['text']}; }}
            QPushButton:pressed, QPushButton:checked {{ background:{accent}; border-color:{accent}; color:white; }}
            QPushButton#providerUse, QPushButton#accentButton {{ background:{accent}; border-color:{accent}; color:white; }}
            QPushButton#providerUse:hover, QPushButton#accentButton:hover {{ background:{accent}; border-color:{accent}; }}
            QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{ background:{c['input']}; color:{c['text']};
                border:1px solid {c['border']}; border-radius:2px; }}
            QTableWidget, QListWidget {{ background:{c['panel2']}; color:{c['text']}; alternate-background-color:{c['panel']};
                border:1px solid {c['border']}; gridline-color:{c['border']}; selection-background-color:{accent}; selection-color:white; }}
            QHeaderView::section {{ background:{c['header']}; color:{c['header_text']}; border:1px solid {c['border']}; padding:6px 7px; font-weight:800; }}
            QPlainTextEdit#liveLog {{ background:{c['log']}; color:{c['log_text']}; border:1px solid {c['border']}; border-radius:2px; }}
            QFrame#sidebarGuide, QFrame#guidePanel, QFrame#contentPanel, QFrame#featureHeader,
            QFrame#helpHeader, QFrame#helpCard, QFrame#statusPanel, QFrame#providerCard {{
                background:{c['panel']}; color:{c['text']}; border:1px solid {c['border']}; border-radius:4px;
            }}
            QLabel#guideText, QLabel#muted, QLabel#helpText {{ color:{c['muted']}; }}
            QLabel#brandTitle, QLabel#sidebarBrandHeader, QLabel#brand {{ background:transparent; color:#2388ff; }}
            QLabel#brandVersion {{ background:transparent; color:{c['text']}; }}
            QLabel#brandCopyright {{ background:transparent; color:{c['muted']}; }}
            QLabel#brandLink {{ background:transparent; color:#7fb7ff; }}
            QLabel#deviceText {{ color:#22c55e; font-weight:800; }}
            QLabel#securityText {{ color:#f5b700; font-weight:800; }}
            QLabel#statusText {{ color:{accent}; font-style:italic; }}
            QListWidget#sidebarNav {{ background:transparent; border:0; spacing:0px; }}
            QListWidget#sidebarNav::item {{ min-height:30px; padding:0 9px; margin:0; border:1px solid {c['border']}; border-radius:2px; background:{c['button']}; }}
            QMenu {{ background:{c['panel']}; color:{c['text']}; border:1px solid {c['border']}; }}
            QMenu::item {{ padding:6px 14px; }}
            QMenu::item:selected {{ background:{accent}; color:white; }}
            QScrollBar:vertical {{ background:{c['bg']}; width:10px; margin:0; }}
            QScrollBar::handle:vertical {{ background:{c['border']}; min-height:24px; border-radius:3px; }}
            QScrollBar:horizontal {{ background:{c['bg']}; height:10px; margin:0; }}
            QScrollBar::handle:horizontal {{ background:{c['border']}; min-width:28px; border-radius:3px; }}
        """)
        _normalise_sidebar(window)
        _apply_action_icons(window)
        _style_help_and_feature_pages(app)
        if hasattr(window, "setWindowIcon"):
            icon = _app_icon()
            if not icon.isNull():
                window.setWindowIcon(icon)

    window._apply_theme = apply
    apply()


def install_user_finish(MainWindow, LoginDialog=None) -> None:
    icon = _app_icon()
    original_init = MainWindow.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._qt_sidebar_version = "1.7.8"
        if not icon.isNull():
            self.setWindowIcon(icon)
        _normalise_sidebar(self)
        _apply_action_icons(self)
        _wrap_theme(self)

    MainWindow.__init__ = init

    if LoginDialog is not None:
        original_login_init = LoginDialog.__init__

        def login_init(self, *args, **kwargs):
            original_login_init(self, *args, **kwargs)
            if not icon.isNull():
                self.setWindowIcon(icon)

        LoginDialog.__init__ = login_init
