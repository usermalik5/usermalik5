"""Compact the Qt sidebar so all legacy-style controls fit without scrolling."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QPushButton


def _set_group_gap(layout, index: int, pixels: int) -> None:
    # Insert an explicit gap before the next logical group without changing
    # the order or behavior of the existing controls.
    if index < layout.count():
        layout.insertSpacing(index, pixels)


def _compact_sidebar(self) -> None:
    sidebar = getattr(self, "sidebar", None)
    if sidebar is None:
        return

    sidebar.setMinimumWidth(240)
    sidebar.setFixedWidth(264)

    layout = sidebar.layout()
    if layout is not None:
        layout.setContentsMargins(8, 5, 8, 6)
        layout.setSpacing(2)

    for button in sidebar.findChildren(QPushButton):
        button.setMinimumHeight(28)
        button.setMaximumHeight(30)
        button.setContentsMargins(4, 1, 4, 1)

    # Exact legacy-style branding order:
    # GELOTECH TOOL
    # v1.7.8 - Angelo Estrada Espinosa
    # © 2026 GeloTech
    # Gsmcodeph.com
    # facebook.com/gelotechxyz
    header = sidebar.findChild(QLabel, "sidebarBrandHeader")
    if header is None:
        # The current shell creates one combined header QLabel without an
        # object name. Find the first label that contains the branding text.
        for label in sidebar.findChildren(QLabel):
            if "GELOTECH" in label.text() and "Gsmcodeph.com" in label.text():
                header = label
                header.setObjectName("sidebarBrandHeader")
                break

    if header is not None:
        version = getattr(self, "_qt_sidebar_version", "1.7.8")
        header.setText(
            f'<span style="color:#2388ff; font-size:20pt; font-weight:800;">GELOTECH</span>'
            f'<span style="color:#8f98a3; font-size:9pt; font-weight:700;"> TOOL</span><br>'
            f'<span style="color:#b0b7c0; font-size:8pt; font-weight:600;">v{version} - Angelo Estrada Espinosa</span><br>'
            f'<span style="color:#6f7782; font-size:8pt;">© 2026 GeloTech</span><br>'
            f'<a href="https://gsmcodeph.com" style="color:#58a6ff; font-size:8pt;">Gsmcodeph.com</a><br>'
            f'<a href="https://facebook.com/gelotechxyz" style="color:#58a6ff; font-size:8pt;">facebook.com/gelotechxyz</a>'
        )
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setOpenExternalLinks(True)
        header.setTextInteractionFlags(Qt.TextBrowserInteraction)
        header.setMaximumHeight(104)
        header.setContentsMargins(0, 0, 0, 0)

    copyright_label = sidebar.findChild(QLabel, "copyrightLabel")
    if copyright_label is not None:
        copyright_label.hide()
    brand = sidebar.findChild(QLabel, "brand")
    if brand is not None:
        brand.hide()
    version_label = sidebar.findChild(QLabel, "versionLabel")
    if version_label is not None:
        version_label.hide()

    # Quiet, explicit theme control matching the requested wording.
    theme_btn = getattr(self, "theme_btn", None)
    if theme_btn is not None:
        is_dark = bool(getattr(self, "dark_mode", False))
        theme_btn.setText(f"Theme - {'Dark' if is_dark else 'Light'}")
        theme_btn.setMinimumHeight(30)
        theme_btn.setMaximumHeight(30)

    nav = getattr(self, "nav", None)
    if isinstance(nav, QListWidget):
        # The final shell already uses direct buttons rather than nav here.
        nav.setSpacing(1)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    for section in sidebar.findChildren(QLabel, "sidebarSection"):
        # Section captions are intentionally hidden; the blank gaps provide
        # the same grouping as the legacy sidebar without visual clutter.
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

    # Add small intentional gaps between the four logical action groups.
    if layout is not None:
        # Header, theme, 4 page buttons, 2 power, 2 connection, accounts,
        # logout, guide. The separators are deliberately subtle.
        # Avoid duplicate insertion if the function is called more than once.
        if not sidebar.property("qt_sidebar_gaps_installed"):
            # Find widgets by their visible text so this stays robust if a
            # button is renamed elsewhere in the shell.
            widgets = sidebar.findChildren(QPushButton)
            text_to_widget = {w.text().strip(): w for w in widgets}
            anchors = [
                text_to_widget.get("DASHBOARD"),
                text_to_widget.get("REBOOT TO RECOVERY"),
                text_to_widget.get("RE-AUTHORIZE ADB"),
                text_to_widget.get("ACCOUNTS"),
            ]
            for widget in anchors:
                if widget is None:
                    continue
                idx = layout.indexOf(widget)
                if idx >= 0:
                    layout.insertSpacing(idx, 7)
            sidebar.setProperty("qt_sidebar_gaps_installed", True)

    # Never introduce a QScrollArea around the sidebar. Everything is sized
    # explicitly so the complete legacy-style sidebar remains visible.


def install_sidebar_compact(MainWindow) -> None:
    original_init = MainWindow.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._qt_sidebar_version = "1.7.8"
        _compact_sidebar(self)

    MainWindow.__init__ = init
    MainWindow._compact_sidebar = _compact_sidebar
