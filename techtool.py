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
import webbrowser
from PIL import Image, ImageDraw, ImageFont
from tech_common import get_bundle_dir, get_app_dir, get_settings_dir, get_live_database_path, Tooltip, subprocess, load_package_database, APP_VERSION

# Application Global Styling Configurations
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Scale UI for high-DPI / small font compensation
ctk.set_widget_scaling(1.15)

from tech_ui import UiMixin
from tech_settings import SettingsMixin
from tech_secscan import SecScanMixin
from tech_secops import SecOpsMixin
from tech_secops2 import SecOps2Mixin
from tech_vtop import VtOpsMixin
from tech_misc import MiscMixin

class GeloTechTool(ctk.CTk, UiMixin, SettingsMixin, SecScanMixin, SecOpsMixin, SecOps2Mixin, VtOpsMixin, MiscMixin):
    PERMISSIONS = {
        "device_info": "Device Info & Package Lists",
        "mirror": "Screen Mirror & Logcat",
        "power": "Reboot (Recovery / Fastboot)",
        "connection": "Re-authorize ADB & Fix Drivers",
        "cleaner": "Popup Ad Virus Cleaner",
        "monitor": "Monitor Running Apps",
        "dns": "Block Ads via DNS",
        "virustotal": "VirusTotal Scanner",
        "restore": "Restore Uninstalled Apps",
    }
    TAB_PERMS = {
        "Popup Ad Virus Cleaner": "cleaner",
        "Monitor Running Apps": "monitor",
        "Block Ads via DNS": "dns",
        "VirusTotal": "virustotal",
    }

    def __init__(self):
        super().__init__()
        self._perm_sidebar_btns = {}
        self.current_user = None
        self.is_admin = True
        self.user_perms = None

        # Primary Window Geometry & Title setup
        self.title(f"GeloTech Tool v{APP_VERSION}")
        try:
            self.iconbitmap(os.path.join(get_bundle_dir(), "gelotech_icon.ico"))
        except Exception:
            pass
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win_w = max(1120, min(1500, int(sw * 0.92)))
        win_h = max(660, min(850, int(sh * 0.88)))
        self.geometry(f"{win_w}x{win_h}+{(sw - win_w) // 2}+{max(0, (sh - win_h) // 3)}")
        self.minsize(min(1120, win_w), min(660, win_h))
        ctk.set_widget_scaling(min(1.5, max(1.0, 1.15 * sh / 900)))
        self.grid_columnconfigure(0, weight=0)  # sidebar fixed
        self.grid_columnconfigure(1, weight=3)  # tab content
        self.grid_columnconfigure(2, weight=1, minsize=340)  # log panel
        self.grid_rowconfigure(0, weight=1)

        self.debloat_packages = []
        self.background_scan_running = False
        self.adb_device_scan_running = False
        self.known_adb_devices = None
        self.adb_monitor_enabled = True
        self._fonts = {
            "row_name": ctk.CTkFont(size=11, weight="bold"),
            "row_badge": ctk.CTkFont(size=9, weight="bold"),
            "row_desc": ctk.CTkFont(size=9),
        }

        self.virustotal_api_key = "25a0a1b604b4d2d0ab385a0d98ec3b198d5c7d9739c61cf3cce442fa7a8f253f"
        self.vt_scan_results = {}
        self.vt_selected = {}

        # ----------------------------------------------------
        # SIDEBAR REGION (Left Layout Pane)
        # ----------------------------------------------------
        self._extract_scrcpy()
        os.environ["PATH"] = self.scrcpy_dir + os.pathsep + os.environ.get("PATH", "")
        self._migrate_settings()
        self._seed_database_defaults()
        self.sidebar_frame = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color="#0d0f12")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # Branding Header Elements (compact, centered)
        brand_font = "Verdana"
        ctk.CTkLabel(self.sidebar_frame, text="\u00a9 2026 GeloTech", font=ctk.CTkFont(family=brand_font, size=10), text_color="#444", height=16).grid(row=0, column=0, padx=14, pady=(6, 0))

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="GELOTECH", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1a8cff", height=26)
        self.logo_label.grid(row=1, column=0, padx=14, pady=(1, 0))

        self.sub_logo_label = ctk.CTkLabel(self.sidebar_frame, text=f"TECH TOOL\nv{APP_VERSION} - Angelo Estrada Espinosa", font=ctk.CTkFont(family=brand_font, size=11, weight="bold"), text_color="#a6a6a6", justify="center", height=34)
        self.sub_logo_label.grid(row=2, column=0, padx=10, pady=(2, 2))

        def _brand_link(parent, text, url):
            lbl = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(family=brand_font, size=10, underline=True), text_color="#58a6ff", cursor="hand2", height=16)
            lbl.pack(pady=0)
            lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            Tooltip(lbl, f"Open {text} in your browser")
            return lbl

        links = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        links.grid(row=3, column=0, padx=10, pady=(0, 1))
        _brand_link(links, "Gsmcodeph.com", "https://gsmcodeph.com")
        _brand_link(links, "facebook.com/gelotechxyz", "https://www.facebook.com/gelotechxyz")

        self.license_label = ctk.CTkLabel(self.sidebar_frame, text="Valid until: 2030-07-17\n● ALL FUNCTIONS ACTIVE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#2ecc71", height=30, justify="center")
        self.license_label.grid(row=4, column=0, padx=14, pady=2)

        separator = ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#2c3340")
        separator.grid(row=5, column=0, padx=12, pady=(2, 3), sticky="ew")

        # Sidebar menu: grouped icon buttons
        row = 6

        def _add_btn(icon, text, command, color="#4d6bfe", perm=None):
            nonlocal row
            btn = ctk.CTkButton(
                self.sidebar_frame, text=f"{icon}  {text}", anchor="w",
                fg_color="#1c2026", hover_color=color, text_color="#e8ecf2",
                border_color="#2c3340", border_width=1, corner_radius=8,
                height=26, font=ctk.CTkFont(size=10, weight="bold"),
                command=command)
            btn.grid(row=row, column=0, padx=10, pady=0, sticky="ew")
            row += 1
            if perm:
                self._perm_sidebar_btns.setdefault(perm, []).append(btn)
            return btn

        def _add_header(title):
            nonlocal row
            ctk.CTkLabel(self.sidebar_frame, text=title, font=ctk.CTkFont(size=8, weight="bold"),
                         text_color="#7a8699", height=14).grid(row=row, column=0, padx=14, pady=(4, 0), sticky="w")
            row += 1

        _add_header("DISPLAY")
        _add_btn("\U0001f4f1", "Screen Mirror (scrcpy)", self.action_scrcpy_mirror, color="#2ecc71", perm="mirror")

        _add_header("POWER")
        _add_btn("\U0001f504", "Reboot to Recovery", lambda: self.run_system_cmd_async([self.scrcpy_adb, "reboot", "recovery"], "Rebooting to Recovery..."), color="#e67e22", perm="power")
        _add_btn("\U0001f501", "Reboot to Fastboot", lambda: self.run_system_cmd_async([self.scrcpy_adb, "reboot", "bootloader"], "Rebooting to Fastboot..."), color="#e67e22", perm="power")

        _add_header("CONNECTION")
        _add_btn("\U0001f504", "Re-authorize ADB", self.action_read_auth_adb, color="#e74c3c", perm="connection")
        _add_btn("\U0001f527", "Fix / DL ADB Drivers", self.action_fix_drivers, color="#9b59b6", perm="connection")

        _add_header("SESSION")
        self._admin_panel_btn = _add_btn("\U0001f511", "Admin Panel", self._open_admin_panel, color="#d4af37")
        _add_btn("\U0001f6aa", "Logout", self._logout, color="#7f8c8d")

        legend = ctk.CTkFrame(self.sidebar_frame, fg_color="#11151c", corner_radius=8)
        legend.grid(row=row, column=0, padx=10, pady=(4, 2), sticky="ew")
        lr = 0
        ctk.CTkLabel(legend, text="REMOVAL LEVELS", font=ctk.CTkFont(size=7, weight="bold"), text_color="#7a8699", height=14).grid(row=lr, column=0, columnspan=2, sticky="w", padx=8, pady=(3, 1)); lr += 1
        for color, term, meaning in (
            ("#2ea043", "Recommended", "safe to remove"),
            ("#58a6ff", "Advanced", "mostly safe"),
            ("#e3b341", "Expert", "may break features"),
            ("#e5534b", "Unsafe", "dangerous, avoid"),
        ):
            ctk.CTkLabel(legend, text="\u25cf", text_color=color, font=ctk.CTkFont(size=7), height=14).grid(row=lr, column=0, padx=(8, 3), pady=0)
            ctk.CTkLabel(legend, text=f"{term} \u2014 {meaning}", font=ctk.CTkFont(size=7), text_color="#8b949e", anchor="w", height=14).grid(row=lr, column=1, sticky="w", padx=(0, 6), pady=0)
            lr += 1
        row += 1

        # ----------------------------------------------------
        # MIDDLE: TAB VIEW
        # ----------------------------------------------------
        self.tabview = ctk.CTkTabview(self, fg_color="#16191e", command=self.on_tab_changed)
        self.tabview.grid(row=0, column=1, padx=(6, 3), pady=8, sticky="nsew")
        
        tabs = ["Popup Ad Virus Cleaner", "Monitor Running Apps", "Block Ads via DNS", "VirusTotal"]
        for tab in tabs:
            self.tabview.add(tab)
            self.tabview.tab(tab).grid_columnconfigure(0, weight=1)

        self.build_virustotal_tab()
        self.build_security_tab()
        self.build_monitor_tab()
        self.build_dns_tab()

        # ----------------------------------------------------
        # RIGHT: UNIFIED LOG PANEL (TSM/UnlockTool style)
        # ----------------------------------------------------
        self._build_log_panel()
        self._build_hint_banner()

        self.log_message("System Initialized. Welcome to GeloTech Tool.")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(150, self.start_adb_device_monitor)
        self.after(200, self._login_gate)

    # ----------------------------------------------------
    # HINT BANNER (bottom of window, grabs attention)
    # ----------------------------------------------------
    def _build_hint_banner(self):
        self._hint_banner = ctk.CTkFrame(self, fg_color="#3a0d10", corner_radius=0, height=30)
        self._hint_banner.grid(row=1, column=0, columnspan=3, sticky="ew")
        self._hint_banner.grid_columnconfigure(0, weight=1)
        self._hint_banner.grid_propagate(False)
        self._hint_label = ctk.CTkLabel(
            self._hint_banner, text="", anchor="w", justify="left",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="#ff4d4d")
        self._hint_label.grid(row=0, column=0, sticky="ew", padx=14, pady=5)
        self._hint_banner.grid_remove()
        self._hint_timer = None

    def show_hint(self, text):
        try:
            if not hasattr(self, "_hint_label"):
                return
            self._hint_label.configure(text="\u26a0  " + text)
            self._hint_banner.grid()
            if self._hint_timer:
                self.after_cancel(self._hint_timer)
            self._hint_timer = self.after(6000, self._hide_hint)
        except Exception:
            pass

    def _hide_hint(self):
        try:
            self._hint_timer = None
            self._hint_banner.grid_remove()
        except Exception:
            pass

    # ----------------------------------------------------
    # UNIFIED LOG PANEL
    # ----------------------------------------------------
    def _build_log_panel(self):
        panel = ctk.CTkFrame(self, fg_color="#01030a", corner_radius=0, border_width=0)
        panel.grid(row=0, column=2, sticky="nsew", padx=(3, 6), pady=8)
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        # Header bar
        hdr = ctk.CTkFrame(panel, fg_color="#03160d", corner_radius=6, height=38)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        hdr.grid_columnconfigure(1, weight=1)
        hdr.grid_propagate(False)

        ctk.CTkLabel(hdr, text="\u25a0 LOG CONSOLE", font=ctk.CTkFont(size=11, weight="bold"), text_color="#00ff66").grid(row=0, column=0, padx=(12, 6), pady=8, sticky="w")

        # Filter chips
        filter_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        filter_frame.grid(row=0, column=1, padx=6, pady=6, sticky="e")
        filters = ["ALL", "ADB", "SECURITY", "VT", "DNS"]
        colors = {"ALL": "#0f3d1e", "ADB": "#0f5a2a", "SECURITY": "#0a7a33", "VT": "#3d1e0f", "DNS": "#0f5a5a"}
        for i, f in enumerate(filters):
            btn = ctk.CTkButton(filter_frame, text=f, width=52, height=22,
                                fg_color=colors[f], hover_color="#14582b",
                                font=ctk.CTkFont(size=8, weight="bold"),
                                command=lambda ff=f: self._set_log_filter(ff))
            btn.pack(side="left", padx=1)

        # Clear button
        ctk.CTkButton(hdr, text="\u2715 Clear", width=60, height=24,
                       fg_color="#3a2a2a", hover_color="#5a3a3a",
                       font=ctk.CTkFont(size=9, weight="bold"),
                       command=self.clear_logs).grid(row=0, column=2, padx=(4, 10), pady=6)

        # Log display
        self.main_log = ctk.CTkTextbox(panel, font=ctk.CTkFont(family="Consolas", size=11),
                                        fg_color="#000200", text_color="#00ff41",
                                        border_color="#0a5a24", border_width=1,
                                        wrap="word")
        self.main_log.grid(row=1, column=0, sticky="nsew")
        self.main_log.tag_config("ADB", foreground="#00ff41")
        self.main_log.tag_config("SECURITY", foreground="#7cff00")
        self.main_log.tag_config("VT", foreground="#29ffbf")
        self.main_log.tag_config("DNS", foreground="#00d8ff")
        self.main_log.tag_config("EXEC", foreground="#b8ff66")
        self.main_log.tag_config("SYSTEM", foreground="#33ff99")
        self.main_log.tag_config("ERROR", foreground="#ff3355")
        self.main_log.tag_config("INFO", foreground="#00cc55")
        self.main_log.tag_config("HINT", foreground="#338844")
        self.main_log.tag_config("DEFAULT", foreground="#00ff41")
        self._log_filter_active = "ALL"

        # Stats bar at bottom
        stats_bar = ctk.CTkFrame(panel, fg_color="#03160d", corner_radius=6, height=28)
        stats_bar.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        stats_bar.grid_propagate(False)
        self.log_line_count_label = ctk.CTkLabel(stats_bar, text="Lines: 0", font=ctk.CTkFont(size=9), text_color="#00cc55")
        self.log_line_count_label.pack(side="left", padx=10, pady=4)
        self.log_filter_label = ctk.CTkLabel(stats_bar, text="Filter: ALL", font=ctk.CTkFont(size=9), text_color="#00cc55")
        self.log_filter_label.pack(side="left", padx=6, pady=4)
        ctk.CTkLabel(stats_bar, text="\u2588 console active", font=ctk.CTkFont(size=8, weight="bold"), text_color="#00ff41").pack(side="right", padx=10, pady=4)

    def _set_log_filter(self, f):
        self._log_filter_active = f
        self.log_filter_label.configure(text=f"Filter: {f}")
        # Re-display all log entries with new filter
        if hasattr(self, '_log_history') and self._log_history:
            self.main_log.delete("1.0", "end")
            for tag, msg in self._log_history:
                if f == "ALL" or f == tag or (f == "ADB" and tag in ("ADB", "EXEC", "SYSTEM")):
                    self.main_log.insert("end", msg + "\n", tag)
            self.main_log.see("end")

    def _extract_scrcpy(self):
        """Extract scrcpy zip to a temp directory and set paths."""
        import zipfile
        import tempfile
        base_path = get_bundle_dir()
        zip_path = os.path.join(base_path, "scrcpy-win64-v3.3.4.zip")
        if not os.path.exists(zip_path):
            # NOTE: log_message() silently no-ops here since main_log hasn't been
            # created yet at this point in __init__, so print to console too.
            print(f"[ADB ERROR] scrcpy zip not found at {zip_path}")
            self.log_message(f"[ADB ERROR] scrcpy zip not found at {zip_path}")
            self.scrcpy_dir = os.path.join(base_path, "scrcpy-win64-v3.3.4")
            self.scrcpy_exe = os.path.join(self.scrcpy_dir, "scrcpy.exe")
            self.scrcpy_adb = os.path.join(self.scrcpy_dir, "adb.exe")
            if not os.path.exists(self.scrcpy_adb):
                print(f"[ADB ERROR] adb.exe also not found at {self.scrcpy_adb} -- all ADB features will fail until scrcpy-win64-v3.3.4.zip is placed next to techtool.py")
            return
        self.scrcpy_dir = tempfile.mkdtemp(prefix="gelotech_scrcpy_")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.scrcpy_dir)

        # The zip's internal layout may not be flat (e.g. everything nested inside
        # an extra subfolder), so search for the actual exe locations rather than
        # assuming they sit directly at the extraction root.
        found_adb, found_scrcpy = None, None
        for root, _dirs, files in os.walk(self.scrcpy_dir):
            if found_adb and found_scrcpy:
                break
            if not found_adb and "adb.exe" in files:
                found_adb = os.path.join(root, "adb.exe")
            if not found_scrcpy and "scrcpy.exe" in files:
                found_scrcpy = os.path.join(root, "scrcpy.exe")

        if found_adb:
            self.scrcpy_adb = found_adb
            self.scrcpy_dir = os.path.dirname(found_adb)  # so PATH env var / cwd point at the real bin folder
        else:
            self.scrcpy_adb = os.path.join(self.scrcpy_dir, "adb.exe")
            print(f"[ADB ERROR] adb.exe not found anywhere under extracted scrcpy folder: {self.scrcpy_dir}")

        self.scrcpy_exe = found_scrcpy or os.path.join(self.scrcpy_dir, "scrcpy.exe")
        self.log_message(f"[ADB] scrcpy extracted to {self.scrcpy_dir}")

    # ----------------------------------------------------
    # TAB INTERFACE CONFIGURATIONS
    # ----------------------------------------------------
    def on_tab_changed(self, *_args):
        pass

    def start_adb_device_monitor(self):
        self.log_message("[ADB] Scanning for connected devices...")
        self.scan_adb_devices()

    def scan_adb_devices(self):
        if not self.adb_monitor_enabled or self.adb_device_scan_running:
            return
        self.adb_device_scan_running = True

        def worker():
            devices = []
            unauthorized = []
            error = None
            try:
                result = subprocess.run(
                    [self.scrcpy_adb, "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, timeout=8
                )
                for line in result.stdout.splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 2:
                        if parts[1] == "device":
                            devices.append(parts[0])
                        elif parts[1] == "unauthorized":
                            unauthorized.append(parts[0])
            except (FileNotFoundError, subprocess.SubprocessError) as scan_error:
                error = scan_error
            finally:
                if self.adb_monitor_enabled:
                    self.after(0, lambda: self.apply_adb_device_status(devices, unauthorized, error))
                    self.after(3000, self.scan_adb_devices)

        threading.Thread(target=worker, daemon=True).start()

    def apply_adb_device_status(self, devices, unauthorized, error):
        self.adb_device_scan_running = False
        if not self.adb_monitor_enabled:
            return
        if error:
            status = "ADB unavailable"
            color = "#e74c3c"
        elif devices:
            status = f"Connected: {', '.join(devices)}"
            color = "#2ecc71"
        elif unauthorized:
            status = f"Unauthorized: {', '.join(unauthorized)} \u2014 accept USB debugging prompt on phone"
            color = "#f39c12"
            self.log_message(f"[ADB] {status}")
            return
        else:
            status = "No authorized ADB device"
            color = "#a6a6a6"

        if status != self.known_adb_devices:
            self.known_adb_devices = status
            self.log_message(f"[ADB] {status}")

    def on_close(self):
        self.adb_monitor_enabled = False
        self.appwatch_monitoring = False
        self._purge_session_database()
        self.destroy()

    @staticmethod
    def _as_list(value):
        return value if isinstance(value, list) else []

    def load_debloat_catalog(self):
        """Load the bundled package database (gelotech_database_v3.json) as debloat records."""
        if hasattr(self, '_debloat_cache') and self._debloat_cache is not None:
            return self._debloat_cache
        lookup = load_package_database(get_live_database_path())
        database = {}
        for pid, entry in lookup.items():
            removal = entry.get("removal", "Unknown")
            database[pid] = {
                "id": pid,
                "label": entry.get("label") or pid,
                "description": entry.get("description") or "No description available.",
                "removal": removal,
                "category": removal,
                "risk": entry.get("risk", "unknown"),
                "manufacturer": entry.get("manufacturer", "Unknown"),
                "warning": entry.get("warning", ""),
                "web": list(entry.get("web") or []),
                "dependencies": list(entry.get("dependencies") or []),
                "required_by": list(entry.get("required_by") or []),
                "suggestions": entry.get("suggestions", ""),
                "tags": list(entry.get("tags") or []),
                "safe_alternatives": list(entry.get("safe_alternatives") or []),
            }
        self._debloat_cache = (database, 0)
        return self._debloat_cache

    def _confirm_and_run_debloat_operation(self, packages, operation):
        action_name = {"disable": "disable", "enable": "enable or restore", "uninstall": "remove for this Android user"}[operation]
        if operation in ("disable", "uninstall"):
            risk_messages = []
            if self.debloat_packages:
                installed_packages = {record["id"] for record in self.debloat_packages}
                for package_id in packages:
                    record = next((r for r in self.debloat_packages if r["id"] == package_id), None)
                    if not record:
                        continue
                    if record.get("warning"):
                        risk_messages.append(f"• {package_id}: {record['warning']}")
                    required_by = set(record.get("required_by", []))
                    required_by.update(
                        candidate["id"] for candidate in self.debloat_packages
                        if package_id in candidate.get("dependencies", [])
                    )
                    installed_dependents = sorted(required_by.intersection(installed_packages) - set(packages))
                    if installed_dependents:
                        preview = ", ".join(installed_dependents[:5])
                        suffix = " …" if len(installed_dependents) > 5 else ""
                        risk_messages.append(f"• {package_id} may be required by installed app(s): {preview}{suffix}")
                    if record.get("category") == "Unsafe":
                        risk_messages.append(f"• {package_id} is marked Unsafe and can break core Android features.")

            if risk_messages:
                warning_text = (
                    "Safety check found the following risk(s):\n\n" + "\n".join(risk_messages) +
                    f"\n\nDo you still want to {action_name} the selected package(s)?"
                )
                if not messagebox.askyesno("Dependency / safety warning", warning_text, icon="warning"):
                    self.log_message("[SECURITY] Action cancelled after the dependency/safety warning.")
                    return
        if not messagebox.askyesno("Confirm package action", f"Do you want to {action_name} {len(packages)} selected package(s)?"):
            return

        should_backup = False
        if operation == "uninstall":
            should_backup = messagebox.askyesno("Backup before uninstall",
                f"Do you want to backup the APK(s) to your computer before uninstalling?\n\n"
                f"This saves the original .apk file(s) so you can restore later if needed.\n"
                f"({len(packages)} package(s))")

        def worker():
            succeeded = 0
            backup_dir = None
            if should_backup:
                backup_dir = os.path.join(get_settings_dir(), "apk_backups")
                os.makedirs(backup_dir, exist_ok=True)
                self.log_message(f"[SECURITY] Backing up APKs to: {backup_dir}")
            for package_id in packages:
                try:
                    if operation == "disable":
                        command = [self.scrcpy_adb, "shell", "pm", "disable-user", "--user", "0", package_id]
                        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                    elif operation == "uninstall":
                        if should_backup and backup_dir:
                            path_res = subprocess.run([self.scrcpy_adb, "shell", "pm", "path", package_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                            apk_paths = [l[len("package:"):].strip() for l in path_res.stdout.splitlines() if l.startswith("package:")]
                            if apk_paths:
                                dest = os.path.join(backup_dir, f"{package_id}.apk")
                                subprocess.run([self.scrcpy_adb, "pull", apk_paths[0], dest], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                                if os.path.isfile(dest):
                                    self.log_message(f"[SECURITY] Backed up: {package_id}.apk")
                                else:
                                    self.log_message(f"[SECURITY ERROR] Backup failed for: {package_id}")
                        command = [self.scrcpy_adb, "shell", "pm", "uninstall", "-k", "--user", "0", package_id]
                        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                    else:
                        subprocess.run([self.scrcpy_adb, "shell", "cmd", "package", "install-existing", "--user", "0", package_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                        result = subprocess.run([self.scrcpy_adb, "shell", "pm", "enable", "--user", "0", package_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)

                    output = (result.stdout + result.stderr).strip()
                    if result.returncode == 0:
                        succeeded += 1
                        self.log_message(f"[SECURITY] {operation.title()}: {package_id}")
                    else:
                        self.log_message(f"[SECURITY ERROR] {package_id}: {output}")
                except (FileNotFoundError, subprocess.SubprocessError) as error:
                    self.log_message(f"[SECURITY ERROR] {package_id}: {error}")
            if succeeded and operation in ("disable", "uninstall"):
                for cleared in packages:
                    subprocess.run([self.scrcpy_adb, "shell", "pm", "clear", cleared], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                    self.log_message(f"[SECURITY] Cache cleared for: {cleared}")
            if succeeded and operation == "uninstall":
                self._record_debloated(packages)
            if succeeded and operation == "enable":
                data = self._load_settings()
                remaining = [p for p in data["debloated"] if p not in packages]
                if len(remaining) != len(data["debloated"]):
                    self._save_debloated(remaining)
            self.log_message(f"[SECURITY] {operation.title()} completed for {succeeded}/{len(packages)} package(s).")
        threading.Thread(target=worker, daemon=True).start()

    # ----------------------------------------------------
    # VIRUSTOTAL TAB UI
    # ----------------------------------------------------
if __name__ == "__main__":
    app = GeloTechTool()
    app.mainloop()
