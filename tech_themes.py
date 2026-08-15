# -*- coding: utf-8 -*-
"""CTkThemesPack integration for GeloTech Tool.

The selected JSON is the source of truth for the palette. It updates both
CustomTkinter defaults (new widgets) and the already-created GeloTech widgets
(existing sidebar, cards, inputs, buttons and page surfaces).
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
    if name not in PALETTES:
        name = DEFAULT_THEME
    data = load_theme_json(name)
    root = data.get("CTk", {})
    frame = data.get("CTkFrame", {})
    button = data.get("CTkButton", {})
    label = data.get("CTkLabel", {})
    entry = data.get("CTkEntry", {})
    return {
        "bg": _value(root.get("fg_color"), dark, "gray14"),
        "panel": _value(frame.get("fg_color"), dark, "gray17"),
        "panel2": _value(frame.get("top_fg_color"), dark, "gray20"),
        "card": _value(frame.get("top_fg_color"), dark, "gray20"),
        "border": _value(frame.get("border_color"), dark, "gray28"),
        "input": _value(entry.get("fg_color"), dark, "gray17"),
        "accent": _value(button.get("fg_color"), dark, "#3b82f6"),
        "accent_h": _value(button.get("hover_color"), dark, "#2f6fe4"),
        "green": "#22c55e",
        "red": "#ef4444",
        "amber": "#f59e0b",
        "text": _value(label.get("text_color"), dark, "#DCE4EE"),
        "muted": _value(entry.get("placeholder_text_color"), dark, "#8b949e"),
        "sidebar": _value(root.get("fg_color"), dark, "gray14"),
    }


def accent_for(name):
    return palette_profile(name, dark=False)["accent"]


def hover_for(name):
    return palette_profile(name, dark=False)["accent_h"]


def _class_attribute_palette(old_data, new_data, dark=False):
    """Build per-widget-class color mappings from two CTk theme JSON files."""
    result = {}
    for cls, old_cfg in old_data.items():
        new_cfg = new_data.get(cls, {})
        if not isinstance(old_cfg, dict) or not isinstance(new_cfg, dict):
            continue
        for attr, old_value in old_cfg.items():
            if attr not in new_cfg:
                continue
            old_color = _value(old_value, dark)
            new_color = _value(new_cfg[attr], dark)
            if isinstance(old_color, str) and isinstance(new_color, str):
                result.setdefault(cls, {})[attr] = (old_color, new_color)
    return result


def _palette_color_map(root, name, dark=False):
    """Return mappings for the existing UI, including hard-coded legacy colors."""
    import tech_common

    new_profile = palette_profile(name, dark)
    previous = getattr(root, "_gelotech_applied_theme", None) or DEFAULT_THEME
    old_profile = palette_profile(previous, dark)
    mapping = {}

    for key, old_color in old_profile.items():
        new_color = new_profile.get(key)
        if isinstance(old_color, str) and isinstance(new_color, str):
            mapping[old_color] = new_color

    light_base = tech_common.THEMES.get("light", {})
    dark_base = tech_common.THEMES.get("dark", {})
    for key in new_profile:
        for base in (light_base, dark_base):
            old_color = base.get(key)
            new_color = new_profile.get(key)
            if isinstance(old_color, str) and isinstance(new_color, str):
                mapping[old_color] = new_color

    reverse_light = {v: k for k, v in light_base.items() if isinstance(v, str)}
    reverse_dark = {v: k for k, v in dark_base.items() if isinstance(v, str)}
    for dark_old, light_old in tech_common.COLOR_SWAP.items():
        for old in (dark_old, light_old):
            slot = reverse_light.get(old) or reverse_dark.get(old)
            if slot and slot in new_profile:
                mapping[old] = new_profile[slot]

    mapping.update({
        "#3b82f6": new_profile["accent"],
        "#2f6fe4": new_profile["accent_h"],
        "#2563c2": new_profile["accent"],
        "#1f6feb": new_profile["accent"],
        "#0d1117": new_profile["input"],
        "#16191e": new_profile["panel"],
        "#11151c": new_profile["panel2"],
        "#131921": new_profile["panel2"],
        "#1b222c": new_profile["card"],
        "#21262d": new_profile["border"],
        "#27313d": new_profile["card"],
        "#30363d": new_profile["border"],
        "#2c3340": new_profile["border"],
        "#e6edf3": new_profile["text"],
        "#e8ecf2": new_profile["text"],
        "#8b949e": new_profile["muted"],
        "#8b98a9": new_profile["muted"],
        "#aab7c4": new_profile["muted"],
        "#aeb8c2": new_profile["muted"],
    })
    return mapping, _class_attribute_palette(
        load_theme_json(previous), load_theme_json(name), dark
    )


def _is_preserved_widget(widget):
    """Keep the phone screen / green log console in its existing style."""
    try:
        cls = type(widget).__name__
        if cls == "CTkTextbox" and str(widget.cget("fg_color")) in {"#000200", "#1D1E1E"}:
            return True
        if cls == "CTkFrame" and str(widget.cget("fg_color")) in {"#01030a", "#03160d"}:
            return True
    except Exception:
        pass
    return False


def recolor_existing_widgets(root, name, dark=False):
    from tkinter import ttk
    import tech_common

    mapping, class_maps = _palette_color_map(root, name, dark)
    stack = list(root.winfo_children())
    attrs = (
        "fg_color", "text_color", "border_color", "hover_color", "progress_color",
        "button_color", "button_hover_color", "dropdown_fg_color",
        "dropdown_hover_color", "dropdown_text_color", "trough_color", "arrow_color",
        "scrollbar_button_color", "scrollbar_button_hover_color",
    )
    while stack:
        widget = stack.pop()
        try:
            stack.extend(widget.winfo_children())
        except Exception:
            pass
        if _is_preserved_widget(widget):
            continue

        cls = type(widget).__name__
        for attr in attrs:
            try:
                current = widget.cget(attr)
            except Exception:
                continue
            if not isinstance(current, str):
                continue
            target = mapping.get(current)
            per_class = class_maps.get(cls, {})
            if not target and attr in per_class and current == per_class[attr][0]:
                target = per_class[attr][1]
            if target and target != current:
                try:
                    widget.configure(**{attr: target})
                except Exception:
                    pass

    profile = palette_profile(name, dark)
    try:
        style = ttk.Style()
        style.configure("AppList.Treeview", background=profile["panel2"], fieldbackground=profile["panel2"], foreground=profile["text"])
        style.configure("AppList.Vertical.Tscrollbar", background=profile["panel"], troughcolor=profile["bg"], arrowcolor=profile["muted"], bordercolor=profile["border"])
        tree = getattr(root, "sec_tree", None)
        if tree is not None:
            tree.tag_configure("normal", background=profile["panel2"], foreground=profile["text"])
            tree.tag_configure("normal_alt", background=profile["panel"], foreground=profile["text"])
    except Exception:
        pass

    try:
        root._fix_button_text_colors("dark" if dark else "light")
    except Exception:
        pass

    tech_common.THEME.update(profile)
    for key, old in tech_common.THEMES.get("light", {}).items():
        if key in profile and isinstance(old, str) and isinstance(profile[key], str):
            tech_common.COLOR_SWAP[old] = profile[key]
    for key, old in tech_common.THEMES.get("dark", {}).items():
        if key in profile and isinstance(old, str) and isinstance(profile[key], str):
            tech_common.COLOR_SWAP[old] = profile[key]

    root._gelotech_applied_theme = name


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
            menu.destroy()
        menu = tk.Menu(root, tearoff=False, bg=profile["panel"], fg=profile["text"], activebackground=profile["accent"], activeforeground=profile["text"], relief="flat", borderwidth=1)

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
    """Apply selected palette to new widgets and recolor the current UI."""
    import customtkinter as ctk

    if name not in PALETTES:
        name = DEFAULT_THEME
    ctk.set_appearance_mode("Dark" if dark else "Light")
    path = os.path.join(THEME_DIR, f"{name}.json")
    try:
        ctk.set_default_color_theme(path if os.path.isfile(path) else "blue")
    except Exception:
        try:
            ctk.set_default_color_theme("blue")
        except Exception:
            pass

    root = getattr(__import__("tkinter"), "_default_root", None)
    if root is not None:
        recolor_existing_widgets(root, name, dark)
        install_theme_dropdown(name)
