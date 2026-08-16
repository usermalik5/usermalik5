"""Automatic Qt app-list refresh when an ADB device connects or reconnects."""
from __future__ import annotations

from PySide6.QtCore import QTimer


def install_auto_refresh(MainWindow) -> None:
    """Complete the legacy-style device lifecycle without reloading on every poll.

    The existing MainWindow._scan_devices method remains responsible for ADB
    detection, device metadata, icon preparation, and mirror startup. This
    wrapper adds the missing transition: once the selected serial changes from
    disconnected/another device to a connected device, refresh the installed
    package list automatically.
    """
    if getattr(MainWindow, "_gelotech_auto_refresh_installed", False):
        return

    original_scan = MainWindow._scan_devices

    def scan_devices(self) -> None:
        previous = getattr(self, "_auto_refresh_last_serial", None)
        original_scan(self)
        current = getattr(self, "serial", None)
        self._auto_refresh_last_serial = current

        # A real connection transition only. The normal 3-second polling loop
        # must not repopulate the table repeatedly while the same phone remains
        # connected.
        if current and current != previous:
            QTimer.singleShot(100, self._auto_refresh_apps_after_connect)

    def refresh_after_connect(self) -> None:
        serial = getattr(self, "serial", None)
        if not serial:
            return
        try:
            self._log(f"[GeloTech] Device ready: {serial}. Loading apps automatically...")
            self.refresh_apps("all")
            if hasattr(self, "cleaner_status"):
                self.cleaner_status.setText(
                    f"{self.table.rowCount()} packages loaded automatically."
                )
        except Exception as exc:
            self._log(f"[GeloTech] Automatic app-list refresh failed: {exc}")

    MainWindow._scan_devices = scan_devices
    MainWindow._auto_refresh_apps_after_connect = refresh_after_connect
    MainWindow._auto_refresh_last_serial = None
    MainWindow._gelotech_auto_refresh_installed = True
