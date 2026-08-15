"""Qt scrcpy integration with a safe foreign-window fallback."""
from __future__ import annotations

import ctypes
import shutil
import subprocess

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QWindow
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget


def _find_window(title: str) -> int:
    try:
        hwnd = ctypes.windll.user32.FindWindowW(None, title)
        return int(hwnd or 0)
    except Exception:
        return 0


def install_scrcpy(MainWindow) -> None:
    """Install Qt-native foreign-window embedding with external fallback."""

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
            ):
                if candidate.is_file():
                    exe = str(candidate)
                    break
        if not exe:
            self._log("[SCRCPY] scrcpy executable not found in PATH/bundle.")
            return

        title = f"GeloTech Mirror - {self.serial}"
        try:
            process = subprocess.Popen(
                [exe, "-s", self.serial, "--window-title", title],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
        except Exception as exc:
            self._log(f"[SCRCPY] Failed to start mirror: {exc}")
            return

        self._qt_scrcpy_process = process
        self._qt_scrcpy_title = title
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
            host = QLabel("Live phone screen")
            host.setAlignment(Qt.AlignCenter)
            layout.addWidget(host)
            layout.addWidget(container, 1)
            dialog.finished.connect(lambda _result: self._qt_stop_scrcpy())
            self._qt_scrcpy_foreign = foreign
            self._qt_scrcpy_container = container
            self._qt_scrcpy_dialog = dialog
            dialog.show()
            container.setFocus()
            self._log("[SCRCPY] Screen mirror embedded in the Qt window.")
        except Exception as exc:
            self._log(f"[SCRCPY] Foreign-window embedding failed; keeping external window: {exc}")

    def _stop_scrcpy(self) -> None:
        process = getattr(self, "_qt_scrcpy_process", None)
        dialog = getattr(self, "_qt_scrcpy_dialog", None)
        if dialog is not None:
            try:
                dialog.blockSignals(True)
                dialog.close()
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
        self._log("[SCRCPY] Mirror stopped.")

    def _bundle_path(self, *parts):
        import os
        import sys
        from pathlib import Path
        return Path(getattr(sys, "_MEIPASS", os.path.dirname(__file__))).joinpath(*parts)

    MainWindow.start_mirror = start_mirror
    MainWindow._qt_embed_scrcpy = _embed_scrcpy
    MainWindow._qt_stop_scrcpy = _stop_scrcpy
    MainWindow._qt_bundle_path = _bundle_path
    MainWindow._qt_scrcpy_process = None
    MainWindow._qt_scrcpy_dialog = None
    MainWindow._qt_scrcpy_container = None
    MainWindow._qt_scrcpy_foreign = None
