# -*- coding: utf-8 -*-
"""True in-dashboard scrcpy embedding for GeloTech."""
import ctypes

from tech_phone_mirror_host import PhoneMirrorManager as _BaseMirrorManager

GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_APPWINDOW = 0x00040000
HWND_TOP = 0
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def _user32():
    return ctypes.windll.user32


def _embed(hwnd, parent, x, y, width, height):
    """Convert a top-level mirror window into a real child window."""
    if not hwnd or not parent:
        return False
    u = _user32()
    try:
        u.SetParent.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        u.SetParent.restype = ctypes.c_void_p
        u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        u.SetWindowLongW.restype = ctypes.c_long
        u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_uint]

        style = u.GetWindowLongW(hwnd, GWL_STYLE)
        u.SetWindowLongW(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD)
        ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex & ~(WS_EX_TOPMOST | WS_EX_APPWINDOW))
        u.SetParent(hwnd, parent)
        u.SetWindowPos(hwnd, HWND_TOP, int(x), int(y), int(width), int(height),
                       SWP_NOACTIVATE | SWP_SHOWWINDOW)
        return True
    except Exception:
        return False


class PhoneMirrorManager(_BaseMirrorManager):
    """Mirror manager whose native windows live inside Dashboard.dash_phone."""

    def _bind_windows(self):
        parent = getattr(self, "_phone_hwnd", 0)
        if not parent:
            return
        overlay = getattr(self, "overlay", None)
        if overlay is not None and getattr(overlay, "hwnd", None):
            try:
                fw = int(396 * self.scale + 0.5)
                fh = int(824 * self.scale + 0.5)
                _embed(overlay.hwnd, parent, 0, 0, fw, fh)
            except Exception:
                pass
        hwnd = getattr(self, "hwnd", None)
        if hwnd:
            try:
                x = int(14 * self.scale + 0.5)
                y = int(12 * self.scale + 0.5)
                w = int(368 * self.scale + 0.5)
                h = int(800 * self.scale + 0.5)
                _embed(hwnd, parent, x, y, w, h)
            except Exception:
                pass

    def _restore_console_safe(self):
        """Restore the existing Dashboard console on Tk's main thread."""
        d = getattr(self, "_dashboard", None)
        if d is not None:
            try:
                d.after_idle(self._restore_dashboard_console)
                return
            except Exception:
                pass
        self._restore_dashboard_console()

    def _restore_dashboard_console(self):
        """Restore the existing log widget using the Dashboard's current layout."""
        c = getattr(self, "_hidden_console", None)
        d = getattr(self, "_dashboard", None)
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
            clip = getattr(d, "_clip_dash_console", None)
            if callable(clip):
                try:
                    clip(int(r[2]), int(r[3]), 24, attempts=3)
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

    def start(self, *args, **kwargs):
        result = super().start(*args, **kwargs)
        if result:
            try:
                self._bind_windows()
            except Exception:
                pass
        return result


__all__ = ["PhoneMirrorManager"]
