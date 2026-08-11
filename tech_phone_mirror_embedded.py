# -*- coding: utf-8 -*-
"""True in-dashboard scrcpy embedding for GeloTech.

The previous Dashboard-owned implementation only *owned* the native scrcpy
and frame windows. Ownership keeps them with GeloTech when minimized, but they
are still top-level Windows windows. This module goes one step further:
both windows are reparented as CHILD windows of the Dashboard phone widget.
They therefore cannot float on the Windows desktop or escape the GeloTech
window.
"""
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
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001


def _user32():
    return ctypes.windll.user32


def _embed(hwnd, parent, x, y, width, height):
    """Convert a top-level mirror window into a child of the phone widget."""
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
                                   ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int,
                                   ctypes.c_uint]

        # Set the child style BEFORE/around SetParent so Windows treats the
        # native window as a genuine child rather than a desktop popup.
        style = u.GetWindowLongW(hwnd, GWL_STYLE)
        style = (style & ~WS_POPUP) | WS_CHILD
        u.SetWindowLongW(hwnd, GWL_STYLE, style)

        ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex &= ~(WS_EX_TOPMOST | WS_EX_APPWINDOW)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)

        u.SetParent(hwnd, parent)
        u.SetWindowPos(hwnd, HWND_TOP, int(x), int(y), int(width), int(height),
                       SWP_NOACTIVATE | SWP_SHOWWINDOW)
        return True
    except Exception:
        return False


class PhoneMirrorManager(_BaseMirrorManager):
    """Mirror manager whose native windows live inside Dashboard.dash_phone."""

    def _bind_windows(self):
        # IMPORTANT: do not use SetWindowLongPtr(GWLP_HWNDPARENT) as an owner.
        # SetParent makes the windows actual CHILD windows of the Dashboard's
        # phone widget, which is what prevents them from appearing on the
        # Windows desktop outside GeloTech.
        parent = getattr(self, "_phone_hwnd", 0)
        if not parent:
            return

        # The frame is the complete phone mockup. scrcpy occupies only the
        # transparent display opening in that frame.
        overlay = getattr(self, "overlay", None)
        if overlay is not None and getattr(overlay, "hwnd", None):
            try:
                # Overlay size is the native iPhone frame size. It is placed
                # at the phone widget origin and remains click-through.
                fw = int(396 * self.scale + 0.5)
                fh = int(824 * self.scale + 0.5)
                _embed(overlay.hwnd, parent, 0, 0, fw, fh)
            except Exception:
                pass

        hwnd = getattr(self, "hwnd", None)
        if hwnd:
            try:
                # The scrcpy child is positioned relative to the phone widget,
                # not the Windows desktop. DISPLAY_RECT is 14,12,368,800.
                x = int(14 * self.scale + 0.5)
                y = int(12 * self.scale + 0.5)
                w = int(368 * self.scale + 0.5)
                h = int(800 * self.scale + 0.5)
                _embed(hwnd, parent, x, y, w, h)
            except Exception:
                pass

    def start(self, *args, **kwargs):
        result = super().start(*args, **kwargs)
        if result:
            # The base manager creates the native windows on its worker path.
            # Embed immediately after startup so there is no persistent
            # desktop-level mirror window. _align_all/_monitor_loop will keep
            # enforcing the child relationship thereafter.
            try:
                self._bind_windows()
            except Exception:
                pass
        return result


__all__ = ["PhoneMirrorManager"]
