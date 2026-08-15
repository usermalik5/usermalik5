"""Qt phone-frame layout adapter for the legacy GeloTech proportions."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from tech_qt_icons import load_icon

# Native dimensions measured from the legacy iPhone frame asset.
PHONE_NATIVE = (396, 824)
DISPLAY_RECT = (14, 12, 368, 800)
PHONE_DISPLAY_SIZE = (353, 735)


def _bundle_path(*parts: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))))
    return root.joinpath(*parts)


def _frame_pixmap() -> QPixmap:
    pixmap = QPixmap(str(_bundle_path("assets", "phone_devices", "iPhone17_P_PM_CosmicOrange@2x.png")))
    if pixmap.isNull():
        return pixmap
    pixmap.setDevicePixelRatio(1.0)
    return pixmap.scaled(
        PHONE_DISPLAY_SIZE[0],
        PHONE_DISPLAY_SIZE[1],
        Qt.IgnoreAspectRatio,
        Qt.SmoothTransformation,
    )


def install_phone_frame(MainWindow: type) -> None:
    """Replace only the Dashboard phone panel with a frame-aware host.

    Existing Dashboard/content functionality remains untouched. The mirror
    module inserts its native scrcpy window into ``phone_host`` using the
    legacy measured screen opening.
    """
    if getattr(MainWindow, "_gelotech_phone_frame_installed", False):
        return

    original_build_shell = MainWindow._build_shell

    def build_shell(self) -> None:
        original_build_shell(self)
        if not getattr(self, "pages", None):
            return
        page = self.pages[0]
        page_layout = page.layout()
        if page_layout is None or page_layout.count() < 1:
            return
        old_phone_panel = page_layout.itemAt(0).widget()
        if old_phone_panel is None:
            return

        phone_panel = QFrame()
        phone_panel.setObjectName("phonePanel")
        phone_panel.setFixedWidth(405)
        phone_layout = QVBoxLayout(phone_panel)
        phone_layout.setContentsMargins(10, 4, 10, 0)
        phone_layout.setSpacing(8)

        self.phone_host = QFrame(phone_panel)
        self.phone_host.setObjectName("phoneHost")
        self.phone_host.setFixedSize(*PHONE_DISPLAY_SIZE)
        self.phone_host.setAttribute(Qt.WA_NativeWindow, True)

        frame = QLabel(self.phone_host)
        frame.setObjectName("phoneFrame")
        frame.setGeometry(0, 0, *PHONE_DISPLAY_SIZE)
        frame.setPixmap(_frame_pixmap())
        frame.setScaledContents(True)
        frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.phone_frame = frame

        phone_layout.addWidget(self.phone_host, 1, Qt.AlignCenter)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        refresh = QPushButton("Refresh")
        refresh.setIcon(load_icon("refresh"))
        refresh.clicked.connect(self.refresh_apps)
        mirror = QPushButton("Screen Mirror")
        mirror.setIcon(load_icon("device-mobile"))
        mirror.clicked.connect(self.start_mirror)
        buttons.addWidget(refresh)
        buttons.addWidget(mirror)
        phone_layout.addLayout(buttons)

        page_layout.removeWidget(old_phone_panel)
        old_phone_panel.deleteLater()
        page_layout.insertWidget(0, phone_panel)

    MainWindow._build_shell = build_shell
    MainWindow._gelotech_phone_frame_installed = True
