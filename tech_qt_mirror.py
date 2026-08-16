"""Qt scrcpy integration using the proven native-window + iPhone overlay model."""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget

from tech_qt_phone import DISPLAY_RECT, PHONE_NATIVE, PHONE_DISPLAY_SIZE


# Win32 constants used to keep the native scrcpy surface borderless and above
# the Qt application while remaining visually constrained to the phone.
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_POPUP = 0x80000000
GWL_STYLE = -16
GWL_EXSTYLE = -20


def _find_window(title: str) -> int:
    try:
        return int(ctypes.windll.user32.FindWindowW(None, title) or 0)
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
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    style &= ~WS_POPUP
    style |= 0x40000000  # WS_CHILD-like borderless child-compatible style.
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    ex |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    ex &= ~WS_EX_APPWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
    user32.SetWindowPos(
        hwnd,
        HWND_TOPMOST,
        int(x), int(y), int(w), int(h),
        SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )


def _make_overlay(self, phone_host: QWidget):
    """Create a click-through translucent top-level iPhone bezel overlay."""
    overlay = QWidget(None, Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
    overlay.setAttribute(Qt.WA_TranslucentBackground, True)
    overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    overlay.setAttribute(Qt.WA_ShowWithoutActivating, True)
    overlay.setWindowFlag(Qt.WindowDoesNotAcceptFocus, True)
    overlay.setFixedSize(*PHONE_DISPLAY_SIZE)

    from PySide6.QtWidgets import QLabel
    frame = QLabel(overlay)
    frame.setGeometry(0, 0, *PHONE_DISPLAY_SIZE)
    frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    frame.setScaledContents(True)
    image = Path(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))) / "assets" / "phone_devices" / "iPhone17_P_PM_CosmicOrange@2x.png"
    pixmap = QPixmap(str(image))
    if not pixmap.isNull():
        pixmap.setDevicePixelRatio(1.0)
        frame.setPixmap(pixmap.scaled(*PHONE_DISPLAY_SIZE, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

    def reposition() -> None:
        if not phone_host.isVisible() or not overlay.isVisible():
            return
        pos = phone_host.mapToGlobal(phone_host.rect().topLeft())
        overlay.move(pos)
        x, y, w, h = _frame_geometry(phone_host)
        # The frame overlay remains at the full phone-frame size; scrcpy only
        # occupies the measured transparent display opening inside it.
        hwnd = getattr(self, "_qt_scrcpy_hwnd", 0)
        if hwnd:
            display_pos = (pos.x() + x, pos.y() + y)
            _set_native_window_geometry(hwnd, display_pos[0], display_pos[1], w, h)

    overlay._reposition = reposition
    overlay.show()
    reposition()
    return overlay


def install_scrcpy(MainWindow) -> None:
    """Install reliable native scrcpy mirroring using the legacy overlay model."""

    def start_mirror(self) -> None:
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
            _set_native_window_geometry(hwnd, pos.x() + x, pos.y() + y, w, h)
            overlay = _make_overlay(self, host)
            self._qt_scrcpy_hwnd = hwnd
            self._qt_scrcpy_overlay = overlay
            self._qt_scrcpy_host = host
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
        if host is None or overlay is None or not host.isVisible():
            return
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
            except Exception:
                pass
        self._qt_scrcpy_timer = None
        self._qt_scrcpy_overlay = None
        self._qt_scrcpy_hwnd = 0
        self._qt_scrcpy_host = None
        self._qt_scrcpy_process = None
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
