# -*- coding: utf-8 -*-
"""Compatibility entry point for the Dashboard-embedded scrcpy mirror."""
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
            try:
                del frame
            except Exception:
                pass

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

    def _restore_console_safe(self):
        """Restore the existing Dashboard console on Tk's UI thread."""
        d = self._dashboard
        if d is not None:
            try:
                d.after_idle(self._restore_dashboard_console)
                return
            except Exception:
                pass
        self._restore_dashboard_console()

    def _restore_dashboard_console(self):
        """Re-map the existing log widget using the Dashboard's current layout.

        The old mirror code saved the rectangle at mirror-start time. That
        rectangle can become stale after DPI/resize/layout changes. The
        Dashboard already owns the authoritative ``_dash_log_rect``; use it
        when the mirror terminates, then force Tk to map and redraw the widget.
        """
        c = getattr(self, "_hidden_console", None)
        d = self._dashboard
        if c is None or d is None:
            return
        try:
            if not c.winfo_exists():
                return
            r = getattr(d, "_dash_log_rect", None) or getattr(self, "_console_place", None)
            if not r:
                return
            c.place(x=int(r[0]), y=int(r[1]), width=int(r[2]), height=int(r[3]))
            c.lift()
            d.update_idletasks()

            # Reapply the phone-screen clipping after the widget is mapped.
            clip = getattr(d, "_clip_dash_console", None)
            if callable(clip):
                try:
                    radius = int(getattr(d, "PHONE_SCREEN_RADIUS", 24))
                    clip(int(r[2]), int(r[3]), radius, attempts=3)
                except Exception:
                    pass
        except Exception as exc:
            try:
                self._log(f"[PHONE] Dashboard log restore deferred: {exc}")
            except Exception:
                pass
            try:
                d.after(100, self._restore_dashboard_console)
                return
            except Exception:
                pass
        self._hidden_console = None
        self._console_place = None


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
