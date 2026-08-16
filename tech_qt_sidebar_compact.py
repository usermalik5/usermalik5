"""Compact the Qt sidebar so all legacy-style controls fit without scrolling."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QPushButton


def _compact_sidebar(self) -> None:
    sidebar = getattr(self, "sidebar", None)
    if sidebar is None:
        return

    sidebar.setMinimumWidth(240)
    sidebar.setFixedWidth(264)

    layout = sidebar.layout()
    if layout is not None:
        # Dense, fixed vertical rhythm: never give the navigation list all
        # remaining height and never wrap the sidebar in a scroll area.
        layout.setContentsMargins(8, 4, 8, 5)
        layout.setSpacing(2)

    # Compact action buttons, matching the legacy tool's dense sidebar.
    for button in sidebar.findChildren(QPushButton):
        button.setMinimumHeight(28)
        button.setMaximumHeight(30)
        button.setContentsMargins(4, 1, 4, 1)

    # Branding is deliberately a quiet top-left header rather than a large
    # centered feature block.
    copyright_label = sidebar.findChild(QLabel, "copyrightLabel")
    if copyright_label is not None:
        copyright_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        copyright_label.setStyleSheet("font-size: 9px; color: #6f7782; padding: 0; margin: 0;")
        copyright_label.setMaximumHeight(14)

    brand = sidebar.findChild(QLabel, "brand")
    if brand is not None:
        brand.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        brand.setStyleSheet("font-size: 29px; font-weight: 700; color: #2388ff; padding: 0; margin: 0;")
        brand.setMaximumHeight(38)

    version = sidebar.findChild(QLabel, "versionLabel")
    if version is not None:
        version.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        version.setStyleSheet("font-size: 10px; font-weight: 600; color: #aeb6c1; padding: 0; margin: 0;")
        version.setMaximumHeight(24)

    # The navigation list has exactly four fixed rows and never expands into
    # the large empty region seen in the previous Qt layout.
    nav = getattr(self, "nav", None)
    if isinstance(nav, QListWidget):
        nav.setSpacing(1)
        nav.setFixedHeight(4 * 29 + 5)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setUniformItemSizes(True)

    # Compact section headers.
    for section in sidebar.findChildren(QLabel, "sidebarSection"):
        section.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        section.setStyleSheet("font-size: 9px; font-weight: 700; color: #6d9ed1; padding: 0; margin: 0;")
        section.setMaximumHeight(14)

    # USB / How-to help stays at the bottom but remains readable.
    guide = sidebar.findChild(type(sidebar), "sidebarGuide")
    if guide is not None:
        guide.setMinimumHeight(116)
        guide.setMaximumHeight(122)
        guide_layout = guide.layout()
        if guide_layout is not None:
            guide_layout.setContentsMargins(6, 4, 6, 4)
            guide_layout.setSpacing(1)
        for label in guide.findChildren(QLabel):
            label.setWordWrap(True)
            label.setStyleSheet("font-size: 8px; padding: 0; margin: 0;")

    # Never introduce a QScrollArea around the sidebar. The controls are sized
    # explicitly so the complete legacy-style sidebar remains visible.


def install_sidebar_compact(MainWindow) -> None:
    original_init = MainWindow.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _compact_sidebar(self)

    MainWindow.__init__ = init
    MainWindow._compact_sidebar = _compact_sidebar
