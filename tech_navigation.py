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

    def show(self, name):
        """Show a page, creating it lazily when a factory is registered."""
        if not self._allowed(name):
            return False

        pages = getattr(self.app, "pages", {})
        if name not in pages:
            factory = getattr(self.app, "_page_factories", {}).get(name)
            if factory is not None:
                factory()
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

        if name == self.DEFAULT_PAGE:
            try:
                self.app.after(60, self.app._dash_refresh_if_visible)
            except Exception:
                pass
        return True

    def show_after_login(self):
        """Select the single authoritative landing page after authentication."""
        return self.show(self.DEFAULT_PAGE)
