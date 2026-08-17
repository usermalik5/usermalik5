"""Final reference-style Qt visual layer for GeloTech.

This module keeps the migrated feature logic intact while making the shell
match the requested compact legacy/reference presentation. It intentionally
lives in an existing PyArmor module so the trial per-file size constraint is
not increased by another obfuscated source file.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

from tech_qt_icons import load_icon
from tech_qt_themes import DEFAULT_UI_FONT, palette_profile

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
    "Refresh": "refresh", "Refresh now": "refresh", "Screen Mirror": "device-mobile",
    "Stop Mirror": "x", "Scan Bloatware": "search", "Restore/Backup": "restore",
    "Restore / Backup": "restore", "Load Apps": "apps", "Advanced Filter": "filter",
    "Select All": "check", "Apply DNS": "shield-check", "Disable DNS": "x",
    "Disable": "x", "DNS Guide": "info-circle", "How it works": "info-circle",
    "Start monitoring": "antenna", "Stop monitoring": "x", "Clear history": "trash",
    "Scan Phone": "scan", "Scan Running": "activity", "Pull + Upload": "upload",
    "Scan Package": "scan", "Load Packages": "packages", "Stop": "x",
    "Refresh Accounts": "refresh", "Change password": "password",
}


def _asset(name: str) -> str:
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, name)


def _set_app_icon() -> QIcon:
    path = _asset("gelotech_icon.ico")
    icon = QIcon(path) if os.path.isfile(path) else QIcon()
    app = QApplication.instance()
    if app is not None and not icon.isNull():
        app.setWindowIcon(icon)
    return icon


def _normalise_sidebar(self) -> None:
    sidebar = getattr(self, "sidebar", None)
    if sidebar is None:
        return
    sidebar.setFixedWidth(264)
    layout = sidebar.layout()
    if layout is not None:
        layout.setContentsMargins(10, 7, 10, 8)
        layout.setSpacing(0)

    nav = getattr(self, "nav", None)
    if isinstance(nav, QListWidget):
        nav.hide()
        nav.setSpacing(0)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    theme = getattr(self, "theme_btn", None)
    for button in sidebar.findChildren(QPushButton):
        if button is theme:
            continue
        raw = button.text().strip().upper()
        mapped = SIDEBAR_LABELS.get(raw)
        if mapped:
            text, icon_name = mapped
            button.setText(text)
            button.setIcon(load_icon(icon_name))
        button.setMinimumHeight(30)
        button.setMaximumHeight(30)
        button.setContentsMargins(0, 0, 0, 0)
        button.setStyleSheet("QPushButton { margin:0; padding:4px 10px; border-radius:2px; }")

    if theme is not None:
        theme.setText("Appearance")
        theme.setToolTip("Change color palette, display mode, and UI font")
        theme.setIcon(QIcon())
        theme.setCheckable(False)
        theme.setMinimumHeight(24)
        theme.setMaximumHeight(24)
        theme.setContentsMargins(0, 0, 0, 0)
        theme.setStyleSheet(
            "QPushButton { background:transparent; border:0; color:#9a9a9a;"
            " min-height:24px; max-height:24px; padding:0 2px; margin:0;"
            " font-size:8.5pt; font-weight:600; text-align:left; }"
            "QPushButton:hover { color:#d8d8d8; }"
            "QPushButton:pressed { color:#7fb7ff; }"
        )

    # Keep one USB guide and one How-to guide. Do not add gaps between action
    # buttons; the guides themselves provide the only lower information area.
    usb_seen = False
    how_seen = False
    for label in sidebar.findChildren(QLabel):
        text = label.text()
        if "USB debugging" in text:
            if usb_seen:
                label.hide()
            else:
                usb_seen = True
        elif "How to use" in text:
            if how_seen:
                label.hide()
            else:
                how_seen = True

    header = None
    for label in sidebar.findChildren(QLabel):
        text = label.text()
        if "GELOTECH" in text and ("Gsmcodeph" in text or "© 2026" in text):
            header = label
            break
    if header is not None:
        version = getattr(self, "_qt_sidebar_version", "1.7.8")
        header.setText(
            '<div style="margin:0;">'
            '<p style="margin:0 0 2px 0;"><span style="color:#2388ff;font-size:20pt;font-weight:800;">GELOTECH</span>'
            '<span style="color:#d8d8d8;font-size:10pt;font-weight:800;"> TOOL</span></p>'
            f'<p style="margin:0 0 2px 0;"><span style="color:#d0d0d0;font-size:8pt;font-weight:700;">v{version} - Angelo Estrada Espinosa</span></p>'
            '<p style="margin:0 0 5px 0;"><span style="color:#9a9a9a;font-size:8pt;">© 2026 GeloTech</span></p>'
            '<p style="margin:0 0 2px 0;"><a href="https://gsmcodeph.com" style="color:#8fc1ff;font-size:9pt;font-weight:700;text-decoration:none;">Gsmcodeph.com</a></p>'
            '<p style="margin:0;"><a href="https://facebook.com/gelotechxyz" style="color:#8fc1ff;font-size:9pt;font-weight:700;text-decoration:none;">facebook.com/gelotechxyz</a></p>'
            '</div>'
        )
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setOpenExternalLinks(True)
        header.setMaximumHeight(130)
        header.setContentsMargins(0, 0, 0, 0)


def _apply_action_icons(self) -> None:
    for button in self.findChildren(QPushButton):
        if button is getattr(self, "theme_btn", None):
            continue
        key = button.text().replace("▾", "").replace("…", "").strip()
        icon_name = ACTION_ICONS.get(key)
        if icon_name:
            button.setIcon(load_icon(icon_name))


def _style_feature_pages(app) -> None:
    app.setStyleSheet(app.styleSheet() + """
        QFrame#featureHeader, QFrame#helpHeader, QFrame#helpCard,
        QFrame#statusPanel, QFrame#contentPanel, QFrame#providerCard {
            border:1px solid palette(mid);
            border-radius:4px;
        }
        QLabel#helpHeading { font-weight:800; font-size:10pt; }
        QLabel#helpText { font-size:9pt; }
        QLabel#pageTitle { padding:3px 0 7px 8px; margin:0; }
        QPushButton#providerHeader { border-radius:4px; }
        QPushButton#providerUse, QPushButton#accentButton { border-radius:3px; }
    """)


def _wrap_apply_theme(self) -> None:
    if getattr(self, "_reference_theme_wrapped", False):
        return
    original = getattr(self.__class__, "_apply_theme", None)
    if original is None:
        return
    self._reference_theme_wrapped = True

    def apply():
        try:
            original(self)
        except TypeError:
            original()
        dark = bool(getattr(self, "dark_mode", True))
        palette = palette_profile(getattr(self, "theme_name", "orange"), dark)
        font_family = getattr(self, "ui_font", DEFAULT_UI_FONT)
        accent = palette.get("accent", "#f97316")
        c = REFERENCE_DARK if dark else REFERENCE_LIGHT
        app = QApplication.instance()
        if app is None:
            return
        app.setStyleSheet(f"""
            * {{ font-family:'{font_family}','Segoe UI',sans-serif; font-size:10pt; }}
            QWidget, QMainWindow, QDialog, QStackedWidget, QScrollArea,
            QAbstractScrollArea::viewport {{ background:{c['bg']}; color:{c['text']}; }}
            QFrame#sidebar {{ background:{c['bg']}; border-right:1px solid {c['border']}; }}
            QPushButton {{ background:{c['button']}; color:{c['text']}; border:1px solid {c['border']};
                border-radius:2px; padding:4px 9px; min-height:30px; max-height:30px; margin:0; font-weight:700; }}
            QPushButton:hover {{ background:{c['button_hover']}; border-color:{accent}; color:{c['text']}; }}
            QPushButton:pressed, QPushButton:checked {{ background:{accent}; border-color:{accent}; color:white; }}
            QPushButton#providerUse, QPushButton#accentButton {{ background:{accent}; border-color:{accent}; color:white; }}
            QLineEdit, QComboBox, QPlainTextEdit, QTextEdit {{ background:{c['input']}; color:{c['text']}; border:1px solid {c['border']}; border-radius:2px; }}
            QTableWidget, QListWidget {{ background:{c['panel2']}; color:{c['text']}; alternate-background-color:{c['panel']}; border:1px solid {c['border']}; gridline-color:{c['border']}; selection-background-color:{accent}; selection-color:white; }}
            QHeaderView::section {{ background:{c['header']}; color:#202020; border:1px solid {c['border']}; padding:6px 7px; font-weight:800; }}
            QPlainTextEdit#liveLog {{ background:{c['log']}; color:{c['log_text']}; border:1px solid {c['border']}; border-radius:2px; }}
            QFrame#sidebarGuide, QFrame#guidePanel, QFrame#contentPanel,
            QFrame#featureHeader, QFrame#helpHeader, QFrame#helpCard,
            QFrame#statusPanel, QFrame#providerCard {{ background:{c['panel']}; color:{c['text']}; border:1px solid {c['border']}; border-radius:4px; }}
            QFrame#deviceCard {{ background:{c['panel']}; color:{c['text']}; border:1px solid {accent}; border-radius:6px; }}
            QLabel#connectionTitle {{ color:{c['muted']}; font-size:8pt; font-weight:800; }}
            QLabel#connectionSummary {{ color:{c['text']}; font-size:10pt; font-weight:800; }}
            QLabel#connectionDetail {{ color:{c['muted']}; font-size:8.5pt; }}
            QLabel#connectionBadge {{ background:transparent; }}
            QLabel#guideText, QLabel#muted, QLabel#helpText {{ color:{c['muted']}; }}
            QLabel#brandTitle, QLabel#sidebarBrandHeader, QLabel#brand {{ background:transparent; color:#2388ff; }}
            QLabel#brandVersion {{ background:transparent; color:{c['text']}; }}
            QLabel#brandCopyright {{ background:transparent; color:{c['muted']}; }}
            QLabel#brandLink {{ background:transparent; color:#7fb7ff; }}
            QLabel#deviceText {{ color:#22c55e; font-weight:800; }}
            QLabel#securityText {{ color:#f5b700; font-weight:800; }}
            QLabel#statusText {{ color:{accent}; font-style:italic; }}
            QListWidget#sidebarNav {{ background:transparent; border:0; spacing:0; }}
            QListWidget#sidebarNav::item {{ min-height:30px; padding:0 9px; margin:0; border:1px solid {c['border']}; border-radius:2px; background:{c['button']}; font-weight:700; }}
            QMenu {{ background:{c['panel']}; color:{c['text']}; border:1px solid {c['border']}; }}
            QMenu::item {{ padding:6px 14px; }}
            QMenu::item:selected {{ background:{accent}; color:white; }}
            QScrollBar:vertical {{ background:{c['bg']}; width:10px; margin:0; }}
            QScrollBar::handle:vertical {{ background:{c['border']}; min-height:24px; border-radius:3px; }}
            QScrollBar:horizontal {{ background:{c['bg']}; height:10px; margin:0; }}
            QScrollBar::handle:horizontal {{ background:{c['border']}; min-width:28px; border-radius:3px; }}
        """)
        _normalise_sidebar(self)
        _apply_action_icons(self)
        _style_feature_pages(app)
        icon = _set_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

    self._apply_theme = apply
    apply()


def install_visual_polish(MainWindow, LoginDialog=None) -> None:
    icon = _set_app_icon()
    original_init = MainWindow.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._qt_sidebar_version = "1.7.8"
        if not icon.isNull():
            self.setWindowIcon(icon)
        _normalise_sidebar(self)
        _apply_action_icons(self)
        _wrap_apply_theme(self)

    MainWindow.__init__ = init

    if LoginDialog is not None:
        original_login_init = LoginDialog.__init__

        def login_init(self, *args, **kwargs):
            original_login_init(self, *args, **kwargs)
            if not icon.isNull():
                self.setWindowIcon(icon)

        LoginDialog.__init__ = login_init
