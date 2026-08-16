"""Final Qt6 runtime/UI fixes layered after feature installers.

This module fixes integration problems without rewriting the migrated feature
modules: database-path normalization, readable running-app monitoring,
legacy-style sidebar composition, and Accounts controls.
"""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tech_common import APP_VERSION, get_bundle_dir, get_session_database_path, load_package_database
from tech_qt_icons import ICONS, load_icon


def _button(text: str, icon_key: str | None = None) -> QPushButton:
    button = QPushButton(text)
    if icon_key:
        button.setIcon(load_icon(ICONS.get(icon_key, icon_key)))
    button.setMinimumHeight(30)
    return button


def _section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sidebarSection")
    return label


def _phone_pixmap() -> QPixmap:
    path = Path(get_bundle_dir()) / "assets" / "phone_devices" / "iPhone17_P_PM_CosmicOrange@2x.png"
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return pixmap
    pixmap.setDevicePixelRatio(1.0)
    return pixmap.scaled(353, 735, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _database_directory() -> Path:
    session = Path(get_session_database_path())
    return session.parent


def _fixed_login_success(self, user, session, db_bytes):
    self.current_user = user or {}
    self.session = session
    if db_bytes:
        session_path = Path(get_session_database_path())
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_bytes(db_bytes)
        # load_package_database expects a directory, not the JSON filename.
        self.db = load_package_database(str(session_path.parent))
    else:
        self.db = load_package_database(str(_database_directory()))

    role = str(self.current_user.get("role", "user"))
    if hasattr(self, "user_label"):
        self.user_label.setText(f"{self.current_user.get('email', 'user')} ({role.upper()})")
    self._log(f"[GeloTech] Logged in as {self.current_user.get('email', 'user')} ({role.upper()}).")
    self._log(f"[GeloTech] Package database loaded: {len(self.db)} entries.")
    self._scan_devices()


def _refresh_monitor(self):
    if not getattr(self, "serial", None):
        self._scan_devices()
    if not getattr(self, "serial", None):
        if hasattr(self, "monitor_status"):
            self.monitor_status.setText("No device connected.")
        return

    result = self._adb(["-s", self.serial, "shell", "dumpsys", "activity", "activities"], 20)
    output = (result.stdout or "") + (result.stderr or "")
    packages: list[str] = []
    for pattern in (
        r"mResumedActivity:.*?\s([A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+)",
        r"mFocusedApp=ActivityRecord\{.*?\s([A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+)",
    ):
        packages.extend(re.findall(pattern, output))
    cleaned: list[str] = []
    for entry in packages:
        package = entry.split("/", 1)[0]
        if package and package not in cleaned:
            cleaned.append(package)

    if hasattr(self, "monitor_table"):
        self.monitor_table.setRowCount(len(cleaned))
        for row, package in enumerate(cleaned):
            self.monitor_table.setItem(row, 0, QTableWidgetItem(package))
            self.monitor_table.setItem(row, 1, QTableWidgetItem("Foreground / active" if row == 0 else "Active window"))

    if hasattr(self, "monitor_status"):
        foreground = cleaned[0] if cleaned else "None detected"
        self.monitor_status.setText(f"Connected: {self.serial}  •  Foreground: {foreground}")


def _build_dashboard(self) -> QWidget:
    page = QWidget()
    outer = QHBoxLayout(page)
    outer.setContentsMargins(10, 10, 10, 8)
    outer.setSpacing(10)

    phone_panel = QFrame()
    phone_panel.setObjectName("phonePanel")
    phone_panel.setFixedWidth(405)
    pv = QVBoxLayout(phone_panel)
    pv.setContentsMargins(10, 4, 10, 0)

    self.phone_frame = QFrame(phone_panel)
    self.phone_frame.setFixedSize(353, 735)
    self.phone_frame.setObjectName("phoneFrame")

    self.phone_host = QFrame(self.phone_frame)
    self.phone_host.setGeometry(0, 0, 353, 735)
    self.phone_host.setObjectName("phoneHost")

    phone_image = QLabel(self.phone_frame)
    phone_image.setGeometry(0, 0, 353, 735)
    phone_image.setAlignment(Qt.AlignCenter)
    phone_image.setPixmap(_phone_pixmap())
    phone_image.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    self.phone_image = phone_image
    self.phone_frame.show()
    pv.addWidget(self.phone_frame, 0, Qt.AlignCenter)

    row = QHBoxLayout()
    refresh = _button("Refresh", "refresh")
    refresh.clicked.connect(self.refresh_apps)
    mirror = _button("Screen Mirror", "device-mobile")
    mirror.clicked.connect(self.start_mirror)
    row.addWidget(refresh)
    row.addWidget(mirror)
    pv.addLayout(row)

    content = QFrame()
    content.setObjectName("contentPanel")
    cv = QVBoxLayout(content)
    cv.setContentsMargins(0, 0, 0, 0)
    cv.setSpacing(7)

    self.log = self.log if hasattr(self, "log") else None
    if self.log is None:
        from PySide6.QtWidgets import QPlainTextEdit
        self.log = QPlainTextEdit(readOnly=True)
    self.log.setObjectName("liveLog")
    self.log.setMinimumHeight(118)
    self.log.setMaximumHeight(150)
    cv.addWidget(self.log)

    status = QHBoxLayout()
    self.cleaner_status = QLabel("Connect a device and press Refresh to load apps.")
    self.security_label = QLabel("Security indicators: 0")
    self.device_inline = QLabel("NO DEVICE")
    self.cleaner_status.setObjectName("statusText")
    self.security_label.setObjectName("securityText")
    self.device_inline.setObjectName("deviceText")
    self.device_label = self.device_inline
    self.phone_status = self.device_inline
    status.addWidget(self.cleaner_status, 1)
    status.addWidget(self.security_label)
    status.addWidget(self.device_inline)
    cv.addLayout(status)

    controls = QHBoxLayout()
    self.search = QLineEdit()
    self.search.setPlaceholderText("🔍 Search packages...")
    select_all = _button("Select All")
    select_all.clicked.connect(self._qt_select_all)
    controls.addWidget(self.search, 1)
    controls.addWidget(select_all)
    refresh2 = _button("Refresh", "refresh")
    refresh2.clicked.connect(self.refresh_apps)
    controls.addWidget(refresh2)
    cv.addLayout(controls)

    self.table = QTableWidget(0, 4)
    self.table.setObjectName("packageTable")
    self.table.setHorizontalHeaderLabels(["APP NAME", "PACKAGE ID", "UAD LEVEL", "DESCRIPTION"])
    self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.table.setSelectionMode(QAbstractItemView.SingleSelection)
    self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.table.setWordWrap(False)
    self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    header = self.table.horizontalHeader()
    for i in range(4):
        header.setSectionResizeMode(i, QHeaderView.Interactive)
    self.table.setColumnWidth(0, 220)
    self.table.setColumnWidth(1, 245)
    self.table.setColumnWidth(2, 125)
    self.table.setColumnWidth(3, 620)
    self.table.setContextMenuPolicy(Qt.CustomContextMenu)
    self.table.customContextMenuRequested.connect(self._table_menu)
    cv.addWidget(self.table, 1)

    toolbar = QHBoxLayout()
    scan = _button("Scan Bloatware", "search")
    from PySide6.QtWidgets import QMenu
    menu = QMenu(scan)
    for level in ("Recommended", "Advanced", "Expert", "Unsafe"):
        menu.addAction(level, lambda l=level: self.scan_bloatware(l))
    scan.setMenu(menu)
    backup = _button("Restore/Backup", "device-floppy")
    backup.clicked.connect(self._backup_help)
    load = _button("Load Apps", "apps")
    load_menu = QMenu(load)
    for name, mode in (("All", "all"), ("User", "user"), ("System", "system"), ("Disabled", "disabled")):
        load_menu.addAction(name, lambda m=mode: self.refresh_apps(m))
    load.setMenu(load_menu)
    advanced = _button("Advanced Filter", "filter")
    advanced.clicked.connect(self.apply_advanced_filter)
    for widget in (scan, backup, load, advanced):
        toolbar.addWidget(widget)
    cv.addLayout(toolbar)

    outer.addWidget(phone_panel)
    outer.addWidget(content, 1)
    self.search.textChanged.connect(lambda text: self._qt_filter_table(text))
    return page


def _qt_select_all(self):
    checked = False
    if self.table.rowCount():
        first = self.table.item(0, 0)
        checked = first is not None and first.checkState() == Qt.Checked
    target = Qt.Unchecked if checked else Qt.Checked
    for row in range(self.table.rowCount()):
        item = self.table.item(row, 0)
        if item:
            item.setCheckState(target)


def _qt_filter_table(self, text: str):
    needle = text.strip().lower()
    shown = 0
    for row in range(self.table.rowCount()):
        values = []
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            values.append(item.text().lower() if item else "")
        visible = not needle or needle in " ".join(values)
        self.table.setRowHidden(row, not visible)
        shown += int(visible)
    self.cleaner_status.setText(f"{shown} matching apps shown." if needle else f"{self.table.rowCount()} apps loaded.")


def _build_monitor(self) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    title = QLabel("MONITOR RUNNING APPS (APP WATCH)")
    title.setObjectName("pageTitle")
    layout.addWidget(title)
    self.monitor_status = QLabel("Connect a device to monitor foreground apps.")
    layout.addWidget(self.monitor_status)
    row = QHBoxLayout()
    refresh = _button("Refresh", "refresh")
    refresh.clicked.connect(self._refresh_monitor)
    row.addWidget(refresh)
    row.addStretch(1)
    layout.addLayout(row)
    self.monitor_table = QTableWidget(0, 2)
    self.monitor_table.setHorizontalHeaderLabels(["PACKAGE", "STATE"])
    self.monitor_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.monitor_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.monitor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    self.monitor_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    layout.addWidget(self.monitor_table, 1)
    return page


def _build_dns(self) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    title = QLabel("BLOCK MOST APPS POPUP ADS")
    title.setObjectName("pageTitle")
    layout.addWidget(title)
    card = QFrame(); card.setObjectName("contentPanel")
    cv = QVBoxLayout(card)
    cv.addWidget(QLabel("Select a private DNS provider. Apply changes to the connected phone."))
    row = QHBoxLayout()
    from PySide6.QtWidgets import QComboBox
    self.dns = QComboBox()
    self.dns.addItems(["dns.adguard-dns.com", "one.one.one.one", "dns.google", "dns.quad9.net"])
    apply_button = _button("Apply DNS")
    apply_button.clicked.connect(self.apply_dns)
    disable = _button("Disable")
    disable.clicked.connect(self.disable_dns)
    row.addWidget(self.dns, 1); row.addWidget(apply_button); row.addWidget(disable)
    cv.addLayout(row)
    cv.addStretch(1)
    layout.addWidget(card, 1)
    return page


def _build_accounts(self) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    top = QHBoxLayout()
    refresh = _button("Refresh Accounts", "refresh")
    refresh.clicked.connect(self.refresh_accounts)
    change = _button("Change password")
    change.setToolTip("Password changes are managed by the account/authentication service.")
    change.clicked.connect(lambda: QMessageBox.information(self, "Change password", "Password changes are managed by the account authentication service. Use the account recovery flow to change it."))
    top.addWidget(refresh); top.addWidget(change); top.addStretch(1)
    layout.addLayout(top)
    self.accounts = QTableWidget(0, 4)
    self.accounts.setHorizontalHeaderLabels(["EMAIL", "ROLE", "BLOCKED", "ACTION"])
    self.accounts.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.accounts.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    self.accounts.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    self.accounts.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
    self.accounts.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
    layout.addWidget(self.accounts, 1)
    return page


def _build_shell(self):
    root = QWidget(); root_layout = QHBoxLayout(root)
    root_layout.setContentsMargins(0, 0, 0, 0); root_layout.setSpacing(0)
    self.sidebar = QFrame(); self.sidebar.setObjectName("sidebar"); self.sidebar.setFixedWidth(264)
    side = QVBoxLayout(self.sidebar); side.setContentsMargins(10, 7, 10, 8); side.setSpacing(4)
    for text, obj in (("© 2026 GeloTech", "copyrightLabel"), ("GELOTECH", "brand"), (f"TECH TOOL\nv{APP_VERSION} - Angelo Estrada Espinosa", "versionLabel")):
        label = QLabel(text); label.setObjectName(obj); label.setAlignment(Qt.AlignCenter); side.addWidget(label)
    for text, url in (("Gsmcodeph.com", "https://gsmcodeph.com"), ("facebook.com/gelotechxyz", "https://facebook.com/gelotechxyz")):
        link = QLabel(f'<a href="{url}">{text}</a>'); link.setAlignment(Qt.AlignCenter); link.setOpenExternalLinks(True); side.addWidget(link)
    self.theme_btn = _button(self.theme_name.capitalize(), "settings"); self.theme_btn.clicked.connect(self._theme_dialog); side.addWidget(self.theme_btn)
    self.nav = QListWidget(); self.nav.setObjectName("sidebarNav"); self.nav.setSelectionMode(QAbstractItemView.SingleSelection)
    for title, key in (("Dashboard", "Dashboard"), ("Monitor Apps", "Monitor Apps"), ("Block Ads DNS", "Block Ads DNS"), ("VirusTotal", "VirusTotal")):
        self.nav.addItem(QListWidgetItem(load_icon(ICONS.get(key, "info-circle")), title))
    self.nav.currentRowChanged.connect(self._nav_changed)
    side.addWidget(self.nav, 1)
    for text, icon, args in (("Reboot to Recovery", "Reboot", ["reboot", "recovery"]), ("Reboot to Fastboot", "Power", ["reboot", "bootloader"])):
        b = _button(text, icon); b.clicked.connect(lambda _=False, a=args: self._adb_simple(a)); side.addWidget(b)
    for text, icon, slot in (("Re-authorize ADB", "Re-authorize ADB", self._reauthorize), ("Fix / DL ADB Drivers", "Fix Drivers", self._driver_help)):
        b = _button(text, icon); b.clicked.connect(slot); side.addWidget(b)
    accounts = _button("Accounts", "Accounts"); accounts.clicked.connect(self._show_accounts); side.addWidget(accounts)
    logout = _button("Logout", "Logout"); logout.clicked.connect(self._logout); side.addWidget(logout)
    guide = QFrame(); guide.setObjectName("sidebarGuide"); gv = QVBoxLayout(guide); gv.setContentsMargins(8, 7, 8, 7); gv.setSpacing(2)
    title = QLabel("USB DEBUGGING"); title.setObjectName("guideTitle")
    text = QLabel("Enable Developer Options → USB debugging, connect the phone, then tap Allow.\nGeloTech prepares app icons automatically."); text.setObjectName("guideText"); text.setWordWrap(True)
    how_title = QLabel("HOW TO USE"); how_title.setObjectName("guideTitle")
    how = QLabel("Refresh loads apps. Load Apps chooses All / User / System / Disabled.\nAdvanced Filter uses the database. Scan Bloatware filters by UAD level.\nRight-click a row for app actions."); how.setObjectName("guideText"); how.setWordWrap(True)
    for w in (title, text, how_title, how): gv.addWidget(w)
    side.addWidget(guide)

    self.stack = QStackedWidget()
    self.pages = [_build_dashboard(self), _build_monitor(self), _build_dns(self), self._vt_page(), _build_accounts(self)]
    for page in self.pages: self.stack.addWidget(page)
    root_layout.addWidget(self.sidebar); root_layout.addWidget(self.stack, 1); self.setCentralWidget(root); self.nav.setCurrentRow(0)


def _nav_changed(self, row):
    if 0 <= row < self.stack.count():
        self.stack.setCurrentIndex(row)
        if row == 1:
            self._refresh_monitor()


def _show_accounts(self):
    self.stack.setCurrentIndex(4)
    self.refresh_accounts()


def install_final_qt_fixes(MainWindow):
    """Install the final runtime fixes after all other Qt installers."""
    MainWindow._login_success = _fixed_login_success
    MainWindow._build_shell = _build_shell
    MainWindow._nav_changed = _nav_changed
    MainWindow._show_accounts = _show_accounts
    MainWindow._refresh_monitor = _refresh_monitor
    MainWindow._qt_select_all = _qt_select_all
    MainWindow._qt_filter_table = _qt_filter_table
