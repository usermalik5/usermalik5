# -*- coding: utf-8 -*-
"""Compatibility entry point for the Dashboard-embedded scrcpy mirror.

Python prefers this package over the legacy ``tech_phone_mirror.py`` module.
The legacy implementation is loaded under a private name so the existing
rendering code remains unchanged, while the Dashboard uses the real child
window manager from ``tech_phone_mirror_embedded.py``.
"""
from pathlib import Path
import importlib.util
import inspect
import sys


_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _PACKAGE_DIR.parent
_LEGACY_PATH = _PROJECT_DIR / "tech_phone_mirror.py"
_LEGACY_NAME = "_gelotech_legacy_phone_mirror"

_spec = importlib.util.spec_from_file_location(_LEGACY_NAME, _LEGACY_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load legacy mirror module: {_LEGACY_PATH}")

_legacy = importlib.util.module_from_spec(_spec)
sys.modules[_LEGACY_NAME] = _legacy
_spec.loader.exec_module(_legacy)

PHONE_SCALE = _legacy.PHONE_SCALE
MIRROR_WINDOW_TITLE = _legacy.MIRROR_WINDOW_TITLE
OVERLAY_WINDOW_TITLE = _legacy.OVERLAY_WINDOW_TITLE
PHONE_IMG_NATIVE = _legacy.PHONE_IMG_NATIVE
DISPLAY_RECT = _legacy.DISPLAY_RECT
ScrcpyWindowManager = _legacy.ScrcpyWindowManager
PhoneFrameOverlay = _legacy.PhoneFrameOverlay

# tech_phone_mirror_host imports this name while the embedded implementation
# is being imported. Expose the original class first to avoid a circular
# inheritance chain; we replace it with the embedded class below.
PhoneMirrorManager = _legacy.PhoneMirrorManager

from tech_phone_mirror_embedded import PhoneMirrorManager as _EmbeddedMirrorManager


class PhoneMirrorManager(_EmbeddedMirrorManager):
    """Embedded mirror that captures the exact Dashboard phone widget."""

    def _capture_host(self):
        dashboard = None
        frame = None
        try:
            frame = inspect.currentframe()
            for _ in range(12):
                if frame is None:
                    break
                frame = frame.f_back
                if frame is None:
                    break
                candidate = frame.f_locals.get("self")
                if candidate is not None and hasattr(candidate, "dash_phone"):
                    dashboard = candidate
                    break
        except Exception:
            dashboard = None
        finally:
            del frame

        if dashboard is not None:
            self._dashboard = dashboard
            try:
                self._log("[PHONE] Dashboard host captured")
            except Exception:
                pass
        else:
            try:
                self._log("[PHONE ERROR] Dashboard host not found")
            except Exception:
                pass

        return super()._capture_host()


__all__ = [
    "PhoneMirrorManager",
    "PHONE_SCALE",
    "MIRROR_WINDOW_TITLE",
    "OVERLAY_WINDOW_TITLE",
    "PHONE_IMG_NATIVE",
    "DISPLAY_RECT",
    "ScrcpyWindowManager",
    "PhoneFrameOverlay",
]
