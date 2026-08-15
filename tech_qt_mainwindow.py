"""PySide6 main window for the GeloTech Qt migration.

The Qt layer owns presentation and Qt event-loop concerns. ADB, auth, signed
source fetching, and package-database parsing remain in the existing shared
modules where those modules are UI-independent.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from tech_common import (
    APP_VERSION,
    get_bundle_dir,
    get_cache_dir,
    get_session_database_path,
    load_package_database,
    save_apps_cache,
    load_apps_cache,
)
from tech_reg import (
    _admin_set_password,
    _fetch_verified_sources,
    _fetch_verified_users,
    _login_user,
    _request_password,
    _set_user_blocked,
)
from tech_qt_icons import ICONS, load_icon
from tech_qt_themes import DEFAULT_THEME, DEFAULT_UI_FONT, PALETTES, UI_FONTS, apply_theme, palette_profile


class LoginWorker(QObject):
    finished = Signal(bool, str, object, object, object)

    def __init__(self, email: str, password: str, phrase: str):
        super().__init__()
        self.email, self.password, self.phrase = email, password, phrase

    def run(self) -> None:
        ok, reason, user, session = _login_user(self.email, self.password, self.phrase or None)
        if not ok:
            self.finished.emit(False, reason, None, None, None)
            return
        db_bytes = _fetch_verified_sources()
        self.finished.emit(True, "", user, session, db_bytes)


class LoginDialog(QDialog):
    logged_in = Signal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"GeloTech Tool v{APP_VERSION} - Sign in")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel("GELOTECH")
        title.setObjectName("brand")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        sub = QLabel("Sign in to continue")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)
        form = QFormLayout()
        self.email = QLineEdit()
        self.email.setPlaceholderText("Email")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Password")
        self.phrase = QLineEdit()
        self.phrase.setEchoMode(QLineEdit.Password)
        self.phrase.setPlaceholderText("Admin secret phrase (admin only)")
        self.phrase.hide()
        form.addRow("Email", self.email)
        form.addRow("Password", self.password)
        form.addRow("Admin phrase", self.phrase)
        layout.addLayout(form)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        row = QHBoxLayout()
        self.signin = QPushButton("Sign in")
        self.signin.setIcon(load_icon("login"))
        self.register = QPushButton("Create an account")
        row.addWidget(self.signin)
        row.addWidget(self.register)
        layout.addLayout(row)
        self.email.textChanged.connect(self._email_changed)
        self.signin.clicked.connect(self._sign_in)
        self.register.clicked.connect(self._register)
        self.email.returnPressed.connect(self._sign_in)
        self.password.returnPressed.connect(self._sign_in)
        self._thread = None
        self._worker = None

    def _email_changed(self, value: str) -> None:
        self.phrase.setVisible(value.strip().lower() == "admin")

    def _register(self) -> None:
        email = self.email.text().strip()
        ok, message = _request_password(email)
        self.status.setText(message)
        if ok:
            QMessageBox.information(self, "GeloTech", message)

    def _sign_in(self) -> None:
        if self._thread is not None:
            return
        email, password = self.email.text().strip(), self.password.text()
        if not email or not password:
            self.status.setText("Enter your email and password.")
            return
        self.signin.setEnabled(False)
        self.status.setText("Signing in…")
        self._thread = QThread(self)
        self._worker = LoginWorker(email, password, self.phrase.text())
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._login_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _login_finished(self, ok, reason, user, session, db_bytes) -> None:
        self.signin.setEnabled(True)
        self._thread = None
        self._worker = None
        if not ok:
            self.status.setText(reason)
            return
        self.logged_in.emit(user, session, db_bytes)
        self.accept()


class MainWindow(QMainWindow):
    """Qt-native GeloTech shell with the current feature set."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"GeloTech Tool v{APP_VERSION}")
        self.resize(1360, 820)
        self.current_user = {}
        self.session = None
        self.db = {}
        self.serial = None
        self._seen_serials = set()
        self._mirror_seen = set()
        self.theme_name = DEFAULT_THEME
        self.ui_font = DEFAULT_UI_FONT
        self._load_preferences()
        self._build_shell()
        self._apply_theme()
        self._adb_timer = QTimer(self)
        self._adb_timer.timeout.connect(self._scan_devices)
        self._adb_timer.start(3000)
        QTimer.singleShot(250, self._open_login)

    # -------------------------- shell --------------------------
    def _build_shell(self):
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = QFrame(objectName="sidebar")
        self.sidebar.setMinimumWidth(235)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(12, 12, 12, 12)
        self.brand = QLabel("GELOTECH", objectName="brand")
        side.addWidget(self.brand)
        self.version = QLabel(f"TECH TOOL\nv{APP_VERSION}")
        self.version.setAlignment(Qt.AlignCenter)
        side.addWidget(self.version)
        self.user_label = QLabel("Not signed in", objectName="muted")
        self.user_label.setAlignment(Qt.AlignCenter)
        side.addWidget(self.user_label)
        self.theme_button = QPushButton("Theme / Font")
        self.theme_button.setIcon(load_icon("settings"))
        self.theme_button.clicked.connect(self._theme_dialog)
        side.addWidget(self.theme_button)

        self.nav = QListWidget()
        self.nav.setSelectionMode(QAbstractItemView.SingleSelection)
        side.addWidget(self.nav, 1)
        for title, icon_name in [
            ("Dashboard", "Dashboard"), ("App Cleaner", "Scan"),
            ("Monitor Apps", "Monitor Apps"), ("Block Ads DNS", "Block Ads DNS"),
            ("VirusTotal", "VirusTotal"), ("Accounts", "Accounts"),
        ]:
            item = QListWidgetItem(load_icon(ICONS.get(icon_name, "info-circle")), title)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._nav_changed)

        for text, icon_name, slot in [
            ("Screen Mirror", "Screen Mirror", self.start_mirror),
            ("Reboot Recovery", "Reboot", lambda: self._adb_simple(["reboot", "recovery"])),
            ("Reboot Fastboot", "Power", lambda: self._adb_simple(["reboot", "bootloader"])),
            ("Re-authorize ADB", "Re-authorize ADB", self._reauthorize),
            ("Fix / DL ADB Drivers", "Fix Drivers", self._driver_help),
            ("Logout", "Logout", self._logout),
        ]:
            btn = QPushButton(text)
            btn.setIcon(load_icon(ICONS.get(icon_name, "info-circle")))
            btn.clicked.connect(slot)
            side.addWidget(btn)
        usb = QLabel("📱 USB debugging:\nEnable Developer Options → USB debugging, connect the phone, then tap Allow.\nGeloTech automatically prepares app icons for new devices.")
        usb.setWordWrap(True)
        usb.setObjectName("muted")
        side.addWidget(usb)
        how = QLabel("💡 How to use:\nRefresh loads user apps. Load Apps chooses All / User / System / Disabled.\nAdvanced Filter uses the database. Scan Bloatware filters by UAD level.\nRight-click a row for app actions.")
        how.setWordWrap(True)
        how.setObjectName("muted")
        side.addWidget(how)

        self.stack = QStackedWidget()
        self.pages = [self._dashboard_page(), self._cleaner_page(), self._monitor_page(), self._dns_page(), self._vt_page(), self._accounts_page()]
        for page in self.pages:
            self.stack.addWidget(page)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.nav.setCurrentRow(0)

    def _nav_changed(self, row: int) -> None:
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            if row == 1:
                self.refresh_apps()
            elif row == 2:
                self._refresh_monitor()
            elif row == 5:
                self.refresh_accounts()

    def _dashboard_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        top = QHBoxLayout()
        phone_frame = QFrame()
        phone_layout = QVBoxLayout(phone_frame)
        img = QLabel()
        img.setAlignment(Qt.AlignCenter)
        asset = Path(getattr(__import__("sys"), "_MEIPASS", os.path.dirname(__file__))) / "assets" / "tech_dash_images" / "iPhone17_P_PM_CosmicOrange@2x.png"
        if asset.is_file():
            img.setPixmap(QPixmap(str(asset)).scaled(360, 740, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            img.setText("iPhone mockup")
        phone_layout.addWidget(img)
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumHeight(170)
        phone_layout.addWidget(self.log)
        actions = QHBoxLayout()
        r = QPushButton("Refresh")
        r.setIcon(load_icon("refresh"))
        r.clicked.connect(self.refresh_apps)
        m = QPushButton("Screen Mirror")
        m.setIcon(load_icon("device-mobile"))
        m.clicked.connect(self.start_mirror)
        actions.addWidget(r); actions.addWidget(m)
        phone_layout.addLayout(actions)
        device = QFrame()
        dlay = QVBoxLayout(device)
        self.device_label = QLabel("No device connected")
        self.device_label.setWordWrap(True)
        dlay.addWidget(self.device_label)
        self.phone_status = QLabel("Waiting for ADB…")
        dlay.addWidget(self.phone_status)
        top.addWidget(phone_frame, 1)
        top.addWidget(device, 1)
        outer.addLayout(top)
        return page

    def _cleaner_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        bar = QHBoxLayout()
        for label, slot, icon in [
            ("Refresh", self.refresh_apps, "refresh"), ("Load Apps", self.refresh_apps, "database"),
            ("Advanced Filter", self.apply_advanced_filter, "scan"), ("Scan Bloatware", self.scan_bloatware, "shield-check"),
            ("Restore / Backup", self._backup_help, "folder"),
        ]:
            b = QPushButton(label); b.setIcon(load_icon(icon)); b.clicked.connect(slot); bar.addWidget(b)
        layout.addLayout(bar)
        self.cleaner_status = QLabel("Connect a device and press Refresh.")
        layout.addWidget(self.cleaner_status)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["APP NAME", "PACKAGE ID", "UAD LEVEL", "DESCRIPTION"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 220); self.table.setColumnWidth(1, 280); self.table.setColumnWidth(2, 145); self.table.setColumnWidth(3, 900)
        layout.addWidget(self.table, 1)
        return page

    def _monitor_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        self.monitor_label = QLabel("Monitor Running Apps")
        layout.addWidget(self.monitor_label)
        self.monitor_text = QPlainTextEdit(readOnly=True)
        layout.addWidget(self.monitor_text)
        return page

    def _dns_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Block Ads DNS"))
        row = QHBoxLayout(); self.dns = QComboBox(); self.dns.addItems(["dns.adguard-dns.com", "one.one.one.one", "dns.google", "dns.quad9.net"])
        apply_btn = QPushButton("Apply DNS"); apply_btn.clicked.connect(self.apply_dns)
        off = QPushButton("Disable"); off.clicked.connect(self.disable_dns)
        row.addWidget(self.dns); row.addWidget(apply_btn); row.addWidget(off); layout.addLayout(row)
        layout.addWidget(QLabel("Private DNS is changed through Android Settings via ADB."))
        return page

    def _vt_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        layout.addWidget(QLabel("VirusTotal Scanner"))
        self.vt_path = QLineEdit(); browse = QPushButton("Choose APK…"); scan = QPushButton("Open File")
        browse.clicked.connect(self._choose_apk); scan.clicked.connect(lambda: QMessageBox.information(self, "VirusTotal", "Use the existing VirusTotal workflow after selecting an APK."))
        row = QHBoxLayout(); row.addWidget(self.vt_path, 1); row.addWidget(browse); row.addWidget(scan); layout.addLayout(row)
        return page

    def _accounts_page(self):
        page = QWidget(); layout = QVBoxLayout(page)
        top = QHBoxLayout(); self.account_refresh = QPushButton("Refresh"); self.account_refresh.clicked.connect(self.refresh_accounts); top.addWidget(self.account_refresh); layout.addLayout(top)
        self.accounts = QTableWidget(0, 3); self.accounts.setHorizontalHeaderLabels(["EMAIL", "ROLE", "BLOCKED"]); layout.addWidget(self.accounts, 1)
        return page

    # -------------------------- auth/preferences --------------------------
    def _preferences_path(self) -> Path:
        base = Path(os.environ.get("APPDATA", os.path.dirname(__file__))) / "GeloTechTool"
        base.mkdir(parents=True, exist_ok=True)
        return base / "qt_preferences.json"

    def _load_preferences(self):
        try:
            data = json.loads(self._preferences_path().read_text(encoding="utf-8"))
            self.theme_name = data.get("theme", DEFAULT_THEME)
            self.ui_font = data.get("font", DEFAULT_UI_FONT)
        except Exception:
            pass

    def _save_preferences(self):
        self._preferences_path().write_text(json.dumps({"theme": self.theme_name, "font": self.ui_font}, indent=2), encoding="utf-8")

    def _apply_theme(self):
        apply_theme(QApplication.instance(), self.theme_name, True, self.ui_font)

    def _theme_dialog(self):
        dlg = QDialog(self); dlg.setWindowTitle("Theme and UI Font")
        form = QFormLayout(dlg)
        theme = QComboBox(); theme.addItems([p.capitalize() for p in PALETTES]); theme.setCurrentIndex(PALETTES.index(self.theme_name) if self.theme_name in PALETTES else 0)
        font = QComboBox(); font.addItems(UI_FONTS); font.setCurrentText(self.ui_font)
        form.addRow("Theme", theme); form.addRow("UI Font", font)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        form.addWidget(buttons)
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            self.theme_name = theme.currentText().lower(); self.ui_font = font.currentText(); self._save_preferences(); self._apply_theme()

    def _open_login(self):
        dlg = LoginDialog(self)
        dlg.logged_in.connect(self._login_success)
        if dlg.exec() != QDialog.Accepted:
            self.close()

    def _login_success(self, user, session, db_bytes):
        self.current_user = user or {}
        self.session = session
        if db_bytes:
            path = Path(get_session_database_path()); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(db_bytes)
        self.db = load_package_database(str(get_session_database_path()))
        role = str(self.current_user.get("role", "user"))
        self.user_label.setText(f"{self.current_user.get('email', 'user')} ({role.upper()})")
        self._log("Login successful. Dashboard ready.")
        self._scan_devices()

    # -------------------------- ADB/device --------------------------
    def _adb_path(self) -> str:
        found = shutil.which("adb")
        if found:
            return found
        root = Path(get_bundle_dir())
        for candidate in [root / "platform-tools" / "adb.exe", root / "adb.exe", root / "tools" / "adb.exe"]:
            if candidate.is_file(): return str(candidate)
        return "adb"

    def _adb(self, args, timeout=30, check=False):
        cmd = [self._adb_path()] + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)

    def _scan_devices(self):
        try:
            result = self._adb(["devices"], timeout=8)
        except Exception as exc:
            self.phone_status.setText(f"ADB unavailable: {exc}")
            return
        devices = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device": devices.append(parts[0])
        if not devices:
            self.serial = None; self.device_label.setText("No device connected"); self.phone_status.setText("Waiting for ADB…"); return
        serial = devices[0]
        new = serial not in self._seen_serials
        self.serial = serial
        self._seen_serials.add(serial)
        model = self._adb(["-s", serial, "shell", "getprop", "ro.product.model"], timeout=8).stdout.strip()
        android = self._adb(["-s", serial, "shell", "getprop", "ro.build.version.release"], timeout=8).stdout.strip()
        self.device_label.setText(f"{model or 'Android device'}\nAndroid {android or '?'}\nADB: {serial}")
        self.phone_status.setText("Connected" + (" • new device detected" if new else ""))
        if new:
            self._log(f"[GeloTech] New device detected: {serial}. Preparing app-icon cache…")
            self._prepare_icon_cache(serial)
            if serial not in self._mirror_seen:
                self._mirror_seen.add(serial)
                QTimer.singleShot(5000, self.start_mirror)

    def _prepare_icon_cache(self, serial: str):
        cache = Path(get_cache_dir()) / hashlib.sha256(serial.encode()).hexdigest()[:32]
        cache.mkdir(parents=True, exist_ok=True)
        manifest = cache / "packages.jsonl"
        if manifest.exists():
            self._log(f"[GeloTech] Icons ready from device cache ({sum(1 for _ in manifest.open(encoding='utf-8'))} entries).")
            return
        helper = Path(get_bundle_dir()) / "ApkIconHelper.apk"
        if helper.exists():
            try:
                self._adb(["-s", serial, "install", "-r", str(helper)], timeout=60)
                self._log("[GeloTech] ApkIconHelper prepared on the new device.")
            except Exception as exc:
                self._log(f"[GeloTech] Icon helper preparation deferred: {exc}")
        # The native helper export pipeline can now populate this per-device
        # location without changing the UI. Cache reuse is the important part
        # for reconnects; an existing manifest is never reinstalled.

    # -------------------------- App Cleaner --------------------------
    def refresh_apps(self):
        if not self.serial:
            self._scan_devices()
        if not self.serial:
            self.cleaner_status.setText("Connect a device first."); return
        try:
            result = self._adb(["-s", self.serial, "shell", "pm", "list", "packages"], timeout=30)
            packages = [line.split(":", 1)[-1].strip() for line in result.stdout.splitlines() if line.startswith("package:")]
            save_apps_cache(packages, self.serial)
        except Exception:
            packages = load_apps_cache(self.serial)
        rows = []
        for pkg in packages:
            record = self.db.get(pkg, {}) if isinstance(self.db, dict) else {}
            label = record.get("label") or record.get("description") or pkg
            desc = str(record.get("description") or "No description available.")
            level = str(record.get("removal") or "Unknown")
            rows.append((label, pkg, level, desc))
        rows.sort(key=lambda x: x[0].lower())
        self.table.setRowCount(len(rows))
        for r, (label, pkg, level, desc) in enumerate(rows):
            for c, value in enumerate((label, pkg, level, desc)):
                item = QTableWidgetItem(value)
                self.table.setItem(r, c, item)
        self.cleaner_status.setText(f"{len(rows)} packages loaded. Use the bottom scrollbar to read long descriptions.")

    def apply_advanced_filter(self):
        QMessageBox.information(self, "Advanced Filter", "The Qt table is now ready for the database-backed filters; the next migration slice will port the existing filter dialog without changing the database logic.")

    def scan_bloatware(self):
        QMessageBox.information(self, "Scan Bloatware", "The Qt migration preserves the existing UAD database and bloatware module. The dedicated Qt action dialog is being ported next.")

    def _backup_help(self):
        QMessageBox.information(self, "Restore / Backup", "APK backup and restore remains owned by the existing ADB logic; this Qt action surface is ready for the full dialog port.")

    # -------------------------- monitor/DNS/mirror --------------------------
    def _refresh_monitor(self):
        if not self.serial:
            self.monitor_text.setPlainText("No device connected."); return
        try:
            result = self._adb(["-s", self.serial, "shell", "dumpsys", "activity", "activities"], timeout=12)
            self.monitor_text.setPlainText(result.stdout[-12000:])
        except Exception as exc:
            self.monitor_text.setPlainText(str(exc))

    def apply_dns(self):
        if self.serial: self._adb(["-s", self.serial, "shell", "settings", "put", "global", "private_dns_mode", "hostname"]); self._adb(["-s", self.serial, "shell", "settings", "put", "global", "private_dns_specifier", self.dns.currentText()])

    def disable_dns(self):
        if self.serial: self._adb(["-s", self.serial, "shell", "settings", "put", "global", "private_dns_mode", "off"])

    def start_mirror(self):
        if not self.serial: return
        exe = shutil.which("scrcpy")
        if not exe:
            for candidate in [Path(get_bundle_dir()) / "scrcpy.exe", Path(get_bundle_dir()) / "scrcpy" / "scrcpy.exe"]:
                if candidate.is_file(): exe = str(candidate); break
        if not exe:
            self._log("[SCRCPY] scrcpy executable not found in PATH/bundle."); return
        try:
            subprocess.Popen([exe, "-s", self.serial, "--window-title", f"GeloTech Mirror - {self.serial}"])
            self._log("[SCRCPY] Screen mirror started (Qt fallback window).")
        except Exception as exc: self._log(f"[SCRCPY] Failed to start mirror: {exc}")

    # -------------------------- system/admin --------------------------
    def _adb_simple(self, command):
        if self.serial: self._adb(["-s", self.serial] + command)

    def _reauthorize(self):
        if self.serial: self._adb(["-s", self.serial, "shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_MOUNTED"])

    def _driver_help(self):
        QMessageBox.information(self, "ADB Drivers", "Use the existing bundled driver workflow from the legacy app. The Qt migration keeps the connection command surface but does not replace the tested driver installer.")

    def _choose_apk(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK files (*.apk)")
        if path: self.vt_path.setText(path)

    def refresh_accounts(self):
        if self.current_user.get("role") != "admin":
            self.accounts.setRowCount(0); self.accounts.setColumnCount(1); self.accounts.setHorizontalHeaderLabels(["Admin only"]); return
        users, error = _fetch_verified_users(self.session)
        if error:
            self.accounts.setRowCount(0); return
        items = list((users or {}).items())
        self.accounts.setRowCount(len(items))
        for r, (email, info) in enumerate(items):
            self.accounts.setItem(r, 0, QTableWidgetItem(email))
            self.accounts.setItem(r, 1, QTableWidgetItem(str(info.get("role", "user"))))
            self.accounts.setItem(r, 2, QTableWidgetItem("Yes" if info.get("blocked") else "No"))

    def _logout(self):
        self.session = None; self.current_user = {}; self.user_label.setText("Not signed in"); self._open_login()

    # -------------------------- logging/close --------------------------
    def _log(self, text: str):
        self.log.appendPlainText(str(text))

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            session = Path(get_session_database_path())
            if session.exists(): session.unlink()
        except Exception: pass
        event.accept()
