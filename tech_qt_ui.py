"""Qt6 visual-parity shell for the original GeloTech Tk layout."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from tech_qt_icons import ICONS, load_icon


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


def _phone_pixmap() -> QPixmap:
    pixmap = QPixmap(str(_bundle_path("assets", "phone_devices", "iPhone17_P_PM_CosmicOrange@2x.png")))
    if pixmap.isNull():
        return pixmap
    pixmap.setDevicePixelRatio(1.0)
    return pixmap.scaled(353, 735, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _build_dashboard(self) -> QWidget:
    page = QWidget()
    outer = QHBoxLayout(page)
    outer.setContentsMargins(10, 10, 10, 8)
    outer.setSpacing(10)

    phone_panel = QFrame()
    phone_panel.setObjectName("phonePanel")
    phone_panel.setFixedWidth(405)
    phone_layout = QVBoxLayout(phone_panel)
    phone_layout.setContentsMargins(10, 4, 10, 0)
    phone_layout.setSpacing(8)

    phone = QLabel()
    phone.setObjectName("phoneMockup")
    phone.setAlignment(Qt.AlignCenter)
    phone.setPixmap(_phone_pixmap())
    phone_layout.addWidget(phone, 1, Qt.AlignCenter)

    phone_buttons = QHBoxLayout()
    phone_buttons.setSpacing(8)
    refresh_phone = _button("Refresh", "refresh")
    refresh_phone.clicked.connect(self.refresh_apps)
    mirror_phone = _button("Screen Mirror", "device-mobile")
    mirror_phone.clicked.connect(self.start_mirror)
    phone_buttons.addWidget(refresh_phone)
    phone_buttons.addWidget(mirror_phone)
    phone_layout.addLayout(phone_buttons)

    content = QFrame()
    content.setObjectName("contentPanel")
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(7)

    self.log = QPlainTextEdit(readOnly=True)
    self.log.setObjectName("liveLog")
    self.log.setPlaceholderText("Live logs")
    self.log.setMinimumHeight(118)
    self.log.setMaximumHeight(128)
    content_layout.addWidget(self.log)

    guide = QFrame()
    guide.setObjectName("guidePanel")
    guide_layout = QVBoxLayout(guide)
    guide_layout.setContentsMargins(9, 6, 9, 6)
    guide_layout.setSpacing(2)
    usb = QLabel("USB debugging: Enable Developer Options → USB debugging, connect the phone, then tap Allow. GeloTech automatically prepares app icons for new devices.")
    how = QLabel("How to use: Refresh loads user apps. Load Apps chooses All / User / System / Disabled. Advanced Filter uses the database. Scan Bloatware filters by UAD level. Right-click a row for app actions.")
    for label in (usb, how):
        label.setObjectName("guideText")
        label.setWordWrap(True)
        guide_layout.addWidget(label)
    content_layout.addWidget(guide)

    status_row = QHBoxLayout()
    self.cleaner_status = QLabel("Connect a device and press Refresh to load apps.")
    self.cleaner_status.setObjectName("statusText")
    self.security_label = QLabel("Security indicators: 0")
    self.security_label.setObjectName("securityText")
    self.device_inline = QLabel("NO DEVICE")
    self.device_inline.setObjectName("deviceText")
    self.device_label = self.device_inline
    self.phone_status = self.device_inline
    status_row.addWidget(self.cleaner_status, 1)
    status_row.addWidget(self.security_label)
    status_row.addWidget(self.device_inline)
    content_layout.addLayout(status_row)

    controls = QHBoxLayout()
    controls.setSpacing(8)
    self.search = QLineEdit()
    self.search.setPlaceholderText("🔍 Search packages...")
    self.search.setMinimumHeight(34)
    self.search.setClearButtonEnabled(True)
    controls.addWidget(self.search, 1)
    select_all = _button("Select All")
    select_all.clicked.connect(lambda: _toggle_select_all(self))
    controls.addWidget(select_all)
    legend = QLabel("● Removable   ● Clean Excluded   ● Uninstall Excluded   ● Both Excluded")
    legend.setObjectName("legendText")
    controls.addWidget(legend, 2)
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
    for index in range(4):
        header.setSectionResizeMode(index, QHeaderView.Interactive)
    table.setColumnWidth(0, 220)
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

    outer.addWidget(phone_panel)
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
        values = [window.table.item(row, col).text().lower() if window.table.item(row, col) else "" for col in range(4)]
        visible = not needle or needle in " ".join(values)
        window.table.setRowHidden(row, not visible)
        shown += int(visible)
    if hasattr(window, "cleaner_status"):
        window.cleaner_status.setText(f"{shown} matching apps shown." if needle else f"{window.table.rowCount()} apps loaded.")


def install_visual_parity(MainWindow: type[QMainWindow]) -> None:
    """Install a full legacy-style Qt shell without replacing feature logic."""
    def build_shell(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(264)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(10, 7, 10, 8)
        side.setSpacing(4)

        copyright_label = QLabel("© 2026 GeloTech")
        copyright_label.setObjectName("copyrightLabel")
        copyright_label.setAlignment(Qt.AlignCenter)
        side.addWidget(copyright_label)
        brand = QLabel("GELOTECH")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignCenter)
        side.addWidget(brand)
        version = QLabel(f"TECH TOOL\nv{self.windowTitle().split('v', 1)[-1]} - Angelo Estrada Espinosa")
        version.setObjectName("versionLabel")
        version.setAlignment(Qt.AlignCenter)
        side.addWidget(version)
        for text, url in (("Gsmcodeph.com", "https://gsmcodeph.com"), ("facebook.com/gelotechxyz", "https://www.facebook.com/gelotechxyz")):
            link = QLabel(f'<a href="{url}">{text}</a>')
            link.setObjectName("brandLink")
            link.setAlignment(Qt.AlignCenter)
            link.setOpenExternalLinks(True)
            side.addWidget(link)

        self.theme_btn = _button(self.theme_name.capitalize(), "settings")
        self.theme_btn.clicked.connect(self._theme_dialog)
        side.addSpacing(2)
        side.addWidget(self.theme_btn)
        side.addSpacing(2)
        side.addWidget(_section_label("PAGES"))

        self.nav = QListWidget()
        self.nav.setObjectName("sidebarNav")
        self.nav.setSelectionMode(QAbstractItemView.SingleSelection)
        self.nav.setSpacing(1)
        for title, key in (("Dashboard", "Dashboard"), ("Monitor Apps", "Monitor Apps"), ("Block Ads DNS", "Block Ads DNS"), ("VirusTotal", "VirusTotal")):
            self.nav.addItem(QListWidgetItem(load_icon(ICONS.get(key, "info-circle")), title))
        self.nav.currentRowChanged.connect(self._nav_changed)
        side.addWidget(self.nav, 1)

        mirror = _button("Screen Mirror", "device-mobile")
        mirror.clicked.connect(self.start_mirror)
        side.addWidget(mirror)

        side.addWidget(_section_label("POWER"))
        for text, icon, slot in (("Reboot to Recovery", "Reboot", lambda: self._adb_simple(["reboot", "recovery"])), ("Reboot to Fastboot", "Power", lambda: self._adb_simple(["reboot", "bootloader"]))):
            button = _button(text, icon)
            button.clicked.connect(slot)
            side.addWidget(button)

        side.addWidget(_section_label("CONNECTION"))
        for text, icon, slot in (("Re-authorize ADB", "Re-authorize ADB", self._reauthorize), ("Fix / DL ADB Drivers", "Fix Drivers", self._driver_help)):
            button = _button(text, icon)
            button.clicked.connect(slot)
            side.addWidget(button)

        side.addWidget(_section_label("SESSION"))
        accounts = _button("Accounts", "Accounts")
        accounts.clicked.connect(lambda: (self.stack.setCurrentIndex(4), self.refresh_accounts()))
        side.addWidget(accounts)
        logout = _button("Logout", "Logout")
        logout.clicked.connect(self._logout)
        side.addWidget(logout)

        guide = QFrame()
        guide.setObjectName("sidebarGuide")
        guide_layout = QVBoxLayout(guide)
        guide_layout.setContentsMargins(8, 7, 8, 7)
        guide_layout.setSpacing(2)
        usb_title = QLabel("USB DEBUGGING")
        usb_title.setObjectName("guideTitle")
        usb_text = QLabel("Enable Developer Options → USB debugging, connect the phone, then tap Allow.\nGeloTech prepares app icons automatically.")
        usb_text.setObjectName("guideText")
        usb_text.setWordWrap(True)
        how_title = QLabel("HOW TO USE")
        how_title.setObjectName("guideTitle")
        how_text = QLabel("Refresh loads apps. Load Apps chooses All / User / System / Disabled.\nAdvanced Filter uses the database. Scan Bloatware filters by UAD level.\nRight-click a row for app actions.")
        how_text.setObjectName("guideText")
        how_text.setWordWrap(True)
        guide_layout.addWidget(usb_title)
        guide_layout.addWidget(usb_text)
        guide_layout.addSpacing(3)
        guide_layout.addWidget(how_title)
        guide_layout.addWidget(how_text)
        side.addWidget(guide)

        self.stack = QStackedWidget()
        self.pages = [_build_dashboard(self), self._monitor_page(), self._dns_page(), self._vt_page(), self._accounts_page()]
        for page in self.pages:
            self.stack.addWidget(page)
        root_layout.addWidget(self.sidebar)
        root_layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.nav.setCurrentRow(0)
        self.search.textChanged.connect(lambda value: _search_table(self, value))

    def nav_changed(self, row: int) -> None:
        if row < 0 or row >= 4:
            return
        self.stack.setCurrentIndex(row)
        if row == 0:
            self.refresh_apps()
        elif row == 1:
            self._refresh_monitor()

    original_open_login = MainWindow._open_login

    def open_login(self) -> None:
        was_visible = self.isVisible()
        self.hide()
        original_open_login(self)
        if self.current_user or was_visible:
            self.show()

    MainWindow._build_shell = build_shell
    MainWindow._nav_changed = nav_changed
    MainWindow._open_login = open_login
