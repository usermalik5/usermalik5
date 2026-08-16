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
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from tech_common import APP_VERSION, get_bundle_dir, get_session_database_path, load_package_database
from tech_qt_icons import ICONS, load_icon, tinted_icon


def _button(text: str, icon_key: str | None = None) -> QPushButton:
    button = QPushButton(text)
    if icon_key:
        button.setIcon(load_icon(ICONS.get(icon_key, icon_key)))
    button.setMinimumHeight(30)
    return button


class ActionConfirmDialog(QDialog):
    """A detailed, themed confirmation dialog used for device-state-changing
    actions. Shows what the action does, its consequences, then Confirm/Cancel."""

    def __init__(self, parent, title, icon_name, color, description, bullets, confirm_text="Confirm"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)
        root = QHBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(18)
        icon = QLabel()
        icon.setPixmap(tinted_icon(icon_name, color, 44).pixmap(44, 44))
        icon.setFixedSize(48, 48)
        root.addWidget(icon, 0, Qt.AlignTop)
        right = QVBoxLayout()
        right.setSpacing(10)
        t = QLabel(title)
        t.setObjectName("dialogTitle")
        right.addWidget(t)
        desc = QLabel(description)
        desc.setWordWrap(True)
        desc.setObjectName("dialogDesc")
        right.addWidget(desc)
        bl = QLabel("• " + "\n• ".join(bullets))
        bl.setWordWrap(True)
        bl.setObjectName("dialogBullets")
        right.addWidget(bl)
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("linkButton")
        cancel.clicked.connect(self.reject)
        ok = QPushButton(confirm_text)
        ok.setStyleSheet(
            f"QPushButton{{background:{color};border:1px solid {color};color:white;border-radius:8px;"
            f"padding:7px 16px;min-height:30px;font-weight:800;}}"
            f"QPushButton:hover{{background:{color};border:1px solid {color};}}"
        )
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        right.addLayout(btns)
        root.addLayout(right, 1)


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
    # The auto-refresh hook only fires on serial *transitions*. If the phone
    # was already connected while the login dialog was open, the table would
    # stay empty (or show "No description available.") until a manual Refresh.
    # Populate it here with the freshly loaded database.
    QTimer.singleShot(250, lambda: self.refresh_apps("all"))


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
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)
    title = QLabel("DASHBOARD")
    title.setObjectName("pageTitle")
    page_layout.addWidget(title)
    outer = QHBoxLayout()
    outer.setContentsMargins(10, 10, 10, 8)
    outer.setSpacing(10)
    page_layout.addLayout(outer, 1)

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
    actions = QHBoxLayout()
    self._monitor_action_btns = []
    for label, icon, fn in (
        ("Force Stop", "power", _monitor_force_stop),
        ("Disable", "x", _monitor_disable),
        ("Uninstall", "trash", _monitor_uninstall),
        ("Clear Data", "database", _monitor_clear_data),
        ("Open", "device-mobile", _monitor_open),
        ("Copy Name", "copy", _monitor_copy),
    ):
        b = _button(label, icon)
        b.clicked.connect(lambda _=False, f=fn: f(self))
        b.setEnabled(False)
        actions.addWidget(b)
        self._monitor_action_btns.append(b)
    actions.addStretch(1)
    layout.addLayout(actions)
    self.monitor_table = QTableWidget(0, 2)
    self.monitor_table.setHorizontalHeaderLabels(["PACKAGE", "STATE"])
    self.monitor_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.monitor_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.monitor_table.setSelectionMode(QAbstractItemView.SingleSelection)
    self.monitor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    self.monitor_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    self.monitor_table.setContextMenuPolicy(Qt.CustomContextMenu)
    self.monitor_table.customContextMenuRequested.connect(lambda pos: _monitor_menu(self, pos))
    self.monitor_table.itemSelectionChanged.connect(lambda: _monitor_selection_changed(self))
    layout.addWidget(self.monitor_table, 1)
    return page


def _monitor_selected(self):
    rows = self.monitor_table.selectionModel().selectedRows()
    if not rows:
        return None
    item = self.monitor_table.item(rows[0].row(), 0)
    return item.text() if item else None


def _monitor_selection_changed(self):
    has = _monitor_selected(self) is not None
    for b in getattr(self, "_monitor_action_btns", []):
        b.setEnabled(has)


def _monitor_force_stop(self):
    pkg = _monitor_selected(self)
    if not pkg:
        return
    self._adb_simple(["shell", "am", "force-stop", pkg]); self._log(f"[Monitor] Force-stop {pkg}"); self._refresh_monitor()


def _monitor_disable(self):
    pkg = _monitor_selected(self)
    if not pkg:
        return
    self._adb_simple(["shell", "pm", "disable-user", "--user", "0", pkg]); self._log(f"[Monitor] Disable {pkg}"); self._refresh_monitor()


def _monitor_uninstall(self):
    pkg = _monitor_selected(self)
    if not pkg:
        return
    self._adb_simple(["shell", "pm", "uninstall", "-k", "--user", "0", pkg]); self._log(f"[Monitor] Uninstall {pkg}"); self._refresh_monitor()


def _monitor_clear_data(self):
    pkg = _monitor_selected(self)
    if not pkg:
        return
    self._adb_simple(["shell", "pm", "clear", pkg]); self._log(f"[Monitor] Clear data {pkg}"); self._refresh_monitor()


def _monitor_open(self):
    pkg = _monitor_selected(self)
    if not pkg:
        return
    self._adb_simple(["shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1"]); self._log(f"[Monitor] Open {pkg}")


def _monitor_copy(self):
    pkg = _monitor_selected(self)
    if not pkg:
        return
    QApplication.clipboard().setText(pkg); self._log(f"[Monitor] Copied package name: {pkg}")


def _monitor_menu(self, pos):
    row = self.monitor_table.rowAt(pos.y())
    if row < 0:
        return
    item = self.monitor_table.item(row, 0)
    if item is None:
        return
    package = item.text()
    menu = QMenu(self)
    menu.addAction(load_icon("power"), "Force Stop", lambda: self._adb_simple(["shell", "am", "force-stop", package]))
    menu.addAction(load_icon("device-mobile"), "Open", lambda: self._adb_simple(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"]))
    menu.addAction(load_icon("x"), "Disable", lambda: self._package_action(package, "disable-user"))
    menu.addAction(load_icon("trash"), "Uninstall", lambda: self._package_action(package, "uninstall", "--user", "0"))
    menu.addAction(load_icon("database"), "Clear Data", lambda: self._adb_simple(["shell", "pm", "clear", package]))
    menu.addAction(load_icon("copy"), "Copy Name", lambda: (QApplication.clipboard().setText(package), self._log(f"[Monitor] Copied {package}")))
    menu.exec(self.monitor_table.viewport().mapToGlobal(pos))


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
    self.dns.addItems(["dns.adguard-dns.com", "one.one.one.one", "dns.google", "dns.quad9.net", "dns.nextdns.io"])
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
    title = QLabel("ADMIN PANEL")
    title.setObjectName("pageTitle")
    layout.addWidget(title)
    top = QHBoxLayout()
    refresh = _button("Refresh Accounts", "refresh")
    refresh.clicked.connect(self.refresh_accounts)
    top.addWidget(refresh); top.addStretch(1)
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
    self.sidebar = QFrame(); self.sidebar.setObjectName("sidebar"); self.sidebar.setFixedWidth(200)
    side = QVBoxLayout(self.sidebar); side.setContentsMargins(10, 7, 10, 8); side.setSpacing(0)

    header = QLabel(
        '<span style="color:#1a8cff; font-size:22pt; font-weight:800;">GELOTECH</span><br>'
        '<span style="color:#555b63; font-size:8pt;">Angelo Estrada Espinosa © 2026 GeloTech</span><br>'
        '<a href="https://gsmcodeph.com" style="color:#58a6ff; font-size:8pt;">Gsmcodeph.com</a><br>'
        '<a href="https://facebook.com/gelotechxyz" style="color:#58a6ff; font-size:8pt;">facebook.com/gelotechxyz</a>'
    )
    header.setAlignment(Qt.AlignCenter); header.setOpenExternalLinks(True); side.addWidget(header)

    self.theme_btn = _button("Dark" if self.dark_mode else "Light", "settings"); self.theme_btn.clicked.connect(self._toggle_theme); side.addWidget(self.theme_btn)

    for title, idx, action in (("DASHBOARD", 0, lambda: (self.stack.setCurrentIndex(0), self.refresh_apps())), ("MONITOR", 1, lambda: (self.stack.setCurrentIndex(1), self._refresh_monitor())), ("AD BLOCK", 2, lambda: self.stack.setCurrentIndex(2)), ("VT SCAN", 3, lambda: self.stack.setCurrentIndex(3))):
        b = _button(title); b.clicked.connect(action); side.addWidget(b)

    for text, mode, icon, color in (("RECOVERY", "recovery", "refresh", "#f97316"), ("FASTBOOT", "bootloader", "power", "#fb923c")):
        b = _button(text, icon); b.clicked.connect(lambda _=False, m=mode: _confirm_reboot(self, m)); side.addWidget(b)
    auth = _button("AUTH ADB", "plug-connected"); auth.clicked.connect(lambda: _confirm_adb_auth(self)); side.addWidget(auth)
    drivers = _button("ADB DRIVERS", "tool"); drivers.clicked.connect(lambda: _confirm_drivers(self)); side.addWidget(drivers)
    accounts = _button("ADMIN"); accounts.clicked.connect(self._show_accounts); side.addWidget(accounts)
    logout = _button("LOGOUT"); logout.clicked.connect(self._logout); side.addWidget(logout)

    side.addSpacing(10)
    usb = QFrame(); usb.setObjectName("sidebarGuide")
    ul = QVBoxLayout(usb); ul.setContentsMargins(8, 8, 8, 8)
    usb_label = QLabel(
        "\U0001f4f1 USB debugging:\n"
        "Enable Developer Options \u2192 USB debugging, connect the phone, then tap Allow.\n"
        "GeloTech automatically prepares app icons for new devices."
    )
    usb_label.setWordWrap(True); usb_label.setObjectName("guideText"); ul.addWidget(usb_label)
    side.addWidget(usb)
    howto = QFrame(); howto.setObjectName("sidebarGuide")
    hl = QVBoxLayout(howto); hl.setContentsMargins(8, 8, 8, 8)
    howto_label = QLabel(
        "\U0001f4a1 How to use:\n"
        "Refresh loads user apps. Load Apps chooses All / User / System / Disabled.\n"
        "Advanced Filter uses the database. Scan Bloatware filters by UAD level.\n"
        "Right-click a row for app actions."
    )
    howto_label.setWordWrap(True); howto_label.setObjectName("guideText"); hl.addWidget(howto_label)
    side.addWidget(howto)

    self.stack = QStackedWidget()
    self.pages = [_build_dashboard(self), _build_monitor(self), _build_dns(self), self._vt_page(), _build_accounts(self)]
    for page in self.pages: self.stack.addWidget(page)
    root_layout.addWidget(self.sidebar); root_layout.addWidget(self.stack, 1); self.setCentralWidget(root); self.stack.setCurrentIndex(0)


def _nav_changed(self, row):
    if 0 <= row < self.stack.count():
        self.stack.setCurrentIndex(row)
        if row == 0:
            self.refresh_apps()
        elif row == 1:
            self._refresh_monitor()


def _show_accounts(self):
    self.stack.setCurrentIndex(4)
    self.refresh_accounts()


def _confirm_reboot(self, mode):
    if mode == "recovery":
        title, icon, color = "Reboot to Recovery", "refresh", "#f97316"
        description = "This restarts the connected phone into Android <b>recovery mode</b>."
        bullets = [
            "The device leaves the normal Android environment and boots the recovery image.",
            "Use this to flash, wipe, or repair the device from recovery.",
            "The screen mirror and ADB session disconnect until the phone is rebooted back to Android.",
        ]
    else:
        title, icon, color = "Reboot to Fastboot", "power", "#fb923c"
        description = "This restarts the connected phone into the <b>bootloader (fastboot)</b> mode."
        bullets = [
            "The device leaves Android and shows the bootloader screen.",
            "Use this to unlock the bootloader or flash images via fastboot.",
            "The screen mirror and ADB session disconnect until the phone is rebooted back to Android.",
        ]
    dlg = ActionConfirmDialog(self, title, icon, color, description, bullets, confirm_text="Reboot now")
    if dlg.exec() == QDialog.Accepted:
        self._adb_simple(["reboot", mode])


def _confirm_adb_auth(self):
    dlg = ActionConfirmDialog(
        self, "Re-authorize ADB", "plug-connected", "#14b8a6",
        "This refreshes the ADB host authorization for this computer.",
        [
            "The phone may show an \u201cAllow USB debugging?\u201d prompt \u2014 tap Allow there.",
            "Use this when the device appears as <i>unauthorized</i> or the connection is stale.",
            "GeloTech re-scans for devices after re-authorizing.",
        ],
        confirm_text="Re-authorize",
    )
    if dlg.exec() == QDialog.Accepted:
        self._reauthorize()


def _confirm_drivers(self):
    dlg = ActionConfirmDialog(
        self, "Fix / Install ADB Drivers", "tool", "#06b6d4",
        "This runs the ADB connection-repair workflow to fix driver and authorization problems.",
        [
            "Stops the current ADB server and starts a fresh one.",
            "Re-scans for connected devices and reports their authorization state.",
            "Resolves most \u201cdevice not found\u201d / unauthorized issues without manual steps.",
        ],
        confirm_text="Run repair",
    )
    if dlg.exec() == QDialog.Accepted:
        if hasattr(self, "action_fix_drivers"):
            self.action_fix_drivers()
        else:
            self._driver_help()


def install_final_qt_fixes(MainWindow):
    """Install the final runtime fixes after all other Qt installers."""
    MainWindow._login_success = _fixed_login_success
    MainWindow._build_shell = _build_shell
    MainWindow._nav_changed = _nav_changed
    MainWindow._show_accounts = _show_accounts
    MainWindow._refresh_monitor = _refresh_monitor
    MainWindow._qt_select_all = _qt_select_all
    MainWindow._qt_filter_table = _qt_filter_table
