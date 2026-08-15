"""Qt scrcpy integration with legacy iPhone-frame geometry."""
from __future__ import annotations

import ctypes
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from tech_qt_phone import DISPLAY_RECT, PHONE_NATIVE


def _find_window(title: str) -> int:
    try:
        return int(ctypes.windll.user32.FindWindowW(None, title) or 0)
    except Exception:
        return 0


def _frame_geometry(host: QWidget) -> tuple[int, int, int, int]:
    """Scale the legacy display opening to the actual Qt phone frame size."""
    width = max(1, host.width())
    height = max(1, host.height())
    sx = width / PHONE_NATIVE[0]
    sy = height / PHONE_NATIVE[1]
    scale = min(sx, sy)
    x = int(DISPLAY_RECT[0] * scale)
    y = int(DISPLAY_RECT[1] * scale)
    w = int(DISPLAY_RECT[2] * scale)
    h = int(DISPLAY_RECT[3] * scale)
    return x, y, w, h


def install_scrcpy(MainWindow) -> None:
    """Install Qt-native scrcpy embedding with a safe external fallback.

    The embedded stream is placed directly inside the Dashboard iPhone frame
    using the same measured screen opening as the legacy overlay implementation.
    """

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
        if host is not None and host.isVisible():
            host_size = (host.width(), host.height())
            _, _, display_w, display_h = _frame_geometry(host)
        else:
            host_size = (353, 735)
            display_w, display_h = 328, 713

        title = f"GeloTech Mirror - {self.serial}"
        try:
            process = subprocess.Popen(
                [
                    exe,
                    "-s", self.serial,
                    "--window-title", title,
                    "--window-width", str(display_w),
                    "--window-height", str(display_h),
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
        self._qt_scrcpy_host_size = host_size
        QTimer.singleShot(250, lambda: self._qt_embed_scrcpy(0))

    def _embed_scrcpy(self, attempt: int = 0) -> None:
        hwnd = _find_window(getattr(self, "_qt_scrcpy_title", ""))
        if not hwnd:
            if attempt < 40:
                QTimer.singleShot(250, lambda: self._qt_embed_scrcpy(attempt + 1))
                return
            process = getattr(self, "_qt_scrcpy_process", None)
            if process is not None and process.poll() is None:
                self._log("[SCRCPY] Embedding was unavailable; external scrcpy window remains active.")
            return

        host = getattr(self, "phone_host", None)
        if host is not None:
            try:
                foreign = QWindow.fromWinId(hwnd)
                container = QWidget.createWindowContainer(foreign, host)
                container.setFocusPolicy(Qt.StrongFocus)
                container.setContentsMargins(0, 0, 0, 0)
                x, y, w, h = _frame_geometry(host)
                container.setGeometry(x, y, w, h)
                container.show()
                container.raise_()

                frame = getattr(self, "phone_frame", None)
                if frame is not None:
                    frame.raise_()
                    frame.setAttribute(Qt.WA_TransparentForMouseEvents, True)

                self._qt_scrcpy_foreign = foreign
                self._qt_scrcpy_container = container
                self._qt_scrcpy_host = host
                self._log(
                    f"[SCRCPY] Mirror fitted to iPhone frame: "
                    f"x={x} y={y} w={w} h={h}."
                )
                self._log("[SCRCPY] Screen mirror embedded in the Qt phone frame.")
                return
            except Exception as exc:
                self._log(
                    f"[SCRCPY] Phone-frame embedding failed; using external window: {exc}"
                )

        # Safe fallback when the phone host is not available.
        try:
            foreign = QWindow.fromWinId(hwnd)
            container = QWidget.createWindowContainer(foreign, self)
            container.setMinimumSize(360, 640)
            container.setFocusPolicy(Qt.StrongFocus)
            dialog = QDialog(self)
            dialog.setWindowTitle("GeloTech Screen Mirror")
            dialog.resize(400, 760)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(8, 8, 8, 8)
            host_label = QLabel("Live phone screen")
            host_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(host_label)
            layout.addWidget(container, 1)
            dialog.finished.connect(lambda _result: self._qt_stop_scrcpy())
            self._qt_scrcpy_foreign = foreign
            self._qt_scrcpy_container = container
            self._qt_scrcpy_dialog = dialog
            dialog.show()
            container.setFocus()
            self._log("[SCRCPY] Screen mirror embedded in fallback window.")
        except Exception as exc:
            self._log(
                f"[SCRCPY] Foreign-window embedding failed; keeping external window: {exc}"
            )

    def _stop_scrcpy(self) -> None:
        process = getattr(self, "_qt_scrcpy_process", None)
        dialog = getattr(self, "_qt_scrcpy_dialog", None)
        container = getattr(self, "_qt_scrcpy_container", None)
        if dialog is not None:
            try:
                dialog.blockSignals(True)
                dialog.close()
            except Exception:
                pass
        if container is not None:
            try:
                container.setParent(None)
                container.deleteLater()
            except Exception:
                pass
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
            except Exception:
                pass
        self._qt_scrcpy_process = None
        self._qt_scrcpy_dialog = None
        self._qt_scrcpy_container = None
        self._qt_scrcpy_foreign = None
        self._qt_scrcpy_host = None
        self._log("[SCRCPY] Mirror stopped.")

    def _bundle_path(self, *parts):
        import os
        import sys
        return Path(
            getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        ).joinpath(*parts)

    MainWindow.start_mirror = start_mirror
    MainWindow._qt_embed_scrcpy = _embed_scrcpy
    MainWindow._qt_stop_scrcpy = _stop_scrcpy
    MainWindow._qt_bundle_path = _bundle_path
    MainWindow._qt_scrcpy_process = None
    MainWindow._qt_scrcpy_dialog = None
    MainWindow._qt_scrcpy_container = None
    MainWindow._qt_scrcpy_foreign = None
    MainWindow._qt_scrcpy_host = None
    MainWindow._qt_scrcpy_host_size = None
