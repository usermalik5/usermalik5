# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox, ttk
import tkinter as tk
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
from PIL import Image, ImageDraw, ImageFont, ImageTk
from tech_common import get_bundle_dir, get_app_dir, get_cache_dir, get_settings_dir, load_banking_apps, Tooltip, subprocess


class SecOps4Mixin:
    def action_sec_show_icons(self):
        def run_cmd(args, timeout=15):
            return subprocess.run([self.scrcpy_adb] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)

        def worker():
            try:
                # Confirm the device is reachable & authorized BEFORE pushing anything
                st = run_cmd(["get-state"]).stdout.strip().lower()
                if st == "unauthorized":
                    self.after(0, lambda: self._sec_log("[GeloTech] Icons: phone not authorized — accept the USB debugging prompt on the phone, then press Icons again.", "#e74c3c"))
                    return
                if st != "device":
                    self.after(0, lambda: self._sec_log(f"[GeloTech] Icons: no device in 'device' state (got '{st}'). Connect and authorize the phone.", "#e74c3c"))
                    return

                r = run_cmd(["shell", "pm", "path", "com.drox.apkiconhelper"])
                if "package:" not in r.stdout:
                    helper = os.path.join(get_bundle_dir(), "ApkIconHelper.apk")
                    if not os.path.isfile(helper):
                        self.after(0, lambda: self._sec_log("[GeloTech] Missing helper APK: ApkIconHelper.apk", "#e74c3c"))
                        return
                    self.after(0, lambda: self._sec_log("[GeloTech] Installing APKIconHelper on device...", "#58a6ff"))
                    inst = run_cmd(["install", "-r", "-t", helper], 60)
                    combined = inst.stdout + inst.stderr
                    if "Success" not in combined:
                        msg = combined.strip()[-300:]
                        hint = ""
                        if "INSTALL_FAILED_USER_RESTRICTED" in combined:
                            hint = " On Android 11+ this means 'Install via USB' is off or the Allow prompt was declined: enable Developer options → 'Install via USB', then press Icons again and tap Allow when the phone asks."
                        elif "not authorized" in combined.lower() or "unauthorized" in combined.lower():
                            hint = " Accept the USB debugging prompt on the phone, then press Icons again."
                        elif "offline" in combined.lower():
                            hint = " The phone looks offline — reconnect the cable and press Icons again."
                        self.after(0, lambda m=msg, h=hint: self._sec_log(f"[GeloTech] Helper install failed: {m}{h}", "#e74c3c"))
                        return
                    # verify the install actually registered before launching
                    ver = run_cmd(["shell", "pm", "path", "com.drox.apkiconhelper"])
                    if "package:" not in ver.stdout:
                        self.after(0, lambda: self._sec_log("[GeloTech] Helper install reported Success but the package is missing — enable 'Install via USB' in Developer options and press Icons again.", "#e74c3c"))
                        return
                export = "/sdcard/Android/data/com.drox.apkiconhelper/files/apk_icon_export"
                flag = export + "/DONE.flag"
                run_cmd(["shell", "rm", "-f", flag])
                run_cmd(["shell", "svc", "power", "stayon", "true"])
                run_cmd(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
                run_cmd(["shell", "wm", "dismiss-keyguard"])

                def launch():
                    run_cmd(["shell", "am", "start", "-n", "com.drox.apkiconhelper/.MainActivity", "--ez", "autoExport", "true"])

                def is_done():
                    chk = run_cmd(["shell", "cat", flag])
                    return bool(chk.stdout.strip())

                done = False
                for attempt in range(2):
                    launch()
                    for i in range(60):
                        time.sleep(2)
                        if is_done():
                            done = True
                            break
                        if i and i % 15 == 0:
                            self.after(0, lambda n=i: self._sec_log(f"[GeloTech] Exporting icons ({n * 2}s)...", "#f39c12"))
                    if done:
                        break
                    self.after(0, lambda: self._sec_log("[GeloTech] Export timed out - retrying automatically...", "#f39c12"))
                    run_cmd(["shell", "am", "force-stop", "com.drox.apkiconhelper"])
                    time.sleep(2)
                run_cmd(["shell", "svc", "power", "stayon", "false"])
                if not done:
                    self.after(0, lambda: self._sec_log("[GeloTech] Helper export did not finish. Unlock your phone and press Icons again.", "#e74c3c"))
                    return
                local = get_cache_dir()
                os.makedirs(local, exist_ok=True)
                run_cmd(["pull", export, local], 120)
                manifest = os.path.join(local, "packages.jsonl")
                if not os.path.isfile(manifest):
                    manifest = os.path.join(local, "apk_icon_export", "packages.jsonl")
                count = 0
                if os.path.isfile(manifest):
                    with open(manifest, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                item = json.loads(line)
                                pkg = item.get("package", "")
                                icon = item.get("icon", "")
                                if pkg and icon:
                                    src = os.path.join(os.path.dirname(manifest), icon)
                                    if os.path.isfile(src):
                                        shutil.copy(src, os.path.join(local, f"{pkg}.png"))
                                        count += 1
                            except Exception:
                                pass
                run_cmd(["shell", "am", "force-stop", "com.drox.apkiconhelper"])
                self._sec_icon_cache = {}
                self._sec_tree_icon_cache = {}
                self._app_labels = None
                self.after(0, lambda: self._sec_render_rows())
                self.after(0, lambda: self._sec_log(f"[GeloTech] Icons synced: {count} apps (helper closed automatically).", "#2ecc71"))
            except Exception as e:
                self.after(0, lambda e=e: self._sec_log(f"[GeloTech] Icon sync error: {e}", "#e74c3c"))
        threading.Thread(target=worker, daemon=True).start()

    def action_sec_backup_restore(self):
        """Single consolidated function: backup/restore of excluded + debloated packages."""
        if not self._can("restore"):
            self._sec_status("Permission denied: Backup / Restore is disabled for this account.", "#e74c3c")
            return
        data = self._load_settings()
        clean = sorted(data.get("clean_excluded", []))
        uninstall = sorted(data.get("uninstall_excluded", []))
        debloated = sorted(data.get("debloated", []))

        dialog = ctk.CTkToplevel(self)
        dialog.title("💾 Backup / Restore")
        dialog.geometry("560x520")
        dialog.transient(self)
        dialog.grab_set()

        header = ctk.CTkFrame(dialog, fg_color="#111622", corner_radius=12, border_width=1, border_color="#303645")
        header.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(header, text="💾 Consolidated Package Settings", font=ctk.CTkFont(size=13, weight="bold"), text_color="#e6edf3").pack(pady=(10, 2))
        ctk.CTkLabel(header, text=f"🟠 Clean Excluded: {len(clean)}   🔴 Uninstall Excluded: {len(uninstall)}   🗑 Debloated: {len(debloated)}",
                     font=ctk.CTkFont(size=10), text_color="#c9d1d9").pack(pady=(0, 10))

        ctk.CTkLabel(dialog, text="Debloated packages (restore to reinstall / re-enable):", font=ctk.CTkFont(size=11, weight="bold"), text_color="#58a6ff").pack(anchor="w", padx=16, pady=(6, 2))

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="#0d1117", corner_radius=8, border_width=1, border_color="#30363d")
        scroll.pack(fill="both", expand=True, padx=12, pady=6)
        vars_ = {}
        if not debloated:
            ctk.CTkLabel(scroll, text="No debloated packages recorded.\nPackages you uninstall via this tool are tracked here automatically.", text_color="#484f58", font=ctk.CTkFont(size=10)).pack(pady=20)
        for pkg in debloated:
            row = ctk.CTkFrame(scroll, fg_color="#161b22", corner_radius=6)
            row.pack(fill="x", padx=4, pady=2)
            var = ctk.BooleanVar(value=True)
            vars_[pkg] = var
            ctk.CTkCheckBox(row, text=pkg, variable=var, font=ctk.CTkFont(size=10), fg_color="#1f6feb", hover_color="#1a5fd0", text_color="#e6edf3").pack(side="left", padx=8, pady=6)
            label = self._resolve_label(pkg)
            if label != pkg:
                ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=9), text_color="#8b949e").pack(side="right", padx=8)

        logbox = ctk.CTkTextbox(dialog, fg_color="#0d1117", border_color="#30363d", border_width=1, corner_radius=8, height=110, font=ctk.CTkFont(size=9, family="Consolas"), text_color="#c9d1d9")
        logbox.pack(fill="x", padx=12, pady=6)
        def log(msg, color="#c9d1d9"):
            logbox.insert("end", f"{msg}\n", (color,))
            logbox.tag_config(color, foreground=color)
            logbox.see("end")

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(0, 12))
        ctk.CTkButton(btn_row, text="♻ Restore Checked", width=140, fg_color="#1f6feb", hover_color="#1a5fd0", command=lambda: self._restore_debloated(vars_, debloated, log, dialog)).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="❌ Close", width=100, fg_color="#3a3a3a", hover_color="#4a4a4a", command=dialog.destroy).pack(side="left", padx=6)

    def _restore_debloated(self, vars_, debloated, log, dialog):
        picked = [pkg for pkg in debloated if vars_.get(pkg, ctk.BooleanVar(value=False)).get()]
        if not picked:
            log("No packages checked.", "#f39c12")
            return

        def worker():
            restored, failed = [], []
            for pkg in picked:
                try:
                    backup_apk = os.path.join(get_settings_dir(), "apk_backups", f"{pkg}.apk")
                    if os.path.isfile(backup_apk):
                        r = subprocess.run([self.scrcpy_adb, "install", "-r", backup_apk], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
                        if "Success" in (r.stdout + r.stderr):
                            restored.append(pkg)
                            self.after(0, lambda p=pkg: log(f"Restored from backup: {p}", "#2ecc71"))
                            continue
                    r = subprocess.run([self.scrcpy_adb, "shell", "cmd", "package", "install-existing", "--user", "0", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                    if "Success" not in (r.stdout + r.stderr):
                        r = subprocess.run([self.scrcpy_adb, "shell", "pm", "enable", "--user", "0", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                    if "Success" in (r.stdout + r.stderr):
                        restored.append(pkg)
                        self.after(0, lambda p=pkg: log(f"Restored (install-existing): {p}", "#2ecc71"))
                    else:
                        failed.append(pkg)
                        self.after(0, lambda p=pkg: log(f"Restore failed: {p}", "#e74c3c"))
                except Exception as e:
                    failed.append(pkg)
                    self.after(0, lambda p=pkg, e=e: log(f"Restore error {p}: {e}", "#e74c3c"))
            if restored:
                remaining = [p for p in debloated if p not in restored]
                self._save_debloated(remaining)
                self.after(0, lambda: log(f"Removed {len(restored)} restored package(s) from the debloated list.", "#58a6ff"))
            self.after(0, lambda: log(f"Restore finished: {len(restored)} ok, {len(failed)} failed.", "#58a6ff"))
            self.after(0, self._sec_render_rows)
        threading.Thread(target=worker, daemon=True).start()

    def _sec_load_device_info(self):
        def worker():
            try:
                vals = {}
                for key, prop in (("model", "ro.product.model"), ("android", "ro.build.version.release"), ("patch", "ro.build.version.security_patch"), ("build", "ro.build.display.id")):
                    r = subprocess.run([self.scrcpy_adb, "shell", "getprop", prop], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                    vals[key] = r.stdout.strip() or "-"
                connected = True
                try:
                    d = subprocess.run([self.scrcpy_adb, "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                    lines = d.stdout.splitlines()
                    if len(lines) < 2 or "device" not in lines[1]:
                        connected = False
                except Exception:
                    connected = False
                model = vals.get("model", "-")

                def apply():
                    try:
                        self.sec_dev_conn.configure(text="\U0001f916 DEVICE CONNECTED" if connected else "\U0001f6ab NO DEVICE",
                                                    text_color="#2ecc71" if connected else "#e74c3c")
                        self.sec_dev_model.configure(text=f"Model Name: {model}", text_color="#e6edf3")
                        self.sec_dev_android.configure(text=f"Android: {vals.get('android', '-')}", text_color="#e6edf3")
                        self.sec_dev_patch.configure(text=f"Security Patch: {vals.get('patch', '-')}", text_color="#e6edf3")
                        self.sec_dev_build.configure(text=f"Build ID: {vals.get('build', '-')}", text_color="#e6edf3")
                        self.sec_dev_model.after(200, self._sec_lookup_device_name, model)
                    except Exception:
                        pass
                self.after(0, apply)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _sec_lookup_device_name(self, model):
        if not model or model == "-":
            return

        def worker():
            try:
                found = model
                try:
                    import urllib.request, urllib.parse, json
                    query = urllib.parse.quote(f"{model} android")
                    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&srlimit=5&format=json"
                    req = urllib.request.Request(url, headers={"User-Agent": "GeloTech-Tool/1.0"})
                    with urllib.request.urlopen(req, timeout=6) as r:
                        data = json.loads(r.read().decode("utf-8"))
                    hits = data.get("query", {}).get("search", [])
                    if hits:
                        title = hits[0].get("title", "").strip()
                        if title and not title.lower().startswith("list of") and "disambiguation" not in title.lower():
                            found = title
                except Exception:
                    found = model
                if found and found != model:
                    def update():
                        try:
                            self.sec_dev_model.configure(text=f"Model Name: {found}  ({model})", text_color="#e6edf3")
                        except Exception:
                            pass
                    self.after(0, update)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _format_sec_bytes(self, b):
        if b < 1024:
            return f"{b} B"
        elif b < 1024**2:
            return f"{b/1024:.1f} KB"
        elif b < 1024**3:
            return f"{b/1024**2:.1f} MB"
        else:
            return f"{b/1024**3:.2f} GB"

    # ----------------------------------------------------
    # VIRUSTOTAL OPERATIONS
    # ----------------------------------------------------

