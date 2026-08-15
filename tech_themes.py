# -*- coding: utf-8 -*-
"""CTkThemesPack integration for GeloTech Tool.

Each bundled JSON remains the source of truth.  The important detail is that
we apply the JSON by *widget type* (CTkFrame, CTkButton, CTkEntry, etc.) rather
than trying to guess a widget's role from whatever color it currently has.
That prevents one palette's accent from leaking into every panel on the next
palette switch.
"""

import json
import os
import sys

try:
    _MEIPASS = getattr(sys, "_MEIPASS", None)
    THEME_DIR = os.path.join(_MEIPASS, "themes") if _MEIPASS else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "themes"
    )
except Exception:  # pragma: no cover
    THEME_DIR = "themes"

PALETTES = [
    "orange", "autumn", "breeze", "carrot", "cherry", "coffee", "lavender",
    "marsh", "metal", "midnight", "patina", "pink", "red", "rime", "rose",
    "sky", "violet", "yellow",
]
DEFAULT_THEME = "orange"


def load_theme_json(name):
    path = os.path.join(THEME_DIR, f"{name}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _value(value, dark=False, fallback=None):
    if isinstance(value, (list, tuple)) and value:
        return value[1 if dark and len(value) > 1 else 0]
    return value if value is not None else fallback


def palette_profile(name, dark=False):
    """Return the small set of shared GeloTech colors used outside CTk widgets."""
    data = load_theme_json(name if name in PALETTES else DEFAULT_THEME)
    root = data.get("CTk", {})
    frame = data.get("CTkFrame", {})
    button = data.get("CTkButton", {})
    label = data.get("CTkLabel", {})
    entry = data.get("CTkEntry", {})
    return {
        "bg": _value(root.get("fg_color"), dark, "gray92"),
        "panel": _value(frame.get("fg_color"), dark, "gray86"),
        "panel2": _value(frame.get("top_fg_color"), dark, "gray81"),
        "card": _value(frame.get("top_fg_color"), dark, "gray81"),
        "border": _value(frame.get("border_color"), dark, "gray65"),
        "input": _value(entry.get("fg_color"), dark, "#F9F9FA"),
        "accent": _value(button.get("fg_color"), dark, "#3b82f6"),
        "accent_h": _value(button.get("hover_color"), dark, "#2f6fe4"),
        "green": "#16a34a" if not dark else "#22c55e",
        "red": "#dc2626" if not dark else "#ef4444",
        "amber": "#d97706" if not dark else "#f59e0b",
        "text": _value(label.get("text_color"), dark, "gray10"),
        "muted": _value(entry.get("placeholder_text_color"), dark, "gray52"),
        "sidebar": _value(root.get("fg_color"), dark, "gray92"),
    }


def _widget_theme(data, class_name, dark=False):
    """Resolve one JSON widget section to concrete CTk configure values."""
    section = data.get(class_name, {})
    if not isinstance(section, dict):
        return {}
    result = {}
    for key, value in section.items():
        resolved = _value(value, dark)
        if isinstance(resolved, str):
            result[key] = resolved
    return result


def accent_for(name):
    return palette_profile(name, dark=False)["accent"]


def hover_for(name):
    return palette_profile(name, dark=False)["accent_h"]


def _is_preserved_widget(widget):
    """Keep the phone screen and neon log console visually independent."""
    try:
        cls = type(widget).__name__
        if cls == "CTkTextbox" and str(widget.cget("fg_color")) in {"#000200", "#1D1E1E"}:
            return True
        if cls == "CTkFrame" and str(widget.cget("fg_color")) in {"#01030a", "#03160d"}:
            return True
    except Exception:
        pass
    return False


def _configure_widget(widget, config):
    """Apply only options supported by the current widget instance."""
    for attr, value in config.items():
        try:
            widget.configure(**{attr: value})
        except Exception:
            continue


def _apply_widget_palette(widget, data, dark=False):
    """Apply the matching CTkThemesPack section to an existing widget."""
    cls = type(widget).__name__
    if cls in {"CTk", "CTkToplevel"}:
        config = _widget_theme(data, cls, dark)
    elif cls in {
        "CTkFrame", "CTkButton", "CTkLabel", "CTkEntry", "CTkCheckBox",
        "CTkSwitch", "CTkRadioButton", "CTkProgressBar", "CTkSlider",
        "CTkOptionMenu", "CTkComboBox", "CTkScrollbar", "CTkSegmentedButton",
        "CTkTextbox", "CTkScrollableFrame",
    }:
        config = _widget_theme(data, cls, dark)
    else:
        return

    if not config:
        return

    # The live phone/mirror terminal deliberately keeps its own black/green design.
    if _is_preserved_widget(widget):
        return

    _configure_widget(widget, config)

    # The theme JSON has ``text_color`` but CTk's disabled text uses a separate
    # option.  Let the pack define that value where available.
    if "text_color_disabled" in config:
        try:
            widget.configure(text_color_disabled=config["text_color_disabled"])
        except Exception:
            pass


def recolor_existing_widgets(root, name, dark=False):
    """Apply the selected JSON directly by widget class; no color guessing."""
    import tkinter as tk
    from tkinter import ttk
    import tech_common

    data = load_theme_json(name if name in PALETTES else DEFAULT_THEME)
    stack = list(root.winfo_children())

    while stack:
        widget = stack.pop()
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
        _apply_widget_palette(widget, data, dark)

    # The package list is ttk-based, so it is outside the CTk theme JSON.
    profile = palette_profile(name, dark)
    try:
        style = ttk.Style()
        style.configure(
            "AppList.Treeview",
            background=profile["panel2"],
            fieldbackground=profile["panel2"],
            foreground=profile["text"],
        )
        style.configure(
            "AppList.Vertical.Tscrollbar",
            background=profile["panel"],
            troughcolor=profile["bg"],
            arrowcolor=profile["muted"],
            bordercolor=profile["border"],
        )
        tree = getattr(root, "sec_tree", None)
        if tree is not None:
            tree.tag_configure("normal", background=profile["panel2"], foreground=profile["text"])
            tree.tag_configure("normal_alt", background=profile["panel"], foreground=profile["text"])
    except Exception:
        pass

    # Keep shared colors available to the handful of legacy custom widgets that
    # intentionally use THEME[] instead of a CTk widget's own defaults.
    tech_common.THEME.update(profile)
    root._gelotech_applied_theme = name if name in PALETTES else DEFAULT_THEME

    # Re-run the existing button contrast guard after the selected palette is in place.
    try:
        root._fix_button_text_colors("dark" if dark else "light")
    except Exception:
        pass


def _find_theme_button(root):
    import customtkinter as ctk

    def walk(widget):
        for child in widget.winfo_children():
            yield child
            yield from walk(child)

    try:
        for widget in walk(root):
            if isinstance(widget, ctk.CTkButton):
                text = str(widget.cget("text")).strip()
                if text.casefold() in {p.casefold() for p in PALETTES}:
                    return widget
    except Exception:
        pass
    return None


def install_theme_dropdown(current_name):
    """Turn the sidebar palette button into a direct palette picker."""
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
            bg=profile["panel2"],
            fg=profile["text"],
            activebackground=profile["accent"],
            activeforeground=profile["text"],
            relief="flat",
            borderwidth=1,
        )

        def select(name):
            root._theme_mode = name
            try:
                data = root._load_settings()
                data["theme"] = name
                root._save_settings(data)
            except Exception:
                pass
            root._apply_theme(name)

        for palette in PALETTES:
            label = ("✓ " if palette == current_name else "") + palette.capitalize()
            menu.add_command(label=label, command=lambda p=palette: select(p))

        root._gelotech_theme_menu = menu

        def open_menu():
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            try:
                menu.tk_popup(x, y)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass

        button.configure(command=open_menu, text=current_name.capitalize())
    except Exception:
        pass


def apply_ctk_theme(name, dark=False):
    """Apply the selected bundled palette to new and existing UI widgets."""
    import customtkinter as ctk
    import tkinter as tk

    if name not in PALETTES:
        name = DEFAULT_THEME

    # CTk consumes the JSON for all widgets created after this call.
    ctk.set_appearance_mode("Dark" if dark else "Light")
    path = os.path.join(THEME_DIR, f"{name}.json")
    try:
        ctk.set_default_color_theme(path if os.path.isfile(path) else "blue")
    except Exception:
        try:
            ctk.set_default_color_theme("blue")
        except Exception:
            pass

    root = getattr(tk, "_default_root", None)
    if root is not None:
        recolor_existing_widgets(root, name, dark)
        install_theme_dropdown(name)
