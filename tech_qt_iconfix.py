"""Qt icon-cache lookup bridge.

Keeps the App Cleaner icon lookup compatible with both legacy cache layouts:
the per-device hashed cache and the shared restored icon cache.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

from tech_common import get_cache_dir
from tech_qt_icons import load_icon


def _cached_icon(self, package: str):
    roots: list[Path] = []
    if getattr(self, "serial", None):
        roots.append(self._cache_dir_for(self.serial))
    roots.append(Path(get_cache_dir()))

    names = (f"{package}.png", f"{package}.ico")
    for root in roots:
        candidates = [*(root / name for name in names)]
        export_root = root / "apk_icon_export"
        candidates.extend(export_root / name for name in names)
        if export_root.is_dir():
            candidates.extend(export_root.rglob(names[0]))
            candidates.extend(export_root.rglob(names[1]))
        for path in candidates:
            try:
                if path.is_file():
                    icon = QIcon(str(path))
                    if not icon.isNull():
                        return icon
            except OSError:
                pass
    return load_icon("device-mobile")


def install_icon_cache_lookup(MainWindow) -> None:
    MainWindow._cached_icon = _cached_icon
