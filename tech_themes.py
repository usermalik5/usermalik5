# -*- coding: utf-8 -*-
"""CTkThemesPack palette management for GeloTech Tool.

The upstream theme JSON is the source of truth. GeloTech keeps its existing
3uTools-style layout, but the selected palette now supplies the actual surface,
text, input, border, accent, and hover colors instead of only replacing the
accent with a hand-maintained fallback table.

The app currently uses the dark side of each CTkThemesPack palette. The JSON
files keep their light-side values so a separate appearance selector can be
added later without changing the theme data format.
"""

import json
import os
import sys

try:
    _MEIPASS = getattr(sys, "_MEIPASS", None)
    if _MEIPASS:
        THEME_DIR = os.path.join(_MEIPASS, "themes")
    else:
        THEME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
except Exception:  # pragma: no cover
    THEME_DIR = "themes"


PALETTES = [
    "orange", "autumn", "breeze", "carrot", "cherry", "coffee", "lavender",
    "marsh", "metal", "midnight", "patina", "pink", "red", "rime", "rose",
    "sky", "violet", "yellow",
]

DEFAULT_THEME = "orange"


def load_theme_json(name):
    """Return one CTkThemesPack palette, or an empty dict if unavailable."""
    path = os.path.join(THEME_DIR, f"{name}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _value(value, dark=False, fallback=None):
    """Resolve a CTk theme value and select its light/dark member."""
    if isinstance(value, (list, tuple)) and value:
        index = 1 if dark and len(value) > 1 else 0
        return value[index]
    return value if value is not None else fallback


def palette_profile(name, dark=False):
    """Map CTkThemesPack colors onto GeloTech's existing shared theme slots."""
    if name not in PALETTES:
        name = DEFAULT_THEME
    data = load_theme_json(name)

    root = data.get("CTk", {})
    frame = data.get("CTkFrame", {})
    button = data.get("CTkButton", {})
    label = data.get("CTkLabel", {})
    entry = data.get("CTkEntry", {})

    bg = _value(root.get("fg_color"), dark, "gray14")
    panel = _value(frame.get("fg_color"), dark, "gray17")
    panel2 = _value(frame.get("top_fg_color"), dark, panel)
    border = _value(frame.get("border_color"), dark, "gray28")
    input_color = _value(entry.get("fg_color"), dark, panel2)
    accent = _value(button.get("fg_color"), dark, "#3b82f6")
    accent_hover = _value(button.get("hover_color"), dark, accent)
    text = _value(label.get("text_color"), dark, "#DCE4EE")
    muted = _value(entry.get("placeholder_text_color"), dark, text)

    return {
        "bg": bg,
        "panel": panel,
        "panel2": panel2,
        "card": panel2,
        "border": border,
        "input": input_color,
        "accent": accent,
        "accent_h": accent_hover,
        "green": "#22c55e",
        "red": "#ef4444",
        "amber": "#f59e0b",
        "text": text,
        "muted": muted,
        "sidebar": bg,
    }


def accent_for(name):
    """Return the actual light-mode button accent from the selected JSON."""
    return palette_profile(name, dark=False)["accent"]


def hover_for(name):
    """Return the actual light-mode button hover color from the selected JSON."""
    return palette_profile(name, dark=False)["accent_h"]


def _install_surface_palette(name, dark=False):
    """Make the CTkThemesPack palette the source of truth for GeloTech surfaces.

    ``TechToolCore._apply_theme`` calls this module before walking the existing
    widget tree. Updating the shared dictionaries here lets the existing theme
    walker recolor older widgets without a second large UI-specific theme layer.
    """
    try:
        import tech_common

        profile = palette_profile(name, dark=dark)
        tech_common.THEME.update(profile)

        dark_tokens = tech_common.THEMES.get("dark", {})
        for key in ("bg", "panel", "panel2", "card", "border", "input", "text", "muted", "sidebar"):
            old = dark_tokens.get(key)
            new = profile.get(key)
            if isinstance(old, str) and isinstance(new, str):
                tech_common.COLOR_SWAP[old] = new

        aliases = {
            "#0d1117": profile["input"],
            "#16191e": profile["panel"],
            "#11151c": profile["panel2"],
            "#131921": profile["panel2"],
            "#1b222c": profile["card"],
            "#21262d": profile["border"],
            "#27313d": profile["card"],
            "#30363d": profile["border"],
            "#2c3340": profile["border"],
            "#e6edf3": profile["text"],
            "#e8ecf2": profile["text"],
            "#8b949e": profile["muted"],
            "#8b98a9": profile["muted"],
            "#aab7c4": profile["muted"],
            "#aeb8c2": profile["muted"],
        }
        for old, new in aliases.items():
            tech_common.COLOR_SWAP[old] = new
    except Exception:
        pass


def _find_theme_button(root):
    """Find the sidebar palette button without coupling this module to GeloTechTool."""
    try:
        import customtkinter as ctk
    except Exception:
        return None

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    try:
        for widget in walk(root):
            if isinstance(widget, ctk.CTkButton):
                try:
                    text = str(widget.cget("text")).strip()
                except Exception:
                    continue
                if text.casefold() in {p.casefold() for p in PALETTES}:
                    return widget
    except Exception:
        pass
    return None


def install_theme_dropdown(current_name):
    """Turn the existing sidebar theme button into a direct palette picker."""
    try:
        import tkinter as tk

        root = getattr(tk, "_default_root", None)
        if root is None:
            return
        button = _find_theme_button(root)
        if button is None:
            return

        profile = palette_profile(current_name, dark=False)
        menu = getattr(root, "_gelotech_theme_menu", None)
        if menu is not None:
            try:
                menu.destroy()
            except Exception:
                pass

        menu = tk.Menu(
            root,
            tearoff=False,
            bg=profile["panel"],
            fg=profile["text"],
            activebackground=profile["accent"],
            activeforeground=profile["text"],
            relief="flat",
            borderwidth=1,
        )

        def select(name):
            try:
                root._theme_mode = name
                data = root._load_settings()
                data["theme"] = name
                root._save_settings(data)
            except Exception:
                pass
            try:
                root._apply_theme(name)
            except Exception:
                pass

        for palette in PALETTES:
            label = palette.capitalize()
            if palette == current_name:
                label = "✓ " + label
            menu.add_command(label=label, command=lambda p=palette: select(p))

        root._gelotech_theme_menu = menu

        def open_menu():
            try:
                x = button.winfo_rootx()
                y = button.winfo_rooty() + button.winfo_height()
                menu.tk_popup(x, y)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass

        button.configure(command=open_menu)
        button.configure(text=current_name.capitalize())
    except Exception:
        pass


def apply_ctk_theme(name, dark=False):
    """Apply the actual CTkThemesPack JSON and synchronize app surfaces."""
    import customtkinter as ctk

    if name not in PALETTES:
        name = DEFAULT_THEME
    path = os.path.join(THEME_DIR, f"{name}.json")

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

    _install_surface_palette(name, dark=dark)
    install_theme_dropdown(name)
