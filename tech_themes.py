# -*- coding: utf-8 -*-
"""CTkThemesPack integration for GeloTech Tool.

Each bundled JSON remains the source of truth. The palette is applied by
widget type, with a small compatibility layer for GeloTech's ttk package list
and custom log consoles.
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

# Windows-friendly UI fonts. The chosen family applies to every GeloTech text
# surface (labels, buttons, entries, lists, log text, dropdowns); only the
# physical phone display keeps its fixed layout.
UI_FONTS = [
    "Segoe UI", "Arial", "Arial Black", "Calibri", "Cambria", "Candara",
    "Comic Sans MS", "Consolas", "Constantia", "Corbel", "Courier New",
    "Franklin Gothic Medium", "Garamond", "Georgia", "Impact",
    "Lucida Console", "Microsoft Sans Serif", "Palatino Linotype",
    "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana",
]
DEFAULT_UI_FONT = "Segoe UI"


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
    """Return shared GeloTech colors used by ttk and custom log surfaces."""
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
    """Only preserve the physical phone/mirror display; GeloTech logs are themed."""
    try:
        role = getattr(widget, "_gelotech_theme_role", "")
        if role == "phone_display":
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

    if not config or _is_preserved_widget(widget):
        return

    _configure_widget(widget, config)


def _apply_log_palette(root, name, dark=False):
    """Theme GeloTech's log consoles without changing the physical phone display."""
    profile = palette_profile(name, dark)
    log_bg = profile["panel2"]
    log_border = profile["border"]
    log_text = profile["text"]
    consoles = getattr(root, "_log_consoles", None) or []

    tag_colors = {
        "ADB": profile["accent"],
        "SECURITY": profile["accent_h"],
        "VT": profile["green"],
        "DNS": profile["accent"],
        "EXEC": profile["amber"],
        "SYSTEM": profile["green"],
        "ERROR": profile["red"],
        "INFO": profile["green"],
        "HINT": profile["muted"],
        "DEFAULT": log_text,
    }

    for entry in consoles:
        frame = entry.get("frame")
        text = entry.get("text")
        if frame is not None:
            _configure_widget(frame, {
                "fg_color": log_bg,
                "border_color": log_border,
            })
        if text is not None:
            _configure_widget(text, {
                "fg_color": log_bg,
                "text_color": log_text,
                "border_color": log_border,
            })
            for tag, color in tag_colors.items():
                try:
                    text.tag_config(tag, foreground=color)
                except Exception:
                    pass

        # The compact console has a LIVE LOGS header and clear button inside it.
        if frame is not None:
            try:
                stack = list(frame.winfo_children())
                while stack:
                    child = stack.pop()
                    stack.extend(child.winfo_children())
                    if type(child).__name__ == "CTkFrame":
                        _configure_widget(child, {
                            "fg_color": profile["card"],
                            "border_color": log_border,
                        })
            except Exception:
                pass


def _apply_app_list_palette(root, name, dark=False):
    """Bring the ttk package list onto the selected theme instead of old dark colors."""
    import tkinter.ttk as ttk

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
    except Exception:
        return

    tree = getattr(root, "sec_tree", None)
    if tree is None:
        return

    # Preserve the meaning of threat/exclusion colors, but remove the old
    # hard-coded dark-green/purple row backgrounds.
    tags = {
        "normal": (profile["panel2"], profile["text"]),
        "normal_alt": (profile["panel"], profile["text"]),
        "threat": (profile["panel2"], profile["red"]),
        "both_excl": (profile["panel2"], profile["accent"]),
        "uninstall_excl": (profile["panel2"], profile["red"]),
        "clean_excl": (profile["panel2"], profile["amber"]),
    }
    for tag, (bg, fg) in tags.items():
        try:
            tree.tag_configure(tag, background=bg, foreground=fg)
        except Exception:
            pass


def _font_weight_for(widget):
    cls = type(widget).__name__
    if cls in {"CTkButton", "CTkCheckBox", "CTkSwitch", "CTkRadioButton",
               "CTkOptionMenu", "CTkComboBox", "CTkSegmentedButton"}:
        return "bold"
    if cls == "CTkLabel":
        try:
            text = str(widget.cget("text"))
            current = widget.cget("font")
            weight = current.cget("weight") if hasattr(current, "cget") else "normal"
            if weight == "bold" or text.isupper() or len(text) < 24:
                return "bold"
        except Exception:
            pass
    return "normal"


def _font_spec(widget, family):
    try:
        current = widget.cget("font")
        if hasattr(current, "cget"):
            size = current.cget("size")
            underline = current.cget("underline")
            overstrike = current.cget("overstrike")
        else:
            size, underline, overstrike = 10, False, False
    except Exception:
        size, underline, overstrike = 10, False, False
    return {"family": family, "size": size, "weight": _font_weight_for(widget),
            "underline": underline, "overstrike": overstrike}


def _apply_ui_font(root, family):
    """Apply the chosen UI font to every GeloTech text surface.

    Covers all CTk text widgets, the ttk package list, and ttk scrollbar
    styling. The physical phone display is preserved via
    ``_is_preserved_widget``; the log consoles follow the chosen font too so
    the whole app reads consistently."""
    if family not in UI_FONTS:
        family = DEFAULT_UI_FONT
    try:
        supported = {"CTkButton", "CTkLabel", "CTkEntry", "CTkCheckBox", "CTkSwitch",
                     "CTkRadioButton", "CTkOptionMenu", "CTkComboBox",
                     "CTkSegmentedButton", "CTkTextbox", "CTkScrollableFrame"}
        stack = list(root.winfo_children())
        while stack:
            widget = stack.pop()
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                pass
            if type(widget).__name__ not in supported or _is_preserved_widget(widget):
                continue
            try:
                widget.configure(font=_font_spec(widget, family))
            except Exception:
                pass
        from tkinter import ttk
        style = ttk.Style()
        for style_name in ("AppList.Treeview", "Treeview"):
            try:
                style.configure(style_name, font=(family, 10))
            except Exception:
                pass
        try:
            style.configure("AppList.Treeview.Heading", font=(family, 10, "bold"))
        except Exception:
            pass
        root._gelotech_ui_font = family
    except Exception:
        pass


def recolor_existing_widgets(root, name, dark=False):
    """Apply the selected JSON directly by widget class and themed GeloTech surfaces."""
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

    _apply_log_palette(root, name, dark)
    _apply_app_list_palette(root, name, dark)

    profile = palette_profile(name, dark)
    tech_common.THEME.update(profile)
    root._gelotech_applied_theme = name if name in PALETTES else DEFAULT_THEME

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

        def save_setting(key, value):
            try:
                data = root._load_settings()
                data[key] = value
                root._save_settings(data)
            except Exception:
                pass

        def select(name):
            root._theme_mode = name
            save_setting("theme", name)
            root._apply_theme(name)

        def select_font(family):
            root._ui_font = family
            save_setting("font", family)
            _apply_ui_font(root, family)

        for palette in PALETTES:
            label = ("✓ " if palette == current_name else "") + palette.capitalize()
            menu.add_command(label=label, command=lambda p=palette: select(p))

        menu.add_separator()
        menu.add_command(label="UI Font", state="disabled")
        current_font = getattr(root, "_ui_font", DEFAULT_UI_FONT)
        for family in UI_FONTS:
            label = ("✓ " if family == current_font else "") + family
            menu.add_command(label=label, command=lambda f=family: select_font(f))

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


def _schedule_theme_refresh(root, name, dark=False):
    """Reapply custom/ttk surfaces after GeloTech's legacy theme pass finishes."""
    def refresh():
        try:
            _apply_log_palette(root, name, dark)
            _apply_app_list_palette(root, name, dark)
            _apply_ui_font(root, getattr(root, "_ui_font", DEFAULT_UI_FONT))
        except Exception:
            pass

    try:
        for delay in (0, 75, 200, 450, 900, 1600):
            root.after(delay, refresh)
    except Exception:
        refresh()


def apply_ctk_theme(name, dark=False):
    """Apply the selected bundled palette to new and existing UI widgets."""
    import customtkinter as ctk
    import tkinter as tk

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

    root = getattr(tk, "_default_root", None)
    if root is not None:
        if not hasattr(root, "_ui_font"):
            try:
                root._ui_font = root._load_settings().get("font", DEFAULT_UI_FONT)
            except Exception:
                root._ui_font = DEFAULT_UI_FONT
        recolor_existing_widgets(root, name, dark)
        install_theme_dropdown(name)
        _apply_ui_font(root, getattr(root, "_ui_font", DEFAULT_UI_FONT))
        _schedule_theme_refresh(root, name, dark)
