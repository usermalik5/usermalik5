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
from tech_common import (get_bundle_dir, get_app_dir, get_cache_dir, has_icon_cache,
                         load_apps_cache, save_apps_cache, fmt_cache_time,
                         Tooltip, subprocess)


class SecScanMixin:
    def action_sec_refresh(self):
        self._sec_animate_start()
        self._sec_load_device_info()
        threading.Thread(target=self._sec_run_load, daemon=True).start()

    def _sec_animate_start(self):
        self._sec_anim_running = True
        self._sec_animate_tick(0)

    def _sec_animate_tick(self, i):
        if not getattr(self, "_sec_anim_running", False):
            self.sec_scan_anim.configure(text="")
            return
        if not self.sec_scan_anim.winfo_exists():
            return
        chars = "\u2588\u2593\u2592\u2591"
        self.sec_scan_anim.configure(text=f"[{chars[i % 4] * 8}]")
        self.after(150, lambda: self._sec_animate_tick(i + 1))

    def _sec_animate_stop(self):
        self._sec_anim_running = False
        self.sec_scan_anim.configure(text="")

    def _sec_log(self, message, color="#8b949e"):
        self.log_message(message)

    def _sec_status(self, text, color="#8b949e"):
        def do():
            try:
                self.sec_status_label.configure(text=text, text_color=color)
            except Exception:
                pass
        if threading.current_thread() is not threading.main_thread():
            self.after(0, do)
        else:
            do()

    def _sec_get_packages(self, force=False):
        now = time.time()
        if not force and hasattr(self, '_pkg_cache') and now - self._pkg_cache["ts"] < 10:
            return self._pkg_cache["data"]
        res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        pkgs = [line[len("package:"):].strip() for line in res.stdout.splitlines() if line.startswith("package:")]
        self._pkg_cache = {"data": pkgs, "ts": now}
        return pkgs

    def _sec_check_scan_cache(self, scan_type):
        if not hasattr(self, '_scan_cache'):
            self._scan_cache = {}
        now = time.time()
        if scan_type in self._scan_cache and now - self._scan_cache[scan_type]["ts"] < 30:
            return self._scan_cache[scan_type]["data"]
        return None

    def _sec_store_scan_cache(self, scan_type, results):
        if not hasattr(self, '_scan_cache'):
            self._scan_cache = {}
        self._scan_cache[scan_type] = {"data": results, "ts": time.time()}

    def _sec_run_load(self):
        try:
            self._sec_status("Loading user apps...", "#58a6ff")
            res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages", "-3"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            pkgs = sorted(line[len("package:"):].strip() for line in res.stdout.splitlines() if line.startswith("package:"))
            if not pkgs:
                cached = load_apps_cache()
                if cached and cached.get("mode") == "user":
                    self.sec_packages = cached["entries"]
                    self.sec_list_mode = "user"
                    self.after(0, self._sec_render_rows)
                    self.after(0, lambda: self.sec_threats_label.configure(text="\U0001f9a0 Possible Threats: 0 (cached)", text_color="#f39c12"))
                    self.after(0, self._sec_animate_stop)
                    self._sec_status(f"\U0001f4be Device NOT detected — showing cached user apps from {fmt_cache_time(cached.get('timestamp', 0))}.", "#f39c12")
                    self._sec_log("[GeloTech] Device not connected; loaded cached user apps.", "#f39c12")
                    return
                self.after(0, self._sec_animate_stop)
                self._sec_status("\u26a0 Device NOT detected. Connect your phone via USB...", "#e74c3c")
                self._sec_log("[GeloTech] No 3rd-party packages found or device not connected.", "#e74c3c")
                self.sec_threats_label.configure(text="\U0001f9a0 Possible Threats: 0")
                return

            self._sec_log(f"[GeloTech] {len(pkgs)} user apps found.", "#58a6ff")
            self.sec_removal_filter = None
            self.sec_legend_filter = None
            labels = self._load_app_labels()
            uad = self._build_uad_lookup()
            excl_clean = self._load_excluded_clean()
            excl_uninstall = self._load_excluded_uninstall()
            self.sec_packages = []
            self.sec_list_mode = "user"
            for p in pkgs:
                rec = uad.get(p, {})
                self.sec_packages.append({
                    "id": p,
                    "label": labels.get(p, self._resolve_label(p)),
                    "system": False,
                    "excluded_clean": p in excl_clean,
                    "excluded_uninstall": p in excl_uninstall,
                    "threat_level": 0,
                    "threat_labels": [],
                    "removal": rec.get("removal", ""),
                    "description": rec.get("description", ""),
                    "risk": rec.get("risk", "unknown"),
                    "category": rec.get("category", "Other"),
                    "manufacturer": rec.get("manufacturer", "Unknown"),
                    "source": rec.get("source", "Unknown"),
                })
            save_apps_cache("user", self.sec_packages)
            self.after(0, self._sec_render_rows)
            self.after(0, lambda: self.sec_progress_bar.set(0.4))
            if not has_icon_cache():
                self.after(200, self.action_sec_show_icons)
            self._sec_status("\u23f3 Checking installers + permissions for threats...", "#f39c12")
            self._sec_threat_scan(pkgs)
        except Exception as e:
            cached = load_apps_cache()
            if cached and cached.get("mode") == "user":
                self.sec_packages = cached["entries"]
                self.sec_list_mode = "user"
                self.after(0, self._sec_render_rows)
                self.after(0, self._sec_animate_stop)
                self._sec_status(f"\u274c Error loading packages — showing cached user apps from {fmt_cache_time(cached.get('timestamp', 0))}.", "#f39c12")
                self._sec_log(f"[GeloTech ERROR] {e}; used cached user apps.", "#f39c12")
                return
            self.after(0, self._sec_animate_stop)
            self._sec_status(f"\u274c Error loading packages: {e}", "#e74c3c")
            self._sec_log(f"[GeloTech ERROR] {e}", "#e74c3c")

    def _sec_threat_scan(self, pkgs):
        try:
            overlay = {}
            try:
                res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "package", "p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                for line in res.stdout.splitlines():
                    if "android.permission.SYSTEM_ALERT_WINDOW" in line:
                        parts = line.strip().split()
                        for p in parts:
                            if p.startswith("package:"):
                                pkg = p.split(":")[1]
                                if pkg in pkgs:
                                    overlay[pkg] = True
            except Exception:
                pass

            installer = {}
            try:
                res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages", "-i"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("package:"):
                        parts = line[len("package:"):].split()
                        pkg = parts[0]
                        inst = parts[1].split("=")[1] if len(parts) > 1 and "=" in parts[1] else ""
                        installer[pkg] = inst
            except Exception:
                pass

            threats_found = 0
            for entry in self.sec_packages:
                p = entry["id"]
                labels = []
                if p in overlay:
                    labels.append("OVERLAY")
                inst = installer.get(p, "")
                if inst and inst not in ("com.android.vending", "com.google.android.feedback"):
                    labels.append(f"SIDELOAD:{inst}")
                if inst == "com.android.vending":
                    labels.append("PLAY")
                if labels:
                    entry["threat_labels"] = labels
                    entry["threat_level"] = 3 if "OVERLAY" in labels else 2
                    threats_found += 1
            self.after(0, lambda: self._sec_render_rows())
            self.after(0, lambda: self.sec_threats_label.configure(text=f"\U0001f9a0 Possible Threats: {threats_found}", text_color="#ff4d4d" if threats_found else "#2ecc71"))
            self.after(0, lambda: self.sec_progress_bar.set(1))
            self.after(0, self._sec_animate_stop)
            self._sec_status(f"\u2705 {len(pkgs)} user apps \u2014 {threats_found} possible threat(s) \U0001f6a8 / safe." if threats_found else f"\u2705 {len(pkgs)} user apps \u2014 0 possible threats / safe.", "#2ecc71" if not threats_found else "#ff4d4d")
        except Exception as e:
            self.after(0, self._sec_animate_stop)
            self._sec_log(f"[GeloTech ERROR] threat scan: {e}", "#e74c3c")

    def _detect_hidden_apps(self, installed):
        hidden = []
        uad = self._build_uad_lookup()
        whitelist = self._load_whitelist()
        try:
            # Get APK paths to distinguish user vs system apps
            path_res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages", "-f"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            pkg_paths = {}
            for line in path_res.stdout.splitlines():
                line = line.strip()
                if line.startswith("package:") and "=" in line:
                    apk_part = line[len("package:"):].split("=")
                    if len(apk_part) == 2:
                        pkg_paths[apk_part[1]] = apk_part[0]

            res = subprocess.run([self.scrcpy_adb, "shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            launcher_pkgs = set()
            for line in res.stdout.splitlines():
                line = line.strip()
                if "/" in line:
                    pkg = line.split("/")[0].strip()
                    if pkg:
                        launcher_pkgs.add(pkg)
            for pkg in installed:
                if pkg in launcher_pkgs or pkg in whitelist:
                    continue
                entry = uad.get(pkg)
                if entry and entry.get("removal") in ("Unsafe", "Expert"):
                    continue
                apk = pkg_paths.get(pkg, "")
                is_system = apk.startswith("/system/") or apk.startswith("/vendor/") or apk.startswith("/product/") or apk.startswith("/odm/")
                cat = "System App" if is_system else "User App"
                hidden.append({"id": pkg, "label": pkg, "category": cat, "description": "No launcher icon – app runs in background without user UI", "source": "Security Scan"})
        except:
            pass
        return hidden

    def _detect_popup_ads(self, installed):
        popup = []
        uad = self._build_uad_lookup()
        try:
            res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "package", "p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            overlay_apps = {}
            for line in res.stdout.splitlines():
                if "android.permission.SYSTEM_ALERT_WINDOW" in line:
                    parts = line.strip().split()
                    for p in parts:
                        if p.startswith("package:"):
                            pkg = p.split(":")[1]
                            if pkg in installed:
                                entry = uad.get(pkg)
                                if entry and entry.get("removal") in ("Unsafe", "Expert"):
                                    continue
                                overlay_apps[pkg] = True
            runtime_res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "activity", "processes"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            recent_order = []
            for line in runtime_res.stdout.splitlines():
                if "ProcessRecord" in line:
                    parts = line.split()
                    for p in parts:
                        if p.startswith("{") or p == "ProcessRecord":
                            continue
                        if "." in p and p not in recent_order:
                            recent_order.append(p)
            for pkg in recent_order:
                if pkg in overlay_apps:
                    popup.append({"id": pkg, "label": pkg, "category": "Popup Ad", "description": "Recently running with SYSTEM_ALERT_WINDOW - likely showing popup ads now", "source": "Security Scan"})
                    overlay_apps.pop(pkg, None)
            for pkg in sorted(overlay_apps):
                popup.append({"id": pkg, "label": pkg, "category": "Popup Ad", "description": "Has SYSTEM_ALERT_WINDOW overlay permission - can draw popup ads", "source": "Security Scan"})
        except:
            pass
        return popup

    def _detect_unknown_sources(self):
        unknown = []
        uad = self._build_uad_lookup()
        try:
            res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages", "-i"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            for line in res.stdout.splitlines():
                line = line.strip()
                if line.startswith("package:"):
                    parts = line[len("package:"):].split()
                    pkg = parts[0]
                    entry = uad.get(pkg)
                    if entry and entry.get("removal") in ("Unsafe", "Expert"):
                        continue
                    installer = parts[1].split("=")[1] if len(parts) > 1 and "=" in parts[1] else ""
                    if installer and installer not in ("com.android.vending", "com.google.android.feedback"):
                        unknown.append({"id": pkg, "label": pkg, "category": "Unknown Source", "description": f"Installed via: {installer}", "source": "Security Scan"})
                    elif not installer:
                        unknown.append({"id": pkg, "label": pkg, "category": "Unknown Source", "description": "No installer info - likely sideloaded", "source": "Security Scan"})
        except:
            pass
        return unknown

    def _detect_risk_permissions(self, installed):
        dangerous = ["android.permission.CAMERA", "android.permission.RECORD_AUDIO", "android.permission.ACCESS_FINE_LOCATION",
                     "android.permission.READ_SMS", "android.permission.SEND_SMS", "android.permission.READ_CONTACTS",
                     "android.permission.READ_CALL_LOG", "android.permission.READ_EXTERNAL_STORAGE",
                     "android.permission.ACCESS_BACKGROUND_LOCATION"]
        uad = self._build_uad_lookup()
        risky = []
        for pkg in installed[:100]:
            entry = uad.get(pkg)
            if entry and entry.get("removal") in ("Unsafe", "Expert"):
                continue
            try:
                res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "package", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                found_perms = []
                for perm in dangerous:
                    if perm in res.stdout:
                        found_perms.append(perm.split(".")[-1])
                if found_perms:
                    risky.append({"id": pkg, "label": pkg, "category": "Risk Permission", "description": f"Permissions: {', '.join(found_perms)}", "source": "Security Scan"})
            except:
                pass
        return risky

    def _detect_fake_apps(self, installed):
        fakes = []
        suspicious_names = ["google", "facebook", "whatsapp", "instagram", "chrome", "youtube", "gmail", "twitter", "snapchat", "tiktok", "telegram", "microsoft", "amazon", "netflix", "spotify", "linkedin"]
        try:
            res = subprocess.run([self.scrcpy_adb, "shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            for line in res.stdout.splitlines():
                line = line.strip()
                if "/" not in line:
                    continue
                pkg = line.split("/")[0].strip()
                for name in suspicious_names:
                    if name in pkg.lower():
                        legit_pkgs = {
                            "google": "com.google.android", "facebook": "com.facebook.katana",
                            "whatsapp": "com.whatsapp", "instagram": "com.instagram.android",
                            "chrome": "com.android.chrome", "youtube": "com.google.android.youtube",
                            "gmail": "com.google.android.gm", "twitter": "com.twitter.android",
                            "snapchat": "com.snapchat.android", "tiktok": "com.zhiliaoapp.musically",
                            "telegram": "org.telegram.messenger", "microsoft": "com.microsoft",
                            "amazon": "com.amazon", "netflix": "com.netflix.mediaclient",
                            "spotify": "com.spotify.music", "linkedin": "com.linkedin.android"
                        }
                        legit = legit_pkgs.get(name, "")
                        if legit and not pkg.startswith(legit):
                            fakes.append({"id": pkg, "label": pkg, "category": "Fake App", "description": f"Suspicious package - name resembles '{name}' but is not the official app", "source": "Security Scan"})
                            break
        except:
            pass
        return fakes

    def _detect_running_apps(self):
        running = []
        uad = self._build_uad_lookup()
        try:
            res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "activity", "processes"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            seen = set()
            for line in res.stdout.splitlines():
                if "ProcessRecord" in line:
                    parts = line.split()
                    for p in parts:
                        if p.startswith("{"):
                            continue
                        if "." in p and not p.startswith("ProcessRecord") and p not in seen:
                            seen.add(p)
                            entry = uad.get(p)
                            if entry and entry.get("removal") in ("Unsafe", "Expert"):
                                continue
                            running.append({"id": p, "label": p, "category": "Running App", "description": "App is currently running in background", "source": "Security Scan"})
        except:
            pass
        return running

    def _detect_all_apps(self, installed):
        catalog = self.load_debloat_catalog()[0]
        all_apps = []
        for pkg in installed:
            entry = catalog.get(pkg, {})
            removal = entry.get("removal", "Unknown")
            desc = entry.get("description", "No description available")
            all_apps.append({"id": pkg, "label": pkg, "category": removal, "description": desc, "source": "Security Scan"})
        return all_apps

    def _detect_device_admin(self):
        admin = []
        uad = self._build_uad_lookup()
        try:
            res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "device_policy"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            for line in res.stdout.splitlines():
                line = line.strip()
                if "Package " in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        pkg = parts[1].strip().split()[0] if parts[1].strip() else None
                        if pkg and "." in pkg:
                            entry = uad.get(pkg)
                            if entry and entry.get("removal") in ("Unsafe", "Expert"):
                                continue
                            admin.append({"id": pkg, "label": pkg, "category": "Device Admin", "description": "Has device admin privileges - can resist uninstallation", "source": "Security Scan"})
        except:
            pass
        return admin

    def _detect_storage_usage(self, installed):
        heavy = []
        uad = self._build_uad_lookup()
        try:
            script = "for f in $(pm list packages -f | sed 's/package://' | sed 's/=.*//'); do echo \"$f $(du -sk $f 2>/dev/null | cut -f1)\"; done"
            res = subprocess.run([self.scrcpy_adb, "shell", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            installed_set = set(installed)
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.rsplit(None, 1)
                if len(parts) != 2:
                    continue
                apk_path, size_str = parts
                pkg = apk_path.rsplit("/", 1)[-1].replace(".apk", "")
                if pkg not in installed_set:
                    continue
                entry = uad.get(pkg)
                if entry and entry.get("removal") in ("Unsafe", "Expert"):
                    continue
                try:
                    size = int(size_str) * 1024
                except:
                    continue
                if size > 80 * 1024 * 1024:
                    heavy.append({"id": pkg, "label": pkg, "category": "Large App", "description": f"APK size: {self._format_sec_bytes(size)}", "source": "Security Scan"})
        except:
            pass
        return heavy

