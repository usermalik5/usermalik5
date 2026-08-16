"""Qt-native Tabler SVG icon loading for GeloTech.

The helper intentionally uses Qt's SVG engine through QIcon. No cairosvg or
other rasterisation dependency is required.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def icon_dir() -> str:
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "assets", "icons", "tabler")


@lru_cache(maxsize=512)
def load_icon(name: str, size: int = 20, weight: str = "outline") -> QIcon:
    """Load a bundled Tabler SVG as a native QIcon.

    ``size`` is retained in the cache key so callers can use the same SVG at
    several display sizes. Qt handles the vector rasterisation.
    """
    safe_weight = weight if weight in {"outline", "filled"} else "outline"
    path = os.path.join(icon_dir(), safe_weight, f"{name}.svg")
    if not os.path.isfile(path):
        # A missing icon should never prevent the application from starting.
        return QIcon()
    icon = QIcon(path)
    # Keep the requested size in the cache key; QIcon remains vector-backed.
    _ = QSize(int(size), int(size))
    return icon


@lru_cache(maxsize=2048)
def tinted_icon(name: str, color: str, size: int = 18) -> QIcon:
    """Load a Tabler SVG and recolour it to ``color`` (hex string).

    Renders the vector to a transparent image, then repaints it with the
    requested colour using a SourceIn composition so the original alpha shape
    is preserved. This lets every button carry its own accent-coloured icon
    without rasterisation dependencies.
    """
    path = os.path.join(icon_dir(), "outline", f"{name}.svg")
    if not os.path.isfile(path):
        return QIcon()
    renderer = QSvgRenderer(path)
    if not renderer.isValid():
        return QIcon()
    img = QImage(QSize(int(size), int(size)), QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    pix = QPixmap.fromImage(img)
    tint = QPainter(pix)
    tint.setCompositionMode(QPainter.CompositionMode_SourceIn)
    tint.fillRect(pix.rect(), QColor(color))
    tint.end()
    return QIcon(pix)


ICONS = {
    "Dashboard": "dashboard",
    "Monitor Apps": "search",
    "Block Ads DNS": "globe",
    "VirusTotal": "virus",
    "Screen Mirror": "device-mobile",
    "Reboot": "refresh",
    "Re-authorize ADB": "plug-connected",
    "Fix Drivers": "tool",
    "Accounts": "key",
    "Logout": "logout",
    "Scan": "scan",
    "Settings": "settings",
    "Device": "device-mobile",
    "Battery": "battery",
    "Wifi": "wifi",
    "Trash": "trash",
    "Folder": "folder",
    "Database": "database",
    "Terminal": "terminal",
    "Alert": "alert-triangle",
    "Info": "info-circle",
    "Check": "check",
    "Close": "x",
    "Lock": "lock",
    "Power": "power",
    "Login": "login",
}
