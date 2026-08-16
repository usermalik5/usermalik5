"""Compact the Qt sidebar so all legacy-style controls fit without scrolling."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QLabel, QListWidget, QPushButton, QScrollArea


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
        layout.setSpacing(4)

    # Every action button gets the same compact height. This is the primary
    # reason the complete Power / Connection / Session areas fit in 820px.
    for button in sidebar.findChildren(QPushButton):
        button.setMinimumHeight(28)
        button.setMaximumHeight(32)
        button.setContentsMargins(4, 2, 4, 2)

    nav = getattr(self, "nav", None)
    if isinstance(nav, QListWidget):
        nav.setSpacing(0)
        nav.setMinimumHeight(88)
        nav.setMaximumHeight(96)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    guide = sidebar.findChild(type(sidebar), "sidebarGuide")
    if guide is not None:
        guide.setMaximumHeight(110)
        guide_layout = guide.layout()
        if guide_layout is not None:
            guide_layout.setContentsMargins(6, 4, 6, 4)
            guide_layout.setSpacing(1)
        for label in guide.findChildren(QLabel):
            label.setStyleSheet("font-size: 8px;")

    # Safety net: if the window is ever too short for every sidebar control,
    # scroll instead of silently cutting the buttons off.
    try:
        central = self.centralWidget()
        if central is not None and central.layout() is not None:
            for i in range(central.layout().count()):
                item = central.layout().itemAt(i)
                if item.widget() is sidebar:
                    central.layout().removeItem(item)
                    scroll = QScrollArea()
                    scroll.setWidgetResizable(True)
                    scroll.setFrameShape(QScrollArea.NoFrame)
                    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                    scroll.setWidget(sidebar)
                    central.layout().insertWidget(i, scroll)
                    break
    except Exception:
        pass


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
