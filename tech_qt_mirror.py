"""Qt scrcpy integration using the legacy embedded child-window model.

Ports the legacy GeloTech mirror behavior into the Qt shell (see
tech_phone_mirror_embedded.py in the legacy repo):
- scrcpy is launched borderless, then reparented with SetParent into the
  phone widget and restyled as WS_CHILD: the video lives INSIDE the mockup
  as a real child window of the phone widget
- the iPhone bezel stays a normal Qt-rendered widget: its transparent
  display opening lets the native child show through, so the stream is
  embedded in the Dashboard phone screen (docs/SCRCPY_GUIDE.md check #2)
- rounded-corner clipping of the child window so the square native surface
  cannot bleed through the frame's rounded opening
- parent-relative coordinates only: no global screen math, so the mirror
  can never drift outside the mockup
- Screen Mirror button acts as a toggle (Screen Mirror <-> Stop Mirror)
- 50ms monitor keeps the child glued to the display opening and re-applies
  the rounded clip
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

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
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


def _embed(hwnd: int, parent: int, x: int, y: int, width: int, height: int) -> bool:
    """Convert the top-level scrcpy window into a real child of the phone
    widget and position it at the display opening (parent-relative)."""
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
        u.SetWindowLongW(hwnd, GWL_EXSTYLE,
                         ex & ~(WS_EX_TOPMOST | WS_EX_APPWINDOW))
        u.SetParent(hwnd, parent)
        u.SetWindowPos(hwnd, HWND_TOP, int(x), int(y), int(width), int(height),
                       SWP_NOACTIVATE | SWP_SHOWWINDOW)
        return True
    except Exception:
        return False


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

        # Parent-relative size only; position is applied by the embed step.
        dx, dy, dw, dh = _display_geometry(host)
        title = f"GeloTech Mirror - {self.serial}"
        _debug(
            f"launch host={type(host).__name__} obj={host.objectName()} "
            f"vis={host.isVisible()} win_vis={self.isVisible()} "
            f"geom={host.geometry().getRect()} dpr={host.devicePixelRatioF()} "
            f"display=({dx},{dy},{dw},{dh})"
        )

        try:
            process = subprocess.Popen(
                [
                    exe,
                    "-s", self.serial,
                    "--window-title", title,
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
            # Same stacking rule as start_mirror: the video child must live
            # inside the bezel image widget, not below it.
            host = getattr(self, "phone_image", None) or host
            # Force a real native window on the phone widget so the scrcpy
            # window can become its child (Qt otherwise keeps it pure-Qt).
            host.setAttribute(Qt.WA_NativeWindow, True)
            parent = int(host.winId())
            dx, dy, dw, dh = _display_geometry(host)
            ok = _embed(hwnd, parent, dx, dy, dw, dh)
            _clip_scrcpy_window(hwnd, dw, dh, _clip_radius(host))
            self._qt_scrcpy_hwnd = hwnd
            self._qt_scrcpy_host = host
            _debug(
                f"embed hwnd={hwnd} parent={parent} ok={ok} "
                f"rect=({dx},{dy},{dw},{dh}) host_size={host.width()}x{host.height()}"
            )
            if not ok:
                self._log("[SCRCPY] Embedding failed; leaving native scrcpy window active.")
                return
            self._log(
                f"[SCRCPY] Video surface embedded inside iPhone frame: "
                f"x={dx} y={dy} w={dw} h={dh}."
            )
            self._log("[SCRCPY] Live phone video active inside Dashboard phone screen.")
            self._qt_scrcpy_timer = QTimer(self)
            self._qt_scrcpy_timer.timeout.connect(self._qt_reposition_scrcpy)
            self._qt_scrcpy_timer.start(50)
        except Exception as exc:
            self._log(f"[SCRCPY] Native mirror positioning failed: {exc}")
            _debug(f"embed EXC {exc!r}")

    def _reposition_scrcpy(self) -> None:
        hwnd = getattr(self, "_qt_scrcpy_hwnd", 0)
        host = getattr(self, "_qt_scrcpy_host", None)
        if not hwnd or host is None:
            return
        try:
            dx, dy, dw, dh = _display_geometry(host)
            u = _user32()
            u.SetWindowPos(hwnd, HWND_TOP, int(dx), int(dy), int(dw), int(dh),
                           SWP_NOACTIVATE | SWP_SHOWWINDOW)
            _clip_scrcpy_window(hwnd, dw, dh, _clip_radius(host))
            self._qt_ensure_mirror_focus()
            now = time.time()
            if now - getattr(self, "_qt_mirror_last_debug", 0.0) > 0.5:
                self._qt_mirror_last_debug = now
                _debug(
                    f"reposition host_vis={host.isVisible()} "
                    f"rect=({dx},{dy},{dw},{dh}) host_size={host.width()}x{host.height()}"
                )
        except Exception:
            pass

    def _ensure_mirror_focus(self) -> None:
        """Keep keyboard focus on the embedded scrcpy child while the user
        interacts with the phone screen.

        Clicking a native child of another process activates the parent
        top-level window, and the host app can then move focus back to one
        of its own widgets, so the scrcpy (SDL) window never receives
        WM_SETFOCUS and scrcpy drops keyboard input.  Re-apply focus only
        when the user's cursor is over the mirror and the mirror's thread
        has lost it (its active window is the child, or it has no focus at
        all).  Never steals focus from other apps or other widgets, and
        never touches scrcpy's window styles, size, or process state.
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
        self._qt_scrcpy_timer = None
        self._qt_scrcpy_hwnd = 0
        self._qt_scrcpy_host = None
        self._qt_scrcpy_process = None
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
    MainWindow._qt_mirror_last_debug = 0.0
    MainWindow._qt_mirror_focus_log = 0.0