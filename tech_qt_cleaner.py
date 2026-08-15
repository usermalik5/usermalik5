"""Qt App Cleaner parity helpers.

This module owns Qt-specific presentation and ADB command wiring for the
cleaner. The package database remains the existing shared source of truth.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QTableWidgetItem,
)

from tech_common import get_settings_dir, load_apps_cache


LEVELS = ("Recommended", "Advanced", "Expert", "Unsafe")


def _load_exclusions() -> tuple[set[str], set[str]]:
    path = Path(get_settings_dir()) / "exclusions.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return set(), set()
    clean = set(map(str, data.get("clean_excluded", data.get("clean", [])) or []))
    uninstall = set(map(str, data.get("uninstall_excluded", data.get("uninstall", [])) or []))
    return clean, uninstall


def _save_exclusions(clean: set[str], uninstall: set[str]) -> None:
    path = Path(get_settings_dir()) / "exclusions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "clean_excluded": sorted(clean),
                "uninstall_excluded": sorted(uninstall),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _record(db: dict, package: str, user_packages: set[str], clean: set[str], uninstall: set[str]) -> dict:
    rec = db.get(package, {}) if isinstance(db, dict) else {}
    return {
        "id": package,
        "label": rec.get("label") or rec.get("description") or package,
        "system": package not in user_packages,
        "excluded_clean": package in clean,
        "excluded_uninstall": package in uninstall,
        "removal": str(rec.get("removal") or "Unknown"),
        "description": str(rec.get("description") or "No description available."),
        "category": str(rec.get("category") or "Other"),
        "source": str(rec.get("source") or "Unknown"),
        "risk": str(rec.get("risk") or "unknown"),
    }


def _installed_packages(window, mode: str = "all") -> list[str]:
    flags = {"user": "-3", "system": "-s", "disabled": "-d"}
    args = ["-s", window.serial, "shell", "pm", "list", "packages"]
    if mode in flags:
        args.append(flags[mode])
    result = window._adb(args, 30)
    return sorted(
        line.split(":", 1)[1].strip()
        for line in result.stdout.splitlines()
        if line.startswith("package:") and ":" in line
    )


def _user_packages(window) -> set[str]:
    try:
        return set(_installed_packages(window, "user"))
    except Exception:
        return set()


def _confirm_yes(window, title: str, message: str) -> bool:
    dialog = QDialog(window)
    dialog.setWindowTitle(title)
    layout = QFormLayout(dialog)
    label = QLabel(f"{message}\n\nType YES to continue:")
    label.setWordWrap(True)
    entry = QLineEdit()
    entry.setPlaceholderText("YES")
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setEnabled(False)
    entry.textChanged.connect(
        lambda text: buttons.button(QDialogButtonBox.Ok).setEnabled(text.strip() == "YES")
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addRow(label)
    layout.addRow(entry)
    layout.addRow(buttons)
    entry.setFocus()
    return dialog.exec() == QDialog.Accepted


def _checked_packages(window) -> list[str]:
    result: list[str] = []
    for row in range(window.table.rowCount()):
        name_item = window.table.item(row, 0)
        pkg_item = window.table.item(row, 1)
        if name_item is None or pkg_item is None:
            continue
        if name_item.checkState() == Qt.Checked:
            result.append(pkg_item.text())
    return result


def _run_packages(window, packages: list[str], operation: str) -> None:
    if not packages or not window.serial:
        return

    def worker() -> None:
        ok = 0
        fail = 0
        for package in packages:
            try:
                if operation == "disable":
                    args = ["-s", window.serial, "shell", "pm", "disable-user", "--user", "0", package]
                elif operation == "uninstall":
                    args = ["-s", window.serial, "shell", "pm", "uninstall", "--user", "0", package]
                elif operation == "clear":
                    args = ["-s", window.serial, "shell", "pm", "clear", "--user", "0", package]
                else:
                    raise ValueError(operation)
                result = window._adb(args, 30)
                text = (result.stdout or "") + (result.stderr or "")
                success = result.returncode == 0 and (
                    operation == "clear" or "Success" in text or "new state: disabled" in text
                )
                if success:
                    ok += 1
                    window._log(f"[GeloTech] {operation.title()}: {package}")
                else:
                    fail += 1
                    window._log(f"[GeloTech ERROR] {operation.title()} failed for {package}: {text.strip()}")
            except Exception as exc:
                fail += 1
                window._log(f"[GeloTech ERROR] {operation.title()} {package}: {exc}")
        window._log(f"[GeloTech] {operation.title()} finished: {ok} succeeded, {fail} failed.")
        window.refresh_apps(getattr(window, "_qt_list_mode", "all"))

    threading.Thread(target=worker, daemon=True).start()


def _backup_packages(window, packages: list[str]) -> None:
    if not packages or not window.serial:
        return
    backup_dir = Path(get_settings_dir()) / "apk_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    def worker() -> None:
        saved = 0
        failed = 0
        for package in packages:
            try:
                result = window._adb(["-s", window.serial, "shell", "pm", "path", package], 20)
                paths = [line[8:].strip() for line in result.stdout.splitlines() if line.startswith("package:")]
                if not paths:
                    failed += 1
                    window._log(f"[GeloTech ERROR] Backup APK not found: {package}")
                    continue
                destination = backup_dir / f"{package}.apk"
                pulled = window._adb(["-s", window.serial, "pull", paths[0], str(destination)], 120)
                if pulled.returncode == 0 and destination.is_file():
                    saved += 1
                    window._log(f"[GeloTech] Backed up: {package}")
                else:
                    failed += 1
                    window._log(f"[GeloTech ERROR] Backup failed: {package}")
            except Exception as exc:
                failed += 1
                window._log(f"[GeloTech ERROR] Backup {package}: {exc}")
        window._log(f"[GeloTech] Backup finished: {saved} saved, {failed} failed.")

    threading.Thread(target=worker, daemon=True).start()


def _restore_dialog(window) -> None:
    backup_dir = Path(get_settings_dir()) / "apk_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(backup_dir.glob("*.apk"))
    if not files:
        QMessageBox.information(window, "Restore / Backup", "No APK backups are available yet.")
        return
    choices = [p.name for p in files]
    selected, ok = QInputDialog.getItem(window, "Restore APK", "Choose a backup to install:", choices, 0, False)
    if not ok:
        return
    source = backup_dir / selected
    if not _confirm_yes(window, "Restore APK", f"Install {selected} on the connected device?"):
        return
    try:
        result = window._adb(["-s", window.serial, "install", "-r", str(source)], 180)
        output = (result.stdout or "") + (result.stderr or "")
        if result.returncode == 0 and "Success" in output:
            QMessageBox.information(window, "Restore APK", f"Restored {selected}.")
            window.refresh_apps(getattr(window, "_qt_list_mode", "all"))
        else:
            QMessageBox.warning(window, "Restore APK", output.strip() or "ADB install failed.")
    except Exception as exc:
        QMessageBox.warning(window, "Restore APK", str(exc))


def _show_apk_info(window, package: str) -> None:
    try:
        path_result = window._adb(["-s", window.serial, "shell", "pm", "path", package], 20)
        dump = window._adb(["-s", window.serial, "shell", "dumpsys", "package", package], 30)
        text = (path_result.stdout or "") + "\n\n" + (dump.stdout or "")
        dialog = QDialog(window)
        dialog.setWindowTitle(f"APK Info — {package}")
        box = QPlainTextEdit(dialog)
        box.setReadOnly(True)
        box.setPlainText(text.strip() or "No package information returned.")
        layout = QHBoxLayout(dialog)
        layout.addWidget(box)
        dialog.resize(850, 620)
        dialog.exec()
    except Exception as exc:
        QMessageBox.warning(window, "APK Info", str(exc))


def _exclude_checked(window, mode: str) -> None:
    packages = _checked_packages(window)
    if not packages:
        QMessageBox.information(window, "Exclude", "Check the apps you want to exclude first.")
        return
    clean, uninstall = _load_exclusions()
    target = clean if mode == "clean" else uninstall
    target.update(packages)
    _save_exclusions(clean, uninstall)
    window._log(f"[GeloTech] Excluded {len(packages)} app(s) from {mode}.")
    window.refresh_apps(getattr(window, "_qt_list_mode", "all"))


def _table_menu(window, pos) -> None:
    row = window.table.rowAt(pos.y())
    if row < 0:
        return
    package_item = window.table.item(row, 1)
    label_item = window.table.item(row, 0)
    if package_item is None:
        return
    package = package_item.text()
    label = label_item.text() if label_item else package
    menu = QMenu(window)
    menu.addAction("Disable", lambda: _single_action(window, package, "disable", label))
    menu.addAction("Uninstall", lambda: _single_action(window, package, "uninstall", label))
    menu.addAction("Clear App Data", lambda: _single_action(window, package, "clear", label))
    menu.addSeparator()
    menu.addAction("Backup APK", lambda: _backup_packages(window, [package]))
    menu.addSeparator()
    menu.addAction("Exclude from Clean", lambda: _exclude_one(window, package, "clean"))
    menu.addAction("Exclude from Uninstall", lambda: _exclude_one(window, package, "uninstall"))
    menu.addAction("APK Info", lambda: _show_apk_info(window, package))
    checked = _checked_packages(window)
    if checked:
        menu.addSeparator()
        menu.addAction(f"Disable ALL {len(checked)} checked", lambda: _batch_action(window, "disable"))
        menu.addAction(f"Uninstall ALL {len(checked)} checked", lambda: _batch_action(window, "uninstall"))
        menu.addAction(f"Backup ALL {len(checked)} checked", lambda: _backup_packages(window, checked))
    menu.exec(window.table.viewport().mapToGlobal(pos))


def _single_action(window, package: str, operation: str, label: str) -> None:
    messages = {
        "disable": f"Disable {label} ({package}) for the current user?",
        "uninstall": f"Uninstall {label} ({package})? This is only for user/third-party packages.",
        "clear": f"Clear storage/data for {label} ({package})? The app remains installed.",
    }
    if _confirm_yes(window, operation.title(), messages[operation]):
        _run_packages(window, [package], operation)


def _batch_action(window, operation: str) -> None:
    packages = _checked_packages(window)
    if not packages:
        QMessageBox.information(window, operation.title(), "Check at least one app first.")
        return
    if _confirm_yes(window, operation.title(), f"{operation.title()} {len(packages)} checked app(s)?"):
        _run_packages(window, packages, operation)


def _exclude_one(window, package: str, mode: str) -> None:
    clean, uninstall = _load_exclusions()
    (clean if mode == "clean" else uninstall).add(package)
    _save_exclusions(clean, uninstall)
    window._log(f"[GeloTech] Excluded {package} from {mode}.")
    window.refresh_apps(getattr(window, "_qt_list_mode", "all"))


def _add_toolbar_buttons(window) -> None:
    if getattr(window, "_qt_cleaner_toolbar_ready", False):
        return
    window._qt_cleaner_toolbar_ready = True
    bar = window.pages[1].layout().itemAt(0).layout()
    if bar is None:
        return
    for text, op in (("Disable Checked", "disable"), ("Uninstall Checked", "uninstall"), ("Backup Checked", "backup")):
        button = QPushButton(text)
        if op == "backup":
            button.clicked.connect(lambda: _backup_packages(window, _checked_packages(window)))
        else:
            button.clicked.connect(lambda _checked=False, value=op: _batch_action(window, value))
        bar.addWidget(button)


def _filter_dialog(window) -> None:
    dialog = QDialog(window)
    dialog.setWindowTitle("Advanced Filter")
    form = QFormLayout(dialog)
    search = QLineEdit()
    search.setPlaceholderText("App name or package ID")
    level = QComboBox(); level.addItem("Any"); level.addItems(LEVELS)
    scope = QComboBox(); scope.addItems(["All", "User apps", "System apps"])
    category = QComboBox(); category.addItem("Any")
    categories = sorted({str(r.get("category") or "Other") for r in getattr(window, "_qt_rows", {}).values()})
    category.addItems(categories)
    source = QComboBox(); source.addItem("Any")
    sources = sorted({str(r.get("source") or "Unknown") for r in getattr(window, "_qt_rows", {}).values()})
    source.addItems(sources)
    form.addRow("Search", search)
    form.addRow("UAD level", level)
    form.addRow("Device scope", scope)
    form.addRow("Category", category)
    form.addRow("Source", source)
    buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
    form.addRow(buttons)

    def apply() -> None:
        needle = search.text().strip().lower()
        wanted_level = level.currentText()
        wanted_scope = scope.currentText()
        wanted_category = category.currentText()
        wanted_source = source.currentText()
        shown = 0
        for row in range(window.table.rowCount()):
            package_item = window.table.item(row, 1)
            name_item = window.table.item(row, 0)
            meta = window._qt_rows.get(row, {})
            haystack = f"{name_item.text() if name_item else ''} {package_item.text() if package_item else ''}".lower()
            visible = True
            visible &= not needle or needle in haystack
            visible &= wanted_level == "Any" or meta.get("removal") == wanted_level
            visible &= wanted_scope == "All" or (wanted_scope == "User apps") == (not meta.get("system"))
            visible &= wanted_category == "Any" or meta.get("category") == wanted_category
            visible &= wanted_source == "Any" or meta.get("source") == wanted_source
            window.table.setRowHidden(row, not visible)
            shown += int(visible)
        window.cleaner_status.setText(f"{shown} matching apps shown.")
        dialog.accept()

    buttons.accepted.connect(apply)
    buttons.rejected.connect(dialog.reject)
    dialog.resize(420, 240)
    dialog.exec()


def _refresh_apps(window, mode: str = "all") -> None:
    if not window.serial:
        window._scan_devices()
    if not window.serial:
        window.cleaner_status.setText("Connect a device first.")
        return
    try:
        packages = _installed_packages(window, mode)
        user_packages = _user_packages(window)
        clean, uninstall = _load_exclusions()
        window._qt_list_mode = mode
        window._qt_rows = {}
        window.table.setRowCount(len(packages))
        for row, package in enumerate(packages):
            meta = _record(window.db, package, user_packages, clean, uninstall)
            window._qt_rows[row] = meta
            icon = window._cached_icon(package)
            values = (meta["label"], package, meta["removal"], meta["description"])
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setCheckState(Qt.Unchecked)
                    if not icon.isNull():
                        item.setIcon(icon)
                window.table.setItem(row, column, item)
        window.cleaner_status.setText(f"{len(packages)} packages loaded. Use the bottom scrollbar to read long descriptions.")
        _add_toolbar_buttons(window)
    except Exception as exc:
        cached = []
        try:
            cached = load_apps_cache(window.serial)
        except Exception:
            pass
        if cached:
            window.table.setRowCount(0)
            window._qt_rows = {}
            for row, package in enumerate(cached):
                meta = _record(window.db, package, set(), *_load_exclusions())
                window._qt_rows[row] = meta
                for column, value in enumerate((meta["label"], package, meta["removal"], meta["description"])):
                    item = QTableWidgetItem(value)
                    if column == 0:
                        item.setCheckState(Qt.Unchecked)
                    window.table.insertRow(row)
                    window.table.setItem(row, column, item)
            window.cleaner_status.setText(f"Loaded {len(cached)} apps from cache. Device refresh failed: {exc}")
        else:
            window.cleaner_status.setText(f"Unable to load packages: {exc}")


def _scan_bloatware(window, level: str) -> None:
    if level not in LEVELS or not window.serial:
        return
    try:
        installed = _installed_packages(window, "all")
        user_packages = _user_packages(window)
        clean, uninstall = _load_exclusions()
        entries = [_record(window.db, package, user_packages, clean, uninstall) for package in installed]
        matches = [entry for entry in entries if entry.get("removal") == level]
        window._qt_list_mode = "all"
        window._qt_rows = {row: entry for row, entry in enumerate(entries)}
        window.table.setRowCount(len(entries))
        for row, meta in enumerate(entries):
            icon = window._cached_icon(meta["id"])
            for column, value in enumerate((meta["label"], meta["id"], meta["removal"], meta["description"])):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setCheckState(Qt.Checked if meta in matches else Qt.Unchecked)
                    if not icon.isNull(): item.setIcon(icon)
                window.table.setItem(row, column, item)
            window.table.setRowHidden(row, meta not in matches)
        window.cleaner_status.setText(
            f"Scan Bloatware: {len(matches)} '{level}' app(s) found and checked from the complete device package list."
        )
        window._log(f"[GeloTech] Scan Bloatware: complete device scan found {len(matches)} '{level}' app(s).")
        _add_toolbar_buttons(window)
    except Exception as exc:
        window.cleaner_status.setText(f"Bloatware scan failed: {exc}")
        window._log(f"[GeloTech ERROR] Bloatware scan: {exc}")


def install_cleaner_parity(MainWindow) -> None:
    """Install the Qt cleaner slice on the migrated MainWindow class."""
    MainWindow.refresh_apps = _refresh_apps
    MainWindow.scan_bloatware = _scan_bloatware
    MainWindow.apply_advanced_filter = _filter_dialog
    MainWindow._table_menu = lambda self, pos: _table_menu(self, pos)
    MainWindow._checked_packages = lambda self: _checked_packages(self)
    MainWindow._backup_help = lambda self: _restore_dialog(self)
    MainWindow._exclude_checked = lambda self, mode: _exclude_checked(self, mode)
