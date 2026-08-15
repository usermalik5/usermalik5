"""Qt-native VirusTotal workflows for the GeloTech migration."""
from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import time
from pathlib import Path

import requests
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


VT_API_KEY = "25a0a1b604b4d2d0ab385a0d98ec3b198d5c7d9739c61cf3cce442fa7a8f253f"
VT_BASE = "https://www.virustotal.com/api/v3"


class _VTWorker(QThread):
    progress = Signal(int, int, str)
    result = Signal(dict)
    error = Signal(str)

    def __init__(self, window, mode: str, package: str | None = None):
        super().__init__(window)
        self.window = window
        self.mode = mode
        self.package = package
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            if self.mode == "package":
                self.result.emit(self._scan_package(self.package or ""))
                return
            packages = self._installed_packages()
            total = len(packages)
            findings: dict = {}
            for index, package in enumerate(packages, start=1):
                if self._stop:
                    break
                try:
                    data = self._lookup_package(package)
                    if data:
                        findings[package] = data
                except Exception as exc:
                    findings[package] = {"error": str(exc)}
                self.progress.emit(index, total, package)
            self.result.emit({"mode": self.mode, "items": findings, "stopped": self._stop})
        except Exception as exc:
            self.error.emit(str(exc))

    def _adb(self, args, timeout=30):
        return self.window._adb(args, timeout)

    def _installed_packages(self) -> list[str]:
        result = self._adb(["-s", self.window.serial, "shell", "pm", "list", "packages"], 30)
        return sorted(
            line.split(":", 1)[1].strip()
            for line in result.stdout.splitlines()
            if line.startswith("package:") and ":" in line
        )

    def _package_apk_path(self, package: str) -> str | None:
        result = self._adb(["-s", self.window.serial, "shell", "pm", "path", package], 20)
        for line in result.stdout.splitlines():
            if line.startswith("package:"):
                return line[8:].strip()
        return None

    def _package_hash(self, package: str, apk_path: str) -> str | None:
        result = self._adb(["-s", self.window.serial, "shell", "sha256sum", apk_path], 30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.split()[0].strip()
        return None

    def _lookup_hash(self, file_hash: str) -> dict:
        response = requests.get(
            f"{VT_BASE}/files/{file_hash}",
            headers={"x-apikey": VT_API_KEY},
            timeout=30,
        )
        if response.status_code == 404:
            return {"hash": file_hash, "not_found": True, "stats": {}}
        response.raise_for_status()
        attributes = response.json().get("data", {}).get("attributes", {})
        return {
            "hash": file_hash,
            "not_found": False,
            "stats": attributes.get("last_analysis_stats", {}),
        }

    def _lookup_package(self, package: str) -> dict:
        apk_path = self._package_apk_path(package)
        if not apk_path:
            return {"error": "APK path not found."}
        file_hash = self._package_hash(package, apk_path)
        if not file_hash:
            return {"error": "Could not calculate APK SHA-256."}
        data = self._lookup_hash(file_hash)
        data["package"] = package
        data["apk_path"] = apk_path
        return data

    def _scan_package(self, package: str) -> dict:
        return {"mode": "package", "items": {package: self._lookup_package(package)}}


def _download_apk(window, package: str) -> tuple[str, str]:
    apk_path = None
    result = window._adb(["-s", window.serial, "shell", "pm", "path", package], 20)
    for line in result.stdout.splitlines():
        if line.startswith("package:"):
            apk_path = line[8:].strip()
            break
    if not apk_path:
        raise RuntimeError(f"Package '{package}' was not found on the device.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".apk")
    tmp.close()
    local_path = tmp.name
    pulled = window._adb(["-s", window.serial, "pull", apk_path, local_path], 120)
    if pulled.returncode != 0 or not os.path.isfile(local_path):
        try:
            os.unlink(local_path)
        except OSError:
            pass
        raise RuntimeError((pulled.stderr or pulled.stdout or "ADB pull failed.").strip())
    return local_path, apk_path


def _upload_if_missing(window, package: str, file_path: str, file_hash: str) -> dict:
    with open(file_path, "rb") as handle:
        response = requests.post(
            f"{VT_BASE}/files",
            headers={"x-apikey": VT_API_KEY},
            files={"file": (f"{package}.apk", handle, "application/vnd.android.package-archive")},
            timeout=120,
        )
    response.raise_for_status()
    analysis_id = response.json().get("data", {}).get("id")
    if not analysis_id:
        raise RuntimeError("VirusTotal did not return an analysis ID.")
    return _poll_analysis(package, file_hash, analysis_id)


def _poll_analysis(package: str, file_hash: str, analysis_id: str) -> dict:
    for _ in range(36):
        response = requests.get(
            f"{VT_BASE}/analyses/{analysis_id}",
            headers={"x-apikey": VT_API_KEY},
            timeout=30,
        )
        response.raise_for_status()
        attributes = response.json().get("data", {}).get("attributes", {})
        if attributes.get("status") == "completed":
            return {
                "package": package,
                "hash": file_hash,
                "stats": attributes.get("stats", {}),
                "uploaded": True,
            }
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for VirusTotal analysis of {package}.")


def install_virustotal(MainWindow) -> None:
    """Install the Qt VirusTotal page and workflows onto MainWindow."""

    original_vt_page = MainWindow._vt_page

    def vt_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("VirusTotal Scanner"))

        row = QHBoxLayout()
        self.vt_package = QComboBox()
        self.vt_package.setEditable(True)
        self.vt_package.setPlaceholderText("Installed package name")
        self.vt_refresh = QPushButton("Load Packages")
        self.vt_scan_package = QPushButton("Scan Package")
        self.vt_scan_phone = QPushButton("Scan Phone")
        self.vt_scan_running = QPushButton("Scan Running")
        self.vt_stop = QPushButton("Stop")
        self.vt_upload = QPushButton("Pull + Upload")
        for widget in (self.vt_package, self.vt_refresh, self.vt_scan_package, self.vt_scan_phone, self.vt_scan_running, self.vt_stop, self.vt_upload):
            row.addWidget(widget)
        layout.addLayout(row)

        self.vt_status = QLabel("Ready.")
        self.vt_progress = QLabel("")
        layout.addWidget(self.vt_status)
        layout.addWidget(self.vt_progress)

        self.vt_results = QPlainTextEdit()
        self.vt_results.setReadOnly(True)
        layout.addWidget(self.vt_results, 1)

        self.vt_refresh.clicked.connect(self._qt_vt_load_packages)
        self.vt_scan_package.clicked.connect(self._qt_vt_scan_package)
        self.vt_scan_phone.clicked.connect(self._qt_vt_scan_phone)
        self.vt_scan_running.clicked.connect(self._qt_vt_scan_running)
        self.vt_stop.clicked.connect(self._qt_vt_stop)
        self.vt_upload.clicked.connect(self._qt_vt_pull_upload)
        self._vt_worker = None
        self._vt_worker_kind = None
        return page

    def _render_vt_items(self, payload: dict) -> None:
        self.vt_results.clear()
        items = payload.get("items", {})
        for package, data in items.items():
            if data.get("error"):
                self.vt_results.appendPlainText(f"{package}\n  ERROR: {data['error']}\n")
                continue
            stats = data.get("stats", {}) or {}
            if data.get("not_found"):
                state = "Not present in VirusTotal"
            else:
                state = (
                    f"malicious={stats.get('malicious', 0)}  "
                    f"suspicious={stats.get('suspicious', 0)}  "
                    f"undetected={stats.get('undetected', 0)}"
                )
            self.vt_results.appendPlainText(f"{package}\n  SHA-256: {data.get('hash', 'unknown')}\n  {state}\n")

    def _qt_vt_load_packages(self) -> None:
        if not self.serial:
            self._scan_devices()
        if not self.serial:
            self.vt_status.setText("Connect a device first.")
            return
        try:
            packages = self._adb(["-s", self.serial, "shell", "pm", "list", "packages"], 30).stdout
            values = sorted(
                line.split(":", 1)[1].strip()
                for line in packages.splitlines()
                if line.startswith("package:") and ":" in line
            )
            self.vt_package.clear()
            self.vt_package.addItems(values)
            self.vt_status.setText(f"Loaded {len(values)} installed packages.")
        except Exception as exc:
            self.vt_status.setText(str(exc))

    def _start_vt_worker(self, mode: str) -> None:
        if self._vt_worker and self._vt_worker.isRunning():
            return
        if not self.serial:
            self._scan_devices()
        if not self.serial:
            self.vt_status.setText("Connect a device first.")
            return
        self._vt_worker_kind = mode
        package = self.vt_package.currentText().strip() if mode == "package" else None
        self._vt_worker = _VTWorker(self, mode, package)
        self._vt_worker.progress.connect(
            lambda current, total, pkg: self.vt_progress.setText(f"Checking {current}/{total}: {pkg}")
        )
        self._vt_worker.result.connect(self._qt_vt_worker_result)
        self._vt_worker.error.connect(lambda message: self.vt_status.setText(f"VirusTotal error: {message}"))
        self._vt_worker.finished.connect(self._qt_vt_worker_finished)
        self.vt_stop.setEnabled(True)
        self.vt_status.setText(f"Scanning {mode}…")
        self._vt_worker.start()

    def _qt_vt_scan_package(self) -> None:
        if not self.vt_package.currentText().strip():
            self.vt_status.setText("Select or enter a package name.")
            return
        self._start_vt_worker("package")

    def _qt_vt_scan_phone(self) -> None:
        self._start_vt_worker("installed")

    def _qt_vt_scan_running(self) -> None:
        if not self.serial:
            self._scan_devices()
        if not self.serial:
            self.vt_status.setText("Connect a device first.")
            return
        self.vt_status.setText("Collecting running packages…")
        try:
            result = self._adb(["-s", self.serial, "shell", "dumpsys", "activity", "activities"], 15)
            running = set()
            for line in result.stdout.splitlines():
                for part in line.replace("{", " ").replace("}", " ").split():
                    if "." in part and part.startswith("com."):
                        running.add(part.strip("(),"))
            self._start_vt_worker("installed")
            self._vt_running_filter = running
        except Exception as exc:
            self.vt_status.setText(str(exc))

    def _qt_vt_stop(self) -> None:
        if self._vt_worker:
            self._vt_worker.stop()
            self.vt_status.setText("Stopping…")

    def _qt_vt_worker_result(self, payload: dict) -> None:
        if getattr(self, "_vt_running_filter", None):
            items = payload.get("items", {})
            running = self._vt_running_filter
            payload["items"] = {key: value for key, value in items.items() if key in running}
        self._render_vt_items(payload)
        self.vt_status.setText("Scan complete." if not payload.get("stopped") else "Scan stopped.")

    def _qt_vt_worker_finished(self) -> None:
        self.vt_stop.setEnabled(False)
        self.vt_progress.clear()
        self._vt_worker = None

    def _qt_vt_pull_upload(self) -> None:
        package = self.vt_package.currentText().strip()
        if not package:
            self.vt_status.setText("Select a package first.")
            return
        if not self.serial:
            self._scan_devices()
        if not self.serial:
            self.vt_status.setText("Connect a device first.")
            return

        def worker() -> None:
            local_path = ""
            try:
                local_path, apk_path = _download_apk(self, package)
                with open(local_path, "rb") as handle:
                    file_hash = hashlib.sha256(handle.read()).hexdigest()
                lookup = _VTWorker._lookup_hash(_VTWorker(self, "package", package), file_hash)
                if lookup.get("not_found"):
                    result = _upload_if_missing(self, package, local_path, file_hash)
                    self._log(f"[VT] Uploaded {package} from {apk_path}; analysis completed.")
                    self.vt_status.setText("Upload and analysis complete.")
                else:
                    result = lookup
                    self._log(f"[VT] {package} already exists in VirusTotal; using existing report.")
                    self.vt_status.setText("Existing VirusTotal report found.")
                self._render_vt_items({"items": {package: result}})
            except Exception as exc:
                self.vt_status.setText(f"VirusTotal error: {exc}")
                QMessageBox.warning(self, "VirusTotal", str(exc))
            finally:
                if local_path:
                    try:
                        os.unlink(local_path)
                    except OSError:
                        pass

        threading.Thread(target=worker, daemon=True).start()

    MainWindow._vt_page = vt_page
    MainWindow._qt_vt_load_packages = _qt_vt_load_packages
    MainWindow._start_vt_worker = _start_vt_worker
    MainWindow._qt_vt_scan_package = _qt_vt_scan_package
    MainWindow._qt_vt_scan_phone = _qt_vt_scan_phone
    MainWindow._qt_vt_scan_running = _qt_vt_scan_running
    MainWindow._qt_vt_stop = _qt_vt_stop
    MainWindow._qt_vt_worker_result = _qt_vt_worker_result
    MainWindow._qt_vt_worker_finished = _qt_vt_worker_finished
    MainWindow._qt_vt_pull_upload = _qt_vt_pull_upload
    MainWindow._legacy_vt_page = original_vt_page
