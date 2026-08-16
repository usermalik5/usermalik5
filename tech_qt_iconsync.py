"""Automatic per-device icon export/import for the Qt migration."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from tech_common import get_bundle_dir, get_cache_dir, get_settings_dir

HELPER_PACKAGE = "com.drox.apkiconhelper"
EXPORT_DIR = "/sdcard/Android/data/com.drox.apkiconhelper/files/apk_icon_export"
DONE_FLAG = f"{EXPORT_DIR}/DONE.flag"


class _IconLogBridge(QObject):
    message = Signal(str)
    finished = Signal(str, bool)


class _IconSyncWorker:
    def __init__(self, window, serial: str, bridge: _IconLogBridge):
        self.window = window
        self.serial = serial
        self.bridge = bridge

    def log(self, text: str) -> None:
        self.bridge.message.emit(text)

    def adb(self, args: list[str], timeout: int = 30):
        return self.window._adb(["-s", self.serial, *args], timeout)

    def cache_root(self) -> Path:
        key = hashlib.sha256(self.serial.encode("utf-8", "replace")).hexdigest()[:32]
        path = Path(get_settings_dir()) / "icon_cache" / key
        path.mkdir(parents=True, exist_ok=True)
        return path

    def read_meta(self) -> dict:
        path = self.cache_root() / "sync.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}

    def write_meta(self, data: dict) -> None:
        path = self.cache_root() / "sync.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)

    def package_fingerprint(self) -> tuple[str | None, int]:
        result = self.adb(["shell", "pm", "list", "packages"], 30)
        packages = sorted(
            line.split(":", 1)[1].strip()
            for line in result.stdout.splitlines()
            if line.startswith("package:") and ":" in line
        )
        if not packages:
            return None, 0
        return hashlib.sha256("\n".join(packages).encode("utf-8")).hexdigest(), len(packages)

    def helper_path(self) -> str | None:
        result = self.adb(["shell", "pm", "path", HELPER_PACKAGE], 15)
        for line in result.stdout.splitlines():
            if line.startswith("package:"):
                return line[8:].strip()
        return None

    def ensure_helper(self) -> bool:
        if self.helper_path():
            self.log("[GeloTech] ApkIconHelper already verified on this device.")
            return True
        helper = Path(get_bundle_dir()) / "ApkIconHelper.apk"
        if not helper.is_file():
            self.log("[GeloTech ERROR] ApkIconHelper.apk is missing from this build.")
            return False
        self.log("[GeloTech] ApkIconHelper not found; installing it once...")
        result = self.adb(["install", "-r", "-t", str(helper)], 60)
        combined = f"{result.stdout}\n{result.stderr}"
        if "Success" not in combined:
            self.log(f"[GeloTech ERROR] Helper installation failed: {combined.strip()[-300:]}")
            return False
        if not self.helper_path():
            self.log("[GeloTech ERROR] Helper installed but verification failed.")
            return False
        return True

    def restore_cache(self, fingerprint: str) -> bool:
        meta = self.read_meta()
        manifest = self.cache_root() / "packages.jsonl"
        if meta.get("package_fingerprint") != fingerprint or not meta.get("icon_count") or not manifest.is_file():
            return False
        local = Path(get_cache_dir())
        local.mkdir(parents=True, exist_ok=True)
        copied = 0
        for source in self.cache_root().glob("*.png"):
            try:
                shutil.copy2(source, local / source.name)
                copied += 1
            except OSError:
                pass
        if copied:
            self.log(f"[GeloTech] Icons ready from device cache ({copied} icons).")
            return True
        return False

    def export_icons(self, fingerprint: str, package_count: int) -> bool:
        if not self.ensure_helper():
            return False

        self.adb(["shell", "rm", "-f", DONE_FLAG], 15)
        self.adb(["shell", "svc", "power", "stayon", "true"], 15)
        self.adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], 15)
        self.adb(["shell", "wm", "dismiss-keyguard"], 15)

        completed = False
        for attempt in range(2):
            self.adb(
                [
                    "shell",
                    "am",
                    "start",
                    "-n",
                    f"{HELPER_PACKAGE}/.MainActivity",
                    "--ez",
                    "autoExport",
                    "true",
                ],
                20,
            )
            for _ in range(60):
                time.sleep(2)
                flag = self.adb(["shell", "cat", DONE_FLAG], 10)
                if flag.stdout.strip():
                    completed = True
                    break
            if completed:
                break
            self.log("[GeloTech] Icon export timed out; retrying once...")
            self.adb(["shell", "am", "force-stop", HELPER_PACKAGE], 15)
            time.sleep(2)

        self.adb(["shell", "svc", "power", "stayon", "false"], 15)
        if not completed:
            self.log("[GeloTech ERROR] Icon export did not finish.")
            return False

        temp_root = Path(get_cache_dir())
        temp_root.mkdir(parents=True, exist_ok=True)
        self.adb(["pull", EXPORT_DIR, str(temp_root)], 120)

        manifest = temp_root / "packages.jsonl"
        if not manifest.is_file():
            manifest = temp_root / "apk_icon_export" / "packages.jsonl"
        if not manifest.is_file():
            self.log("[GeloTech ERROR] Icon export finished but packages.jsonl was not found.")
            return False

        count = 0
        for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            package = item.get("package", "")
            icon = item.get("icon", "")
            if not package or not icon:
                continue
            source = manifest.parent / icon
            if source.is_file():
                shutil.copy2(source, temp_root / f"{package}.png")
                count += 1

        cache = self.cache_root()
        shutil.copy2(manifest, cache / "packages.jsonl")
        for source in temp_root.glob("*.png"):
            try:
                shutil.copy2(source, cache / source.name)
            except OSError:
                pass
        self.write_meta(
            {
                "serial": self.serial,
                "package_fingerprint": fingerprint,
                "package_count": package_count,
                "icon_count": count,
                "helper_verified": True,
                "synced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )
        self.adb(["shell", "am", "force-stop", HELPER_PACKAGE], 15)
        self.log(f"[GeloTech] Icons synced: {count} apps; device cache updated.")
        return count > 0

    def run(self) -> None:
        success = False
        try:
            state = self.adb(["get-state"], 10).stdout.strip().lower()
            if state != "device":
                self.log("[GeloTech] Icon sync waiting: device is not ready for ADB.")
                return
            fingerprint, package_count = self.package_fingerprint()
            if not fingerprint:
                self.log("[GeloTech] Icon sync waiting: package list is not ready.")
                return
            if self.restore_cache(fingerprint):
                success = True
                return
            success = self.export_icons(fingerprint, package_count)
        except Exception as exc:
            self.log(f"[GeloTech ERROR] Icon sync failed: {exc}")
        finally:
            self.bridge.finished.emit(self.serial, success)


def install_icon_sync(MainWindow) -> None:
    """Run the verified icon export/cache flow and refresh the table when ready."""

    def icon_sync_completed(self, serial: str, success: bool) -> None:
        if serial != getattr(self, "serial", None):
            return
        if success:
            self._log(f"[GeloTech] Icon sync complete for {serial}; refreshing app icons...")
        else:
            self._log(f"[GeloTech] Icon sync did not complete for {serial}; using fallback icons.")
        QTimer.singleShot(0, self.refresh_apps)

    def prepare_icon_cache(self, serial: str) -> None:
        bridge = _IconLogBridge(self)
        bridge.message.connect(self._log)
        bridge.finished.connect(lambda device_serial, success: icon_sync_completed(self, device_serial, success))
        setattr(self, "_qt_icon_log_bridge", bridge)
        import threading
        worker = _IconSyncWorker(self, serial, bridge)
        threading.Thread(target=worker.run, daemon=True, name=f"GeloTech-IconSync-{serial}").start()

    MainWindow._prepare_icon_cache = prepare_icon_cache
    MainWindow._icon_sync_completed = icon_sync_completed
