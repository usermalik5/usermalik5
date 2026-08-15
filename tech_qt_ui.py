"""Qt6 visual-parity shell for the original GeloTech Tk layout.

This module only replaces layout/styling composition. Feature methods remain
owned by their existing Qt migration modules and are wired before MainWindow
is constructed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QLineEdit,
    QHeaderView,
    QAbstractItemView,
    QWidget,
)

from tech_qt_icons import ICONS, load_icon
from tech_qt_themes import PALETTES, UI_FONTS


def _bundle_path(*parts: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", os.path.dirname(__file__)))
    return root.joinpath(*parts)


def _section_label(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sidebarSection")
    return label


def _button(text: str, icon_key: str | None = None) -> QPushButton:
    button = QPushButton(text)
    if icon_key:
        button.setIcon(load_icon(ICONS.get(icon_key, icon_key)))
    button.setMinimumHeight(30)
    button.setCursor(Qt.PointingHandCursor)
    return button


def _build_dashboard(self) -> QWidget:
    page = QWidget()
    outer = QHBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(12)

    # Left phone column: mirrors the legacy application's dominant phone area.
    phone_column = QFrame()
    phone_column.setObjectName("phonePanel")
    phone_column.setFixedWidth(390)
    phone_layout = QVBoxLayout(phone_column)
    phone_layout.setContentsMargins(12, 12, 12, 8)
    phone_layout.setSpacing(8)

    phone = QLabel()
    phone.setObjectName("phoneMockup")
    phone.setAlignment(Qt.AlignCenter)
    phone.setMinimumHeight(690)
    phone.setPixmap(
        QPixmap(str(_bundle_path("assets", "phone_devices", "iPhone17_P_PM_CosmicOrange@2x.png"))).scaled(
            360, 740, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
    )
    phone_layout.addWidget(phone, 1)

    phone_actions = QHBoxLayout()
    refresh_phone = _button("Refresh", "refresh")
    refresh_phone.clicked.connect(self.refresh_apps)
    mirror_phone = _button("Screen Mirror", "device-mobile")
    mirror_phone.clicked.connect(self.start_mirror)
    phone_actions.addWidget(refresh_phone)
    phone_actions.addWidget(mirror_phone)
    phone_layout.addLayout(phone_actions)

    # Right column: live log + instructions + status + cleaner workspace.
    content = QFrame()
    content.setObjectName("contentPanel")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(8)

    self.log = QPlainTextEdit(readOnly=True)
    self.log.setObjectName("liveLog")
    self.log.setPlaceholderText("Live logs")
    self.log.setMinimumHeight(105)
    self.log.setMaximumHeight(150)
    content_layout.addWidget(self.log)

    guide = QFrame()
    guide.setObjectName("guidePanel")
    guide_layout = QVBoxLayout(guide)
    guide_layout.setContentsMargins(10, 7, 10, 7)
    guide_layout.setSpacing(3)
    usb = QLabel(
        "USB debugging: Enable Developer Options → USB debugging, connect the phone, then tap Allow. "
        "GeloTech automatically prepares app icons for new devices."
    )
    usb.setObjectName("guideText")
    usb.setWordWrap(True)
    how = QLabel(
        "How to use: Refresh loads user apps. Load Apps chooses All / User / System / Disabled. "
        "Advanced Filter uses the database. Scan Bloatware filters by UAD level. Right-click a row for app actions."
    )
    how.setObjectName("guideText")
    how.setWordWrap(True)
    guide_layout.addWidget(usb)
    guide_layout.addWidget(how)
    content_layout.addWidget(guide)

    status_row = QHBoxLayout()
    self.cleaner_status = QLabel("Connect a device and press Refresh.")
    self.cleaner_status.setObjectName("statusText")
    self.cleaner_status.setWordWrap(False)
    self.security_label = QLabel("Security indicators: 0")
    self.security_label.setObjectName("securityText")
    self.device_inline = QLabel("NO DEVICE")
    self.device_inline.setObjectName("deviceText")
    status_row.addWidget(self.cleaner_status, 1)
    status_row.addWidget(self.security_label)
    status_row.addWidget(self.device_inline)
    content_layout.addLayout(status_row)

    controls = QHBoxLayout()
    controls.setSpacing(8)
    self.search = QLineEdit()
    self.search.setPlaceholderText("🔍 Search packages...")
    self.search.setClearButtonEnabled(True)
    self.search.setMinimumHeight(34)
    controls.addWidget(self.search, 1)

    select_all = _button("Select All")
    select_all.clicked.connect(lambda: _toggle_select_all(self))
    controls.addWidget(select_all)

    self.legend = QLabel("● Removable    ● Clean Excluded    ● Uninstall Excluded    ● Both Excluded")
    self.legend.setObjectName("legendText")
    controls.addWidget(self.legend, 2)

    refresh = _button("Refresh", "refresh")
    refresh.clicked.connect(self.refresh_apps)
    controls.addWidget(refresh)
    content_layout.addLayout(controls)

    removal = QHBoxLayout()
    removal_label = QLabel("REMOVAL LEVELS:")
    removal_label.setObjectName("subHeading")
    removal.addWidget(removal_label)
    for level in ("Recommended", "Advanced", "Expert", "Unsafe"):
        label = QLabel(f"● {level}")
        label.setObjectName("legendText")
        removal.addWidget(label)
    removal.addStretch(1)
    content_layout.addLayout(removal)

    table = QTableWidget(0, 4)
    table.setObjectName("packageTable")
    table.setHorizontalHeaderLabels(["APP NAME", "PACKAGE ID", "UAD LEVEL", "DESCRIPTION"])
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.Interactive)
    header.setSectionResizeMode(1, QHeaderView.Interactive)
    header.setSectionResizeMode(2, QHeaderView.Interactive)
    header.setSectionResizeMode(3, QHeaderView.Interactive)
    table.setColumnWidth(0, 210)
    table.setColumnWidth(1, 245)
    table.setColumnWidth(2, 125)
    table.setColumnWidth(3, 560)
    table.setContextMenuPolicy(Qt.CustomContextMenu)
    table.customContextMenuRequested.connect(self._table_menu)
    self.table = table
    content_layout.addWidget(table, 1)

    toolbar = QHBoxLayout()
    toolbar.setSpacing(8)

    scan = _button("Scan Bloatware", "search")
    scan_menu = QMenu(scan)
    for level in ("Recommended", "Advanced", "Expert", "Unsafe"):
        scan_menu.addAction(level, lambda l=level: self.scan_bloatware(l))
    scan.setMenu(scan_menu)
    toolbar.addWidget(scan)

    backup = _button("Restore/Backup", "device-floppy")
    backup.clicked.connect(self._backup_help)
    toolbar.addWidget(backup)

    load = _button("Load Apps", "apps")
    load_menu = QMenu(load)
    load_menu.addAction("All", lambda: self.refresh_apps())
    load_menu.addAction("User", lambda: self.refresh_apps("user"))
    load_menu.addAction("System", lambda: self.refresh_apps("system"))
    load_menu.addAction("Disabled", lambda: self.refresh_apps("disabled"))
    load.setMenu(load_menu)
    toolbar.addWidget(load)

    advanced = _button("Advanced Filter", "filter")
    advanced.clicked.connect(self.apply_advanced_filter)
    toolbar.addWidget(advanced)

    content_layout.addLayout(toolbar)
    outer.addWidget(phone_column)
    outer.addWidget(content, 1)
    return page


def _toggle_select_all(window) -> None:
    state = None
    for row in range(window.table.rowCount()):
        item = window.table.item(row, 0)
        if item is not None:
            state = item.checkState()
            break
    target = Qt.Unchecked if state == Qt.Checked else Qt.Checked
    for row in range(window.table.rowCount()):
        item = window.table.item(row, 0)
        if item is not None:
            item.setCheckState(target)


def _search_table(window, text: str) -> None:
    needle = text.strip().lower()
    shown = 0
    for row in range(window.table.rowCount()):
        values = []
        for col in range(4):
            item = window.table.item(row, col)
            values.append(item.text().lower() if item else "")
        visible = not needle or needle in " ".join(values)
        window.table.setRowHidden(row, not visible)
        shown += int(visible)
    if hasattr(window, "cleaner_status"):
        window.cleaner_status.setText(f"{shown} matching apps shown." if needle else f"{window.table.rowCount()} apps loaded.")


def install_visual_parity(MainWindow: type[QMainWindow]) -> None:
    """Replace only MainWindow's shell composition with the legacy geometry."""
    def build_shell(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(264)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(12, 10, 12, 10)
        side.setSpacing(5)

        brand = QLabel("GELOTECH")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        side.addWidget(brand)
        version = QLabel(f"TECH TOOL\nv{self.windowTitle().split('v', 1)[-1]}")
        version.setObjectName("versionLabel")
        version.setAlignment(Qt.AlignCenter)
        side.addWidget(version)

        self.user_label = QLabel("Not signed in")
        self.user_label.setObjectName("muted")
        self.user_label.setAlignment(Qt.AlignCenter)
        side.addWidget(self.user_label)

        theme_btn = _button("Theme / Font", "settings")
        theme_btn.clicked.connect(self._theme_dialog)
        side.addWidget(theme_btn)
        side.addSpacing(4)

        side.addWidget(_section_label("PAGES"))
        self.nav = QListWidget()
        self.nav.setObjectName("sidebarNav")
        self.nav.setSelectionMode(QAbstractItemView.SingleSelection)
        self.nav.setSpacing(2)
        for title, key in [
            ("Dashboard", "Dashboard"),
            ("Monitor Apps", "Monitor Apps"),
            ("Block Ads DNS", "Block Ads DNS"),
            ("VirusTotal", "VirusTotal"),
        ]:
            item = QListWidgetItem(load_icon(ICONS.get(key, "info-circle")), title)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._nav_changed)
        side.addWidget(self.nav)

        mirror = _button("Screen Mirror", "device-mobile")
        mirror.clicked.connect(self.start_mirror)
        side.addWidget(mirror)

        side.addWidget(_section_label("POWER"))
        for text, icon, slot in (
            ("Reboot to Recovery", "Reboot", lambda: self._adb_simple(["reboot", "recovery"])),
            ("Reboot to Fastboot", "Power", lambda: self._adb_simple(["reboot", "bootloader"])),
        ):
            b = _button(text, icon)
            b.clicked.connect(slot)
            side.addWidget(b)

        side.addWidget(_section_label("CONNECTION"))
        for text, icon, slot in (
            ("Re-authorize ADB", "Re-authorize ADB", self._reauthorize),
            ("Fix / DL ADB Drivers", "Fix Drivers", self._driver_help),
        ):
            b = _button(text, icon)
            b.clicked.connect(slot)
            side.addWidget(b)

        side.addWidget(_section_label("SESSION"))
        accounts = _button("Accounts", "Accounts")
        accounts.clicked.connect(lambda: self.nav.setCurrentRow(4))
        side.addWidget(accounts)
        logout = _button("Logout", "Logout")
        logout.clicked.connect(self._logout)
        side.addWidget(logout)

        guide = QFrame()
        guide.setObjectName("sidebarGuide")
        guide_layout = QVBoxLayout(guide)
        guide_layout.setContentsMargins(8, 8, 8, 8)
        usb_title = QLabel("USB DEBUGGING")
        usb_title.setObjectName("guideTitle")
        usb = QLabel("Enable Developer Options → USB debugging, connect the phone, then tap Allow.\nGeloTech prepares app icons automatically.")
        usb.setWordWrap(True)
        usb.setObjectName("guideText")
        how_title = QLabel("HOW TO USE")
        how_title.setObjectName("guideTitle")
        how = QLabel("Refresh loads apps. Load Apps chooses All / User / System / Disabled.\nAdvanced Filter uses the database. Scan Bloatware filters by UAD level.\nRight-click a row for app actions.")
        how.setWordWrap(True)
        how.setObjectName("guideText")
        guide_layout.addWidget(usb_title)
        guide_layout.addWidget(usb)
        guide_layout.addSpacing(4)
        guide_layout.addWidget(how_title)
        guide_layout.addWidget(how)
        side.addWidget(guide)

        self.stack = QStackedWidget()
        self.pages = [
            _build_dashboard(self),
            self._monitor_page(),
            self._dns_page(),
            self._vt_page(),
            self._accounts_page(),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        self.stack.insertWidget(5, self._task_page())

        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.nav.setCurrentRow(0)
        self.search.textChanged.connect(lambda value: _search_table(self, value))

    def nav_changed(self, row: int) -> None:
        mapping = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}
        index = mapping.get(row, 0)
        self.stack.setCurrentIndex(index)
        if row == 0:
            self.refresh_apps()
        elif row == 1:
            self._refresh_monitor()
        elif row == 4:
            self.refresh_accounts()

    MainWindow._build_shell = build_shell
    MainWindow._nav_changed = nav_changed
