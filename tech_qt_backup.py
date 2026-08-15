"""Qt APK backup/restore dialog using the existing GeloTech storage location."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from tech_common import get_settings_dir


def install_backup_restore(MainWindow) -> None:
    """Install the full APK backup/restore dialog on MainWindow."""

    def backup_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("APK Backup / Restore")
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("APK backups are stored in the GeloTechTool AppData folder."))

        files = QListWidget()
        files.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(files, 1)

        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh")
        backup = QPushButton("Backup Checked Apps")
        restore = QPushButton("Restore Selected APK")
        close = QPushButton("Close")
        for button in (refresh, backup, restore, close):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        def backup_dir() -> Path:
            path = Path(get_settings_dir()) / "apk_backups"
            path.mkdir(parents=True, exist_ok=True)
            return path

        def load_files() -> None:
            files.clear()
            for path in sorted(backup_dir().glob("*.apk")):
                item = QListWidgetItem(path.name)
                item.setToolTip(str(path))
                files.addItem(item)

        def do_backup() -> None:
            packages = self._checked_packages()
            if not packages:
                QMessageBox.information(dialog, "Backup", "Check the apps you want to back up in the App Cleaner list first.")
                return
            from tech_qt_cleaner import _backup_packages
            _backup_packages(self, packages)
            QMessageBox.information(dialog, "Backup", f"Started backup for {len(packages)} checked app(s).")
            load_files()

        def do_restore() -> None:
            item = files.currentItem()
            if item is None:
                QMessageBox.information(dialog, "Restore", "Select an APK backup first.")
                return
            source = backup_dir() / item.text()
            if not self.serial:
                self._scan_devices()
            if not self.serial:
                QMessageBox.warning(dialog, "Restore", "Connect a device first.")
                return
            confirm = QMessageBox.question(
                dialog,
                "Restore APK",
                f"Install {source.name} on the connected device?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return
            result = self._adb(["-s", self.serial, "install", "-r", str(source)], 180)
            output = (result.stdout or "") + (result.stderr or "")
            if result.returncode == 0 and "Success" in output:
                self._log(f"[GeloTech] Restored: {source.name}")
                QMessageBox.information(dialog, "Restore", f"Restored {source.name}.")
                self.refresh_apps(getattr(self, "_qt_list_mode", "all"))
            else:
                QMessageBox.warning(dialog, "Restore", output.strip() or "ADB install failed.")

        refresh.clicked.connect(load_files)
        backup.clicked.connect(do_backup)
        restore.clicked.connect(do_restore)
        close.clicked.connect(dialog.accept)
        load_files()
        dialog.exec()

    MainWindow._backup_help = backup_dialog
