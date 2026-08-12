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
from tech_common import get_bundle_dir, get_app_dir, get_settings_dir, get_live_database_path, Tooltip, subprocess, load_package_database, APP_VERSION, THEME, THEMES, COLOR_SWAP, CANONICAL_DARK
from tech_navigation import NavigationController
from tech_bloatware import BloatwareFilterMixin
from tech_task_manager import TaskManager
from tech_database import DatabaseService

# Application Global Styling Configurations
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Scale UI for high-DPI / small font compensation
ctk.set_widget_scaling(1.15)

from tech_ui import UiMixin
from tech_settings import SettingsMixin
from tech_secscan import SecScanMixin
from tech_secops import SecOpsMixin
from tech_secops3 import SecOps3Mixin
from tech_secops2 import SecOps2Mixin
from tech_secops4 import SecOps4Mixin
from tech_dash import DashboardMixin
from tech_vtop import VtOpsMixin
from tech_misc import MiscMixin

class GeloTechTool(ctk.CTk, UiMixin, SettingsMixin, SecScanMixin, SecOpsMixin, BloatwareFilterMixin, SecOps3Mixin, SecOps2Mixin, SecOps4Mixin, DashboardMixin, VtOpsMixin, MiscMixin):
    PERMISSIONS = {
        "device_info": "Device Info & Package Lists",
        "mirror": "Screen Mirror & Logcat",
        "power": "Reboot (Recovery / Fastboot)",
        "connection": "Re-authorize ADB & Fix Drivers",
        "cleaner": "Adware Remover",
        "monitor": "Monitor Running Apps",
        "dns": "Block Ads via DNS",
        "virustotal": "VirusTotal Scanner",
        "restore": "Restore Uninstalled Apps",
    }
    TAB_PERMS = {
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
        self.task_manager = TaskManager(self.after)
        self.database_service = DatabaseService(get_live_database_path())
        self._theme_mode = self._load_settings().get("theme", "dark")

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
        self.grid_columnconfigure(1, weight=1)  # tab content fills the remaining width
        self.grid_rowconfigure(0, weight=1)     # main content
        self.grid_rowconfigure(1, weight=0)     # hint banner

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

        separator = ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#2c3340")
        separator.grid(row=5, column=0, padx=12, pady=(2, 3), sticky="ew")

        self.theme_btn = ctk.CTkButton(
            self.sidebar_frame, text="\u2600\ufe0f  Light Mode" if self._theme_mode == "dark" else "\U0001f319  Dark Mode",
            anchor="w", fg_color=THEME["panel2"], hover_color="#1f6feb", text_color="#e8ecf2",
            border_color="#2c3340", border_width=1, corner_radius=8,
            height=26, font=ctk.CTkFont(size=10, weight="bold"),
            command=self._toggle_theme)
        self.theme_btn.grid(row=6, column=0, padx=10, pady=(4, 0), sticky="ew")

        # Sidebar menu: grouped icon buttons
        row = 7

        def _add_btn(icon, text, command, color="#4d6bfe", perm=None):
            nonlocal row
            btn = ctk.CTkButton(
                self.sidebar_frame, text=f"{icon}  {text}", anchor="w",
                fg_color=THEME["panel2"], hover_color=color, text_color="#e8ecf2",
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

        self.page_nav_btns = {}
        self._navigation = NavigationController(self)

        def _add_nav_btn(name, icon, text, perm):
            nonlocal row
            btn = ctk.CTkButton(
                self.sidebar_frame, text=f"{icon}  {text}", anchor="w",
                fg_color=THEME["panel2"], hover_color="#1f6feb", text_color="#e8ecf2",
                border_color="#2c3340", border_width=1, corner_radius=8,
                height=28, font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda n=name: self._show_page(n))
            btn.grid(row=row, column=0, padx=10, pady=0, sticky="ew")
            row += 1
            self.page_nav_btns[name] = btn
            if perm:
                self._perm_sidebar_btns.setdefault(perm, []).append(btn)
            return btn

        _add_header("PAGES")
        _add_nav_btn("Dashboard", "\U0001f4ca", "Dashboard", None)
        _add_nav_btn("Monitor Running Apps", "\U0001f50d", "Monitor Apps", "monitor")
        _add_nav_btn("Block Ads via DNS", "\U0001f30f", "Block Ads DNS", "dns")
        _add_nav_btn("VirusTotal", "\U0001f9a0", "VirusTotal", "virustotal")

        sep2 = ctk.CTkFrame(self.sidebar_frame, height=1, fg_color="#2c3340")
        sep2.grid(row=row, column=0, padx=12, pady=(4, 3), sticky="ew")
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

        # ----------------------------------------------------
        # MIDDLE: PAGE STACK (3uTools-style sidebar navigation)
        # ----------------------------------------------------
        self.page_container = ctk.CTkFrame(self, fg_color=THEME["bg"], corner_radius=0)
        self.page_container.grid(row=0, column=1, padx=(6, 6), pady=8, sticky="nsew")
        self.page_container.grid_columnconfigure(0, weight=1)
        self.page_container.grid_rowconfigure(0, weight=1)
        self.pages = {}
        self._current_page = None

        # Pages are created lazily after authentication. Dashboard is the first
        # page created after login; other pages are built on first navigation.
        self._page_factories = {
            "Dashboard": self.build_dashboard_page,
            "Monitor Running Apps": self.build_monitor_tab,
            "Block Ads via DNS": self.build_dns_tab,
            "VirusTotal": self.build_virustotal_tab,
        }

        # ----------------------------------------------------
        # HINT BANNER + STATUS BAR
        # ----------------------------------------------------
        self._build_hint_banner()
        self._build_status_bar()

        self.log_message("System Initialized. Welcome to GeloTech Tool.")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._apply_theme(self._theme_mode)
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
    def _build_log_panel(self, parent, fixed_height=None, place_rect=None,
                         log_font_size=10, minimal=False):
        # Live log console rendered INSIDE the Android phone screen on the
        # Dashboard, and (compacted) on top of the App Cleaner page.
        # place_rect=(x, y, w, h): instead of grid(), position the console
        # with place() at the given rect (used for the phone-image screen
        # cutout on the Dashboard). log_font_size scales the log text to
        # the console's on-screen width. minimal=True renders ONLY the log
        # stream (no header/chips/stats bar) to look like a phone UI.
        console = ctk.CTkFrame(parent, fg_color="#01030a", corner_radius=6,
                               border_width=0 if (place_rect or minimal) else 1, border_color="#131a22",
                               width=(place_rect[2] if place_rect else 0),
                               height=(place_rect[3] if place_rect else 0))
        if place_rect:
            console.place(x=place_rect[0], y=place_rect[1])
            console.grid_propagate(False)
        else:
            console.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        TAG_COLORS = {
            "ADB": "#00ff41", "SECURITY": "#7cff00", "VT": "#29ffbf",
            "DNS": "#00d8ff", "EXEC": "#b8ff66", "SYSTEM": "#33ff99",
            "ERROR": "#ff3355", "INFO": "#00cc55", "HINT": "#338844",
            "DEFAULT": "#00ff41",
        }

        def _style_textbox(tb):
            for name, color in TAG_COLORS.items():
                tb.tag_config(name, foreground=color)

        if minimal:
            console.grid_columnconfigure(0, weight=1)
            console.grid_rowconfigure(0, weight=1)
            main_log = ctk.CTkTextbox(console, font=ctk.CTkFont(family="Consolas", size=log_font_size),
                                      fg_color="#000200", text_color="#00ff41",
                                      border_width=0, wrap="word", corner_radius=0)
            main_log.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
            _style_textbox(main_log)
            entry = {
                "frame": console, "text": main_log,
                "count_label": None, "filter_label": None,
                "filter": "ALL",
            }
            if not hasattr(self, "_log_consoles"):
                self._log_consoles = []
                self._log_console = console
                self.main_log = main_log
                self.log_line_count_label = None
                self.log_filter_label = None
                self._log_filter_active = "ALL"
                self._log_clear_btn = None
            self._log_consoles.append(entry)
            return

        console.grid_columnconfigure(0, weight=1)
        console.grid_rowconfigure(1, weight=1)
        if fixed_height:
            console.configure(height=fixed_height)
            console.grid_propagate(False)

        # Header bar: title + clear
        hdr = ctk.CTkFrame(console, fg_color="#03160d", corner_radius=6, height=24)
        hdr.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="\u25a0 LIVE LOGS", font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#00ff66").grid(row=0, column=0, padx=(8, 4), pady=2, sticky="w")
        clear_btn = ctk.CTkButton(hdr, text="\u2715", width=22, height=20,
                      fg_color="#3a2a2a", hover_color="#5a3a3a",
                      font=ctk.CTkFont(size=9, weight="bold"),
                      command=self.clear_logs)
        clear_btn.grid(row=0, column=1, padx=(0, 4), pady=2)

        # Log display (color-coded by process)
        main_log = ctk.CTkTextbox(console, font=ctk.CTkFont(family="Consolas", size=log_font_size),
                                  fg_color="#000200", text_color="#00ff41",
                                  border_color="#0a5a24", border_width=1,
                                  wrap="word")
        main_log.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
        main_log.tag_config("ADB", foreground="#00ff41")       # adb / device commands
        main_log.tag_config("SECURITY", foreground="#7cff00")  # Adware Remover / cleaner
        main_log.tag_config("VT", foreground="#29ffbf")        # VirusTotal
        main_log.tag_config("DNS", foreground="#00d8ff")       # DNS / ad blocking
        main_log.tag_config("EXEC", foreground="#b8ff66")      # system command execution
        main_log.tag_config("SYSTEM", foreground="#33ff99")    # system / login events
        main_log.tag_config("ERROR", foreground="#ff3355")     # errors
        main_log.tag_config("INFO", foreground="#00cc55")
        main_log.tag_config("HINT", foreground="#338844")
        main_log.tag_config("DEFAULT", foreground="#00ff41")

        # Filter chips row
        # Stats bar at bottom (phone home indicator strip)
        entry = {
            "frame": console, "text": main_log,
            "count_label": None, "filter_label": None,
            "filter": "ALL",
        }
        if not hasattr(self, "_log_consoles"):
            self._log_consoles = []
            # Backward-compat: the first console (Dashboard phone) keeps the
            # original attribute names used by the rest of the app.
            self._log_console = console
            self.main_log = main_log
            self.log_line_count_label = None
            self.log_filter_label = None
            self._log_filter_active = "ALL"
            self._log_clear_btn = clear_btn
        self._log_consoles.append(entry)

    def _set_log_filter(self, f, entry=None):
        if entry is None:
            consoles = getattr(self, "_log_consoles", None)
            entry = consoles[0] if consoles else None
            if entry is None:
                return
        entry["filter"] = f
        if entry.get("filter_label") is not None:
            entry["filter_label"].configure(text=f"Filter: {f}")
        # Re-display all log entries with new filter
        if hasattr(self, '_log_history') and self._log_history:
            entry["text"].delete("1.0", "end")
            for tag, msg in self._log_history:
                if f == "ALL" or f == tag or (f == "ADB" and tag in ("ADB", "EXEC", "SYSTEM")):
                    entry["text"].insert("end", msg + "\n", tag)
            entry["text"].see("end")

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

    def page(self, name):
        """Return (creating on first use) the frame of the named page."""
        if name not in self.pages:
            frame = ctk.CTkFrame(self.page_container, fg_color=THEME["bg"])
            frame.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = frame
        return self.pages[name]

    def _show_page(self, name):
        """Single application navigation entry point."""
        return self._navigation.show(name)

    def _initialize_runtime_after_login(self):
        """Initialize device/runtime resources only after authentication."""
        if getattr(self, "_runtime_initialized", False):
            return
        self._runtime_initialized = True
        self._extract_scrcpy()
        os.environ["PATH"] = self.scrcpy_dir + os.pathsep + os.environ.get("PATH", "")
        self._migrate_settings()
        if hasattr(self, "database_service"):
            self.database_service.clear()
        self._seed_database_defaults()
        self._navigation.show_after_login()
        self.after(150, self.start_adb_device_monitor)

    def _build_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, fg_color=THEME["sidebar"], corner_radius=0, height=26)
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.status_bar.grid_columnconfigure(1, weight=1)
        self.status_bar.grid_propagate(False)
        ctk.CTkLabel(self.status_bar, text=f"GeloTech Tool v{APP_VERSION} \u2014 3uTools-style UI",
                     font=ctk.CTkFont(size=9), text_color="#5b6773").grid(row=0, column=1, padx=12, pady=3, sticky="e")

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

        self.task_manager.submit(worker)

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

    def _toggle_theme(self):
        mode = "light" if self._theme_mode != "light" else "dark"
        self._theme_mode = mode
        try:
            data = self._load_settings()
            data["theme"] = mode
            self._save_settings(data)
        except Exception:
            pass
        self._apply_theme(mode)

    def _apply_theme(self, mode):
        """Recolor the whole widget tree for light/dark (phone + log console stay dark)."""
        THEME.update(THEMES[mode])
        ctk.set_appearance_mode("Light" if mode == "light" else "Dark")
        swap = COLOR_SWAP if mode == "light" else {v: CANONICAL_DARK.get(v, k) for k, v in COLOR_SWAP.items()}
        self._theme_walk(self, swap)
        try:
            self.theme_btn.configure(
                text="\U0001f319  Dark Mode" if mode == "light" else "\u2600\ufe0f  Light Mode")
        except Exception:
            pass
        try:
            style = ttk.Style()
            if mode == "light":
                style.configure("AppList.Treeview", background="#fbfcfd", fieldbackground="#fbfcfd",
                                foreground="#1b2530")
                style.configure("AppList.Vertical.TScrollbar", background="#dde2e8", troughcolor="#fbfcfd",
                                arrowcolor="#566170", bordercolor="#fbfcfd")
                tags = {
                    "threat": ("#fdecef", "#c0392b"), "both_excl": ("#f1eafb", "#7d3fb8"),
                    "uninstall_excl": ("#fdeaea", "#d64545"), "clean_excl": ("#faf1e0", "#b7791f"),
                    "normal": ("#eaf6ef", "#1b2530"), "normal_alt": ("#e2f1e8", "#1b2530"),
                }
            else:
                style.configure("AppList.Treeview", background="#0d1117", fieldbackground="#0d1117",
                                foreground="#e6edf3")
                style.configure("AppList.Vertical.TScrollbar", background="#21262d", troughcolor="#0d1117",
                                arrowcolor="#8b949e", bordercolor="#0d1117")
                tags = {
                    "threat": ("#2a1015", "#ff6b6b"), "both_excl": ("#241a33", "#d2a8ff"),
                    "uninstall_excl": ("#2a1212", "#ff8f8f"), "clean_excl": ("#2a2010", "#ffd08a"),
                    "normal": ("#0f2017", "#e6edf3"), "normal_alt": ("#0c1b13", "#e6edf3"),
                }
            for tag, (bg, fg) in tags.items():
                try:
                    self.sec_tree.tag_configure(tag, background=bg, foreground=fg)
                except Exception:
                    pass
        except Exception:
            pass

    @staticmethod
    def _theme_walk(root, swap=COLOR_SWAP):
        stack = list(root.winfo_children())
        while stack:
            w = stack.pop()
            try:
                stack.extend(w.winfo_children())
            except Exception:
                pass
            for attr in ("fg_color", "text_color", "border_color", "hover_color",
                         "progress_color", "button_color", "button_hover_color",
                         "dropdown_fg_color", "dropdown_hover_color",
                         "dropdown_text_color", "trough_color", "arrow_color",
                         "scrollbar_button_color", "scrollbar_button_hover_color"):
                try:
                    v = w.cget(attr)
                except Exception:
                    continue
                if isinstance(v, str) and v in swap:
                    try:
                        w.configure(**{attr: swap[v]})
                    except Exception:
                        pass

    def on_close(self):
        self.adb_monitor_enabled = False
        self.appwatch_monitoring = False
        mgr = getattr(self, "_phone_mirror", None)
        if mgr is not None:
            try:
                mgr.stop()
            except Exception:
                pass
        dash_id = getattr(self, "_dash_refresh_after", None)
        if dash_id is not None:
            try:
                self.after_cancel(dash_id)
            except Exception:
                pass
        self._purge_session_database()
        try:
            self.task_manager.shutdown(wait=False)
        except Exception:
            pass
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
        self.task_manager.submit(worker)

    # ----------------------------------------------------
    # VIRUSTOTAL TAB UI
    # ----------------------------------------------------
from tech_hardening import apply_hardening
apply_hardening(GeloTechTool)

if __name__ == "__main__":
    app = GeloTechTool()
    app.mainloop()
