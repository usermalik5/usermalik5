"""Rich Qt feature pages and help dialogs for Monitor Apps, DNS, and VirusTotal."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setMinimumHeight(34)
    return button


def _card(title: str, body: str) -> QFrame:
    card = QFrame()
    card.setObjectName("helpCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 10, 12, 10)
    heading = QLabel(title)
    heading.setObjectName("helpHeading")
    text = QLabel(body)
    text.setObjectName("helpText")
    text.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(text)
    return card


def _guide(parent, title: str, subtitle: str, cards: list[tuple[str, str]]) -> None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(700, 580)
    outer = QVBoxLayout(dialog)

    header = QFrame()
    header.setObjectName("helpHeader")
    hv = QVBoxLayout(header)
    title_label = QLabel(title.upper())
    title_label.setObjectName("pageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setWordWrap(True)
    subtitle_label.setObjectName("helpText")
    hv.addWidget(title_label)
    hv.addWidget(subtitle_label)
    outer.addWidget(header)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    bv = QVBoxLayout(body)
    for card_title, card_body in cards:
        bv.addWidget(_card(card_title, card_body))
    bv.addStretch(1)
    scroll.setWidget(body)
    outer.addWidget(scroll, 1)

    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    outer.addWidget(buttons)
    dialog.exec()


def _monitor_help(parent) -> None:
    _guide(
        parent,
        "Monitor Running Apps",
        "Use App Watch to find the application that is currently appearing on the phone and to investigate unexpected popups or foreground changes.",
        [
            ("What it does", "Monitor Apps watches the connected Android device and reports the package currently in the foreground. This gives you a quick way to identify which application owns what you are seeing on the phone."),
            ("How to use App Watch", "Turn monitoring on, then use the phone normally. Refresh or let the monitor update when a suspicious popup or screen appears. The latest detected package is shown in the status area."),
            ("Read the package name", "Android package names are unique identifiers such as com.instagram.android. Use that package name in App Cleaner to inspect its UAD level, description, and available actions."),
            ("What the result means", "A foreground result only tells you which application Android reports as active. It is not a malware verdict. Combine it with the App Cleaner database and VirusTotal when investigating a suspicious application."),
        ],
    )


def _dns_help(parent) -> None:
    _guide(
        parent,
        "Private DNS Guide",
        "Private DNS changes the service used to translate website names into network addresses and can also block domains before an app reaches them.",
        [
            ("AdGuard DNS", "A practical choice for blocking many ads and trackers without setting up a separate account."),
            ("Cloudflare / Google", "General-purpose DNS services focused on fast and reliable name resolution rather than strong content filtering."),
            ("Quad9", "A security-focused DNS service intended to block known malicious and phishing domains."),
            ("CleanBrowsing", "Provides family, adult-content, and security filtering profiles. Choose it when category-based filtering is important."),
            ("Control D / SecureDNS / NextDNS", "These services provide more control or specialized privacy/filtering options. Some support custom rules or profile-based filtering."),
            ("Apply DNS", "Writes the selected Private DNS hostname to the connected Android device. The phone must be reachable through ADB."),
            ("Disable DNS", "Turns Private DNS back off. Use this when an application stops connecting and you want to test whether DNS filtering caused the problem."),
        ],
    )


def _vt_help(parent) -> None:
    _guide(
        parent,
        "VirusTotal Guide",
        "VirusTotal compares APK hashes and submitted APK files with many security engines. Use it as an investigation aid, not as the only malware decision.",
        [
            ("Scan Package", "Checks one installed package. This is the fastest choice when you already know which application you want to investigate."),
            ("Scan Phone", "Checks installed packages on the connected device and looks up their APK hashes against VirusTotal."),
            ("Scan Running", "Focuses the VirusTotal check on packages currently reported as active/running by Android."),
            ("Pull + Upload", "Pulls an APK from the phone, calculates its SHA-256 value, checks whether VirusTotal already knows the file, and uploads it if necessary."),
            ("Understanding detections", "Malicious and suspicious counts are warning signals. A detection is not automatically proof of malware; consider the number of engines, package identity, APK source, and application behavior."),
            ("SHA-256", "The SHA-256 value identifies the exact APK file. Different versions of the same application can produce different hashes."),
            ("Privacy", "Pull + Upload sends the APK to VirusTotal. Only upload files you are comfortable sharing with the service."),
        ],
    )


def _header(title: str, subtitle: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("featureHeader")
    layout = QHBoxLayout(frame)
    title_box = QVBoxLayout()
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("helpText")
    subtitle_label.setWordWrap(True)
    title_box.addWidget(title_label)
    title_box.addWidget(subtitle_label)
    layout.addLayout(title_box, 1)
    return frame


def _build_monitor(self) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    header = _header("MONITOR RUNNING APPS (APP WATCH)", "Find which app is currently active on the phone. Turn monitoring on, use the phone normally, then inspect the detected activity.")
    actions = QHBoxLayout()
    self.monitor_toggle = _button("Start monitoring")
    self.monitor_toggle.setCheckable(True)
    self.monitor_toggle.toggled.connect(lambda checked: _toggle_monitor(self, checked))
    help_button = _button("How it works")
    help_button.clicked.connect(lambda: _monitor_help(self))
    refresh = _button("Refresh now")
    refresh.clicked.connect(self._refresh_monitor)
    actions.addWidget(self.monitor_toggle)
    actions.addWidget(refresh)
    actions.addWidget(help_button)
    actions.addStretch(1)
    layout.addWidget(header)
    layout.addLayout(actions)

    instructions = QFrame()
    instructions.setObjectName("contentPanel")
    iv = QVBoxLayout(instructions)
    title = QLabel("How to catch the culprit app")
    title.setObjectName("helpHeading")
    steps = QLabel("1. Turn on Start monitoring.\n2. Exit the app you are currently using and use the phone normally.\n3. When an unexpected popup or screen appears, leave it visible and check the activity list.\n4. The latest foreground package is the best candidate.\n5. Open App Cleaner with that package name for more information and actions.")
    steps.setWordWrap(True)
    steps.setObjectName("helpText")
    iv.addWidget(title)
    iv.addWidget(steps)
    layout.addWidget(instructions)

    status = QFrame()
    status.setObjectName("statusPanel")
    sv = QHBoxLayout(status)
    self.monitor_status = QLabel("Monitoring: OFF    Foreground: —")
    self.monitor_status.setObjectName("statusText")
    self.monitor_count = QLabel("Events: 0")
    self.monitor_count.setObjectName("statusText")
    sv.addWidget(self.monitor_status, 1)
    sv.addWidget(self.monitor_count)
    layout.addWidget(status)

    self.monitor_table = QTableWidget(0, 3)
    self.monitor_table.setHorizontalHeaderLabels(["PACKAGE", "STATE", "WHAT TO DO"])
    self.monitor_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.monitor_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.monitor_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    self.monitor_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
    self.monitor_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
    layout.addWidget(self.monitor_table, 1)

    footer = QHBoxLayout()
    clear = _button("Clear history")
    clear.clicked.connect(lambda: _clear_monitor(self))
    footer.addWidget(clear)
    footer.addStretch(1)
    layout.addLayout(footer)
    self._monitor_timer = QTimer(self)
    self._monitor_timer.timeout.connect(lambda: _monitor_tick(self))
    self._monitor_event_count = 0
    return page


def _toggle_monitor(self, checked: bool) -> None:
    if checked:
        self.monitor_toggle.setText("Stop monitoring")
        self.monitor_status.setText("Monitoring: ON    Foreground: checking…")
        self._monitor_timer.start(1200)
        _monitor_tick(self)
    else:
        self.monitor_toggle.setText("Start monitoring")
        self.monitor_status.setText("Monitoring: OFF    Foreground: —")
        self._monitor_timer.stop()


def _monitor_tick(self) -> None:
    self._refresh_monitor()
    if getattr(self, "serial", None):
        self._monitor_event_count += 1
        self.monitor_count.setText(f"Checks: {self._monitor_event_count}")
        rows = []
        for row in range(self.monitor_table.rowCount()):
            package = self.monitor_table.item(row, 0).text() if self.monitor_table.item(row, 0) else ""
            state = self.monitor_table.item(row, 1).text() if self.monitor_table.item(row, 1) else ""
            rows.append((package, state))
        for row in range(self.monitor_table.rowCount()):
            self.monitor_table.setItem(row, 2, QTableWidgetItem("Compare with App Cleaner / VirusTotal" if row == 0 else "Observe activity"))


def _clear_monitor(self) -> None:
    self._monitor_event_count = 0
    self.monitor_count.setText("Checks: 0")
    self.monitor_table.setRowCount(0)


def _build_dns(self) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    header = _header("BLOCK MOST APPS POPUP ADS", "Choose a Private DNS service. Filtering happens at the DNS level, before many ad or tracking domains can be reached.")
    header_layout = header.layout()
    if header_layout is not None:
        status = QLabel("Private DNS: checking")
        status.setObjectName("securityText")
        header_layout.addWidget(status)
        self.dns_status = status
    layout.addWidget(header)

    panel = QFrame()
    panel.setObjectName("contentPanel")
    pv = QVBoxLayout(panel)
    intro = QLabel("Select a provider below. Use Apply DNS to set it on the connected phone, or Disable to return to normal Android DNS behavior.")
    intro.setWordWrap(True)
    intro.setObjectName("helpText")
    pv.addWidget(intro)

    row = QHBoxLayout()
    self.dns = QComboBox()
    providers = [
        ("AdGuard DNS — blocks ads & trackers", "dns.adguard-dns.com"),
        ("Cloudflare 1.1.1.1 — fast & private", "one.one.one.one"),
        ("Google DNS — reliable", "dns.google"),
        ("Quad9 — blocks malware & phishing", "dns.quad9.net"),
        ("CleanBrowsing Family — safe for kids", "family-filter-dns.cleanbrowsing.org"),
        ("CleanBrowsing Adult — blocks adult content", "adult-filter-dns.cleanbrowsing.org"),
        ("CleanBrowsing Security — blocks malware", "security-filter-dns.cleanbrowsing.org"),
        ("Control D — custom rules", "p0.freedns.controld.com"),
        ("NextDNS — advanced filtering", "dns.nextdns.io"),
    ]
    for label, value in providers:
        self.dns.addItem(label, value)
    self.dns_apply = _button("Apply DNS")
    self.dns_disable = _button("Disable")
    self.dns_help_button = _button("DNS Guide")
    self.dns_apply.clicked.connect(self.apply_dns)
    self.dns_disable.clicked.connect(self.disable_dns)
    self.dns_help_button.clicked.connect(lambda: _dns_help(self))
    row.addWidget(self.dns, 1)
    row.addWidget(self.dns_apply)
    row.addWidget(self.dns_disable)
    row.addWidget(self.dns_help_button)
    pv.addLayout(row)

    explanation = QHBoxLayout()
    for title, text in (
        ("Ad & tracker blocking", "AdGuard is a simple starting point."),
        ("Security", "Quad9 and CleanBrowsing Security focus on malicious domains."),
        ("Family / content", "CleanBrowsing profiles filter categories of content."),
    ):
        explanation.addWidget(_card(title, text), 1)
    pv.addLayout(explanation)
    pv.addStretch(1)
    layout.addWidget(panel, 1)
    return page


def _build_vt(self) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    header = _header("VIRUSTOTAL SCANNER", "Scan installed APKs, inspect the currently active application, or pull an APK and upload it when no existing VirusTotal report is available.")
    layout.addWidget(header)

    actions = QFrame()
    actions.setObjectName("contentPanel")
    av = QHBoxLayout(actions)
    self.vt_package = QComboBox()
    self.vt_package.setEditable(True)
    self.vt_package.setPlaceholderText("Select or enter package name")
    self.vt_refresh = _button("Load Packages")
    self.vt_scan_package = _button("Scan Package")
    self.vt_scan_phone = _button("Scan Phone")
    self.vt_scan_running = _button("Scan Running")
    self.vt_stop = _button("Stop")
    self.vt_upload = _button("Pull + Upload")
    self.vt_help_button = _button("VirusTotal Guide")
    for widget in (self.vt_package, self.vt_refresh, self.vt_scan_package, self.vt_scan_phone, self.vt_scan_running, self.vt_stop, self.vt_upload, self.vt_help_button):
        av.addWidget(widget)
    layout.addWidget(actions)

    summary = QFrame()
    summary.setObjectName("statusPanel")
    sv = QHBoxLayout(summary)
    self.vt_status = QLabel("Ready.")
    self.vt_progress = QLabel("")
    self.vt_security_hint = QLabel("0 scans • no current findings")
    self.vt_status.setObjectName("statusText")
    sv.addWidget(self.vt_status, 1)
    sv.addWidget(self.vt_progress)
    sv.addWidget(self.vt_security_hint)
    layout.addWidget(summary)

    self.vt_results = QPlainTextEdit()
    self.vt_results.setReadOnly(True)
    self.vt_results.setPlaceholderText("VirusTotal results will appear here.")
    self.vt_results.setObjectName("resultConsole")
    layout.addWidget(self.vt_results, 1)

    help_panel = QFrame()
    help_panel.setObjectName("contentPanel")
    hv = QHBoxLayout(help_panel)
    hv.addWidget(_card("What is checked", "GeloTech calculates an APK SHA-256 hash and checks the corresponding VirusTotal file report."), 1)
    hv.addWidget(_card("When uploading is used", "Pull + Upload is used when the selected APK does not already have a VirusTotal report."), 1)
    hv.addWidget(_card("How to read results", "Malicious and suspicious detections are warning signals. Review the package identity and the number of engines reporting it."), 1)
    layout.addWidget(help_panel)

    self.vt_refresh.clicked.connect(self._qt_vt_load_packages)
    self.vt_scan_package.clicked.connect(self._qt_vt_scan_package)
    self.vt_scan_phone.clicked.connect(self._qt_vt_scan_phone)
    self.vt_scan_running.clicked.connect(self._qt_vt_scan_running)
    self.vt_stop.clicked.connect(self._qt_vt_stop)
    self.vt_upload.clicked.connect(self._qt_vt_pull_upload)
    self.vt_help_button.clicked.connect(lambda: _vt_help(self))
    return page


def install_help_pages(MainWindow) -> None:
    """Restore rich legacy-style feature workspaces plus separate help dialogs."""
    MainWindow._monitor_page = _build_monitor
    MainWindow._dns_page = _build_dns
    MainWindow._vt_page = _build_vt
