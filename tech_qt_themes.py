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

UI_FONTS = [
    "Segoe UI", "Arial", "Arial Black", "Calibri", "Cambria", "Candara",
    "Comic Sans MS", "Consolas", "Constantia", "Corbel", "Courier New",
    "Franklin Gothic Medium", "Garamond", "Georgia", "Impact",
    "Lucida Console", "Microsoft Sans Serif", "Palatino Linotype", "Tahoma",
    "Times New Roman", "Trebuchet MS", "Verdana",
]
DEFAULT_UI_FONT = "Segoe UI"


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
    return f"""
    * {{ font-family: \"{font_family}\"; font-size: 10pt; }}
    QWidget {{ color: {p['text']}; background: {p['bg']}; }}
    QMainWindow, QDialog {{ background: {p['bg']}; }}

    QFrame#sidebar {{
        background: {p['panel2']};
        border-right: 1px solid {p['border']};
    }}
    QLabel#brand {{
        color: {p['accent']};
        font-size: 22pt;
        font-weight: 800;
    }}
    QLabel#versionLabel {{ font-size: 9pt; font-weight: 700; }}
    QLabel#sidebarSection {{
        color: {p['muted']};
        font-size: 8pt;
        font-weight: 800;
        letter-spacing: 0.6px;
        padding-top: 5px;
    }}
    QLabel#muted {{ color: {p['muted']}; }}

    QListWidget#sidebarNav {{
        background: transparent;
        border: 0;
        outline: 0;
    }}
    QListWidget#sidebarNav::item {{
        min-height: 28px;
        padding: 5px 9px;
        border: 1px solid {p['border']};
        border-radius: 8px;
        background: {p['panel']};
        font-weight: 700;
    }}
    QListWidget#sidebarNav::item:hover {{ background: {p['accent_hover']}; }}
    QListWidget#sidebarNav::item:selected {{
        background: {p['accent']};
        color: white;
        border-color: {p['accent']};
    }}

    QPushButton {{
        background: {p['panel']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 8px;
        padding: 5px 10px;
        min-height: 28px;
        font-weight: 700;
    }}
    QPushButton:hover {{ background: {p['accent_hover']}; color: white; }}
    QPushButton:pressed, QPushButton:checked {{ background: {p['accent']}; color: white; }}
    QPushButton:disabled {{ color: {p['muted']}; background: {p['panel2']}; }}

    QLineEdit, QComboBox {{
        background: {p['input']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 7px;
        padding: 6px 9px;
        min-height: 28px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border-color: {p['accent']}; }}

    QFrame#phonePanel {{ background: transparent; }}
    QLabel#phoneMockup {{ background: transparent; }}
    QFrame#contentPanel {{ background: {p['bg']}; }}
    QPlainTextEdit#liveLog {{
        background: {p['panel2']};
        color: #7CFF00;
        border: 1px solid {p['border']};
        border-radius: 7px;
        padding: 7px;
        font-family: Consolas, \"Courier New\", monospace;
        font-size: 9pt;
    }}
    QFrame#guidePanel, QFrame#sidebarGuide {{
        background: {p['panel']};
        border: 1px solid {p['border']};
        border-radius: 8px;
    }}
    QLabel#guideTitle {{ font-size: 8pt; font-weight: 800; }}
    QLabel#guideText {{ color: {p['muted']}; font-size: 8pt; }}
    QLabel#statusText {{ font-style: italic; color: {p['accent']}; }}
    QLabel#securityText {{ color: {p['amber']}; font-weight: 800; }}
    QLabel#deviceText {{ color: {p['green']}; font-weight: 800; }}
    QLabel#legendText {{ color: {p['muted']}; font-size: 8pt; }}
    QLabel#subHeading {{ font-weight: 800; font-size: 9pt; }}

    QTableWidget#packageTable {{
        background: {p['panel2']};
        alternate-background-color: {p['panel']};
        color: {p['text']};
        border: 1px solid {p['border']};
        gridline-color: {p['border']};
        selection-background-color: {p['accent']};
        selection-color: white;
        outline: 0;
    }}
    QTableWidget#packageTable::item {{ padding: 4px 7px; }}
    QHeaderView::section {{
        background: {p['panel']};
        color: {p['text']};
        padding: 6px 7px;
        border: 0;
        border-right: 1px solid {p['border']};
        border-bottom: 1px solid {p['border']};
        font-weight: 800;
        font-size: 9pt;
    }}

    QPlainTextEdit, QTextEdit {{
        background: {p['panel2']};
        color: {p['text']};
        border: 1px solid {p['border']};
        border-radius: 7px;
        padding: 6px;
    }}
    QScrollBar:vertical {{ background: {p['bg']}; width: 11px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {p['border']}; min-height: 24px; border-radius: 5px; }}
    QScrollBar:horizontal {{ background: {p['bg']}; height: 11px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {p['border']}; min-width: 28px; border-radius: 5px; }}

    QMenu {{
        background: {p['panel']};
        border: 1px solid {p['border']};
        padding: 4px;
    }}
    QMenu::item {{ padding: 6px 14px; }}
    QMenu::item:selected {{ background: {p['accent']}; color: white; }}
    """


def apply_theme(app: QApplication, name: str, dark: bool = True, font_family: str = DEFAULT_UI_FONT) -> None:
    app.setStyleSheet(build_stylesheet(name, dark, font_family))
    app.setProperty("gelotech_theme", name)
    app.setProperty("gelotech_font", font_family)
