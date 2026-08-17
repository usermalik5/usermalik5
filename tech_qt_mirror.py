"""Qt scrcpy integration using the legacy native-window mirror model.

Ports the legacy GeloTech dashboard mirror behavior (tech_phone_mirror.py /
tech_phone_mirror_host.py) into the Qt shell:
- scrcpy stays a NATIVE top-level window, never reparented with SetParent:
  the legacy host module documents that SetParent changes scrcpy's input
  behavior (keyboard dies), while a native window keeps full rendering and
  input, including SDL keyboard capture after a click activates it
- the scrcpy window is OWNED by the Qt main window (GWLP_HWNDPARENT), so it
  minimizes/hides together with the application, and is positioned over the
  phone mockup's display opening using global screen coordinates
- a transparent, fully click-through bezel overlay window draws the iPhone
  frame ABOVE the video, so the single Dashboard mockup look is preserved
  while clicks and key focus fall straight through to scrcpy
- rounded-corner clipping of the scrcpy window so the square native surface
  cannot bleed through the frame's rounded opening
- Screen Mirror button acts as a toggle (Screen Mirror <-> Stop Mirror)
- 50ms monitor keeps scrcpy + overlay glued to the display opening
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QPoint, QRect
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QPushButton, QWidget

from tech_qt_phone import DISPLAY_RECT, PHONE_NATIVE


_DEBUG_LOG = os.path.join(
    os.environ.get("TEMP") or ".", "gelotech_qt_mirror_debug.log")


def _debug(msg: str) -> None:
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{time.time():.3f} {msg}\n")
    except Exception:
        pass


# Win32 constants (same values as the legacy mirror subsystem).
GWL_STYLE = -16
GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
HWND_TOP = 0
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
# The transparent opening in the frame PNG is rounded; clip the square native
# scrcpy window so its background cannot appear as four sharp corners inside.
DISPLAY_CORNER_RADIUS = 30


def _user32():
    return ctypes.windll.user32


def _gdi32():
    return ctypes.windll.gdi32


def _find_window(title: str) -> int:
    try:
        return int(_user32().FindWindowW(None, title) or 0)
    except Exception:
        return 0


def _display_geometry(host: QWidget) -> tuple[int, int, int, int]:
    """Return the legacy display opening in physical pixels, relative to the
    phone widget.  Only the widget's own size matters - never its position -
    so the result cannot go stale when the window moves."""
    width = max(1, host.width())
    height = max(1, host.height())
    sx = width / PHONE_NATIVE[0]
    sy = height / PHONE_NATIVE[1]
    scale = min(sx, sy)
    dpr = 1.0
    try:
        dpr = float(host.devicePixelRatioF() or 1.0)
    except Exception:
        pass
    return (
        int(DISPLAY_RECT[0] * scale * dpr),
        int(DISPLAY_RECT[1] * scale * dpr),
        max(1, int(DISPLAY_RECT[2] * scale * dpr)),
        max(1, int(DISPLAY_RECT[3] * scale * dpr)),
    )


def _clip_radius(host: QWidget) -> int:
    try:
        scale = min(host.width() / PHONE_NATIVE[0],
                    host.height() / PHONE_NATIVE[1])
        return max(2, int(DISPLAY_CORNER_RADIUS * scale + 0.5))
    except Exception:
        return DISPLAY_CORNER_RADIUS


def _own_window(hwnd: int, owner: int) -> bool:
    """Make hwnd an OWNED window of the Qt main window.

    Ownership (GWLP_HWNDPARENT), not SetParent: scrcpy remains a native
    top-level window, which preserves its rendering and input behavior
    (SDL keyboard capture included), while Windows still minimizes and
    hides it together with the GeloTech application.  Mirrors the legacy
    tech_phone_mirror_host._set_owner design.
    """
    if not hwnd or not owner:
        return False
    u = _user32()
    try:
        u.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                        ctypes.c_void_p]
        u.SetWindowLongPtrW.restype = ctypes.c_void_p
        u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                     ctypes.c_long]
        u.SetWindowLongW.restype = ctypes.c_long
        u.SetWindowLongPtrW(hwnd, GWLP_HWNDPARENT, ctypes.c_void_p(owner))
        ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex & ~WS_EX_TOPMOST)
        return True
    except Exception:
        return False


class _MirrorOverlay(QWidget):
    """Transparent, fully click-through frame window drawn ABOVE the video.

    Renders the iPhone bezel (the phone mockup's own pixmap) so the single
    Dashboard mockup look is preserved while scrcpy stays a native window
    underneath.  Every mouse event and the keyboard focus fall through the
    opening to the scrcpy window (legacy PhoneFrameOverlay behavior).
    """

    def __init__(self, pixmap: QPixmap | None = None) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlag(Qt.WindowTransparentForInput, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
        self._pixmap = pixmap
        self._hole = None  # (x, y, w, h) of the video opening, overlay-local

    def set_hole(self, x: int, y: int, w: int, h: int) -> None:
        self._hole = (int(x), int(y), int(w), int(h))

    def paintEvent(self, event) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.SmoothPixmapTransform)
            if self._hole is None:
                painter.drawPixmap(self.rect(), self._pixmap)
            else:
                # Draw only the bezel margins around the video opening so the
                # live video always shows through the hole.
                hx, hy, hw, hh = self._hole
                w, h = self.width(), self.height()
                sw, sh = self._pixmap.width(), self._pixmap.height()
                strips = [
                    (0, 0, w, hy),           # top
                    (0, hy + hh, w, h - hy - hh),  # bottom
                    (0, hy, hx, hh),         # left
                    (hx + hw, hy, w - hx - hw, hh),  # right
                ]
                for rx, ry, rw, rh in strips:
                    if rw <= 0 or rh <= 0:
                        continue
                    painter.drawPixmap(
                        QRect(rx, ry, rw, rh),
                        self._pixmap,
                        QRect(int(rx * sw / w), int(ry * sh / h),
                              max(1, int(rw * sw / w)), max(1, int(rh * sh / h))),
                    )
        finally:
            painter.end()


def _global_opening(host: QWidget):
    """Return (x, y, w, h) of the display opening in global screen pixels."""
    dx, dy, dw, dh = _display_geometry(host)
    try:
        dpr = float(host.devicePixelRatioF() or 1.0)
    except Exception:
        dpr = 1.0
    gp = host.mapToGlobal(QPoint(0, 0))
    return int(gp.x() * dpr + dx), int(gp.y() * dpr + dy), dw, dh


def _clip_scrcpy_window(hwnd: int, width: int, height: int, radius: int) -> None:
    """Clip the native scrcpy child to the frame's rounded display opening.

    SetWindowRgn affects only the visible shape of the window; it does not
    alter the scrcpy rendering surface or mouse coordinates.
    """
    if not hwnd or width <= 0 or height <= 0:
        return
    try:
        gdi = _gdi32()
        u = _user32()
        radius = max(2, int(radius))
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
            # Windows owns the region after SetWindowRgn succeeds.
            if not u.SetWindowRgn(hwnd, region, True):
                gdi.DeleteObject(region)
    except Exception:
        # Clipping is cosmetic. Never allow it to prevent the mirror itself.
        pass


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("flags", ctypes.c_uint32),
        ("hwndActive", ctypes.c_void_p),
        ("hwndFocus", ctypes.c_void_p),
        ("hwndCapture", ctypes.c_void_p),
        ("hwndMenuOwner", ctypes.c_void_p),
        ("hwndMoveSize", ctypes.c_void_p),
        ("hwndCaret", ctypes.c_void_p),
        ("rcCaret", _RECT),
    ]


def _mirror_user32_setup() -> None:
    u = _user32()
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                           ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetGUIThreadInfo.argtypes = [wintypes.DWORD,
                                   ctypes.POINTER(_GUITHREADINFO)]
    u.GetGUIThreadInfo.restype = wintypes.BOOL
    u.GetCursorPos.argtypes = [ctypes.POINTER(_POINT)]
    u.GetCursorPos.restype = wintypes.BOOL
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
    u.GetWindowRect.restype = wintypes.BOOL
    u.GetForegroundWindow.restype = wintypes.HWND
    u.SetFocus.argtypes = [wintypes.HWND]
    u.SetFocus.restype = wintypes.HWND


def _find_mirror_buttons(self) -> list:
    buttons = []
    try:
        for button in self.findChildren(QPushButton):
            text = button.text()
            if "Screen Mirror" in text or "Stop Mirror" in text:
                buttons.append(button)
    except Exception:
        pass
    return buttons


def _set_mirror_button_state(self, active: bool) -> None:
    for button in _find_mirror_buttons(self):
        try:
            button.setText("\U0001f6d1 Stop Mirror" if active else "\U0001f4f1 Screen Mirror")
        except Exception:
            pass


def install_scrcpy(MainWindow) -> None:
    """Install reliable embedded scrcpy mirroring (legacy child-window model)."""

    def start_mirror(self) -> None:
        # Toggle: a running mirror is stopped by clicking again.
        process = getattr(self, "_qt_scrcpy_process", None)
        if process is not None and process.poll() is None:
            self._log("[SCRCPY] Stopping screen mirror")
            self._qt_stop_scrcpy()
            _set_mirror_button_state(self, False)
            return

        if not self.serial:
            self._scan_devices()
        if not self.serial:
            self._log("[SCRCPY] No connected device.")
            return

        exe = shutil.which("scrcpy")
        if not exe:
            for candidate in (
                self._qt_bundle_path("scrcpy.exe"),
                self._qt_bundle_path("scrcpy", "scrcpy.exe"),
                self._qt_bundle_path("scrcpy-win64-v3.3.4", "scrcpy.exe"),
            ):
                if candidate.is_file():
                    exe = str(candidate)
                    break
        if not exe:
            self._log("[SCRCPY] scrcpy executable not found in PATH/bundle.")
            return

        host = getattr(self, "phone_host", None)
        if host is None:
            self._log("[SCRCPY] Phone host unavailable; cannot fit mirror to frame.")
            return

        # Embed INTO the bezel image widget: a native child window always
        # renders above its parent's content, so the video shows through the
        # image's transparent screen opening while the bezel stays on top of
        # the window edges.  phone_host sits BELOW phone_image in Qt's native
        # stacking, so parenting there hides the stream behind the bezel.
        host = getattr(self, "phone_image", None) or host

        # Global screen coordinates so the native scrcpy window spawns right
        # over the phone display opening (native model: no SetParent).
        gx, gy, dw, dh = _global_opening(host)
        title = f"GeloTech Mirror - {self.serial}"
        _debug(
            f"launch host={type(host).__name__} obj={host.objectName()} "
            f"vis={host.isVisible()} win_vis={self.isVisible()} "
            f"geom={host.geometry().getRect()} dpr={host.devicePixelRatioF()} "
            f"opening=({gx},{gy},{dw},{dh})"
        )

        try:
            process = subprocess.Popen(
                [
                    exe,
                    "-s", self.serial,
                    "--window-title", title,
                    "--window-x", str(gx),
                    "--window-y", str(gy),
                    "--window-width", str(dw),
                    "--window-height", str(dh),
                    "--window-borderless",
                    "--no-audio",
                    "--max-size=1280",
                    "--no-power-on",
                    "--keyboard=sdk",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
        except Exception as exc:
            self._log(f"[SCRCPY] Failed to start mirror: {exc}")
            return

        self._qt_scrcpy_process = process
        self._qt_scrcpy_title = title
        self._qt_scrcpy_hwnd = 0
        _set_mirror_button_state(self, True)
        self._log(
            f"[SCRCPY] Target phone display: w={dw} h={dh}."
        )
        QTimer.singleShot(250, lambda: self._qt_embed_scrcpy(0))

    def _embed_scrcpy(self, attempt: int = 0) -> None:
        hwnd = _find_window(getattr(self, "_qt_scrcpy_title", ""))
        if not hwnd:
            if attempt < 40:
                QTimer.singleShot(250, lambda: self._qt_embed_scrcpy(attempt + 1))
                return
            process = getattr(self, "_qt_scrcpy_process", None)
            if process is not None and process.poll() is None:
                self._log("[SCRCPY] Window was not found; leaving native scrcpy running as fallback.")
            return

        host = getattr(self, "phone_host", None)
        if host is None:
            self._log("[SCRCPY] Phone host disappeared; leaving native scrcpy window active.")
            return

        try:
            # Native model: scrcpy stays a top-level window owned by the app,
            # positioned over the phone display opening in global coordinates.
            host = getattr(self, "phone_image", None) or host
            main_hwnd = int(self.winId())
            gx, gy, dw, dh = _global_opening(host)
            owned = _own_window(hwnd, main_hwnd)
            u = _user32()
            u.SetWindowPos(hwnd, HWND_TOP, int(gx), int(gy), int(dw), int(dh),
                           SWP_NOACTIVATE | SWP_SHOWWINDOW)
            _clip_scrcpy_window(hwnd, dw, dh, _clip_radius(host))
            self._qt_scrcpy_hwnd = hwnd
            self._qt_scrcpy_host = host

            # Transparent bezel overlay above the video: keeps the single
            # Dashboard mockup look while clicks/focus reach scrcpy.
            overlay = self._qt_scrcpy_overlay
            if overlay is None or not overlay.isVisible():
                try:
                    pixmap = host.grab()
                except Exception:
                    pixmap = None
                if pixmap is None or pixmap.isNull():
                    try:
                        pixmap = host.pixmap() if hasattr(host, "pixmap") else None
                    except Exception:
                        pixmap = None
                overlay = _MirrorOverlay(pixmap)
                overlay.resize(host.width(), host.height())
                overlay.move(host.mapToGlobal(QPoint(0, 0)))
                hg = host.mapToGlobal(QPoint(0, 0))
                overlay.set_hole(int(gx - hg.x()), int(gy - hg.y()),
                                 int(dw), int(dh))
                overlay.show()
                _own_window(int(overlay.winId()), main_hwnd)
                self._qt_scrcpy_overlay = overlay
            _debug(
                f"embed hwnd={hwnd} owned={owned} "
                f"rect=({gx},{gy},{dw},{dh}) host_size={host.width()}x{host.height()} "
                f"overlay={int(overlay.winId())}"
            )
            if not owned:
                self._log("[SCRCPY] Ownership failed; leaving native scrcpy window active.")
            self._log(
                f"[SCRCPY] Video surface positioned over Dashboard phone screen: "
                f"x={gx} y={gy} w={dw} h={dh}."
            )
            self._log("[SCRCPY] Live phone video active inside Dashboard phone screen.")
            self._qt_scrcpy_timer = QTimer(self)
            self._qt_scrcpy_timer.timeout.connect(self._qt_reposition_scrcpy)
            self._qt_scrcpy_timer.start(50)
            self._qt_scrcpy_settle_until = time.time() + 1.5
        except Exception as exc:
            self._log(f"[SCRCPY] Native mirror positioning failed: {exc}")
            _debug(f"embed EXC {exc!r}")

    def _reposition_scrcpy(self) -> None:
        hwnd = getattr(self, "_qt_scrcpy_hwnd", 0)
        host = getattr(self, "_qt_scrcpy_host", None)
        if not hwnd or host is None:
            return
        u = _user32()
        overlay = getattr(self, "_qt_scrcpy_overlay", None)
        # The mirror belongs to the tool: it may only float over the
        # Dashboard page.  Hide it when the app is minimized/hidden or the
        # user navigated to another page, and bring it back on return.
        if (self.isMinimized() or self.isHidden()
                or not getattr(self, "_qt_dashboard_active", True)):
            try:
                u.ShowWindow(hwnd, 0)
            except Exception:
                pass
            if overlay is not None and overlay.isVisible():
                overlay.hide()
            return
        try:
            if overlay is not None and not overlay.isVisible():
                overlay.show()
            # Let SDL settle its window first: fighting it during startup
            # causes flicker/glitches.
            if time.time() < getattr(self, "_qt_scrcpy_settle_until", 0.0):
                return
            gx, gy, dw, dh = _global_opening(host)
            now_rect = _RECT()
            u.GetWindowRect(hwnd, ctypes.byref(now_rect))
            size_changed = (now_rect.right - now_rect.left != dw
                            or now_rect.bottom - now_rect.top != dh)
            if (now_rect.left, now_rect.top) != (gx, gy) or size_changed:
                flags = SWP_NOACTIVATE
                if not u.IsWindowVisible(hwnd):
                    flags |= SWP_SHOWWINDOW
                u.SetWindowPos(hwnd, HWND_TOP, int(gx), int(gy), int(dw), int(dh),
                               flags)
                if size_changed:
                    # Region clipping is expensive; re-apply only when the
                    # video surface actually changed size.
                    _clip_scrcpy_window(hwnd, dw, dh, _clip_radius(host))
            if overlay is not None and overlay.isVisible():
                hpos = host.mapToGlobal(QPoint(0, 0))
                opos = overlay.pos()
                if (overlay.width(), overlay.height()) != (host.width(), host.height()) \
                        or (opos.x(), opos.y()) != (hpos.x(), hpos.y()):
                    overlay.resize(host.width(), host.height())
                    overlay.move(hpos)
                # Keep the frame directly above the video (insert-after
                # scrcpy, never above other apps).  Skip when already there.
                ohwnd = int(overlay.winId())
                if ohwnd and u.GetWindow(ohwnd, 3) != hwnd:
                    u.SetWindowPos(ohwnd, hwnd, 0, 0, 0, 0,
                                   SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
            self._qt_ensure_mirror_focus()
            now = time.time()
            if now - getattr(self, "_qt_mirror_last_debug", 0.0) > 0.5:
                self._qt_mirror_last_debug = now
                _debug(
                    f"reposition host_vis={host.isVisible()} "
                    f"rect=({gx},{gy},{dw},{dh}) host_size={host.width()}x{host.height()}"
                )
        except Exception:
            pass

    def _ensure_mirror_focus(self) -> None:
        """Keep keyboard focus on the scrcpy window while the user
        interacts with the phone screen.

        The mirror is a native top-level window: clicking the phone screen
        activates it directly and SDL captures the keyboard.  This guard
        only re-applies focus when the user's cursor is over the mirror,
        our app is foreground, and the scrcpy thread has lost focus to a
        Qt widget.  Never steals focus from other apps or other widgets,
        and never touches scrcpy's window styles, size, or process state.
        """
        hwnd = getattr(self, "_qt_scrcpy_hwnd", 0)
        if not hwnd:
            return
        try:
            u = _user32()
            _mirror_user32_setup()
            if u.GetForegroundWindow() != int(self.winId()):
                return
            tid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(tid))
            if not tid.value:
                return
            info = _GUITHREADINFO()
            info.cbSize = ctypes.sizeof(_GUITHREADINFO)
            if not u.GetGUIThreadInfo(tid.value, ctypes.byref(info)):
                return
            if int(info.hwndFocus or 0) == hwnd:
                return
            active = int(info.hwndActive or 0)
            if active != hwnd and int(info.hwndFocus or 0) != 0:
                return
            pt = _POINT()
            if not u.GetCursorPos(ctypes.byref(pt)):
                return
            rect = _RECT()
            if not u.GetWindowRect(hwnd, ctypes.byref(rect)):
                return
            if not (rect.left <= pt.x <= rect.right
                    and rect.top <= pt.y <= rect.bottom):
                return
            u.SetFocus(hwnd)
            now = time.time()
            if now - getattr(self, "_qt_mirror_focus_log", 0.0) > 2.0:
                self._qt_mirror_focus_log = now
                _debug(f"focus restored to {hwnd}")
        except Exception:
            pass

    def _stop_scrcpy(self) -> None:
        timer = getattr(self, "_qt_scrcpy_timer", None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        process = getattr(self, "_qt_scrcpy_process", None)
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2)
                if process.poll() is None:
                    process.kill()
            except Exception:
                pass
        overlay = getattr(self, "_qt_scrcpy_overlay", None)
        if overlay is not None:
            try:
                overlay.close()
                overlay.deleteLater()
            except Exception:
                pass
        self._qt_scrcpy_timer = None
        self._qt_scrcpy_hwnd = 0
        self._qt_scrcpy_host = None
        self._qt_scrcpy_process = None
        self._qt_scrcpy_overlay = None
        _set_mirror_button_state(self, False)
        self._log("[SCRCPY] Mirror stopped.")

    def _bundle_path(self, *parts):
        return Path(
            getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ).joinpath(*parts)

    MainWindow.start_mirror = start_mirror
    MainWindow._qt_embed_scrcpy = _embed_scrcpy
    MainWindow._qt_reposition_scrcpy = _reposition_scrcpy
    MainWindow._qt_ensure_mirror_focus = _ensure_mirror_focus
    MainWindow._qt_stop_scrcpy = _stop_scrcpy
    MainWindow._qt_bundle_path = _bundle_path
    MainWindow._qt_scrcpy_process = None
    MainWindow._qt_scrcpy_hwnd = 0
    MainWindow._qt_scrcpy_host = None
    MainWindow._qt_scrcpy_timer = None
    MainWindow._qt_scrcpy_overlay = None
    MainWindow._qt_scrcpy_settle_until = 0.0
    MainWindow._qt_dashboard_active = True
    MainWindow._qt_mirror_last_debug = 0.0
    MainWindow._qt_mirror_focus_log = 0.0