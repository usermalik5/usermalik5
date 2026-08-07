# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox, ttk
import threading
import os
import json
import time
import re
import tempfile
import hashlib
import sys
import requests
import datetime
import shutil
from PIL import Image, ImageDraw, ImageFont
from tech_common import get_bundle_dir, get_app_dir, Tooltip, subprocess


class UiMixin:
    def build_virustotal_tab(self):
        tab = self.tabview.tab("VirusTotal")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        header.grid(row=0, column=0, padx=15, pady=(12, 8), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="\U0001f9a0", font=ctk.CTkFont(size=24), text_color="#2980b9").grid(row=0, column=0, padx=(14, 5), pady=10)
        info = ctk.CTkFrame(header, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w", pady=8)
        ctk.CTkLabel(info, text="VIRUSTOTAL SCANNER", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2980b9").pack(anchor="w")
        ctk.CTkLabel(info, text="Scan phone packages or upload APKs via VirusTotal API", font=ctk.CTkFont(size=11), text_color="#a6a6a6").pack(anchor="w")
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.grid(row=0, column=2, padx=(8, 12), pady=10)
        self.vt_scan_btn = ctk.CTkButton(btn_frame, text="Scan Phone", width=110, height=36, fg_color="#2980b9", hover_color="#1f618d", font=ctk.CTkFont(weight="bold"), command=self.action_vt_scan_installed)
        self.vt_scan_btn.pack(side="left", padx=2)
        self.vt_scan_running_btn = ctk.CTkButton(btn_frame, text="Scan Running", width=110, height=36, fg_color="#8e44ad", hover_color="#71368a", font=ctk.CTkFont(weight="bold"), command=self.action_vt_scan_running)
        self.vt_scan_running_btn.pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="Pull & Upload", width=110, height=36, fg_color="#16a085", hover_color="#117a65", font=ctk.CTkFont(weight="bold"), command=self.action_vt_upload_apk).pack(side="left", padx=2)

        self.vt_progress_frame = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        self.vt_progress_frame.grid(row=1, column=0, padx=15, pady=(0, 8), sticky="ew")
        self.vt_progress_frame.grid_columnconfigure(1, weight=1)
        self.vt_progress_frame.grid_columnconfigure(2, weight=1)
        self.vt_progress_label = ctk.CTkLabel(self.vt_progress_frame, text="Scan progress", font=ctk.CTkFont(size=11, weight="bold"), text_color="#aab7c4")
        self.vt_progress_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.vt_progress_bar = ctk.CTkProgressBar(self.vt_progress_frame, height=18, corner_radius=6, fg_color="#2a3340", progress_color="#2980b9")
        self.vt_progress_bar.grid(row=0, column=1, padx=8, pady=8, sticky="ew")
        self.vt_progress_bar.set(0)
        self.vt_scanning_label = ctk.CTkLabel(self.vt_progress_frame, text="Ready", font=ctk.CTkFont(size=11), text_color="#8da1b8")
        self.vt_scanning_label.grid(row=0, column=2, padx=10, pady=8, sticky="w")
        self.vt_stop_btn = ctk.CTkButton(self.vt_progress_frame, text="Stop", width=60, height=28, fg_color="#7f8c8d", hover_color="#95a5a6", font=ctk.CTkFont(size=11, weight="bold"), command=self.action_vt_stop)
        self.vt_stop_btn.grid(row=0, column=3, padx=(0, 10), pady=8)
        self.vt_progress_frame.grid_remove()

        stats = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        stats.grid(row=2, column=0, padx=15, pady=(0, 8), sticky="ew")
        self.vt_status_label = ctk.CTkLabel(stats, text="Ready", font=ctk.CTkFont(size=11), text_color="#2ecc71")
        self.vt_status_label.pack(side="left", padx=15, pady=8)
        self.vt_scanned_label = ctk.CTkLabel(stats, text="Scanned: 0", font=ctk.CTkFont(size=11), text_color="#a6a6a6")
        self.vt_scanned_label.pack(side="left", padx=15, pady=8)
        self.vt_malicious_label = ctk.CTkLabel(stats, text="Malicious: 0", font=ctk.CTkFont(size=11, weight="bold"), text_color="#e74c3c")
        self.vt_malicious_label.pack(side="left", padx=15, pady=8)

        th = ctk.CTkFrame(tab, fg_color="#27313d", corner_radius=6)
        th.grid(row=3, column=0, padx=15, pady=(5, 0), sticky="ew")
        th.grid_columnconfigure(0, minsize=42, weight=0)
        th.grid_columnconfigure(1, minsize=250, weight=5)
        th.grid_columnconfigure(2, minsize=100, weight=0)
        th.grid_columnconfigure(3, minsize=100, weight=0)
        th.grid_columnconfigure(4, minsize=300, weight=3)
        headers = [("", "center"), ("PACKAGE / FILE", "w"), ("DETECTION", "center"), ("SCORE", "center"), ("DETAILS", "w")]
        for col, (text, anchor) in enumerate(headers):
            ctk.CTkLabel(th, text=text, anchor=anchor, font=ctk.CTkFont(size=11, weight="bold"), text_color="#d9e5ee").grid(row=0, column=col, padx=6, pady=7, sticky="ew")

        self.vt_rows_frame = ctk.CTkScrollableFrame(tab, fg_color="#131921", corner_radius=6)
        self.vt_rows_frame.grid(row=4, column=0, padx=15, pady=(0, 7), sticky="nsew")
        self.vt_rows_frame.grid_columnconfigure(0, weight=1)

        batch = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        batch.grid(row=5, column=0, padx=15, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(batch, text="\u25a3 SELECTED", font=ctk.CTkFont(size=11, weight="bold"), text_color="#cbd9e6").pack(side="left", padx=(12, 8), pady=9)
        ctk.CTkButton(batch, text="\u23f8 Disable", width=92, height=30, fg_color="#d35400", command=lambda: self.action_vt_selected("disable")).pack(side="left", padx=3, pady=8)
        ctk.CTkButton(batch, text="\u21bb Enable", width=92, height=30, fg_color="#138d75", command=lambda: self.action_vt_selected("enable")).pack(side="left", padx=3, pady=8)
        ctk.CTkButton(batch, text="\u2715 Uninstall", width=102, height=30, fg_color="#c0392b", command=lambda: self.action_vt_selected("uninstall")).pack(side="left", padx=3, pady=8)
        ctk.CTkButton(batch, text="Clear", width=74, height=30, fg_color="#395670", command=self.clear_vt_selection).pack(side="right", padx=12, pady=8)

    # ----------------------------------------------------
    # SECURITY SCAN TAB UI
    # ----------------------------------------------------
    def build_security_tab(self):
        tab = self.tabview.tab("Popup Ad Virus Cleaner")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        # Row 0 - Device header (APK Cleaner style)
        header = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8, border_width=0)
        header.grid(row=0, column=0, padx=15, pady=(12, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.grid(row=0, column=0, padx=(14, 10), pady=8, sticky="w")
        ctk.CTkLabel(title_block, text="APK CLEANER & UNINSTALLER", font=ctk.CTkFont(size=20, weight="bold"), text_color="#58a6ff").pack(anchor="w")
        ctk.CTkLabel(title_block, text="Popup Ad Virus Cleaner", font=ctk.CTkFont(size=9, weight="bold"), text_color="#8b949e").pack(anchor="w")
        self.sec_refresh_btn = ctk.CTkButton(header, text="\U0001f504 Refresh", width=110, height=34, fg_color="#21262d", hover_color="#30363d", border_width=1, border_color="#30363d", font=ctk.CTkFont(weight="bold", size=11), command=self.action_sec_refresh)
        self.sec_refresh_btn.grid(row=0, column=2, padx=(8, 14), pady=10)
        Tooltip(self.sec_refresh_btn, "Reload the app list from your phone and re-scan for threats (popup-ads / sideloaded apps).")

        dev = ctk.CTkFrame(header, fg_color="transparent")
        dev.grid(row=1, column=0, columnspan=3, padx=14, pady=(0, 10), sticky="w")
        self.sec_dev_model = ctk.CTkLabel(dev, text="Model: -", font=ctk.CTkFont(size=10), text_color="#8b949e")
        self.sec_dev_model.pack(side="left", padx=(0, 14))
        self.sec_dev_android = ctk.CTkLabel(dev, text="Android: -", font=ctk.CTkFont(size=10), text_color="#8b949e")
        self.sec_dev_android.pack(side="left", padx=(0, 14))
        self.sec_dev_patch = ctk.CTkLabel(dev, text="Security Patch: -", font=ctk.CTkFont(size=10), text_color="#8b949e")
        self.sec_dev_patch.pack(side="left", padx=(0, 14))
        self.sec_dev_build = ctk.CTkLabel(dev, text="Build ID: -", font=ctk.CTkFont(size=10), text_color="#8b949e")
        self.sec_dev_build.pack(side="left", padx=(0, 14))
        self.sec_dev_conn = ctk.CTkLabel(dev, text="\u26a0 No device", font=ctk.CTkFont(size=10, weight="bold"), text_color="#e74c3c")
        self.sec_dev_conn.pack(side="left", padx=(6, 0))

        # Row 1 - Status bar: status | scan anim | threats counter | progress
        stats = ctk.CTkFrame(tab, fg_color="#131921", corner_radius=8)
        stats.grid(row=1, column=0, padx=15, pady=(0, 6), sticky="ew")
        self.sec_status_label = ctk.CTkLabel(stats, text="Initializing...", font=ctk.CTkFont(size=10, slant="italic"), text_color="#8b949e")
        self.sec_status_label.pack(side="left", padx=12, pady=6)
        self.sec_scan_anim = ctk.CTkLabel(stats, text="", font=ctk.CTkFont(size=11), text_color="#58a6ff")
        self.sec_scan_anim.pack(side="left", padx=(4, 10), pady=6)
        self.sec_threats_label = ctk.CTkLabel(stats, text="\U0001f9a0 Possible Threats: 0", font=ctk.CTkFont(size=10, weight="bold"), text_color="#ff4d4d")
        self.sec_threats_label.pack(side="left", padx=8, pady=6)
        self.sec_virus_counter = ctk.CTkLabel(stats, text="\U0001f9a0 Adware Risk Score: 0", font=ctk.CTkFont(size=10, weight="bold"), text_color="#8b949e")
        self.sec_virus_counter.pack(side="left", padx=8, pady=6)
        self.sec_progress_bar = ctk.CTkProgressBar(stats, height=12, corner_radius=6, fg_color="#21262d", progress_color="#58a6ff", width=170)
        self.sec_progress_bar.pack(side="right", padx=12, pady=6)
        self.sec_progress_bar.set(0)

        # Row 2 - Toolbar: search + select all + legend
        toolbar = ctk.CTkFrame(tab, fg_color="#131921", corner_radius=8)
        toolbar.grid(row=2, column=0, padx=15, pady=(0, 6), sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)
        self.sec_search_entry = ctk.CTkEntry(toolbar, placeholder_text="\U0001f50d Search packages...", fg_color="#0d1117", border_color="#30363d", height=32, font=ctk.CTkFont(size=11))
        self.sec_search_entry.grid(row=0, column=0, columnspan=2, padx=(10, 8), pady=6, sticky="ew")
        self.sec_search_entry.bind("<KeyRelease>", self._sec_on_search)
        Tooltip(self.sec_search_entry, "Type to filter the list — matches the app name or package ID. Example: typing 'bank' shows only apps with 'bank' in the name.")
        self.sec_select_all_btn = ctk.CTkButton(toolbar, text="\u2610 Select All", width=120, height=30, fg_color="#21262d", hover_color="#30363d", border_width=1, border_color="#30363d", font=ctk.CTkFont(size=10, weight="bold"), command=self.action_sec_toggle_all)
        self.sec_select_all_btn.grid(row=0, column=3, padx=(8, 6), pady=6)
        Tooltip(self.sec_select_all_btn, "Check or uncheck every app at once. Remember: CHECKED apps are the ones Clean / Uninstall Virus / Fix Popup Ad act on.")

        legend_items = [
            ("lightgreen", "Removable", "removable"),
            ("orange", "Clean Excluded", "clean"),
            ("red", "Uninstall Excluded", "uninstall"),
            ("#8957e5", "Both Excluded", "both"),
        ]
        self.sec_legend_widgets = {}
        for i, (color, text, mode) in enumerate(legend_items):
            col = 4 + i * 2
            dot = ctk.CTkLabel(toolbar, text="\u25cf", text_color=color, font=ctk.CTkFont(size=10), cursor="hand2")
            dot.grid(row=0, column=col, padx=(4, 0), pady=6)
            lbl = ctk.CTkLabel(toolbar, text=text, font=ctk.CTkFont(size=9), text_color="#8b949e", cursor="hand2")
            lbl.grid(row=0, column=col + 1, padx=(2, 8), pady=6)
            for w in (dot, lbl):
                w.bind("<Button-1>", lambda e, m=mode: self._sec_toggle_legend_filter(m))
                Tooltip(w, f"Click to show only {text} apps. Click again to reset.")
            self.sec_legend_widgets[mode] = (dot, lbl)
        toolbar.grid_columnconfigure(4 + len(legend_items) * 2, weight=0)

        # Row 3 - Package list (icon rows)
        self.sec_list_frame = ctk.CTkScrollableFrame(tab, fg_color="#0d1117", corner_radius=8, border_width=1, border_color="#30363d")
        self.sec_list_frame.grid(row=3, column=0, padx=15, pady=(0, 6), sticky="nsew")
        self.sec_list_frame.grid_columnconfigure(0, weight=1)
        self.sec_list_empty = ctk.CTkLabel(self.sec_list_frame, text="\U0001f4e6 Connect a device and press Refresh to load apps", font=ctk.CTkFont(size=12), text_color="#484f58")
        self.sec_list_empty.pack(pady=30)

        # Row 4 - Big emoji action buttons (spread evenly across available width)
        actions = ctk.CTkFrame(tab, fg_color="#131921", corner_radius=8)
        actions.grid(row=4, column=0, padx=15, pady=(0, 6), sticky="ew")
        for i in range(8):
            actions.grid_columnconfigure(i, weight=1, uniform="act")
        btn_style = dict(height=40, width=0, font=ctk.CTkFont(size=11, weight="bold"), border_width=1, corner_radius=8)
        btn_clean = ctk.CTkButton(actions, text="\U0001f9f9 Clean", fg_color="#1f6feb", hover_color="#1a5fd0", border_color="#2f81f7", command=self.action_sec_clean_checked, **btn_style)
        btn_clean.grid(row=0, column=0, padx=4, pady=8, sticky="ew")
        Tooltip(btn_clean, "Clears storage/data of the CHECKED apps only (apps stay installed, only data/cache is wiped). Fixes full-storage and app-crashing bugs. Apps in the Clean Excluded list are skipped.")
        btn_uninstall = ctk.CTkButton(actions, text="\u274c Uninstall Virus", fg_color="#c0392b", hover_color="#a82521", border_color="#e05d4a", command=self.action_sec_uninstall_checked, **btn_style)
        btn_uninstall.grid(row=0, column=1, padx=4, pady=8, sticky="ew")
        Tooltip(btn_uninstall, "Uninstalls only the CHECKED 3rd-party apps that cause the popup-ad virus. Apps in the Uninstall Excluded list are safe. Removed apps are recorded for later restore.")
        btn_bugs = ctk.CTkButton(actions, text="\U0001f41b Fix Popup Ad", fg_color="#b45309", hover_color="#92400e", border_color="#d97706", command=self.action_sec_remove_bugs, **btn_style)
        btn_bugs.grid(row=0, column=2, padx=4, pady=8, sticky="ew")
        Tooltip(btn_bugs, "One-tap fix for popup-ad bug on the CHECKED apps: Phase 1 cleans storage of checked apps, Phase 2 uninstalls the checked 3rd-party apps (system apps are never removed).")
        btn_excl = ctk.CTkButton(actions, text="\u2795 Exclude", fg_color="#21262d", hover_color="#30363d", border_color="#30363d", command=self.action_sec_add_excluded, **btn_style)
        btn_excl.grid(row=0, column=3, padx=4, pady=8, sticky="ew")
        Tooltip(btn_excl, "Protects the CHECKED apps from Clean / Uninstall. Choose Clean (keeps data), Uninstall (keeps installed) or Both. Excluded apps show orange/red rows.")
        btn_info = None
        btn_backup = ctk.CTkButton(actions, text="\U0001f4be Backup", fg_color="#21262d", hover_color="#30363d", border_color="#30363d", command=self.action_sec_backup_restore, **btn_style)
        btn_backup.grid(row=0, column=4, padx=4, pady=8, sticky="ew")
        Tooltip(btn_backup, "Your saved settings in one place: view exclusion counts and restore apps you uninstalled earlier (reinstalls them on your phone).")
        btn_all = ctk.CTkButton(actions, text="\U0001f4e6 All", fg_color="#21262d", hover_color="#30363d", border_color="#30363d", command=self.action_list_all_packages, **btn_style)
        btn_all.grid(row=0, column=6, padx=4, pady=8, sticky="ew")
        Tooltip(btn_all, "Loads EVERY installed package into this list. The action buttons below (Clean / Uninstall / Disable / Exclude...) then work on the apps you check. Right-click any app row for per-app actions (Disable / Uninstall / Clean / Exclude / Info).")
        btn_disabled = ctk.CTkButton(actions, text="\U0001f4e5 Disabled", fg_color="#21262d", hover_color="#30363d", border_color="#30363d", command=self.action_list_disabled_packages, **btn_style)
        btn_disabled.grid(row=0, column=7, padx=4, pady=8, sticky="ew")
        Tooltip(btn_disabled, "Loads the disabled packages on your phone into this list. The action buttons below work on the apps you check.")
        btn_filter = ctk.CTkButton(actions, text="\U0001f50e Filter", fg_color="#0f7489", hover_color="#0c5f70", border_color="#1497ab", command=self.action_sec_db_filter, **btn_style)
        btn_filter.grid(row=0, column=8, padx=4, pady=8, sticky="ew")
        Tooltip(btn_filter, "Loads apps matching database criteria (removal level, risk, category, manufacturer, source) into the list. Review, then check and use Uninstall.")
        self._perm_sidebar_btns.setdefault("device_info", []).extend([btn_all, btn_disabled, btn_filter])

        # Row 5 - Inline result / log panel
        self.sec_result_panel = ctk.CTkTextbox(tab, fg_color="#0d1117", border_color="#30363d", border_width=1, corner_radius=8, height=110, font=ctk.CTkFont(size=9, family="Consolas"), text_color="#c9d1d9")
        self.sec_result_panel.grid(row=5, column=0, padx=15, pady=(0, 6), sticky="ew")
        self._sec_result_tags = {}
        self._sec_log("[GeloTech] APK Cleaner ready. Connect device, press Refresh.", "#8b949e")

        # Row 6 - USB debugging help (collapsible)
        self.sec_help_frame = ctk.CTkFrame(tab, fg_color="#131921", corner_radius=8)
        self.sec_help_frame.grid(row=6, column=0, padx=15, pady=(0, 12), sticky="ew")
        self.sec_help_btn = ctk.CTkButton(self.sec_help_frame, text="\U0001f4f1 How to enable USB Debugging  \u25be", height=26, fg_color="transparent", hover_color="#21262d", font=ctk.CTkFont(size=10, weight="bold"), text_color="#58a6ff", anchor="w", command=self._toggle_sec_help)
        self.sec_help_btn.pack(fill="x", padx=6, pady=2)
        self.sec_help_body = ctk.CTkFrame(self.sec_help_frame, fg_color="transparent")
        self.sec_help_visible = False
        steps = [
            "1. On your phone, open Settings \u2192 About Phone",
            "2. Tap \u201cBuild Number\u201d 7 times until \u201cYou are now a developer!\u201d appears",
            "3. Go back \u2192 open Developer Options (usually under System / Additional Settings)",
            "4. Turn ON \u201cUSB debugging\u201d",
            "5. Connect the phone to this PC with a USB cable (use a data cable, not a charge-only one)",
            "6. On the phone, tap \u201cAllow\u201d when the \u201cAllow USB debugging?\u201d prompt appears (tick Always allow)",
            "7. Back in this tool, press \U0001f504 Refresh \u2014 the header should show \u2705 Device connected",
        ]
        for s in steps:
            ctk.CTkLabel(self.sec_help_body, text=s, font=ctk.CTkFont(size=9), text_color="#8b949e", anchor="w", justify="left", wraplength=1100).pack(fill="x", padx=12, pady=1)

        self._sec_anim_running = False
        self.after(300, self._sec_load_device_info)
        self.after(400, self.action_sec_refresh)

    # ----------------------------------------------------
    # DNS TAB UI
    # ----------------------------------------------------
    def build_dns_tab(self):
        tab = self.tabview.tab("Block Ads via DNS")
        tab.grid_columnconfigure(0, weight=1)

        # Header
        header = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        header.grid(row=0, column=0, padx=15, pady=(12, 8), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="\ud83c\udf10", font=ctk.CTkFont(size=24)).grid(row=0, column=0, padx=(14, 5), pady=10)
        ctk.CTkLabel(header, text="Block most Apps popup Ads | Select DNS Server from OPTIONS BELOW", font=ctk.CTkFont(size=14, weight="bold"), text_color="#e67e22").grid(row=0, column=1, sticky="w", pady=10)
        self.dns_status_label = ctk.CTkLabel(header, text="Check DNS...", font=ctk.CTkFont(size=11), text_color="#8b949e")
        self.dns_status_label.grid(row=0, column=2, padx=10, pady=10, sticky="e")

        # Config area
        config = ctk.CTkFrame(tab, fg_color="#131921", corner_radius=8)
        config.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="ew")
        config.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(config, text="DNS Provider:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#d1d5db").grid(row=0, column=0, padx=(14, 8), pady=12, sticky="w")
        self.dns_options = {
            "🛡️ AdGuard DNS (blocks ads & trackers)": "dns.adguard-dns.com",
            "☁️ Cloudflare 1.1.1.1 (fast & private)": "one.one.one.one",
            "🔍 Google DNS (reliable)": "dns.google",
            "🔒 Quad9 (blocks malware & phishing)": "dns.quad9.net",
            "👪 CleanBrowsing Family (safe for kids)": "family-filter-dns.cleanbrowsing.org",
            "🔞 CleanBrowsing Adult (blocks adult content)": "adult-filter-dns.cleanbrowsing.org",
            "🛡️ CleanBrowsing Security (blocks malware)": "security-filter-dns.cleanbrowsing.org",
            "⚙️ Control D (custom rules)": "dns.controld.com",
            "🇪🇺 SecureDNS EU (privacy focused)": "dot.securedns.eu",
            "🎯 NextDNS (advanced filtering)": "dns.nextdns.io"
        }
        self.dns_dropdown = ctk.CTkComboBox(config, values=list(self.dns_options.keys()),
            fg_color="#0d1117", border_color="#282e37", button_color="#282e37", button_hover_color="#395670",
            dropdown_fg_color="#0d1117", dropdown_hover_color="#1f2a3a", dropdown_text_color="#d1d5db",
            text_color="#d1d5db", width=380, state="readonly")
        self.dns_dropdown.grid(row=0, column=1, padx=(0, 10), pady=12, sticky="ew")

        ctk.CTkButton(config, text="\u2713 Apply DNS", width=100, height=32, fg_color="#e67e22", hover_color="#d35400", font=ctk.CTkFont(weight="bold"), command=self.action_dns_apply).grid(row=0, column=2, padx=(0, 6), pady=12)
        ctk.CTkButton(config, text="\u274c Disable", width=90, height=32, fg_color="#c0392b", hover_color="#a82521", font=ctk.CTkFont(weight="bold"), command=self.action_dns_disable).grid(row=0, column=3, padx=(0, 14), pady=12)

        # Refresh current status
        self.after(500, self.action_dns_refresh)

    # ----------------------------------------------------
    # MONITOR RUNNING APPS (APP WATCH) TAB UI
    # ----------------------------------------------------
    def build_monitor_tab(self):
        tab = self.tabview.tab("Monitor Running Apps")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        # Row 0 - Header with monitoring switch
        header = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        header.grid(row=0, column=0, padx=15, pady=(12, 6), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="\U0001f50d", font=ctk.CTkFont(size=24), text_color="#1abc9c").grid(row=0, column=0, padx=(14, 5), pady=8)
        info = ctk.CTkFrame(header, fg_color="transparent")
        info.grid(row=0, column=1, sticky="w", pady=8)
        ctk.CTkLabel(info, text="MONITOR RUNNING APPS (APP WATCH)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#1abc9c").pack(anchor="w")
        ctk.CTkLabel(info, text="Find which app shows pop-up ads \u2014 monitor, use your phone, then check history", font=ctk.CTkFont(size=10), text_color="#a6a6a6").pack(anchor="w")
        self.appwatch_switch = ctk.CTkSwitch(header, text="Start monitoring", font=ctk.CTkFont(size=11, weight="bold"), command=self.toggle_appwatch, progress_color="#1abc9c")
        self.appwatch_switch.grid(row=0, column=2, padx=(8, 12), pady=10)

        # Row 1 - How to use
        howto = ctk.CTkFrame(tab, fg_color="#131921", corner_radius=8)
        howto.grid(row=1, column=0, padx=15, pady=(0, 6), sticky="ew")
        ctk.CTkLabel(howto, text="How to catch the culprit app:", font=ctk.CTkFont(size=10, weight="bold"), text_color="#1abc9c").grid(row=0, column=0, padx=(12, 8), pady=(8, 2), sticky="w")
        ctk.CTkLabel(howto, text=(
            "1. Turn on \u201cStart monitoring\u201d\n"
            "2. Exit this app and start using your phone normally\n"
            "3. When a pop-up ad randomly appears, open this app and check the activity history below\n"
            "4. The latest launched app is most likely the one showing the annoying ads\n"
            "5. Use Stop / Disable / Uninstall on the culprit app"),
            justify="left", anchor="w", font=ctk.CTkFont(size=9), text_color="#a6a6a6").grid(row=1, column=0, padx=(12, 8), pady=(0, 8), sticky="w")

        # Row 2 - Status bar
        status = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        status.grid(row=2, column=0, padx=15, pady=(0, 6), sticky="ew")
        status.grid_columnconfigure(1, weight=1)
        self.appwatch_status_label = ctk.CTkLabel(status, text="Monitoring: OFF", font=ctk.CTkFont(size=10, weight="bold"), text_color="#e74c3c")
        self.appwatch_status_label.grid(row=0, column=0, padx=12, pady=6, sticky="w")
        self.appwatch_now_label = ctk.CTkLabel(status, text="Foreground: \u2014", font=ctk.CTkFont(size=10), text_color="#a6a6a6")
        self.appwatch_now_label.grid(row=0, column=1, padx=12, pady=6, sticky="w")
        self.appwatch_count_label = ctk.CTkLabel(status, text="Events: 0", font=ctk.CTkFont(size=10), text_color="#1abc9c")
        self.appwatch_count_label.grid(row=0, column=2, padx=12, pady=6, sticky="e")

        # Row 3 - Activity history
        self.appwatch_frame = ctk.CTkScrollableFrame(tab, fg_color="#131921", corner_radius=6)
        self.appwatch_frame.grid(row=3, column=0, padx=15, pady=(0, 6), sticky="nsew")
        self.appwatch_frame.grid_columnconfigure(1, weight=1)

        # Row 4 - Bottom actions
        batch = ctk.CTkFrame(tab, fg_color="#1b222c", corner_radius=8)
        batch.grid(row=4, column=0, padx=15, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(batch, text="Actions apply to the latest (culprit) app", font=ctk.CTkFont(size=10, weight="bold"), text_color="#cbd9e6").pack(side="left", padx=(12, 8), pady=9)
        ctk.CTkButton(batch, text="\u2715 Clear History", width=110, height=30, fg_color="#395670", hover_color="#1f2a3a", command=self.action_appwatch_clear).pack(side="right", padx=12, pady=8)

        self.appwatch_history = []
        self.appwatch_monitoring = False

    # ----------------------------------------------------
    # MONITOR RUNNING APPS (APP WATCH) OPERATIONS
    # ----------------------------------------------------
