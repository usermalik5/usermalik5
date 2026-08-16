"""Qt scrcpy integration using the proven native-window + iPhone overlay model.

Ports the legacy GeloTech mirror behavior into the Qt shell:
- native scrcpy top-level window positioned at the phone display opening
- transparent iPhone bezel overlay above it (click-through)
- rounded-corner clipping of the scrcpy surface so square corners do not
  bleed through the frame's rounded opening
- scrcpy + overlay become *owned* windows of the GeloTech main window, so
  they minimize/hide with the app and never escape as independent windows
- Screen Mirror button acts as a toggle (Screen Mirror <-> Stop Mirror)
- 50ms monitor keeps both windows glued and raises them in the correct
  order (scrcpy first, overlay on top)
"""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QPushButton, QWidget

from tech_qt_phone import DISPLAY_RECT, PHONE_NATIVE, PHONE_DISPLAY_SIZE


# Win32 constants (same values as the legacy mirror subsystem).
HWND_TOP = 0
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
GWL_EXSTYLE = -20
GWLP_HWNDPARENT = -8

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


def _frame_geometry(host: QWidget) -> tuple[int, int, int, int]:
    """Return the legacy display opening scaled to the Qt phone frame."""
    width = max(1, host.width())
    height = max(1, host.height())
    sx = width / PHONE_NATIVE[0]
    sy = height / PHONE_NATIVE[1]
    scale = min(sx, sy)
    return (
        int(DISPLAY_RECT[0] * scale),
        int(DISPLAY_RECT[1] * scale),
        int(DISPLAY_RECT[2] * scale),
        int(DISPLAY_RECT[3] * scale),
    )


def _set_native_window_geometry(hwnd: int, x: int, y: int, w: int, h: int) -> None:
    """Position the real scrcpy top-level window without reparenting it."""
    u = _user32()
    ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    ex &= ~WS_EX_APPWINDOW
    u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    u.SetWindowPos(
        hwnd,
        HWND_TOP,
        int(x), int(y), int(w), int(h),
        SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )


def _set_owner(hwnd: int, owner: int) -> None:
    """Make hwnd an owned window of the GeloTech main window.

    Ownership (not SetParent) keeps scrcpy a native top-level window so its
    rendering/input behavior is preserved, while Windows now minimizes and
    hides it together with the application and closes it when the app exits.
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


def _clip_scrcpy_window(hwnd: int, width: int, height: int) -> None:
    """Clip the native scrcpy window to the frame's rounded display opening.

    SetWindowRgn only changes the visible shape of the top-level window; it
    does not alter the scrcpy rendering surface or mouse coordinates.
    """
    if not hwnd or width <= 0 or height <= 0:
        return
    try:
        gdi = _gdi32()
        u = _user32()
        radius = max(2, int(DISPLAY_CORNER_RADIUS + 0.5))
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
            if not u.SetWindowRgn(hwnd, region, True):
                gdi.DeleteObject(region)
    except Exception:
        pass


def _raise_mirror_windows(self) -> None:
    """Raise scrcpy first, then the bezel overlay on top of it."""
    u = _user32()
    hwnd = getattr(self, "_qt_scrcpy_hwnd", 0)
    if hwnd:
        try:
            u.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
                           SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            pass
    overlay = getattr(self, "_qt_scrcpy_overlay", None)
    if overlay is not None:
        try:
            ohwnd = int(overlay.winId())
            u.SetWindowPos(ohwnd, HWND_TOP, 0, 0, 0, 0,
                           SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception:
            try:
                overlay.raise_()
            except Exception:
                pass


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


def _make_overlay(self, phone_host: QWidget):
    """Create a click-through translucent top-level iPhone bezel overlay."""
    overlay = QWidget(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
    overlay.setAttribute(Qt.WA_TranslucentBackground, True)
    overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    overlay.setAttribute(Qt.WA_ShowWithoutActivating, True)
    overlay.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
    try:
        overlay.setWindowFlag(Qt.WindowTransparentForInput, True)
    except AttributeError:
        pass
    overlay.setFixedSize(*PHONE_DISPLAY_SIZE)

    from PySide6.QtWidgets import QLabel
    frame = QLabel(overlay)
    frame.setGeometry(0, 0, *PHONE_DISPLAY_SIZE)
    frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    frame.setScaledContents(True)
    image = Path(
        getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    ) / "assets" / "phone_devices" / "iPhone17_P_PM_CosmicOrange@2x.png"
    pixmap = QPixmap(str(image))
    if not pixmap.isNull():
        pixmap.setDevicePixelRatio(1.0)
        frame.setPixmap(
            pixmap.scaled(
                *PHONE_DISPLAY_SIZE,
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def reposition() -> None:
        if not phone_host.isVisible() or not overlay.isVisible():
            return
        pos = phone_host.mapToGlobal(phone_host.rect().topLeft())
        overlay.move(pos)
        x, y, w, h = _frame_geometry(phone_host)
        hwnd = getattr(self, "_qt_scrcpy_hwnd", 0)
        if hwnd:
            _set_native_window_geometry(hwnd, pos.x() + x, pos.y() + y, w, h)
            _clip_scrcpy_window(hwnd, w, h)
        _raise_mirror_windows(self)

    overlay._reposition = reposition
    overlay.show()
    reposition()
    return overlay


def install_scrcpy(MainWindow) -> None:
    """Install reliable native scrcpy mirroring using the legacy overlay model."""

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

        x, y, w, h = _frame_geometry(host)
        global_pos = host.mapToGlobal(host.rect().topLeft())
        screen_x = global_pos.x() + x
        screen_y = global_pos.y() + y
        title = f"GeloTech Mirror - {self.serial}"

        try:
            process = subprocess.Popen(
                [
                    exe,
                    "-s", self.serial,
                    "--window-title", title,
                    "--window-width", str(w),
                    "--window-height", str(h),
                    "--window-x", str(screen_x),
                    "--window-y", str(screen_y),
                    "--window-borderless",
                    "--always-on-top",
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
        self._qt_scrcpy_overlay = None
        _set_mirror_button_state(self, True)
        self._log(
            f"[SCRCPY] Target phone display: x={screen_x} y={screen_y} "
            f"w={w} h={h}."
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
            x, y, w, h = _frame_geometry(host)
            pos = host.mapToGlobal(host.rect().topLeft())
            self._qt_scrcpy_hwnd = hwnd
            _set_native_window_geometry(hwnd, pos.x() + x, pos.y() + y, w, h)
            _clip_scrcpy_window(hwnd, w, h)
            overlay = _make_overlay(self, host)
            self._qt_scrcpy_overlay = overlay
            self._qt_scrcpy_host = host
            # Own both native windows to the app so they hide/minimize/close
            # together with GeloTech instead of floating as independent
            # always-on-top windows.
            owner = int(self.winId())
            _set_owner(hwnd, owner)
            try:
                _set_owner(int(overlay.winId()), owner)
            except Exception:
                pass
            self._log(
                f"[SCRCPY] Video surface positioned inside iPhone frame: "
                f"x={x} y={y} w={w} h={h}."
            )
            self._log("[SCRCPY] Live phone video active with iPhone bezel overlay.")
            self._qt_scrcpy_timer = QTimer(self)
            self._qt_scrcpy_timer.timeout.connect(self._qt_reposition_scrcpy)
            self._qt_scrcpy_timer.start(50)
        except Exception as exc:
            self._log(f"[SCRCPY] Native mirror positioning failed: {exc}")

    def _reposition_scrcpy(self) -> None:
        host = getattr(self, "_qt_scrcpy_host", None)
        overlay = getattr(self, "_qt_scrcpy_overlay", None)
        hwnd = getattr(self, "_qt_scrcpy_hwnd", 0)
        if host is None or overlay is None or not host.isVisible():
            return
        if hwnd:
            try:
                from PySide6.QtCore import Qt as _Qt
                if not host.isVisible():
                    return
            except Exception:
                pass
        overlay._reposition()

    def _stop_scrcpy(self) -> None:
        timer = getattr(self, "_qt_scrcpy_timer", None)
        if timer is not None:
            timer.stop()
            timer.deleteLater()
        overlay = getattr(self, "_qt_scrcpy_overlay", None)
        if overlay is not None:
            try:
                overlay.close()
                overlay.deleteLater()
            except Exception:
                pass
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
        self._qt_scrcpy_overlay = None
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
    MainWindow._qt_stop_scrcpy = _stop_scrcpy
    MainWindow._qt_bundle_path = _bundle_path
    MainWindow._qt_scrcpy_process = None
    MainWindow._qt_scrcpy_hwnd = 0
    MainWindow._qt_scrcpy_overlay = None
    MainWindow._qt_scrcpy_host = None
    MainWindow._qt_scrcpy_timer = None