"""Qt6 theme engine for GeloTech.

CTkThemesPack remains the palette source of truth. The Qt stylesheet keeps
the same palette names while reproducing the compact legacy GeloTech UI.
"""
from __future__ import annotations

import json
import os
import sys
from functools import lru_cache

from PySide6.QtWidgets import QApplication

THEME_DIR = os.path.join(
    getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))),
    "themes",
)

PALETTES = [
    "orange", "autumn", "breeze", "carrot", "cherry", "coffee", "lavender",
    "marsh", "metal", "midnight", "patina", "pink", "red", "rime", "rose",
    "sky", "violet", "yellow",
]
DEFAULT_THEME = "orange"

UI_FONTS = ["Segoe UI Variable", "Segoe UI", "Aptos", "Bahnschrift", "Consolas"]
DEFAULT_UI_FONT = "Segoe UI Variable"


def _resolve(value, dark: bool = False, fallback: str = "#ffffff") -> str:
    if isinstance(value, (list, tuple)) and value:
        value = value[1 if dark and len(value) > 1 else 0]
    return str(value or fallback)


@lru_cache(maxsize=32)
def load_palette(name: str) -> dict:
    if name not in PALETTES:
        name = DEFAULT_THEME
    path = os.path.join(THEME_DIR, f"{name}.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def palette_profile(name: str, dark: bool = True) -> dict[str, str]:
    data = load_palette(name)
    root = data.get("CTk", {})
    frame = data.get("CTkFrame", {})
    button = data.get("CTkButton", {})
    label = data.get("CTkLabel", {})
    entry = data.get("CTkEntry", {})
    return {
        "bg": _resolve(root.get("fg_color"), dark, "#171a1f"),
        "panel": _resolve(frame.get("fg_color"), dark, "#20242a"),
        "panel2": _resolve(frame.get("top_fg_color"), dark, "#191c21"),
        "border": _resolve(frame.get("border_color"), dark, "#353b45"),
        "input": _resolve(entry.get("fg_color"), dark, "#11151a"),
        "accent": _resolve(button.get("fg_color"), dark, "#f97316"),
        "accent_hover": _resolve(button.get("hover_color"), dark, "#ea580c"),
        "text": _resolve(label.get("text_color"), dark, "#f4f4f5"),
        "muted": _resolve(entry.get("placeholder_text_color"), dark, "#9298a3"),
        "green": "#22c55e",
        "red": "#ef4444",
        "amber": "#f59e0b",
    }


def build_stylesheet(name: str = DEFAULT_THEME, dark: bool = True, font_family: str = DEFAULT_UI_FONT) -> str:
    p = palette_profile(name, dark)
    if dark:
        c = dict(sidebar="#0d0f12", card="#171b20", card2="#15191e", border="#2c3340",
                 disabled="#111419", log_bg="#1b222c", log_text="#7CFF00", panel="#1b222c",
                 table_bg="#111a16", table_alt="#0e1813", table_grid="#17241d")
    else:
        c = dict(sidebar="#f2f3f5", card="#ffffff", card2="#eef0f2", border="#d0d7de",
                 disabled="#e9ecef", log_bg="#f6f8fa", log_text="#1a7f37", panel="#f6f8fa",
                 table_bg="#ffffff", table_alt="#f3f6f4", table_grid="#dfe7df")
    return f"""
    * {{ font-family: \"{font_family}\", \"Segoe UI\", sans-serif; font-size: 10pt; }}
    QWidget {{ color: {p['text']}; background: {p['bg']}; }}
    QMainWindow, QDialog {{ background: {p['bg']}; }}

    QFrame#sidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
    QLabel#brand {{ color: #1a8cff; font-size: 22pt; font-weight: 800; }}
    QLabel#copyrightLabel {{ color: #555b63; font-size: 8pt; }}
    QLabel#versionLabel {{ color: #a6a6a6; font-size: 9pt; font-weight: 700; }}
    QLabel#brandLink {{ color: #58a6ff; font-size: 8pt; }}
    QLabel#sidebarSection {{ color: #7a8699; font-size: 8pt; font-weight: 800; padding-top: 5px; }}
    QLabel#muted {{ color: {p['muted']}; }}

    QListWidget#sidebarNav {{ background: transparent; border: 0; outline: 0; }}
    QListWidget#sidebarNav::item {{ min-height: 27px; padding: 5px 9px; border: 1px solid {c['border']}; border-radius: 8px; background: {c['card']}; font-weight: 700; }}
    QListWidget#sidebarNav::item:hover {{ background: {p['accent_hover']}; color: white; }}
    QListWidget#sidebarNav::item:selected {{ background: {p['accent']}; color: white; border-color: {p['accent']}; }}

    QPushButton {{ background: {c['card']}; color: {p['text']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 5px 10px; min-height: 28px; font-weight: 700; }}
    QPushButton:hover {{ background: {p['accent_hover']}; color: white; }}
    QPushButton:pressed, QPushButton:checked {{ background: {p['accent']}; color: white; }}
    QPushButton:disabled {{ color: #666c74; background: {c['disabled']}; }}

    QLineEdit, QComboBox {{ background: {p['input']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 7px; padding: 6px 9px; min-height: 28px; }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {p['accent']}; }}

    QFrame#phonePanel, QFrame#contentPanel {{ background: transparent; }}
    QPlainTextEdit#liveLog {{ background: {c['log_bg']}; color: {c['log_text']}; border: 1px solid {c['border']}; border-radius: 7px; padding: 7px; font-family: Consolas, \"Courier New\", monospace; font-size: 9pt; }}
    QFrame#guidePanel {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 8px; }}
    QFrame#sidebarGuide {{ background: {c['card2']}; border: 1px solid {c['border']}; border-radius: 8px; }}
    QLabel#guideTitle {{ color: {p['text']}; font-size: 8pt; font-weight: 800; }}
    QLabel#guideText {{ color: {p['muted']}; font-size: 8pt; }}
    QLabel#pageTitle {{ color: #1a8cff; font-size: 15pt; font-weight: 800; padding: 2px 0 10px 12px; border-left: 4px solid #1a8cff; border-bottom: 1px solid {p['border']}; margin-bottom: 6px; }}
    QLabel#statusText {{ font-style: italic; color: {p['accent']}; }}
    QLabel#securityText {{ color: {p['amber']}; font-weight: 800; }}
    QLabel#deviceText {{ color: {p['green']}; font-weight: 800; }}
    QLabel#legendText {{ color: {p['muted']}; font-size: 8pt; }}
    QLabel#subHeading {{ font-weight: 800; font-size: 9pt; }}

    QTableWidget#packageTable {{ background: {c['table_bg']}; alternate-background-color: {c['table_alt']}; color: {p['text']}; border: 1px solid {c['border']}; gridline-color: {c['table_grid']}; selection-background-color: {p['accent']}; selection-color: white; outline: 0; }}
    QTableWidget#packageTable::item {{ padding: 4px 7px; }}
    QHeaderView::section {{ background: #d9d9d9; color: #202020; padding: 6px 7px; border: 0; border-right: 1px solid #a7a7a7; border-bottom: 1px solid #a7a7a7; font-weight: 800; font-size: 9pt; }}

    QPlainTextEdit, QTextEdit {{ background: {p['panel2']}; color: {p['text']}; border: 1px solid {p['border']}; border-radius: 7px; padding: 6px; }}
    QScrollBar:vertical {{ background: {p['bg']}; width: 11px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {p['border']}; min-height: 24px; border-radius: 5px; }}
    QScrollBar:horizontal {{ background: {p['bg']}; height: 11px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {p['border']}; min-width: 28px; border-radius: 5px; }}
    QMenu {{ background: {p['panel']}; border: 1px solid {p['border']}; padding: 4px; border-radius: 8px; }}
    QMenu::item {{ padding: 6px 14px; border-radius: 5px; }}
    QMenu::item:selected {{ background: {p['accent']}; color: white; }}
    QComboBox QAbstractItemView {{ background: {p['panel']}; color: {p['text']}; selection-background-color: {p['accent']}; selection-color: white; border: 1px solid {p['border']}; outline: 0; }}

    QDialog {{ border-radius: 12px; }}
    QLabel#dialogTitle {{ color: {p['text']}; font-size: 14pt; font-weight: 800; }}
    QLabel#dialogDesc {{ color: {p['text']}; font-size: 10pt; }}
    QLabel#dialogBullets {{ color: {p['muted']}; font-size: 9.5pt; }}

    QPushButton#accentButton {{ background: {p['accent']}; color: white; border: 1px solid {p['accent']}; border-radius: 8px; padding: 7px 16px; min-height: 30px; font-weight: 800; }}
    QPushButton#accentButton:hover {{ background: {p['accent_hover']}; }}
    QPushButton#accentButton:disabled {{ color: #666c74; background: {c['disabled']}; border-color: {c['disabled']}; }}
    QPushButton#linkButton {{ background: transparent; color: {p['accent']}; border: 0; padding: 6px 4px; min-height: 26px; font-weight: 700; }}
    QPushButton#linkButton:hover {{ color: {p['accent_hover']}; text-decoration: underline; }}

    QFrame#providerCard {{ background: {c['card']}; border: 1px solid {c['border']}; border-radius: 10px; }}
    QPushButton#providerHeader {{ background: transparent; border: 0; border-radius: 10px; text-align: left; padding: 0; }}
    QPushButton#providerHeader:hover {{ background: {c['card2']}; }}
    QPushButton#providerHeader:pressed {{ background: {c['card2']}; color: {p['text']}; }}
    QLabel#providerName {{ font-weight: 800; font-size: 11pt; }}
    QLabel#providerHost {{ font-family: Consolas, "Courier New", monospace; font-size: 8.5pt; color: {p['muted']}; }}
    QLabel#providerChevron {{ font-size: 12pt; color: {p['muted']}; padding: 0 4px; }}
    QLabel#providerDesc {{ font-size: 9pt; color: {p['text']}; }}
    QLabel#providerKey {{ font-weight: 800; font-size: 8.5pt; color: {p['muted']}; }}
    QLabel#providerValue {{ font-size: 9pt; color: {p['text']}; }}
    QLabel#providerLink {{ font-size: 8.5pt; color: {p['accent']}; }}
    QLabel#providerLink:hover {{ color: {p['accent_hover']}; }}
    QPushButton#providerUse {{ background: {p['accent']}; color: white; border: 1px solid {p['accent']}; border-radius: 8px; padding: 6px 14px; min-height: 30px; font-weight: 800; }}
    QPushButton#providerUse:hover {{ background: {p['accent_hover']}; }}

    QFrame#loginBrand {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a8cff, stop:1 #6366f1); }}
    QLabel#loginTitle {{ color: white; font-size: 26pt; font-weight: 900; }}
    QLabel#loginTag {{ color: rgba(255,255,255,0.85); font-size: 10pt; }}
    QLabel#loginFeat {{ color: rgba(255,255,255,0.92); font-size: 9.5pt; }}
    QLabel#loginWelcome {{ color: {p['text']}; font-size: 19pt; font-weight: 800; }}
    QLabel#loginSub {{ color: {p['muted']}; font-size: 9.5pt; }}
    QLabel#fieldLabel {{ color: {p['muted']}; font-size: 8.5pt; font-weight: 700; }}
    QLabel#loginStatus {{ color: {p['amber']}; font-size: 9pt; }}
    """


def apply_theme(app: QApplication, name: str, dark: bool = True, font_family: str = DEFAULT_UI_FONT) -> None:
    app.setStyleSheet(build_stylesheet(name, dark, font_family))
    app.setProperty("gelotech_theme", name)
    app.setProperty("gelotech_font", font_family)
