"""Qt ADB connection repair workflow for the migration."""
from __future__ import annotations

import threading


def install_driver_workflow(MainWindow) -> None:
    """Replace the placeholder driver button with the tested ADB reset flow."""

    def action_fix_drivers(self) -> None:
        if getattr(self, "_driver_thread", None) and self._driver_thread.is_alive():
            return
        self._driver_thread = threading.Thread(target=self._repair, daemon=True)
        self._driver_thread.start()

    def _repair(self) -> None:
        try:
            self._log("[ADB] Stopping the current ADB server...")
            self._adb(["kill-server"], 10)
            self._log("[ADB] Starting a fresh ADB server...")
            started = self._adb(["start-server"], 15)
            if started.returncode != 0:
                raise RuntimeError((started.stderr or started.stdout or "ADB start-server failed.").strip())
            self._log("[ADB] ADB server restarted successfully.")
            if self.serial:
                self._log(f"[ADB] Rechecking device {self.serial}...")
                self._scan_devices()
                self._log("[ADB] Device check complete.")
            else:
                self._log("[ADB] No authorized device is currently connected.")
        except Exception as exc:
            self._log(f"[ADB ERROR] Driver/connection repair failed: {exc}")

    MainWindow.action_fix_drivers = action_fix_drivers
    MainWindow._qt_repair_drivers = _repair
