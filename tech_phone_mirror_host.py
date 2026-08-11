# -*- coding: utf-8 -*-
"""Dashboard-owned scrcpy host.

Keeps the existing native scrcpy + transparent iPhone-frame implementation,
but makes the two windows owned by the GeloTech application instead of
independent always-on-top desktop windows. The mirror is visible only while
the Dashboard phone widget is visible.

The scrcpy window is also clipped to the rounded display opening of the
phone frame. This prevents the square native scrcpy background from leaking
through the four corners, which is especially visible in GeloTech Light Mode.
"""
import ctypes
import time
import threading

from tech_phone_mirror import (
    PhoneMirrorManager as _BasePhoneMirrorManager,
    ScrcpyWindowManager,
    PHONE_SCALE,
)

GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8
WS_EX_TOPMOST = 0x00000008
HWND_TOP = 0
HWND_NOTOPMOST = -2
SW_HIDE = 0
SW_SHOWNA = 8
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

# The transparent opening in iphone_frame_overlay.png is rounded.  scrcpy
# itself is a normal rectangular native window, so its black background can
# otherwise appear as four sharp corners inside the frame.  Clip only the
# scrcpy window; the frame overlay remains unchanged and click-through.
DISPLAY_CORNER_RADIUS = 30


def _user32():
    return ctypes.windll.user32


def _gdi32():
    return ctypes.windll.gdi32


def _set_owner(hwnd, owner):
    """Make hwnd an owned window of the GeloTech main window.

    This is intentionally ownership, not SetParent: scrcpy remains a native
    top-level window, which preserves its rendering/input behavior, while
    Windows now minimizes/hides it with the GeloTech application.
    """
    if not hwnd or not owner:
        return
    u = _user32()
    try:
        u.SetWindowLongPtrW.restype = ctypes.c_void_p
        u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                        ctypes.c_void_p]
        u.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, ctypes.c_void_p(owner))
        style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, style & ~WS_EX_TOPMOST)
        u.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                       SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    except Exception:
        pass


def _clip_scrcpy_window(hwnd, width, height):
    """Clip the native scrcpy window to the frame's rounded display opening.

    SetWindowRgn affects only the visible shape of the top-level window; it
    does not alter the scrcpy rendering surface or mouse coordinates.  This
    is preferable to screenshot compositing and keeps the live stream fully
    interactive.
    """
    if not hwnd or width <= 0 or height <= 0:
        return
    try:
        gdi = _gdi32()
        u = _user32()
        radius = max(2, int(DISPLAY_CORNER_RADIUS * PHONE_SCALE + 0.5))
        radius = min(radius, width // 2, height // 2)
        gdi.CreateRoundRectRgn.restype = ctypes.c_void_p
        gdi.CreateRoundRectRgn.argtypes = [
            ctypes.c_int32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
            ctypes.c_int32, ctypes.c_int32,
        ]
        u.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_bool]
        region = gdi.CreateRoundRectRgn(0, 0, width + 1, height + 1,
                                        radius * 2, radius * 2)
        if region:
            # Windows owns the region after SetWindowRgn succeeds; do not
            # DeleteObject(region) here.
            if not u.SetWindowRgn(hwnd, region, True):
                gdi.DeleteObject(region)
    except Exception:
        # Clipping is cosmetic. Never allow it to prevent the mirror itself
        # from starting if a Windows/GDI call is unavailable.
        pass


class PhoneMirrorManager(_BasePhoneMirrorManager):
    """Existing mirror manager with application-owned window lifetime."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._host_hwnd = 0
        self._phone_hwnd = 0
        self._host_visible = False

    def _capture_host(self):
        """Capture HWNDs from Tk while start() is called on the UI thread."""
        d = self._dashboard
        try:
            top = d.winfo_toplevel()
            phone = getattr(d, "dash_phone", None)
            self._host_hwnd = int(top.winfo_id()) if top else 0
            self._phone_hwnd = int(phone.winfo_id()) if phone else 0
        except Exception:
            self._host_hwnd = 0
            self._phone_hwnd = 0

    def start(self, *args, **kwargs):
        self._capture_host()
        return super().start(*args, **kwargs)

    def _dashboard_visible(self):
        """Use Win32 HWND state only; do not touch Tk from the monitor thread."""
        u = _user32()
        if not self._host_hwnd or not self._phone_hwnd:
            return True
        try:
            return bool(u.IsWindow(self._host_hwnd)
                        and u.IsWindow(self._phone_hwnd)
                        and u.IsWindowVisible(self._host_hwnd)
                        and u.IsWindowVisible(self._phone_hwnd)
                        and not u.IsIconic(self._host_hwnd))
        except Exception:
            return True

    def _window_exists(self, hwnd):
        try:
            return bool(hwnd and _user32().IsWindow(hwnd))
        except Exception:
            return False

    def _bind_windows(self):
        if self._host_hwnd:
            _set_owner(self.hwnd, self._host_hwnd)
        if self.overlay is not None:
            _set_owner(self.overlay.hwnd, self._host_hwnd)

    def _set_visible(self, visible):
        u = _user32()
        if self.hwnd and self._window_exists(self.hwnd):
            u.ShowWindow(self.hwnd, SW_SHOWNA if visible else SW_HIDE)
        if self.overlay is not None and self._window_exists(self.overlay.hwnd):
            u.ShowWindow(self.overlay.hwnd, SW_SHOWNA if visible else SW_HIDE)
        self._host_visible = bool(visible)

    def _align_all(self):
        # Preserve the original geometry/alignment implementation, then
        # immediately remove TOPMOST so the mirror cannot escape the app.
        super()._align_all()
        self._bind_windows()
        if self.hwnd:
            _user32().ShowWindow(self.hwnd, SW_SHOWNA)
            rect = ScrcpyWindowManager.rect(self.hwnd)
            if rect:
                _clip_scrcpy_window(self.hwnd, rect[2], rect[3])
        if self.overlay is not None and self.overlay.hwnd:
            _user32().SetWindowPos(
                self.overlay.hwnd, HWND_TOP, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            _set_owner(self.overlay.hwnd, self._host_hwnd)
        self._host_visible = True

    def _monitor_loop(self):
        """Original monitor behavior plus strict Dashboard visibility gating."""
        timeout = 15.0
        t0 = time.time()
        while not self._stop.is_set():
            if not self.hwnd:
                self.hwnd = ScrcpyWindowManager.find_hwnd(
                    self.proc, timeout=timeout, poll=0.2)
                if self.hwnd:
                    self._log(f"[SCRCPY] scrcpy HWND found: {self.hwnd}")
                    self._log("[PHONE] Positioning frame")
                    self._align_all()
                    self._log("[PHONE] Mirror ready (Dashboard-owned)")
                    self._set_state("active")
                elif self._stop.is_set() or time.time() - t0 > timeout:
                    try:
                        code = self.proc.poll() if self.proc is not None else None
                    except Exception:
                        code = None
                    self._log("[SCRCPY ERROR] scrcpy window not found "
                              f"(exit={code}) - is the phone connected?")
                    self._cleanup()
                    return
                continue

            if not self._window_exists(self.hwnd):
                self._log("[SCRCPY] scrcpy window closed")
                self._cleanup()
                return
            if self.overlay is None or not self._window_exists(self.overlay.hwnd):
                self._log("[PHONE] Overlay closed")
                self._cleanup()
                return

            dashboard_visible = self._dashboard_visible()
            if not dashboard_visible:
                if self._host_visible:
                    self._set_visible(False)
                time.sleep(0.08)
                continue

            if not self._host_visible:
                self._set_visible(True)
                self._align_all()

            expected = self._expected_scrcpy_rect()
            actual = ScrcpyWindowManager.rect(self.hwnd)
            if expected and actual and actual != expected:
                self._align_all()
            else:
                # Keep the frame above scrcpy, but never topmost over other
                # applications. Both windows are owned by GeloTech.
                self._bind_windows()
                _user32().SetWindowPos(self.hwnd, HWND_TOP, 0, 0, 0, 0,
                                       SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                _clip_scrcpy_window(self.hwnd, actual[2], actual[3])
                _user32().SetWindowPos(self.overlay.hwnd, HWND_TOP, 0, 0, 0, 0,
                                       SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            time.sleep(0.05)


__all__ = ["PhoneMirrorManager", "PHONE_SCALE"]
