"""Compact the Qt sidebar so all legacy-style controls fit without scrolling."""
from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QListWidget, QPushButton


def _compact_sidebar(self) -> None:
    sidebar = getattr(self, "sidebar", None)
    if sidebar is None:
        return

    # Match the dense vertical rhythm of the legacy tool.
    sidebar.setMinimumWidth(240)
    sidebar.setFixedWidth(264)
    layout = sidebar.layout()
    if layout is not None:
        layout.setContentsMargins(8, 5, 8, 6)
        layout.setSpacing(2)

    # Every action button gets the same compact height. This is the primary
    # reason the complete Power / Connection / Session areas fit in 820px.
    for button in sidebar.findChildren(QPushButton):
        button.setMinimumHeight(24)
        button.setMaximumHeight(27)
        button.setContentsMargins(4, 0, 4, 0)

    nav = getattr(self, "nav", None)
    if isinstance(nav, QListWidget):
        nav.setSpacing(0)
        nav.setMinimumHeight(96)
        nav.setMaximumHeight(104)
        nav.setVerticalScrollBarPolicy(QAbstractItemView.ScrollBarAlwaysOff)
        nav.setHorizontalScrollBarPolicy(QAbstractItemView.ScrollBarAlwaysOff)

    guide = sidebar.findChild(type(sidebar), "sidebarGuide")
    if guide is not None:
        guide.setMaximumHeight(122)
        guide_layout = guide.layout()
        if guide_layout is not None:
            guide_layout.setContentsMargins(6, 4, 6, 4)
            guide_layout.setSpacing(1)
        for label in guide.findChildren(type(self.brand)):
            label.setStyleSheet("font-size: 8px;")


def install_sidebar_compact(MainWindow) -> None:
    original_show = getattr(MainWindow, "show", None)

    # The visual-parity installer has already built the complete legacy shell
    # before this hook runs, so compacting can happen immediately after the
    # MainWindow constructor finishes.
    original_init = MainWindow.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _compact_sidebar(self)

    MainWindow.__init__ = init
    MainWindow._compact_sidebar = _compact_sidebar
