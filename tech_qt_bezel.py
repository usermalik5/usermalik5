"""Small compatibility layer for the Qt phone bezel over scrcpy."""
from __future__ import annotations


def install_bezel_alias(MainWindow):
    original = MainWindow._build_shell

    def build_shell(self):
        original(self)
        image = getattr(self, "phone_image", None)
        host = getattr(self, "phone_host", None)
        if image is not None and host is not None:
            # tech_qt_mirror raises phone_frame after embedding the foreign
            # scrcpy window. Point that contract at the actual bezel image.
            self.phone_frame = image
            image.raise_()

    MainWindow._build_shell = build_shell
