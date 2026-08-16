"""Qt phone-frame adapter using the existing Dashboard iPhone mockup."""
from __future__ import annotations

from PySide6.QtWidgets import QLabel

# Native dimensions measured from the legacy iPhone frame asset.
PHONE_NATIVE = (396, 824)
DISPLAY_RECT = (14, 12, 368, 800)
PHONE_DISPLAY_SIZE = (353, 735)


def install_phone_frame(MainWindow: type) -> None:
    """Expose the existing Dashboard phone mockup as the scrcpy host.

    The visual-parity dashboard already owns the single iPhone frame. The
    mirror implementation positions the real native scrcpy window against
    this widget and draws a transparent bezel overlay over it. Do not create
    another phone panel here: doing so would produce a duplicate/floating
    phone when scrcpy starts.
    """
    if getattr(MainWindow, "_gelotech_phone_frame_installed", False):
        return

    original_build_shell = MainWindow._build_shell

    def build_shell(self) -> None:
        original_build_shell(self)
        page = self.pages[0] if getattr(self, "pages", None) else None
        if page is None or page.layout() is None or page.layout().count() < 1:
            return

        phone_panel = page.layout().itemAt(0).widget()
        if phone_panel is None:
            return

        frame = phone_panel.findChild(QLabel, "phoneMockup")
        if frame is None:
            # Keep the shell usable even if the visual-parity implementation
            # changes its object name later.
            frame = phone_panel.findChild(QLabel)

        if frame is None:
            return

        self.phone_host = frame
        self.phone_frame = frame
        self.phone_image = frame
        self._gelotech_phone_frame_installed = True

    MainWindow._build_shell = build_shell
    MainWindow._gelotech_phone_frame_installed = True
