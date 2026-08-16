"""PySide6 main window for the GeloTech Qt migration."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, QObject, Signal
from PySide6.QtGui import QCloseEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
    QPlainTextEdit, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QHeaderView,
)

from tech_common import (
    APP_VERSION, get_bundle_dir, get_cache_dir, get_session_database_path,
    load_package_database, save_apps_cache, load_apps_cache,
)
from tech_reg import (
    _fetch_verified_sources, _fetch_verified_users, _login_user,
    _request_password, _set_user_blocked,
)
from tech_qt_icons import ICONS, load_icon
from tech_qt_themes import DEFAULT_THEME, DEFAULT_UI_FONT, apply_theme


class LoginWorker(QObject):
    finished = Signal(bool, str, object, object, object)

    def __init__(self, email, password, phrase):
        super().__init__(); self.email = email; self.password = password; self.phrase = phrase

    def run(self):
        ok, reason, user, session = _login_user(self.email, self.password, self.phrase or None)
        if not ok:
            self.finished.emit(False, reason, None, None, None); return
        self.finished.emit(True, "", user, session, _fetch_verified_sources())


class LoginDialog(QDialog):
    logged_in = Signal(object, object, object)

    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle(f"GeloTech Tool v{APP_VERSION} - Sign in"); self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel("GELOTECH"); title.setObjectName("brand"); title.setAlignment(Qt.AlignCenter); layout.addWidget(title)
        sub = QLabel("Sign in to continue"); sub.setAlignment(Qt.AlignCenter); layout.addWidget(sub)
        form = QFormLayout(); self.email = QLineEdit(); self.password = QLineEdit(); self.phrase = QLineEdit()
        self.email.setPlaceholderText("Email"); self.password.setPlaceholderText("Password"); self.phrase.setPlaceholderText("Admin secret phrase")
        self.password.setEchoMode(QLineEdit.Password); self.phrase.setEchoMode(QLineEdit.Password); self.phrase.hide()
        form.addRow("Email", self.email); form.addRow("Password", self.password); form.addRow("Admin phrase", self.phrase); layout.addLayout(form)
        self.status = QLabel(""); self.status.setWordWrap(True); layout.addWidget(self.status)
        row = QHBoxLayout(); self.signin = QPushButton("Sign in"); self.signin.setIcon(load_icon("login")); self.register = QPushButton("Create an account")
        row.addWidget(self.signin); row.addWidget(self.register); layout.addLayout(row)
        self.email.textChanged.connect(lambda s: self.phrase.setVisible(s.strip().lower() == "admin"))
        self.signin.clicked.connect(self._sign_in); self.register.clicked.connect(self._register)
        self._thread = None; self._worker = None

    def _register(self):
        ok, message = _request_password(self.email.text().strip()); self.status.setText(message)
        if ok: QMessageBox.information(self, "GeloTech", message)

    def _sign_in(self):
        if self._thread or not self.email.text().strip() or not self.password.text():
            self.status.setText("Enter your email and password."); return
        self.signin.setEnabled(False); self.status.setText("Signing in…")
        self._thread = QThread(self); self._worker = LoginWorker(self.email.text().strip(), self.password.text(), self.phrase.text())
        self._worker.moveToThread(self._thread); self._thread.started.connect(self._worker.run); self._worker.finished.connect(self._finished); self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater); self._thread.start()

    def _finished(self, ok, reason, user, session, db_bytes):
        self.signin.setEnabled(True); self._thread = None; self._worker = None
        if not ok: self.status.setText(reason); return
        self.logged_in.emit(user, session, db_bytes); self.accept()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f"GeloTech Tool v{APP_VERSION}"); self.resize(1360, 820)
        self.current_user = {}; self.session = None; self.db = {}; self.serial = None; self._seen_serials = set(); self._auto_mirror_seen = set()
        self.theme_name = DEFAULT_THEME; self.dark_mode = True; self._load_preferences(); self._build_shell(); self._apply_theme()
        self._adb_timer = QTimer(self); self._adb_timer.timeout.connect(self._scan_devices); self._adb_timer.start(3000); QTimer.singleShot(250, self._open_login); self._scrcpy_proc = None

    def _build_shell(self):
        root = QWidget(); layout = QHBoxLayout(root); layout.setContentsMargins(0, 0, 0, 0)
        self.sidebar = QFrame(); self.sidebar.setObjectName("sidebar"); self.sidebar.setMinimumWidth(240); side = QVBoxLayout(self.sidebar); side.setContentsMargins(12, 12, 12, 12)
        self.brand = QLabel("GELOTECH"); self.brand.setObjectName("brand"); side.addWidget(self.brand)
        self.version = QLabel(f"TECH TOOL\nv{APP_VERSION}"); self.version.setAlignment(Qt.AlignCenter); side.addWidget(self.version)
        self.user_label = QLabel("Not signed in"); self.user_label.setObjectName("muted"); self.user_label.setAlignment(Qt.AlignCenter); side.addWidget(self.user_label)
        self.theme_btn = QPushButton("Dark" if self.dark_mode else "Light"); self.theme_btn.setIcon(load_icon("settings")); self.theme_btn.clicked.connect(self._toggle_theme); side.addWidget(self.theme_btn)
        self.nav = QListWidget(); self.nav.setSelectionMode(QAbstractItemView.SingleSelection); side.addWidget(self.nav, 1)
        for title, key in [("Dashboard", "Dashboard"), ("App Cleaner", "Scan"), ("Monitor Apps", "Monitor Apps"), ("Block Ads DNS", "Block Ads DNS"), ("VirusTotal", "VirusTotal"), ("Task Manager", "database"), ("Accounts", "Accounts")]:
            self.nav.addItem(QListWidgetItem(load_icon(ICONS.get(key, "info-circle")), title))
        self.nav.currentRowChanged.connect(self._nav_changed)
        for text, key, slot in [
            ("Reboot to Recovery", "Reboot", lambda: self._adb_simple(["reboot", "recovery"])),
            ("Reboot to Fastboot", "Power", lambda: self._adb_simple(["reboot", "bootloader"])), ("Re-authorize ADB", "Re-authorize ADB", self._reauthorize),
            ("Fix / DL ADB Drivers", "Fix Drivers", self._driver_help), ("Logout", "Logout", self._logout),
        ]:
            b = QPushButton(text); b.setIcon(load_icon(ICONS.get(key, "info-circle"))); b.clicked.connect(slot); side.addWidget(b)
        # USB debugging + How-to hints placed below the sidebar logouts
        usb = QLabel("📱 USB debugging:\nEnable Developer Options → USB debugging, connect the phone, then tap Allow.\nGeloTech automatically prepares app icons for new devices.")
        usb.setWordWrap(True); usb.setObjectName("muted"); side.addWidget(usb)
        howto = QLabel("💡 How to use:\nRefresh loads user apps. Load Apps chooses All / User / System / Disabled.\nAdvanced Filter uses the database. Scan Bloatware filters by UAD level.\nRight-click a row for app actions.")
        howto.setWordWrap(True); howto.setObjectName("muted"); side.addWidget(howto)
        for text in ["📱 USB debugging:\nEnable Developer Options → USB debugging, connect the phone, then tap Allow.\nGeloTech automatically prepares app icons for new devices.", "💡 How to use:\nRefresh loads user apps. Load Apps chooses All / User / System / Disabled.\nAdvanced Filter uses the database. Scan Bloatware filters by UAD level.\nRight-click a row for app actions."]:
            label = QLabel(text); label.setWordWrap(True); label.setObjectName("muted"); side.addWidget(label)
        self.stack = QStackedWidget(); self.pages = [self._dashboard_page(), self._cleaner_page(), self._monitor_page(), self._dns_page(), self._vt_page(), self._task_page(), self._accounts_page()]
        for page in self.pages: self.stack.addWidget(page)
        layout.addWidget(self.sidebar); layout.addWidget(self.stack, 1); self.setCentralWidget(root); self.nav.setCurrentRow(0)

    def _nav_changed(self, row):
        if 0 <= row < self.stack.count():
            self.stack.setCurrentIndex(row)
            if row == 1: self.refresh_apps()
            elif row == 2: self._refresh_monitor()
            elif row == 5: self._refresh_task_manager()
            elif row == 6: self.refresh_accounts()

    def _dashboard_page(self):
        page = QWidget(); outer = QVBoxLayout(page); top = QHBoxLayout(); phone = QFrame(); pv = QVBoxLayout(phone)
        image = QLabel(); image.setAlignment(Qt.AlignCenter); asset = Path(getattr(__import__("sys"), "_MEIPASS", os.path.dirname(__file__))) / "assets" / "phone_devices" / "iPhone17_P_PM_CosmicOrange@2x.png"
        if asset.is_file(): image.setPixmap(QPixmap(str(asset)).scaled(360, 740, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else: image.setText("iPhone mockup")
        pv.addWidget(image); self.log = QPlainTextEdit(readOnly=True); self.log.setMaximumHeight(170); pv.addWidget(self.log)
        row = QHBoxLayout(); refresh = QPushButton("Refresh"); refresh.setIcon(load_icon("refresh")); refresh.clicked.connect(self.refresh_apps); mirror = QPushButton("Screen Mirror"); mirror.setIcon(load_icon("device-mobile")); mirror.clicked.connect(self.start_mirror); row.addWidget(refresh); row.addWidget(mirror); pv.addLayout(row)
        info = QFrame(); iv = QVBoxLayout(info); self.device_label = QLabel("No device connected"); self.device_label.setWordWrap(True); self.phone_status = QLabel("Waiting for ADB…"); iv.addWidget(self.device_label); iv.addWidget(self.phone_status)
        top.addWidget(phone, 1); top.addWidget(info, 1); outer.addLayout(top); return page

    def _cleaner_page(self):
        page = QWidget(); layout = QVBoxLayout(page); bar = QHBoxLayout()
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh_apps); bar.addWidget(refresh)
        load = QPushButton("Load Apps ▾"); menu = QMenu(load); menu.addAction("All", lambda: self.refresh_apps()); menu.addAction("User", lambda: self.refresh_apps("user")); menu.addAction("System", lambda: self.refresh_apps("system")); menu.addAction("Disabled", lambda: self.refresh_apps("disabled")); load.setMenu(menu); bar.addWidget(load)
        advanced = QPushButton("Advanced Filter"); advanced.clicked.connect(self.apply_advanced_filter); bar.addWidget(advanced)
        bloat = QPushButton("Scan Bloatware ▾"); bm = QMenu(bloat)
        for level in ("Recommended", "Advanced", "Expert", "Unsafe"): bm.addAction(level, lambda l=level: self.scan_bloatware(l))
        bloat.setMenu(bm); bar.addWidget(bloat)
        backup = QPushButton("Restore / Backup"); backup.clicked.connect(self._backup_help); bar.addWidget(backup); layout.addLayout(bar)
        self.cleaner_status = QLabel("Connect a device and press Refresh."); layout.addWidget(self.cleaner_status)
        self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(["APP NAME", "PACKAGE ID", "UAD LEVEL", "DESCRIPTION"]); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.setAlternatingRowColors(True); self.table.setWordWrap(False); self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed); self.table.setColumnWidth(3, 900); self.table.setContextMenuPolicy(Qt.CustomContextMenu); self.table.customContextMenuRequested.connect(self._table_menu)
        layout.addWidget(self.table, 1); return page

    def _monitor_page(self):
        page = QWidget(); layout = QVBoxLayout(page); self.monitor_label = QLabel("Monitor Running Apps"); self.monitor_text = QPlainTextEdit(readOnly=True); layout.addWidget(self.monitor_label); layout.addWidget(self.monitor_text, 1); return page

    def _dns_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("Block Ads DNS")); row = QHBoxLayout(); self.dns = QComboBox(); self.dns.addItems(["dns.adguard-dns.com", "one.one.one.one", "dns.google", "dns.quad9.net"]); a = QPushButton("Apply DNS"); a.clicked.connect(self.apply_dns); off = QPushButton("Disable"); off.clicked.connect(self.disable_dns); row.addWidget(self.dns, 1); row.addWidget(a); row.addWidget(off); layout.addLayout(row); return page

    def _vt_page(self):
        page = QWidget(); layout = QVBoxLayout(page); layout.addWidget(QLabel("VirusTotal Scanner")); self.vt_path = QLineEdit(); b = QPushButton("Choose APK…"); b.clicked.connect(self._choose_apk); layout.addWidget(self.vt_path); layout.addWidget(b); layout.addWidget(QLabel("The existing VirusTotal API workflow remains the source of truth; this page provides the Qt file-selection surface.")); return page

    def _task_page(self):
        page = QWidget(); layout = QVBoxLayout(page); self.task_text = QPlainTextEdit(readOnly=True); layout.addWidget(QLabel("Task Manager / device processes")); layout.addWidget(self.task_text, 1); return page

    def _accounts_page(self):
        page = QWidget(); layout = QVBoxLayout(page); r = QPushButton("Refresh Accounts"); r.clicked.connect(self.refresh_accounts); layout.addWidget(r); self.accounts = QTableWidget(0, 4); self.accounts.setHorizontalHeaderLabels(["EMAIL", "ROLE", "BLOCKED", "ACTION"]); layout.addWidget(self.accounts, 1); return page

    def _preferences_path(self):
        base = Path(os.environ.get("APPDATA", os.path.dirname(__file__))) / "GeloTechTool"; base.mkdir(parents=True, exist_ok=True); return base / "qt_preferences.json"

    def _load_preferences(self):
        try:
            data = json.loads(self._preferences_path().read_text(encoding="utf-8")); mode = data.get("theme", "dark"); self.dark_mode = str(mode).lower() != "light"
        except Exception: pass

    def _save_preferences(self): self._preferences_path().write_text(json.dumps({"theme": "light" if not self.dark_mode else "dark"}, indent=2), encoding="utf-8")
    def _apply_theme(self): apply_theme(QApplication.instance(), DEFAULT_THEME, self.dark_mode, DEFAULT_UI_FONT)

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.theme_btn.setText("Dark" if self.dark_mode else "Light")
        self._save_preferences(); self._apply_theme()

    def _open_login(self):
        dlg = LoginDialog(self); dlg.logged_in.connect(self._login_success)
        if dlg.exec() != QDialog.Accepted: self.close()

    def _login_success(self, user, session, db_bytes):
        self.current_user = user or {}; self.session = session
        if db_bytes: p = Path(get_session_database_path()); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(db_bytes)
        self.db = load_package_database(str(get_session_database_path())); role = str(self.current_user.get("role", "user")); self.user_label.setText(f"{self.current_user.get('email', 'user')} ({role.upper()})"); self._log("Logged in. Dashboard ready."); self._scan_devices()

    def _adb_path(self):
        found = shutil.which("adb")
        if found: return found
        root = Path(get_bundle_dir())
        for candidate in (root / "platform-tools" / "adb.exe", root / "adb.exe", root / "tools" / "adb.exe"):
            if candidate.is_file(): return str(candidate)
        return "adb"

    def _adb(self, args, timeout=30): return subprocess.run([self._adb_path()] + list(args), capture_output=True, text=True, timeout=timeout)

    def _scan_devices(self):
        try: result = self._adb(["devices"], 8)
        except Exception as exc: self.phone_status.setText(f"ADB unavailable: {exc}"); return
        devices = [p.split()[0] for p in result.stdout.splitlines()[1:] if len(p.split()) >= 2 and p.split()[1] == "device"]
        if not devices: self.serial = None; self.device_label.setText("No device connected"); self.phone_status.setText("Waiting for ADB…"); return
        serial = devices[0]; new = serial not in self._seen_serials; self.serial = serial; self._seen_serials.add(serial)
        model = self._adb(["-s", serial, "shell", "getprop", "ro.product.model"], 8).stdout.strip(); android = self._adb(["-s", serial, "shell", "getprop", "ro.build.version.release"], 8).stdout.strip(); self.device_label.setText(f"{model or 'Android device'}\nAndroid {android or '?'}\nADB: {serial}"); self.phone_status.setText("Connected" + (" • new device detected" if new else ""))
        if new:
            self._log(f"[ADB] Connected: {serial}"); self._prepare_icon_cache(serial)
            if serial not in self._auto_mirror_seen: self._auto_mirror_seen.add(serial); QTimer.singleShot(5000, self.start_mirror)

    def _cache_dir_for(self, serial): return Path(get_cache_dir()) / hashlib.sha256(serial.encode()).hexdigest()[:32]

    def _prepare_icon_cache(self, serial):
        cache = self._cache_dir_for(serial); cache.mkdir(parents=True, exist_ok=True); manifest = cache / "packages.jsonl"
        if manifest.is_file():
            try: count = sum(1 for _ in manifest.open(encoding="utf-8"))
            except Exception: count = 0
            self._log(f"[GeloTech] Icons ready from device cache ({count} entries)."); return
        helper = Path(get_bundle_dir()) / "ApkIconHelper.apk"
        if helper.is_file():
            try: result = self._adb(["-s", serial, "install", "-r", str(helper)], 60); self._log("[GeloTech] ApkIconHelper prepared on the new device." if result.returncode == 0 else f"[GeloTech] Helper install returned {result.returncode}.")
            except Exception as exc: self._log(f"[GeloTech] Icon helper preparation failed: {exc}")
        else: self._log("[GeloTech] ApkIconHelper.apk not available in this source build; cache restore will still be used when present.")

    def refresh_apps(self, mode="all"):
        if not self.serial: self._scan_devices()
        if not self.serial: self.cleaner_status.setText("Connect a device first."); return
        flags = {"user": "-3", "system": "-s", "disabled": "-d"}; args = ["-s", self.serial, "shell", "pm", "list", "packages"]
        if mode in flags: args.append(flags[mode])
        try:
            out = self._adb(args, 30); packages = [line.split(":", 1)[-1].strip() for line in out.stdout.splitlines() if line.startswith("package:")]; save_apps_cache(packages, self.serial)
        except Exception: packages = load_apps_cache(self.serial)
        rows = []
        for pkg in packages:
            rec = self.db.get(pkg, {}) if isinstance(self.db, dict) else {}; label = rec.get("label") or pkg; rows.append((label, pkg, rec.get("removal", "Unknown"), rec.get("description", "No description available.")))
        rows.sort(key=lambda x: x[0].lower()); self.table.setRowCount(len(rows))
        for r, (label, pkg, level, desc) in enumerate(rows):
            icon = self._cached_icon(pkg)
            for c, value in enumerate((label, pkg, level, desc)):
                item = QTableWidgetItem(str(value));
                if c == 0 and not icon.isNull(): item.setIcon(icon)
                self.table.setItem(r, c, item)
        self.cleaner_status.setText(f"{len(rows)} packages loaded. Horizontal scrollbar reads full descriptions.")

    def _cached_icon(self, package):
        root = self._cache_dir_for(self.serial) if self.serial else None
        if not root or not root.exists(): return load_icon("device-mobile")
        from PySide6.QtGui import QIcon
        for path in (root / f"{package}.png", root / f"{package}.ico", root / "apk_icon_export" / f"{package}.png"):
            if path.is_file(): return QIcon(str(path))
        return load_icon("device-mobile")

    def apply_advanced_filter(self):
        dlg = QDialog(self); dlg.setWindowTitle("Advanced Filter"); form = QFormLayout(dlg); level = QComboBox(); level.addItems(["Any", "Recommended", "Advanced", "Expert", "Unsafe"]); form.addRow("UAD level", level); buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel); form.addWidget(buttons); buttons.rejected.connect(dlg.reject); buttons.accepted.connect(dlg.accept)
        if dlg.exec():
            value = level.currentText(); self._filter_table(lambda r: value == "Any" or self.table.item(r, 2).text() == value)

    def scan_bloatware(self, level):
        self.refresh_apps("all"); self._filter_table(lambda r: self.table.item(r, 2).text() == level); self._log(f"[GeloTech] Scan Bloatware: showing '{level}' apps from the complete installed list.")

    def _filter_table(self, predicate):
        shown = 0
        for r in range(self.table.rowCount()):
            visible = predicate(r); self.table.setRowHidden(r, not visible); shown += int(visible)
        self.cleaner_status.setText(f"{shown} matching apps shown.")

    def _table_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0: return
        item = self.table.item(row, 1)
        if item is None: return
        package = item.text(); menu = QMenu(self); menu.addAction("Disable", lambda: self._package_action(package, "disable-user")); menu.addAction("Uninstall", lambda: self._package_action(package, "uninstall", "--user", "0")); menu.addAction("Clear App Data", lambda: self._package_action(package, "clear", "--user", "0")); menu.exec(self.table.viewport().mapToGlobal(pos))

    def _package_action(self, package, action, *extra):
        if not self.serial: return
        try:
            result = self._adb(["-s", self.serial, "shell", "pm", action, *extra, package], 30); self._log(f"[ADB] {action} {package}: {result.stdout.strip() or result.stderr.strip()}"); self.refresh_apps()
        except Exception as exc: QMessageBox.warning(self, "ADB", str(exc))

    def _backup_help(self): QMessageBox.information(self, "Restore / Backup", "The existing APK backup/restore logic remains authoritative. This Qt page is wired for the full dialog port.")

    def _refresh_monitor(self):
        if not self.serial: self.monitor_text.setPlainText("No device connected."); return
        try: self.monitor_text.setPlainText(self._adb(["-s", self.serial, "shell", "dumpsys", "activity", "activities"], 12).stdout[-14000:])
        except Exception as exc: self.monitor_text.setPlainText(str(exc))

    def _refresh_task_manager(self):
        if not self.serial: self.task_text.setPlainText("No device connected."); return
        try: self.task_text.setPlainText(self._adb(["-s", self.serial, "shell", "ps", "-A"], 12).stdout[-16000:])
        except Exception as exc: self.task_text.setPlainText(str(exc))

    def apply_dns(self):
        if self.serial: self._adb(["-s", self.serial, "shell", "settings", "put", "global", "private_dns_mode", "hostname"]); self._adb(["-s", self.serial, "shell", "settings", "put", "global", "private_dns_specifier", self.dns.currentText()])

    def disable_dns(self):
        if self.serial: self._adb(["-s", self.serial, "shell", "settings", "put", "global", "private_dns_mode", "off"])

    def start_mirror(self):
        if not self.serial: return
        exe = shutil.which("scrcpy") or next((str(p) for p in [Path(get_bundle_dir()) / "scrcpy.exe", Path(get_bundle_dir()) / "scrcpy" / "scrcpy.exe"] if p.is_file()), None)
        if not exe: self._log("[SCRCPY] scrcpy executable not found in PATH/bundle."); return
        try:
            self._scrcpy_proc = subprocess.Popen([exe, "-s", self.serial, "--window-title", f"GeloTech Mirror - {self.serial}"])
            self._log("[SCRCPY] Screen mirror started.")
        except Exception as exc: self._log(f"[SCRCPY] Failed to start mirror: {exc}")

    def stop_mirror(self):
        proc = getattr(self, "_qt_scrcpy_process", None) or getattr(self, "_scrcpy_proc", None)
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try: proc.kill()
                except Exception: pass
            self._scrcpy_proc = None
            self._qt_scrcpy_process = None
            self._log("[SCRCPY] Screen mirror stopped.")
        if hasattr(self, "_qt_scrcpy_timer") and self._qt_scrcpy_timer:
            self._qt_scrcpy_timer.stop()
            self._qt_scrcpy_timer.deleteLater()
            self._qt_scrcpy_timer = None
        overlay = getattr(self, "_qt_scrcpy_overlay", None)
        if overlay:
            try: overlay.close(); overlay.deleteLater()
            except Exception: pass
            self._qt_scrcpy_overlay = None

    def _adb_simple(self, command):
        if self.serial: self._adb(["-s", self.serial] + command)

    def _reauthorize(self):
        try: subprocess.run([self._adb_path(), "reconnect"], capture_output=True, text=True, timeout=10)
        except Exception as exc: self._log(f"[ADB] reconnect failed: {exc}")

    def _driver_help(self): QMessageBox.information(self, "ADB Drivers", "Use the existing bundled ADB driver installer from the legacy build. The Qt migration intentionally does not replace the tested driver package yet.")

    def _choose_apk(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", "", "APK files (*.apk)")
        if path: self.vt_path.setText(path)

    def refresh_accounts(self):
        if self.current_user.get("role") != "admin": self.accounts.setRowCount(0); return
        users, error = _fetch_verified_users(self.session)
        if error: self._log(error); return
        items = list((users or {}).items()); self.accounts.setRowCount(len(items))
        for r, (email, info) in enumerate(items):
            blocked = bool(info.get("blocked")); self.accounts.setItem(r, 0, QTableWidgetItem(email)); self.accounts.setItem(r, 1, QTableWidgetItem(str(info.get("role", "user")))); self.accounts.setItem(r, 2, QTableWidgetItem("Yes" if blocked else "No"))
            button = QPushButton("Unblock" if blocked else "Block"); button.clicked.connect(lambda _=False, e=email, b=not blocked: self._block_account(e, b))
            # Change password (managed via admin phrase / external system)
            change_pw = QPushButton("Change password"); change_pw.setEnabled(False); change_pw.setToolTip("Password change managed via admin phrase / external system")
            self.accounts.setCellWidget(r, 3, button)
            # Insert change password widget after the block button
            layout = QVBoxLayout(); layout.addWidget(button); layout.addWidget(change_pw)
            w = QWidget(); w.setLayout(layout)
            self.accounts.setCellWidget(r, 3, w)

    def _block_account(self, email, blocked):
        error = _set_user_blocked(email, blocked, self.session)
        if error: QMessageBox.warning(self, "Accounts", error)
        else: self.refresh_accounts()

    def _logout(self): self.session = None; self.current_user = {}; self.user_label.setText("Not signed in"); self._open_login()
    def _log(self, text): self.log.appendPlainText(str(text))

    def closeEvent(self, event: QCloseEvent):
        if hasattr(self, "_qt_stop_scrcpy"):
            self._qt_stop_scrcpy()
        self.stop_mirror()
        try:
            p = Path(get_session_database_path())
            if p.exists(): p.unlink()
        except Exception: pass
        event.accept()
