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
from tech_common import (get_bundle_dir, get_app_dir, load_banking_apps,
                         load_apps_cache, save_apps_cache, fmt_cache_time,
                         Tooltip, subprocess)
from tech_phone_mirror import PhoneMirrorManager, PHONE_SCALE


class MiscMixin:
    def toggle_appwatch(self):
        if self.appwatch_switch.get() == 1:
            self.appwatch_monitoring = True
            self.appwatch_status_label.configure(text="Monitoring: ON", text_color="#2ecc71")
            self.log_message("[ADB] App Watch monitoring started. Use your phone normally...")
            threading.Thread(target=self._appwatch_loop, daemon=True).start()
        else:
            self.appwatch_monitoring = False
            self.appwatch_status_label.configure(text="Monitoring: OFF", text_color="#e74c3c")
            self.log_message("[ADB] App Watch monitoring stopped.")

    def _appwatch_loop(self):
        last_pkg = None
        last_ts = None
        while self.appwatch_monitoring:
            try:
                pkg = self._get_top_app()
                if pkg:
                    self.after(0, lambda p=pkg: self.appwatch_now_label.configure(text=f"Foreground: {p}"))
                if pkg and pkg != last_pkg:
                    now = datetime.datetime.now()
                    if last_pkg is not None and last_ts is not None and self.appwatch_history:
                        duration = int((now - last_ts).total_seconds())
                        prev = self.appwatch_history[0]
                        prev["duration"] = duration
                        prev["suspect"] = duration < 6
                        if prev["suspect"]:
                            self.log_message(f"[ADB] SUSPECT popup app: {prev['pkg']} was in foreground for only {duration}s")
                    last_pkg, last_ts = pkg, now
                    self.appwatch_history.insert(0, {
                        "time": now.strftime("%H:%M:%S"),
                        "pkg": pkg,
                        "label": self._resolve_label(pkg),
                        "duration": None,
                        "suspect": False,
                    })
                    if len(self.appwatch_history) > 200:
                        self.appwatch_history = self.appwatch_history[:200]
                    self.log_message(f"[ADB] Foreground app changed: {pkg}")
                    self.after(0, self._refresh_appwatch_ui)
            except Exception:
                pass
            time.sleep(1.5)

    def _get_top_app(self):
        try:
            res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "activity", "top"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=6)
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("ACTIVITY"):
                    parts = line.split()
                    if len(parts) >= 2 and "/" in parts[1]:
                        pkg = parts[1].split("/")[0]
                        if "." in pkg:
                            return pkg
        except Exception:
            pass
        try:
            res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "window", "windows"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=6)
            m = re.search(r"mCurrentFocus=Window\{[^}]*u0 ([^/]+)/", res.stdout)
            if m and "." in m.group(1):
                return m.group(1)
        except Exception:
            pass
        return None

    def _refresh_appwatch_ui(self):
        self.appwatch_count_label.configure(text=f"Events: {len(self.appwatch_history)}")
        for child in self.appwatch_frame.winfo_children():
            child.destroy()
        for i, ev in enumerate(self.appwatch_history):
            row = ctk.CTkFrame(self.appwatch_frame, fg_color="#1b232d" if i % 2 else "#222c37", corner_radius=4)
            row.grid(row=i, column=0, sticky="ew", pady=1)
            row.grid_columnconfigure(1, weight=1)
            name = ev.get("label") or ev["pkg"]
            ctk.CTkLabel(row, text=ev["time"], font=ctk.CTkFont(size=10), text_color="#8da1b8", width=56).grid(row=0, column=0, padx=(8, 2), pady=8)
            name_frame = ctk.CTkFrame(row, fg_color="transparent")
            name_frame.grid(row=0, column=1, padx=6, pady=8, sticky="w")
            ctk.CTkLabel(name_frame, text=name, font=ctk.CTkFont(size=11, weight="bold"), text_color="#e8ecf2", anchor="w").pack(anchor="w")
            ctk.CTkLabel(name_frame, text=ev["pkg"], font=ctk.CTkFont(size=9), text_color="#7a8699", anchor="w").pack(anchor="w")
            if i == 0:
                badge = "\u26a0 LATEST" if not ev.get("suspect") else "\u26a0 POPUP SUSPECT!"
                badge_color = "#2ecc71" if not ev.get("suspect") else "#e74c3c"
                ctk.CTkLabel(row, text=badge, width=110, height=22, fg_color=badge_color, corner_radius=8,
                    font=ctk.CTkFont(size=9, weight="bold")).grid(row=0, column=2, padx=6, pady=8)
            bframe = ctk.CTkFrame(row, fg_color="transparent")
            bframe.grid(row=0, column=3, padx=6, pady=6)
            ctk.CTkButton(bframe, text="\u23f9 Stop", width=58, height=24, fg_color="#c0392b", hover_color="#a82521",
                font=ctk.CTkFont(size=9, weight="bold"),
                command=lambda p=ev["pkg"]: self._appwatch_action(p, "stop")).pack(side="left", padx=1)
            ctk.CTkButton(bframe, text="\u23f8 Disable", width=68, height=24, fg_color="#d35400", hover_color="#a8420f",
                font=ctk.CTkFont(size=9, weight="bold"),
                command=lambda p=ev["pkg"]: self._appwatch_action(p, "disable")).pack(side="left", padx=1)
            ctk.CTkButton(bframe, text="\u2715 Uninstall", width=80, height=24, fg_color="#8e44ad", hover_color="#71368a",
                font=ctk.CTkFont(size=9, weight="bold"),
                command=lambda p=ev["pkg"]: self._appwatch_action(p, "uninstall")).pack(side="left", padx=1)

    def _appwatch_action(self, pkg, operation):
        if not self._can("monitor"):
            self.log_message("[ADB] Permission denied: Monitor Running Apps is disabled for this account.")
            return
        if operation == "stop":
            def task():
                try:
                    subprocess.run([self.scrcpy_adb, "shell", "am", "force-stop", pkg],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                    self.log_message(f"[ADB] Force-stopped {pkg}")
                except Exception as e:
                    self.log_message(f"[ADB ERROR] {e}")
            threading.Thread(target=task, daemon=True).start()
        else:
            self._confirm_and_run_debloat_operation([pkg], operation)

    def action_appwatch_clear(self):
        self.appwatch_history.clear()
        self.appwatch_count_label.configure(text="Events: 0")
        for child in self.appwatch_frame.winfo_children():
            child.destroy()
        self.log_message("[ADB] App Watch history cleared.")

    # ----------------------------------------------------
    # DNS OPERATIONS
    # ----------------------------------------------------
    def action_dns_refresh(self):
        """Check current Private DNS setting."""
        try:
            mode = subprocess.run([self.scrcpy_adb, "shell", "settings", "get", "global", "private_dns_mode"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5).stdout.strip()
            spec = subprocess.run([self.scrcpy_adb, "shell", "settings", "get", "global", "private_dns_specifier"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5).stdout.strip()
            if mode == "hostname" and spec:
                self.dns_status_label.configure(text=f"Active: {spec}", text_color="#2ecc71")
            elif mode == "opportunistic":
                self.dns_status_label.configure(text="Mode: Opportunistic (system default)", text_color="#f39c12")
            else:
                self.dns_status_label.configure(text="Private DNS: Disabled", text_color="#e74c3c")
        except:
            self.dns_status_label.configure(text="Unable to read DNS setting", text_color="#e74c3c")

    def action_dns_apply(self):
        """Set Private DNS to the hostname in the entry field."""
        if not self._can("dns"):
            self.log_message("[DNS] Permission denied: Block Ads via DNS is disabled for this account.")
            return
        label = self.dns_dropdown.get()
        hostname = self.dns_options.get(label, label.strip())
        if not hostname or hostname == label.strip():
            self.log_message("[DNS] Invalid DNS selection.")
            return
        def task():
            self.log_message(f"[DNS] Setting Private DNS to {hostname}...")
            subprocess.run([self.scrcpy_adb, "shell", "settings", "put", "global", "private_dns_mode", "hostname"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            subprocess.run([self.scrcpy_adb, "shell", "settings", "put", "global", "private_dns_specifier", hostname], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            self.log_message(f"[DNS] Private DNS set to {hostname}")
            self.after(0, self.action_dns_refresh)
        threading.Thread(target=task, daemon=True).start()

    def action_dns_disable(self):
        """Disable Private DNS."""
        if not self._can("dns"):
            self.log_message("[DNS] Permission denied: Block Ads via DNS is disabled for this account.")
            return
        def task():
            self.log_message("[DNS] Disabling Private DNS...")
            subprocess.run([self.scrcpy_adb, "shell", "settings", "put", "global", "private_dns_mode", "off"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            subprocess.run([self.scrcpy_adb, "shell", "settings", "delete", "global", "private_dns_specifier"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            self.log_message("[DNS] Private DNS disabled")
            self.after(0, self.action_dns_refresh)
        threading.Thread(target=task, daemon=True).start()

    # ----------------------------------------------------
    # SECURITY SCAN OPERATIONS
    # ----------------------------------------------------
    def action_list_all_packages(self):
        self._sec_load_package_list("all")

    def action_list_user_packages(self):
        self._sec_load_package_list("user")

    def action_list_system_packages(self):
        self._sec_load_package_list("system")

    def action_list_disabled_packages(self):
        self._sec_load_package_list("disabled")

    def _sec_load_package_list(self, mode):
        if not self._can("device_info"):
            self.after(0, lambda: self._sec_status("Permission denied: package lists disabled for this account.", "#e74c3c"))
            self.after(0, lambda: self._sec_log("[GeloTech] Permission denied: package lists disabled for this account.", "#e74c3c"))
            return
        if mode == "all":
            args = ["shell", "pm", "list", "packages"]
            label = "ALL"
        elif mode == "user":
            args = ["shell", "pm", "list", "packages", "-3"]
            label = "USER APPS"
        elif mode == "system":
            args = ["shell", "pm", "list", "packages", "-s"]
            label = "SYSTEM APPS"
        else:
            args = ["shell", "pm", "list", "packages", "-d"]
            label = "DISABLED"
        self.sec_list_mode = mode
        self._sec_status(f"Loading {label} packages...", "#58a6ff")
        self._sec_log(f"[GeloTech] Loading {label} package list...", "#8b949e")

        cached = load_apps_cache()
        if cached and cached.get("mode") == mode:
            entries = cached["entries"]
            self.sec_packages = entries
            self.sec_legend_filter = None
            self.sec_removal_filter = None
            self.after(0, self._sec_render_rows)
            self.after(0, lambda: self.sec_threats_label.configure(text=f"{label}: {len(entries)} apps (cached)", text_color="#58a6ff"))
            self.after(0, lambda: self._sec_status(f"\U0001f4be Showing cached {label} list from {fmt_cache_time(cached.get('timestamp', 0))}. Refreshing from device...", "#58a6ff"))
            self.after(0, lambda: self._sec_log(f"[GeloTech] {label}: rendered from local Windows cache; refreshing from device in background.", "#8b949e"))

        def worker():
            try:
                res = subprocess.run([self.scrcpy_adb] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
                pkgs = [line[len("package:"):].strip() for line in res.stdout.splitlines() if line.startswith("package:")]
                if not pkgs:
                    self.after(0, lambda: self._sec_status("No packages found or device not connected.", "#e74c3c"))
                    self.after(0, lambda: self._sec_log(f"[GeloTech] {label}: no packages found or device not connected.", "#e74c3c"))
                    return
                labels = self._load_app_labels()
                uad = self._build_uad_lookup()
                excl_clean = self._load_excluded_clean()
                excl_uninstall = self._load_excluded_uninstall()
                banking = load_banking_apps()
                entries = []
                for p in sorted(pkgs):
                    rec = uad.get(p, {})
                    entries.append({
                        "id": p,
                        "label": labels.get(p, self._resolve_label(p)),
                        "system": False,
                        "excluded_clean": p in excl_clean,
                        "excluded_uninstall": p in excl_uninstall,
                        "banking": p in banking,
                        "threat_level": 0,
                        "threat_labels": [],
                        "removal": rec.get("removal", ""),
                        "description": rec.get("description", ""),
                        "risk": rec.get("risk", "unknown"),
                        "category": rec.get("category", "Other"),
                        "manufacturer": rec.get("manufacturer", "Unknown"),
                        "source": rec.get("source", "Unknown"),
                    })
                self.sec_list_mode = mode
                self.sec_packages = entries
                self.sec_legend_filter = None
                self.sec_removal_filter = None
                save_apps_cache(mode, entries)
                self.after(0, self._sec_render_rows)
                self.after(0, lambda: self.sec_threats_label.configure(text=f"{label}: {len(entries)} apps", text_color="#58a6ff"))
                self.after(0, lambda: self._sec_status(f"{label} packages: {len(entries)} loaded. Use the action buttons below on the apps you check.", "#58a6ff"))
                self.after(0, lambda: self._sec_log(f"[GeloTech] {label}: {len(entries)} package(s) loaded into the list.", "#58a6ff"))
            except Exception as e:
                self.after(0, lambda e=e: self._sec_status(f"\u274c Error loading packages: {e}", "#e74c3c"))
                self.after(0, lambda e=e: self._sec_log(f"[GeloTech ERROR] {e}", "#e74c3c"))
        threading.Thread(target=worker, daemon=True).start()

    def _sec_apply_filter(self, criteria, source_entries):
        selection = {
            "removal": criteria.get("removal", "Any"),
            "risk": criteria.get("risk", "Any"),
            "category": criteria.get("category", "Any"),
            "manufacturer": criteria.get("manufacturer", "Any"),
            "source": criteria.get("source", "Any"),
        }
        respect_exclude = criteria.get("respect_exclude", True)
        banking = load_banking_apps()
        out = []
        for e in source_entries:
            if selection["removal"] != "Any" and e.get("removal") != selection["removal"]:
                continue
            if selection["risk"] != "Any" and (e.get("risk") or "unknown") != selection["risk"]:
                continue
            if selection["category"] != "Any" and e.get("category") != selection["category"]:
                continue
            if selection["manufacturer"] != "Any" and e.get("manufacturer") != selection["manufacturer"]:
                continue
            if selection["source"] != "Any" and e.get("source") != selection["source"]:
                continue
            if respect_exclude and (e.get("exclude_uninstall") or e.get("excluded_uninstall") or e["id"] in banking):
                continue
            out.append(e)
        return out

    def _sec_load_db_filter(self, criteria):
        if not self._can("device_info"):
            self.after(0, lambda: self._sec_status("Permission denied: package lists disabled for this account.", "#e74c3c"))
            self.after(0, lambda: self._sec_log("[GeloTech] Permission denied: package lists disabled for this account.", "#e74c3c"))
            return
        self._filter_criteria = dict(criteria)
        self.sec_list_mode = "filter"
        self._sec_status("Loading matching apps from the database...", "#58a6ff")
        self._sec_log("[GeloTech] Loading database filter...", "#8b949e")

        def finish(matches, cached_ts=None):
            self.sec_list_mode = "filter"
            self.sec_packages = matches
            self.sec_legend_filter = None
            self.sec_removal_filter = None
            self.after(0, self._sec_render_rows)
            if matches:
                note = " (cached)" if cached_ts else ""
                self.after(0, lambda: self.sec_threats_label.configure(text=f"Filter: {len(matches)} apps", text_color="#58a6ff"))
                self.after(0, lambda: self._sec_status(f"Filter: {len(matches)} app(s) match{note}. Use the action buttons below on the apps you check.", "#58a6ff"))
                self.after(0, lambda: self._sec_log(f"[GeloTech] FILTER: {len(matches)} package(s) loaded into the list.", "#8b949e"))
            else:
                self.after(0, lambda: self._sec_status("No apps match these database criteria.", "#f39c12"))
                self.after(0, lambda: self._sec_log("[GeloTech] FILTER: no apps match these criteria.", "#f39c12"))

        def worker():
            try:
                res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
                installed = [line[len("package:"):].strip() for line in res.stdout.splitlines() if line.startswith("package:")]
                if not installed:
                    cached = load_apps_cache()
                    if cached and cached.get("mode") == "all":
                        matches = self._sec_apply_filter(criteria, cached["entries"])
                        finish(matches, cached.get("timestamp", 0))
                        self.after(0, lambda: self._sec_status(f"\U0001f4be Device not connected — filtered the local cache from {fmt_cache_time(cached.get('timestamp', 0))}.", "#f39c12"))
                        self.after(0, lambda: self._sec_log("[GeloTech] FILTER: device not connected; applied filter to local cache.", "#f39c12"))
                        return
                    self.after(0, lambda: self._sec_status("No packages found or device not connected.", "#e74c3c"))
                    self.after(0, lambda: self._sec_log("[GeloTech] FILTER: no packages found or device not connected.", "#e74c3c"))
                    return
                uad = self._build_uad_lookup()
                labels = self._load_app_labels()
                excl_clean = self._load_excluded_clean()
                excl_uninstall = self._load_excluded_uninstall()
                banking = load_banking_apps()
                fresh = []
                for p in sorted(installed):
                    record = uad.get(p)
                    if not record:
                        continue
                    fresh.append({
                        "id": p,
                        "label": labels.get(p, self._resolve_label(p)),
                        "system": False,
                        "excluded_clean": p in excl_clean,
                        "excluded_uninstall": p in excl_uninstall,
                        "banking": p in banking,
                        "threat_level": 0,
                        "threat_labels": [],
                        "removal": record.get("removal", ""),
                        "description": record.get("description", ""),
                        "risk": record.get("risk", "unknown"),
                        "category": record.get("category", "Other"),
                        "manufacturer": record.get("manufacturer", "Unknown"),
                        "source": record.get("source", "Unknown"),
                    })
                matches = self._sec_apply_filter(criteria, fresh)
                finish(matches)
            except Exception as e:
                cached = load_apps_cache()
                if cached and cached.get("mode") == "all":
                    matches = self._sec_apply_filter(criteria, cached["entries"])
                    finish(matches, cached.get("timestamp", 0))
                    self.after(0, lambda e=e: self._sec_status(f"\u274c Error: {e} — filtered the local cache from {fmt_cache_time(cached.get('timestamp', 0))} instead.", "#f39c12"))
                    self.after(0, lambda e=e: self._sec_log(f"[GeloTech ERROR] {e}; applied filter to local cache.", "#f39c12"))
                    return
                self.after(0, lambda e=e: self._sec_status(f"\u274c Error loading filter: {e}", "#e74c3c"))
                self.after(0, lambda e=e: self._sec_log(f"[GeloTech ERROR] {e}", "#e74c3c"))
        threading.Thread(target=worker, daemon=True).start()

    def _sec_refresh_current_list(self):
        mode = getattr(self, "sec_list_mode", "user")
        if mode == "user":
            self.action_sec_refresh()
        elif mode == "all":
            self.action_list_all_packages()
        elif mode == "system":
            self.action_list_system_packages()
        elif mode == "disabled":
            self.action_list_disabled_packages()
        elif mode == "filter":
            self._sec_load_db_filter(getattr(self, "_filter_criteria", {}))
        else:
            self.action_sec_refresh()

    def action_scrcpy_mirror(self):
        mgr = getattr(self, "_phone_mirror", None)
        if mgr is not None and mgr.state != "off":
            self.log_message("[SCRCPY] Stopping screen mirror")
            mgr.stop()
            return
        if not os.path.exists(self.scrcpy_exe):
            self.log_message(f"[ADB ERROR] scrcpy not found at {self.scrcpy_exe}")
            return
        def worker():
            self.log_message("[ADB] Restarting ADB server for screen mirror...")
            try:
                subprocess.run([self.scrcpy_adb, "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                time.sleep(1)
                subprocess.run([self.scrcpy_adb, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                time.sleep(2)
            except Exception as e:
                self.log_message(f"[ADB ERROR] {e}")
            self._start_phone_mirror(-1, -1)
        threading.Thread(target=worker, daemon=True).start()

    def _start_phone_mirror(self, sx, sy):
        try:
            mgr = getattr(self, "_phone_mirror", None)
            if mgr is None:
                mgr = self._phone_mirror = PhoneMirrorManager(
                    os.path.join(get_bundle_dir(), "assets", "phone_devices",
                                 "iphone_frame_overlay.png"),
                    scale=PHONE_SCALE, log=self.log_message,
                    on_state=self._mirror_state)
            mgr.start(self.scrcpy_exe, self.scrcpy_adb, self.scrcpy_dir, sx, sy)
        except Exception as e:
            self.log_message(f"[PHONE ERROR] mirror start failed: {e}")

    def _mirror_state(self, state):
        if state == "active":
            self.log_message("[PHONE] Mirror ready")
        elif state == "stopped":
            self.log_message("[SCRCPY] Mirror stopped")
    
    # --- Windows Host Driver Management & Log Tracing Utilities ---
    def action_fix_drivers(self):
        self.run_system_cmd_async([self.scrcpy_adb, "kill-server"], "Clearing old host framework background loop tasks...")
        self.run_system_cmd_async([self.scrcpy_adb, "start-server"], "Re-initializing fresh connection loop parameters...")

    def action_read_auth_adb(self):
        def worker():
            self.log_message("[ADB] Restarting server to force re-authorization...")
            try:
                subprocess.run([self.scrcpy_adb, "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                time.sleep(1)
                subprocess.run([self.scrcpy_adb, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                time.sleep(2)
                subprocess.run([self.scrcpy_adb, "usb"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                self.log_message("[ADB] Server restarted. Check your phone for the USB debugging authorization prompt.")
            except Exception as e:
                self.log_message(f"[ADB ERROR] {e}")
        threading.Thread(target=worker, daemon=True).start()

    def log_message(self, message):
        if threading.current_thread() is not threading.main_thread():
            try:
                self.after(0, self.log_message, message)
            except Exception:
                pass
            return
        consoles = getattr(self, "_log_consoles", None)
        if not consoles:
            return

        # Determine tag based on prefix
        if message.startswith("[VT"):
            tag = "VT"
        elif message.startswith("[SECURITY"):
            tag = "SECURITY"
        elif message.startswith("[DNS"):
            tag = "DNS"
        elif message.startswith("[EXEC"):
            tag = "EXEC"
        elif message.startswith("[GeloTech ERROR]"):
            tag = "ERROR"
        elif message.startswith("[GeloTech"):
            tag = "SECURITY"
        elif message.startswith("[CRITICAL") or "ERROR" in message[:20]:
            tag = "ERROR"
        elif message.startswith("[ADB") or message.startswith("System") or message.startswith("Logged"):
            tag = "SYSTEM"
        elif message.startswith("[HINT"):
            tag = "HINT"
        else:
            tag = "DEFAULT"

        # Store in history for filter replay
        if not hasattr(self, '_log_history'):
            self._log_history = []
        self._log_history.append((tag, message))
        if len(self._log_history) > 1000:
            self._log_history = self._log_history[-500:]

        # Insert into every live console, honoring each console's own filter
        for c in consoles:
            tb = c.get("text")
            if tb is None or not tb.winfo_exists():
                continue
            if c.get("filter", "ALL") != "ALL":
                if c["filter"] == tag or (c["filter"] == "ADB" and tag in ("ADB", "EXEC", "SYSTEM")):
                    tb.insert("end", message + "\n", tag)
                    tb.see("end")
            else:
                tb.insert("end", message + "\n", tag)
                tb.see("end")
        self._update_log_count()

    def _update_log_count(self):
        for c in getattr(self, "_log_consoles", ()):
            try:
                lbl = c.get("count_label")
                if lbl is None:
                    continue
                count = int(c["text"].index("end-1c").split(".")[0])
                lbl.configure(text=f"Lines: {count}")
            except Exception:
                pass

    def clear_logs(self):
        for c in getattr(self, "_log_consoles", ()):
            try:
                c["text"].delete("1.0", "end")
                lbl = c.get("count_label")
                if lbl is not None:
                    lbl.configure(text="Lines: 0")
            except Exception:
                pass
        self._log_history = []

    def run_system_cmd_async(self, command_list, execution_text="Processing offline task parameters..."):
        """Ensures system operations run independently from the UI layout thread to prevent freezes."""
        def task():
            if execution_text:
                self.log_message(f"[EXEC] {execution_text}")
            try:
                res = subprocess.run(command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
                if res.stdout: self.log_message(res.stdout.strip())
                if res.stderr: self.log_message(f"[SHELL ERROR RESPONSE] {res.stderr.strip()}")
            except FileNotFoundError:
                self.log_message("[CRITICAL SYSTEM ERROR] Standard execution platform binaries (adb/fastboot) are missing from local paths.")
            except Exception as e:
                self.log_message(f"[CRITICAL ERROR] Core pipeline pipeline failure: {str(e)}")
        threading.Thread(target=task, daemon=True).start()
