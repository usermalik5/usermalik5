"""Compact Qt sidebar matching the dense legacy/reference layout."""
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
        layout.setContentsMargins(8, 5, 8, 6)
        # Reference-style dense stack: buttons touch each other.
        layout.setSpacing(0)

    for button in sidebar.findChildren(QPushButton):
        button.setMinimumHeight(29)
        button.setMaximumHeight(29)
        button.setContentsMargins(4, 0, 4, 0)
        button.setStyleSheet(
            ""
            "QPushButton { margin: 0; padding: 4px 9px; border-radius: 2px; }"
            "QPushButton + QPushButton { margin-top: 0px; }"
            """
        )

    header = sidebar.findChild(QLabel, "sidebarBrandHeader")
    if header is None:
        for label in sidebar.findChildren(QLabel):
            if "GELOTECH" in label.text() and "Gsmcodeph.com" in label.text():
                header = label
                header.setObjectName("sidebarBrandHeader")
                break

    if header is not None:
        version = getattr(self, "_qt_sidebar_version", "1.7.8")
        header.setText(
            f'<span style="color:#2388ff; font-size:20pt; font-weight:800;">GELOTECH</span>'
            f'<span style="color:#d6d6d6; font-size:9pt; font-weight:700;"> TOOL</span><br>'
            f'<span style="color:#d0d0d0; font-size:8pt; font-weight:600;">v{version} - Angelo Estrada Espinosa</span><br>'
            f'<span style="color:#9a9a9a; font-size:8pt;">© 2026 GeloTech</span><br>'
            f'<a href="https://gsmcodeph.com" style="color:#7fb7ff; font-size:8pt;">Gsmcodeph.com</a><br>'
            f'<a href="https://facebook.com/gelotechxyz" style="color:#7fb7ff; font-size:8pt;">facebook.com/gelotechxyz</a>'
        )
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setOpenExternalLinks(True)
        header.setTextInteractionFlags(Qt.TextBrowserInteraction)
        header.setMaximumHeight(104)
        header.setContentsMargins(0, 0, 0, 0)

    for name in ("copyrightLabel", "brand", "versionLabel"):
        label = sidebar.findChild(QLabel, name)
        if label is not None:
            label.hide()

    theme_btn = getattr(self, "theme_btn", None)
    if theme_btn is not None:
        is_dark = bool(getattr(self, "dark_mode", True))
        theme_btn.setText("Theme - Dark" if is_dark else "Theme - Light")
        theme_btn.setMinimumHeight(29)
        theme_btn.setMaximumHeight(29)

    nav = getattr(self, "nav", None)
    if isinstance(nav, QListWidget):
        nav.setSpacing(0)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    for section in sidebar.findChildren(QLabel, "sidebarSection"):
        section.hide()

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

    # Deliberately no spacer widgets between logical groups. The dense button
    # placement is part of the requested reference style.
    if layout is not None:
        while layout.count() and layout.itemAt(0).spacerItem() is not None:
            layout.takeAt(0)
        sidebar.setProperty("qt_sidebar_gaps_installed", False)


def install_sidebar_compact(MainWindow) -> None:
    original_init = MainWindow.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._qt_sidebar_version = "1.7.8"
        _compact_sidebar(self)

    MainWindow.__init__ = init
    MainWindow._compact_sidebar = _compact_sidebar
