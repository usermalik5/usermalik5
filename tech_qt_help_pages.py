"""Qt help/guide windows for Monitor Apps, DNS, and VirusTotal."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)


def _card(title: str, body: str) -> QFrame:
    card = QFrame()
    card.setObjectName("helpCard")
    layout = QVBoxLayout(card)
    heading = QLabel(title)
    heading.setObjectName("helpHeading")
    text = QLabel(body)
    text.setObjectName("helpText")
    text.setWordWrap(True)
    layout.addWidget(heading)
    layout.addWidget(text)
    return card


def _guide(parent, title: str, subtitle: str, cards: list[tuple[str, str]]) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(680, 560)
    outer = QVBoxLayout(dlg)
    header = QFrame()
    header.setObjectName("helpHeader")
    hv = QVBoxLayout(header)
    h = QLabel(title.upper())
    h.setObjectName("pageTitle")
    s = QLabel(subtitle)
    s.setWordWrap(True)
    s.setObjectName("helpText")
    hv.addWidget(h)
    hv.addWidget(s)
    outer.addWidget(header)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    body = QWidget()
    bv = QVBoxLayout(body)
    bv.setSpacing(10)
    for title_text, body_text in cards:
        bv.addWidget(_card(title_text, body_text))
    bv.addStretch(1)
    scroll.setWidget(body)
    outer.addWidget(scroll, 1)

    buttons = QDialogButtonBox(QDialogButtonBox.Close)
    buttons.rejected.connect(dlg.reject)
    buttons.accepted.connect(dlg.accept)
    outer.addWidget(buttons)
    dlg.exec()


def _monitor_help(parent) -> None:
    _guide(
        parent,
        "Monitor Running Apps",
        "Use this page to see which Android app is currently in the foreground and to refresh the device state.",
        [
            ("What this page is for", "Monitor Apps is useful when you are trying to find an app that suddenly appears on screen, shows a popup, or becomes active unexpectedly. GeloTech checks the connected phone and reports the active package instead of displaying raw Android diagnostic output."),
            ("Foreground / active", "Foreground / active means Android reports that package as the current visible or focused activity. Other entries may represent another active window reported by Android. The result is a quick indication of what is currently using the screen."),
            ("How to use it", "Connect the phone with USB debugging enabled, open Monitor Apps, then press Refresh. Use the phone normally and refresh again when the app you are investigating appears. The package name can then be compared with the App Cleaner list."),
            ("What the package name means", "The package name is Android's unique identifier, such as com.instagram.android. You can use the same identifier in App Cleaner to inspect its UAD level and available actions."),
            ("Important limitation", "Monitor Apps is an indicator, not proof that an application is malicious. Use the package information, App Cleaner database details, and VirusTotal results together when investigating suspicious behavior."),
        ],
    )


def _dns_help(parent) -> None:
    _guide(
        parent,
        "Private DNS Guide",
        "Choose a DNS provider to reduce advertising, tracking, phishing, or unwanted content at the DNS level.",
        [
            ("What Private DNS does", "Private DNS changes the DNS service used by the Android phone. DNS is the part of the connection that turns a website name into the address your phone connects to. A filtering provider can refuse requests for known advertising, tracking, malware, or unwanted-content domains."),
            ("AdGuard DNS", "A general-purpose filtering choice for ads and trackers. It is a good starting point when the main goal is reducing advertising and tracking without using a custom account."),
            ("Cloudflare / Google", "These are general DNS choices focused more on reliable name resolution than aggressive content filtering. Use them when you want a neutral DNS service rather than an ad-blocking filter."),
            ("Quad9", "A security-focused option intended to block known malicious domains. It is useful when your priority is malware and phishing protection."),
            ("CleanBrowsing", "CleanBrowsing provides profiles designed for family, adult-content, and security filtering. The choice of profile changes what categories of domains are blocked."),
            ("NextDNS / custom filtering", "NextDNS can provide more advanced filtering and custom rules. It is most useful when you want more control than a simple preset DNS provider."),
            ("Apply / Disable", "Apply DNS writes the selected Private DNS hostname to the connected phone. Disable turns Private DNS off. The phone must be connected through ADB for GeloTech to apply the setting."),
            ("If something stops working", "DNS filtering can occasionally block a domain required by an application. Disable Private DNS to test whether DNS filtering is the cause, then choose a less restrictive provider if necessary."),
        ],
    )


def _vt_help(parent) -> None:
    _guide(
        parent,
        "VirusTotal Guide",
        "Use VirusTotal to check APK hashes and uploaded APK files against multiple security engines.",
        [
            ("Scan Package", "Choose one installed package and check its APK hash against VirusTotal. This is the fastest option when you are investigating one application."),
            ("Scan Phone", "Checks installed packages on the connected device and looks up their APK hashes. Packages already known to VirusTotal can return existing analysis statistics without uploading the APK."),
            ("Scan Running", "Focuses the scan on packages that Android reports as currently active or running. This is useful when you are investigating an app that appears while you are using the phone."),
            ("Pull + Upload", "Pulls the selected APK from the phone, calculates its SHA-256 hash, checks whether VirusTotal already knows that file, and uploads it when no existing report is found. The analysis is then polled until it completes or fails."),
            ("Understanding results", "Malicious and suspicious detections are warning signals, not automatic proof of malware. A single detection can be a false positive. Look at the detection count, the package identity, the APK source, and what the application actually does."),
            ("SHA-256", "The SHA-256 value identifies the exact APK file being checked. Two versions of the same application can have different hashes, so an old VirusTotal result does not necessarily describe the APK currently installed on your phone."),
            ("Privacy reminder", "Uploading an APK sends that file to VirusTotal. Only use Pull + Upload when you are comfortable sharing the APK with the service and understand the service's handling of submitted files."),
        ],
    )


def install_help_pages(MainWindow) -> None:
    """Add useful guide controls without replacing migrated feature logic."""
    original_monitor = MainWindow._monitor_page
    original_dns = MainWindow._dns_page
    original_vt = MainWindow._vt_page

    def monitor_page(self):
        page = original_monitor(self)
        layout = page.layout()
        if layout is not None:
            row = QHBoxLayout()
            row.addStretch(1)
            info = QPushButton("How Monitor Apps works")
            info.clicked.connect(lambda: _monitor_help(self))
            row.addWidget(info)
            layout.insertLayout(0, row)
        return page

    def dns_page(self):
        page = original_dns(self)
        layout = page.layout()
        if layout is not None:
            row = QHBoxLayout()
            row.addStretch(1)
            info = QPushButton("Private DNS Guide")
            info.clicked.connect(lambda: _dns_help(self))
            row.addWidget(info)
            layout.insertLayout(1, row)
        return page

    def vt_page(self):
        page = original_vt(self)
        layout = page.layout()
        if layout is not None:
            row = QHBoxLayout()
            row.addStretch(1)
            info = QPushButton("VirusTotal Guide")
            info.clicked.connect(lambda: _vt_help(self))
            row.addWidget(info)
            layout.insertLayout(1, row)
        return page

    MainWindow._monitor_page = monitor_page
    MainWindow._dns_page = dns_page
    MainWindow._vt_page = vt_page
