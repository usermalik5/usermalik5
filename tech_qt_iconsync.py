"""Automatic per-device icon export/import for the Qt migration.

Mirrors the legacy ApkIconHelper workflow while accepting both the legacy
flat icon_cache layout and nested adb-pulled export layouts.
"""
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
        try:
            return json.loads((self.cache_root() / "sync.json").read_text(encoding="utf-8"))
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
        cache = self.cache_root()
        manifest = cache / "packages.jsonl"
        expected = int(meta.get("icon_count") or 0)
        if meta.get("package_fingerprint") != fingerprint or expected <= 0 or not manifest.is_file():
            return False
        shared = Path(get_cache_dir())
        shared.mkdir(parents=True, exist_ok=True)
        copied = 0
        for source in cache.glob("*.png"):
            try:
                shutil.copy2(source, shared / source.name)
                copied += 1
            except OSError:
                pass
        if copied:
            self.log(f"[GeloTech] Icons ready from device cache ({copied} icons).")
            return True
        return False

    def _find_manifest(self, root: Path) -> Path | None:
        direct = [root / "packages.jsonl", root / "apk_icon_export" / "packages.jsonl"]
        for candidate in direct:
            if candidate.is_file():
                return candidate
        try:
            return next(root.rglob("packages.jsonl"))
        except StopIteration:
            return None

    def _resolve_icon_source(self, manifest: Path, icon_value: str) -> Path | None:
        if not icon_value:
            return None
        raw = Path(icon_value.replace("/", os.sep))
        candidates: list[Path] = []
        if raw.is_absolute():
            candidates.append(raw)
        else:
            candidates.extend([
                manifest.parent / raw,
                manifest.parent.parent / raw,
                Path(get_cache_dir()) / raw,
            ])
            candidates.append(manifest.parent / raw.name)
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        try:
            return next(manifest.parent.rglob(raw.name))
        except StopIteration:
            return None

    def export_icons(self, fingerprint: str, package_count: int) -> bool:
        if not self.ensure_helper():
            return False

        shared = Path(get_cache_dir())
        shared.mkdir(parents=True, exist_ok=True)
        pulled = shared / "apk_icon_export"
        if pulled.exists():
            shutil.rmtree(pulled, ignore_errors=True)

        self.adb(["shell", "rm", "-rf", EXPORT_DIR], 20)
        self.adb(["shell", "svc", "power", "stayon", "true"], 15)
        self.adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"], 15)
        self.adb(["shell", "wm", "dismiss-keyguard"], 15)

        completed = False
        for attempt in range(2):
            start = self.adb(
                ["shell", "am", "start", "-n", f"{HELPER_PACKAGE}/.MainActivity", "--ez", "autoExport", "true"],
                20,
            )
            if start.returncode != 0:
                self.log(f"[GeloTech] Helper launch returned {start.returncode}: {(start.stderr or start.stdout).strip()[-220:]}")
            for tick in range(60):
                time.sleep(2)
                flag = self.adb(["shell", "cat", DONE_FLAG], 10)
                if flag.stdout.strip():
                    completed = True
                    break
                if tick and tick % 15 == 0:
                    self.log(f"[GeloTech] Exporting icons ({tick * 2}s)...")
            if completed:
                break
            self.log("[GeloTech] Icon export timed out; retrying once...")
            self.adb(["shell", "am", "force-stop", HELPER_PACKAGE], 15)
            time.sleep(2)

        self.adb(["shell", "svc", "power", "stayon", "false"], 15)
        if not completed:
            self.log("[GeloTech ERROR] Icon export did not finish. Unlock the phone and retry.")
            return False

        pull = self.adb(["pull", EXPORT_DIR, str(shared)], 180)
        if pull.returncode != 0:
            self.log(f"[GeloTech ERROR] Icon export pull failed: {(pull.stderr or pull.stdout).strip()[-400:]}")
            return False

        manifest = self._find_manifest(shared)
        if manifest is None:
            self.log("[GeloTech ERROR] Icon export finished but packages.jsonl was not found.")
            return False

        cache = self.cache_root()
        count = 0
        seen_packages: set[str] = set()
        for line in manifest.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except (ValueError, TypeError):
                continue
            package = str(item.get("package") or "").strip()
            icon = str(item.get("icon") or "").strip()
            if not package:
                continue
            source = self._resolve_icon_source(manifest, icon)
            if source is None:
                continue
            target = shared / f"{package}.png"
            try:
                shutil.copy2(source, target)
                shutil.copy2(source, cache / target.name)
                seen_packages.add(package)
            except OSError:
                pass

        # Recovery path for helper builds whose manifest points elsewhere but
        # still produced the legacy flat package.png files.
        if not seen_packages:
            for source in shared.rglob("*.png"):
                name = source.stem
                if "." not in name or name in seen_packages:
                    continue
                try:
                    shutil.copy2(source, shared / f"{name}.png")
                    shutil.copy2(source, cache / f"{name}.png")
                    seen_packages.add(name)
                except OSError:
                    pass

        count = len(seen_packages)
        try:
            shutil.copy2(manifest, cache / "packages.jsonl")
        except OSError:
            pass

        self.write_meta({
            "serial": self.serial,
            "package_fingerprint": fingerprint,
            "package_count": package_count,
            "icon_count": count,
            "helper_verified": True,
            "synced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
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
        bridge.finished.connect(lambda device_serial, ok: icon_sync_completed(self, device_serial, ok))
        self._qt_icon_log_bridge = bridge
        import threading
        threading.Thread(
            target=_IconSyncWorker(self, serial, bridge).run,
            daemon=True,
            name=f"GeloTech-IconSync-{serial}",
        ).start()

    MainWindow._prepare_icon_cache = prepare_icon_cache
    MainWindow._icon_sync_completed = icon_sync_completed
