# -*- coding: utf-8 -*-
"""Centralized page navigation for GeloTech Tool."""

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
                fix(getattr(self.app, "_theme_mode", "dark"))
        except Exception:
            pass

    def _refresh_cleaner_readability(self):
        """Normalize App Cleaner table/instructions after lazy creation.

        The Cleaner page is built after authentication, so the initial theme
        pass cannot style these widgets. Keep the presentation here lightweight
        and idempotent: headings make the four data fields unambiguous, the
        instruction banners stay short enough to wrap cleanly, and columns use
        the real Treeview width rather than forcing the window wider.
        """
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
                try:
                    self.app._sec_relayout_columns()
                except Exception:
                    pass

            usb = getattr(self.app, "_sec_banner_usb", None)
            howto = getattr(self.app, "_sec_banner_howto", None)
            header = getattr(self.app, "_sec_banner_header", None)
            if usb is not None:
                usb.configure(
                    text=(
                        "📱 USB debugging: Enable Developer Options → USB debugging, "
                        "connect the phone, then tap Allow. GeloTech automatically "
                        "prepares app icons for new devices."
                    ),
                    wraplength=max(220, (header.winfo_width() - 28) if header is not None else 900),
                )
            if howto is not None:
                howto.configure(
                    text=(
                        "💡 How to use: Refresh loads user apps. Load Apps chooses "
                        "All / User / System / Disabled. Advanced Filter uses the "
                        "database. Scan Bloatware filters by UAD level. Right-click "
                        "a row for app actions."
                    ),
                    wraplength=max(220, (header.winfo_width() - 28) if header is not None else 900),
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
            if name == "Adware Remover":
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
