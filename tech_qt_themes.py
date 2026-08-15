"""Qt6 theme engine for GeloTech.

The bundled CTkThemesPack JSON files remain the palette source of truth. This
module resolves their widget colors into a Qt stylesheet while keeping the
same palette names and UI font choices available to users.
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
    table = p["panel2"]
    return f"""
    QWidget {{
        font-family: \"{font_family}\";
        font-size: 10pt;
        color: {p['text']};
        background: {p['bg']};
    }}
    QMainWindow, QDialog {{ background: {p['bg']}; }}
    QFrame#sidebar {{ background: {p['panel2']}; border-right: 1px solid {p['border']}; }}
    QLabel#brand {{ color: {p['accent']}; font-size: 22pt; font-weight: 800; }}
    QLabel#muted {{ color: {p['muted']}; }}
    QToolButton, QPushButton {{
        background: {p['panel']}; border: 1px solid {p['border']};
        border-radius: 7px; padding: 6px 9px; font-weight: 700;
    }}
    QToolButton:hover, QPushButton:hover {{ background: {p['accent_hover']}; }}
    QToolButton:checked {{ background: {p['accent']}; color: white; }}
    QLineEdit, QComboBox, QSpinBox {{
        background: {p['input']}; border: 1px solid {p['border']};
        border-radius: 6px; padding: 6px;
    }}
    QPlainTextEdit, QTextEdit {{
        background: {table}; border: 1px solid {p['border']};
        border-radius: 7px; padding: 6px;
    }}
    QGroupBox {{ border: 1px solid {p['border']}; border-radius: 8px; margin-top: 10px; padding-top: 10px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
    QTableWidget, QTreeWidget {{
        background: {table}; alternate-background-color: {p['panel']};
        border: 1px solid {p['border']}; gridline-color: {p['border']};
    }}
    QHeaderView::section {{ background: {p['panel']}; color: {p['text']}; padding: 7px; border: 0; border-right: 1px solid {p['border']}; font-weight: 800; }}
    QProgressBar {{ background: {p['panel']}; border: 1px solid {p['border']}; border-radius: 6px; text-align: center; }}
    QProgressBar::chunk {{ background: {p['accent']}; border-radius: 6px; }}
    QScrollBar:vertical {{ background: {p['bg']}; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {p['border']}; min-height: 24px; border-radius: 6px; }}
    QScrollBar:horizontal {{ background: {p['bg']}; height: 12px; margin: 0; }}
    QScrollBar::handle:horizontal {{ background: {p['border']}; min-width: 24px; border-radius: 6px; }}
    """


def apply_theme(app: QApplication, name: str, dark: bool = True, font_family: str = DEFAULT_UI_FONT) -> None:
    app.setStyleSheet(build_stylesheet(name, dark, font_family))
    app.setProperty("gelotech_theme", name)
    app.setProperty("gelotech_font", font_family)
