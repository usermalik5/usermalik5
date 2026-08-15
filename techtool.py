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
import tech_themes
from tech_common import get_bundle_dir, get_app_dir, get_settings_dir, get_live_database_path, Tooltip, subprocess, load_package_database, APP_VERSION, THEME, THEMES, COLOR_SWAP, CANONICAL_DARK
from tech_navigation import NavigationController
from tech_bloatware import BloatwareFilterMixin
from tech_task_manager import TaskManager
from tech_database import DatabaseService

# Application Global Styling Configurations
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme(
    os.path.join(tech_themes.THEME_DIR, f"{tech_themes.DEFAULT_THEME}.json"))

# Scale UI for high-DPI / small font compensation
ctk.set_widget_scaling(1.15)

from tech_ui import UiMixin
from tech_settings import SettingsMixin
from tech_settings_login import SettingsLoginMixin
from tech_secscan import SecScanMixin
from tech_secops import SecOpsMixin
from tech_secops3 import SecOps3Mixin
from tech_secops2 import SecOps2Mixin
from tech_secops4 import SecOps4Mixin
from tech_dash import DashboardMixin
from tech_vtop import VtOpsMixin
from tech_misc import MiscMixin
from techtool_core import TechToolCore

class GeloTechTool(ctk.CTk, UiMixin, SettingsMixin, SettingsLoginMixin, SecScanMixin, SecOpsMixin, BloatwareFilterMixin, SecOps3Mixin, SecOps2Mixin, SecOps4Mixin, DashboardMixin, VtOpsMixin, MiscMixin, TechToolCore):
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
        self._theme_mode = self._load_settings().get("theme", tech_themes.DEFAULT_THEME)

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
        self._icon_sync_seen_serials = set()
        self._auto_mirror_seen = set()
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
            self.sidebar_frame, text=tech_themes.DEFAULT_THEME.capitalize(),
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
        self._admin_panel_btn = _add_btn("\U0001f511", "Accounts", self._open_admin_panel, color="#d4af37")
        _add_btn("\U0001f6aa", "Logout", self._logout, color="#7f8c8d")

        # USB debugging + How-to instructions, pinned below the Logout button.
        self._sec_banner_usb = ctk.CTkLabel(
            self.sidebar_frame,
            text=(
                "\U0001f4f1 USB debugging:\n"
                "Enable Developer Options \u2192 USB debugging, connect the phone, then tap Allow.\n"
                "GeloTech automatically prepares app icons for new devices."
            ),
            font=ctk.CTkFont(size=9), text_color="#aeb8c2", anchor="w", justify="left",
            wraplength=200)
        self._sec_banner_usb.grid(row=row, column=0, padx=12, pady=(10, 2), sticky="w")
        row += 1

        self._sec_banner_howto = ctk.CTkLabel(
            self.sidebar_frame,
            text=(
                "\U0001f4a1 How to use:\n"
                "Refresh loads user apps. Load Apps chooses All / User / System / Disabled.\n"
                "Advanced Filter uses the database. Scan Bloatware filters by UAD level.\n"
                "Right-click a row for app actions."
            ),
            font=ctk.CTkFont(size=9), text_color="#58a6ff", anchor="w", justify="left",
            wraplength=200)
        self._sec_banner_howto.grid(row=row, column=0, padx=12, pady=(2, 10), sticky="w")
        row += 1
        self.sidebar_frame.bind("<Configure>", self._sec_banner_wraplength)

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
        self._hint_banner = ctk.CTkFrame(self, fg_color="#3a0d10", corner_radius=0)
        self._hint_banner.grid(row=1, column=0, columnspan=3, sticky="ew")
        self._hint_banner.grid_columnconfigure(0, weight=1)
        self._hint_label = ctk.CTkLabel(
            self._hint_banner, text="", anchor="w", justify="left",
            font=ctk.CTkFont(size=10, weight="bold"), text_color="#ff4d4d")
        self._hint_label.grid(row=0, column=0, sticky="ew", padx=14, pady=5)
        self._hint_banner.bind("<Configure>", self._hint_banner_wraplength)
        self._hint_banner.grid_remove()
        self._hint_timer = None
        if not getattr(self, "_root_configure_bound", False):
            self._root_configure_bound = True
            self.bind("<Configure>", self._on_root_configure)

    def _hint_banner_wraplength(self, _event=None):
        try:
            banner = getattr(self, "_hint_banner", None)
            label = getattr(self, "_hint_label", None)
            if banner is None or label is None:
                return
            width = banner.winfo_width()
            if width < 10:
                return
            label.configure(wraplength=max(80, width - 28))
        except Exception:
            pass

    def _on_root_configure(self, _event=None):
        """Debounced: react to window resize / maximize / monitor change by
        re-anchoring the phone-screen console and re-laying out the package
        list, instead of relying on one-time geometry."""
        if getattr(self, "_root_configure_pending", False):
            return
        self._root_configure_pending = True
        try:
            self.after(180, self._on_root_configure_done)
        except Exception:
            self._root_configure_pending = False

    def _on_root_configure_done(self):
        self._root_configure_pending = False
        try:
            clip = getattr(self, "_dash_clip", None)
            if clip is not None:
                self._clip_dash_console(*clip)
        except Exception:
            pass
        try:
            if hasattr(self, "_sec_relayout_columns"):
                self._sec_relayout_columns()
        except Exception:
            pass

    def show_hint(self, text):
        try:
            if not hasattr(self, "_hint_label"):
                return
            self._hint_label.configure(text="\u26a0  " + text)
            self._hint_banner.grid()
            self.after(0, self._hint_banner_wraplength)
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
            if devices:
                self._auto_prepare_new_device_icons(devices)
                self._auto_launch_mirror(devices)
            else:
                self._icon_sync_seen_serials.clear()
                self._auto_mirror_seen.clear()

    def _auto_launch_mirror(self, devices):
        """Auto-launch the phone mirror 5s after a device connects, so the
        screen stays visible while using the app. Never auto-stops; the user
        can stop it via the sidebar button."""
        try:
            if len(devices) != 1:
                return
            mgr = getattr(self, "_phone_mirror", None)
            if mgr is not None and mgr.state != "off":
                return
            if not os.path.exists(self.scrcpy_exe):
                return
            serial = devices[0]
            if serial in self._auto_mirror_seen:
                return
            self._auto_mirror_seen.add(serial)
            self.log_message("[SCRCPY] Device connected - opening screen mirror in 5 seconds")
            self.after(5000, self._delayed_auto_mirror)
        except Exception as exc:
            self.log_message(f"[PHONE ERROR] Auto mirror skipped: {exc}")

    def _delayed_auto_mirror(self):
        """Fire the delayed auto-mirror start, skipping if already running."""
        try:
            mgr = getattr(self, "_phone_mirror", None)
            if mgr is not None and mgr.state != "off":
                return
            self._start_phone_mirror(-1, -1)
        except Exception as exc:
            self.log_message(f"[PHONE ERROR] Auto mirror failed: {exc}")

    def _auto_prepare_new_device_icons(self, devices):
        """Automatically prepare icons when a new single authorized device is detected."""
        try:
            if len(devices) != 1:
                if len(devices) > 1:
                    self.log_message("[GeloTech] Multiple ADB devices connected; automatic icon sync waits until one device remains.")
                return
            serial = devices[0]
            if serial in self._icon_sync_seen_serials:
                return
            self._icon_sync_seen_serials.add(serial)
            self._sec_icon_cache = {}
            self._sec_tree_icon_cache = {}
            self._app_labels = None
            self.log_message(f"[GeloTech] New device detected: {serial}. Preparing app icons automatically...")
            self.after(200, self.action_sec_show_icons)
        except Exception as exc:
            self.log_message(f"[GeloTech] Automatic icon preparation skipped: {exc}")

    def _toggle_theme(self):
        # Cycle through the bundled CTkThemesPack palettes (orange first).
        try:
            idx = tech_themes.PALETTES.index(self._theme_mode)
        except ValueError:
            idx = 0
        mode = tech_themes.PALETTES[(idx + 1) % len(tech_themes.PALETTES)]
        self._theme_mode = mode
        try:
            data = self._load_settings()
            data["theme"] = mode
            self._save_settings(data)
        except Exception:
            pass
        self._apply_theme(mode)

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
        # Discard the in-memory auth session token (never persisted anyway).
        self._auth_session = None
        self.is_admin = False
        self.user_perms = None
        self.user_tabs = None
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
