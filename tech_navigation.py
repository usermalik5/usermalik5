# -*- coding: utf-8 -*-
"""Centralized page navigation for GeloTech Tool."""

import customtkinter as ctk

DEFAULT_THEME = {
    "accent": "#1a8cff",
    "panel2": "#16191e",
    "accent_h": "#155bb5",
}


class NavigationController:
    DEFAULT_PAGE = "Dashboard"

    def __init__(self, app):
        self.app = app

    def _allowed(self, name):
        if name == self.DEFAULT_PAGE:
            return True
        perm = getattr(self.app, "TAB_PERMS", {}).get(name)
        if perm is None:
            return True
        can = getattr(self.app, "_can", None)
        return True if can is None else bool(can(perm))

    def _refresh_page_theme(self):
        """Apply shared contrast to widgets created by a lazy page factory."""
        try:
            fix = getattr(self.app, "_fix_button_text_colors", None)
            if callable(fix):
                fix(getattr(self.app, "_theme_mode", "light"))
        except Exception:
            pass

    def _patch_cleaner_table_scrolling(self):
        """Keep the existing Treeview and add horizontal scrolling for long descriptions."""
        app = self.app
        tree = getattr(app, "sec_tree", None)
        list_frame = getattr(app, "sec_list_frame", None)
        if tree is None or list_frame is None:
            return
        try:
            if getattr(app, "sec_hsb", None) is None:
                from tkinter import ttk
                list_frame.grid_columnconfigure(0, weight=1)
                list_frame.grid_rowconfigure(0, weight=1)
                list_frame.grid_rowconfigure(1, weight=0)
                style = ttk.Style()
                style.configure(
                    "AppList.Horizontal.TScrollbar",
                    background="#21262d",
                    troughcolor="#0d1117",
                    arrowcolor="#8b949e",
                    bordercolor="#0d1117",
                )
                app.sec_hsb = ttk.Scrollbar(
                    list_frame,
                    orient="horizontal",
                    command=tree.xview,
                    style="AppList.Horizontal.TScrollbar",
                )
                app.sec_hsb.grid(row=1, column=0, sticky="ew")
                tree.configure(xscrollcommand=app.sec_hsb.set)
            app.sec_hsb.grid()

            original_relayout = getattr(app, "_gelotech_original_sec_relayout", None)
            if original_relayout is None and hasattr(app, "_sec_relayout_columns"):
                original_relayout = app._sec_relayout_columns
                app._gelotech_original_sec_relayout = original_relayout

                def relayout_with_description_scroll():
                    try:
                        original_relayout()
                    except Exception:
                        pass
                    try:
                        tree.column("#0", width=42, minwidth=42, stretch=False, anchor="center")
                        tree.column("chk", width=32, minwidth=32, stretch=False, anchor="center")
                        tree.column("name", width=210, minwidth=150, stretch=False, anchor="w")
                        tree.column("package", width=260, minwidth=180, stretch=False, anchor="w")
                        tree.column("badges", width=160, minwidth=110, stretch=False, anchor="w")
                        tree.column("desc", width=820, minwidth=500, stretch=False, anchor="w")
                    except Exception:
                        pass

                app._sec_relayout_columns = relayout_with_description_scroll

            try:
                app._sec_relayout_columns()
            except Exception:
                pass
        except Exception:
            pass

    def _refresh_cleaner_readability(self):
        """Normalize App Cleaner table/instructions after page construction."""
        try:
            tree = getattr(self.app, "sec_tree", None)
            if tree is not None:
                try:
                    tree.configure(show="tree headings")
                except Exception:
                    pass
                for col, heading in (
                    ("name", "APP NAME"),
                    ("package", "PACKAGE ID"),
                    ("badges", "UAD LEVEL"),
                    ("desc", "DESCRIPTION"),
                ):
                    try:
                        tree.heading(col, text=heading, anchor="w")
                    except Exception:
                        pass
                self._patch_cleaner_table_scrolling()

            usb = getattr(self.app, "_sec_banner_usb", None)
            howto = getattr(self.app, "_sec_banner_howto", None)
            header = getattr(self.app, "_sec_banner_header", None)
            wraplength = max(220, (header.winfo_width() - 28) if header is not None else 900)
            if usb is not None:
                usb.configure(
                    text=(
                        "📱 USB debugging:\n"
                        "Enable Developer Options → USB debugging, connect the phone, then tap Allow.\n"
                        "GeloTech automatically prepares app icons for new devices."
                    ),
                    justify="left",
                    anchor="w",
                    wraplength=wraplength,
                )
            if howto is not None:
                howto.configure(
                    text=(
                        "💡 How to use:\n"
                        "Refresh loads user apps. Load Apps chooses All / User / System / Disabled.\n"
                        "Advanced Filter uses the database. Scan Bloatware filters by UAD level.\n"
                        "Right-click a row for app actions."
                    ),
                    justify="left",
                    anchor="w",
                    wraplength=wraplength,
                )
        except Exception:
            pass

    def show(self, name):
        """Show a page, creating it lazily when a factory is registered."""
        if not self._allowed(name):
            return False

        pages = getattr(self.app, "pages", {})
        created = False
        if name not in pages:
            factory = getattr(self.app, "_page_factories", {}).get(name)
            if factory is not None:
                factory()
                created = True
        if name not in pages:
            return False

        for page_name, frame in pages.items():
            if page_name == name:
                frame.grid()
            else:
                frame.grid_remove()

        self.app._current_page = name
        theme = getattr(self.app, "_navigation_theme", DEFAULT_THEME)
        for page_name, button in getattr(self.app, "page_nav_btns", {}).items():
            active = page_name == name
            try:
                button.configure(
                    fg_color=theme["accent"] if active else theme["panel2"],
                    text_color="#ffffff" if active else "#e8ecf2",
                    hover_color=theme["accent_h"] if active else "#1f6feb",
                )
            except Exception:
                pass

        if created:
            self._refresh_page_theme()
            if name in ("Dashboard", "Adware Remover"):
                self._refresh_cleaner_readability()

        if name == self.DEFAULT_PAGE:
            try:
                self.app.after(60, self.app._dash_refresh_if_visible)
            except Exception:
                pass
        return True

    def show_after_login(self):
        """Select the single authoritative landing page after authentication."""
        return self.show(self.DEFAULT_PAGE)
