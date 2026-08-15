"""Small compatibility adapters for the Qt visual-parity shell."""
from __future__ import annotations


def install_qt_compat(MainWindow: type) -> None:
    """Keep legacy MainWindow runtime contracts valid after visual shell replacement."""
    if getattr(MainWindow, "_gelotech_compat_installed", False):
        return

    original_scan_devices = MainWindow._scan_devices
    original_open_login = MainWindow._open_login

    def scan_devices(self, *args, **kwargs):
        # The parity shell renames these presentation widgets but the migrated
        # device/cache code still writes to the legacy attributes.
        if hasattr(self, "device_inline"):
            self.device_label = self.device_inline
        if hasattr(self, "cleaner_status"):
            self.phone_status = self.cleaner_status
        return original_scan_devices(self, *args, **kwargs)

    def open_login(self, *args, **kwargs):
        # Match the legacy flow: never show the dashboard behind the sign-in box.
        self.hide()
        result = original_open_login(self, *args, **kwargs)
        if self.current_user:
            self.show()
        return result

    MainWindow._scan_devices = scan_devices
    MainWindow._open_login = open_login
    MainWindow._gelotech_compat_installed = True
