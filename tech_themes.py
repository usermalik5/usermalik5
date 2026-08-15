# -*- coding: utf-8 -*-
"""Theme palette management for GeloTech Tool.

Integrates the upstream CTkThemesPack palettes (see ``themes/*.json``) so the
sidebar toggle can switch between palettes while keeping every widget
contrast-readable in both light and dark appearance.

Two concerns are separated:
  * **CTk default widgets** (CTkButton, CTkEntry, the scrollbars, etc.) are
    styled from the pack ``themes/<name>.json`` via ``apply_ctk_theme``.
  * **Custom 3uTools-style surfaces** (sidebar, panels, cards, the status bar,
    the log console frame) use the app's own hex palettes in ``THEMES``.
    ``PALETTE_COLORS`` maps each palette name to a full light<->dark hex map
    so the existing ``COLOR_SWAP``/``_theme_walk`` walker recolors them, and
    ``_fix_button_text_colors`` picks a readable text color per background.

Themes are bundled as data files (``themes/*.json``) next to the executable.
"""

import os
import json

# Where the bundled theme JSON files live, accounting for the one-file
# PyInstaller layout (files sit next to the frozen exe / in _MEIPASS) as well
# as a plain source checkout.
try:
    import sys

    _MEIPASS = getattr(sys, "_MEIPASS", None)
    if _MEIPASS:
        THEME_DIR = os.path.join(_MEIPASS, "themes")
    else:
        # themes/ lives alongside this module (inside the repo / next to the
        # frozen exe bundle), not one directory above it.
        THEME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
except Exception:  # pragma: no cover - defensive
    THEME_DIR = "themes"


def load_theme_json(name):
    """Load a CTkThemesPack theme JSON by name (e.g. ``"orange"``).

    Returns the parsed dict, or an empty dict if missing/corrupt.
    """
    path = os.path.join(THEME_DIR, name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# The palettes users can switch between. "orange" is the shipped default.
# Order matters for the sidebar toggle (cycled in this order).
PALETTES = [
    "orange", "autumn", "breeze", "carrot", "cherry", "coffee", "lavender",
    "marsh", "metal", "midnight", "patina", "pink", "red", "rime", "rose",
    "sky", "violet", "yellow",
]

DEFAULT_THEME = "orange"


def _pack_accent(name):
    """Pull the dark-mode button foreground from a pack theme (the accent)."""
    data = load_theme_json(name)
    try:
        btn = data.get("CTkButton", {})
        fg = btn.get("fg_color", ["#FF6505", "#FF6505"])
        if isinstance(fg, list) and len(fg) >= 2:
            return fg[1]
        return fg
    except Exception:
        return "#FF6505"


# Fallback accent palette per theme (dark-mode button color from each pack's
# CTkButton.fg_color when available; kept compact so this module stays small).
_FALLBACK_ACCENT = {
    "orange": "#FF6505", "autumn": "#D35400", "breeze": "#0275D8",
    "carrot": "#FF6F00", "cherry": "#C2185B", "coffee": "#6F4E37",
    "lavender": "#9C27B0", "marsh": "#009688", "metal": "#4ECDC4",
    "midnight": "#1976D2", "patina": "#008080", "pink": "#E1306C",
    "red": "#DC143C", "rime": "#7FDBFF", "rose": "#FF66CC", "sky": "#039BE5",
    "violet": "#673AB7", "yellow": "#FFD300",
}

# Hover color per palette (a step darker along the pack's own ramp where the
# pack exposes one; otherwise a darken of the accent).
_HOVER = {
    "orange": "#CC5500", "autumn": "#B84500", "breeze": "#0257B3",
    "carrot": "#CC5500", "cherry": "#8E0045", "coffee": "#4E3A2A",
    "lavender": "#6A1B9A", "marsh": "#00796B", "midnight": "#115296",
    "patina": "#005F5F", "pink": "#A31052", "red": "#9B1B32",
    "rime": "#62B1E9", "rose": "#CC0066", "sky": "#0275D8",
    "violet": "#4527A0", "yellow": "#D4AF37",
}


def _darken(hexcolor, amount=0.18):
    """Return a hex color darkened by ``amount`` (0..1) for hover variants."""
    try:
        h = hexcolor.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        r = max(0, int(r * (1 - amount)))
        g = max(0, int(g * (1 - amount)))
        b = max(0, int(b * (1 - amount)))
        return "#%02x%02x%02x" % (r, g, b)
    except Exception:
        return hexcolor


def accent_for(name):
    """Dark-mode accent (button fg) for a palette."""
    return _FALLBACK_ACCENT.get(name, _pack_accent(name))


def hover_for(name):
    return _HOVER.get(name, _darken(accent_for(name)))


def apply_ctk_theme(name):
    """Apply the pack's CTk default-widget theme for ``name``.

    Sets CustomTkinter's default color theme from the bundled
    ``themes/<name>.json`` via its file path (CTk accepts a path or a dict).
    Falls back to CTk's built-in ``blue`` theme if the file is missing/corrupt.
    Never raises.
    """
    import customtkinter as ctk
    if name not in PALETTES:
        name = DEFAULT_THEME
    path = os.path.join(THEME_DIR, name + ".json")
    try:
        if os.path.isfile(path):
            ctk.set_default_color_theme(path)
        else:
            ctk.set_default_color_theme("blue")
    except Exception:
        try:
            ctk.set_default_color_theme("blue")
        except Exception:
            pass
