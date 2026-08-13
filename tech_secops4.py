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
    def _icon_device_key(self, serial):
        return hashlib.sha256(serial.encode("utf-8", "replace")).hexdigest()[:32]

    def _icon_device_cache_dir(self, serial):
        path = os.path.join(get_settings_dir(), "icon_cache", self._icon_device_key(serial))
        os.makedirs(path, exist_ok=True)
        return path

    def _icon_cache_meta_path(self, serial):
        return os.path.join(self._icon_device_cache_dir(serial), "sync.json")

    def _icon_load_meta(self, serial):
        try:
            with open(self._icon_cache_meta_path(serial), "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError, TypeError):
            return {}

    def _icon_save_meta(self, serial, meta):
        path = self._icon_cache_meta_path(serial)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, sort_keys=True)
        os.replace(tmp, path)

    def _icon_run_cmd(self, args, timeout=15):
        return subprocess.run([self.scrcpy_adb] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)

    def _icon_wait_for_helper(self, attempts=4, delay=1.0):
        """Verify helper presence; package-manager transients are not treated as missing."""
        import time
        last_error = ""
        for attempt in range(attempts):
            result = self._icon_run_cmd(["shell", "pm", "path", "com.drox.apkiconhelper"])
            out = (result.stdout or "").strip()
            err = (result.stderr or "").strip()
            if "package:" in out:
                return out.split("package:", 1)[1].splitlines()[0].strip(), None
            last_error = out or err
            transient = any(token in (out + " " + err).lower() for token in ("can't find service", "package manager", "binder", "service"))
            if attempt < attempts - 1 and (transient or not out):
                time.sleep(delay)
                continue
            if attempt < attempts - 1:
                time.sleep(delay)
        return None, last_error

    def _icon_package_fingerprint(self):
        result = self._icon_run_cmd(["shell", "pm", "list", "packages"], 30)
        packages = sorted(
            line.split(":", 1)[1].strip()
            for line in (result.stdout or "").splitlines()
            if line.strip().startswith("package:") and line.split(":", 1)[1].strip()
        )
        if not packages:
            return None, 0
        return hashlib.sha256("\n".join(packages).encode("utf-8")).hexdigest(), len(packages)

    def _icon_restore_device_cache(self, serial):
        cache_dir = self._icon_device_cache_dir(serial)
        meta = self._icon_load_meta(serial)
        manifest = os.path.join(cache_dir, "packages.jsonl")
        if not meta.get("package_fingerprint") or not os.path.isfile(manifest):
            return False
        local = get_cache_dir()
        os.makedirs(local, exist_ok=True)
        copied = 0
        for name in os.listdir(cache_dir):
            if not name.endswith(".png"):
                continue
            try:
                shutil.copy2(os.path.join(cache_dir, name), os.path.join(local, name))
                copied += 1
            except OSError:
                pass
        return copied > 0

    def _icon_store_device_cache(self, serial, manifest, package_fingerprint, package_count):
        cache_dir = self._icon_device_cache_dir(serial)
        local = os.path.dirname(manifest)
        shutil.copy2(manifest, os.path.join(cache_dir, "packages.jsonl"))
        icon_count = 0
        for name in os.listdir(local):
            if not name.endswith(".png"):
                continue
            try:
                shutil.copy2(os.path.join(local, name), os.path.join(cache_dir, name))
                icon_count += 1
            except OSError:
                pass
        self._icon_save_meta(serial, {
            "serial": serial,
            "package_fingerprint": package_fingerprint,
            "package_count": package_count,
            "icon_count": icon_count,
            "helper_verified": True,
            "synced_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

    def action_sec_show_icons(self, automatic=False, force=False):
        def worker():
            import time
            serial = None
            try:
                state = ""
                for _ in range(4):
                    state = self._icon_run_cmd(["get-state"]).stdout.strip().lower()
                    if state == "device":
                        break
                    if state == "unauthorized":
                        self.after(0, lambda: self._sec_log("[GeloTech] Icons: authorize USB debugging on the phone first.", "#e74c3c"))
                        return
                    time.sleep(1.0)
                if state != "device":
                    self.after(0, lambda: self._sec_log("[GeloTech] Icons: device is not ready yet; automatic sync will wait for the next device event.", "#f39c12"))
                    return

                serial_result = self._icon_run_cmd(["get-serialno"])
                serial = (serial_result.stdout or "").strip()
                if not serial or serial.lower() in {"unknown", "no permissions"}:
                    self.after(0, lambda: self._sec_log("[GeloTech] Icons: could not identify the connected device.", "#e74c3c"))
                    return

                fingerprint, package_count = self._icon_package_fingerprint()
                if fingerprint is None:
                    self.after(0, lambda: self._sec_log("[GeloTech] Icons: package list is not ready; automatic sync skipped for now.", "#f39c12"))
                    return

                meta = self._icon_load_meta(serial)
                cache_matches = meta.get("package_fingerprint") == fingerprint and bool(meta.get("icon_count"))
                if cache_matches and not force and self._icon_restore_device_cache(serial):
                    self._sec_icon_cache = {}
                    self._sec_tree_icon_cache = {}
                    self._app_labels = None
                    self.after(0, self._sec_render_rows)
                    self.after(0, lambda: self._sec_log(f"[GeloTech] Icons ready from device cache ({meta.get('icon_count', 0)} icons).", "#2ecc71"))
                    return

                helper_path, helper_error = self._icon_wait_for_helper()
                if not helper_path:
                    transient = helper_error and any(token in helper_error.lower() for token in ("can't find service", "package manager", "binder", "service"))
                    if transient:
                        self.after(0, lambda: self._sec_log("[GeloTech] Android package manager is still starting; no APK was pushed.", "#f39c12"))
                        return
                    helper = os.path.join(get_bundle_dir(), "ApkIconHelper.apk")
                    if not os.path.isfile(helper):
                        self.after(0, lambda: self._sec_log("[GeloTech] Missing ApkIconHelper.apk in the application bundle.", "#e74c3c"))
                        return
                    self.after(0, lambda: self._sec_log("[GeloTech] ApkIconHelper not found; installing it once...", "#58a6ff"))
                    install = self._icon_run_cmd(["install", "-r", "-t", helper], 60)
                    combined = (install.stdout or "") + (install.stderr or "")
                    if "Success" not in combined:
                        msg = combined.strip()[-300:]
                        self.after(0, lambda m=msg: self._sec_log(f"[GeloTech] Helper install failed: {m}", "#e74c3c"))
                        return
                    helper_path, _ = self._icon_wait_for_helper()
                    if not helper_path:
                        self.after(0, lambda: self._sec_log("[GeloTech] Helper installed but verification failed; automatic sync stopped without another install attempt.", "#e74c3c"))
                        return

                meta["helper_verified"] = True
                meta["helper_verified_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._icon_save_meta(serial, meta)

                if not force and cache_matches and self._icon_restore_device_cache(serial):
                    self._sec_icon_cache = {}
                    self._sec_tree_icon_cache = {}
                    self._app_labels = None
                    self.after(0, self._sec_render_rows)
                    self.after(0, lambda: self._sec_log(f"[GeloTech] Icons restored from cache ({meta.get('icon_count', 0)} icons).", "#2ecc71"))
                    return

                export = "/sdcard/Android/data/com.drox.apkiconhelper/files/apk_icon_export"
                flag = export + "/DONE.flag"
                self._icon_run_cmd(["shell", "rm", "-f", flag])
                self._icon_run_cmd(["shell", "svc", "power", "stayon", "true"])
                self._icon_run_cmd(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
                self._icon_run_cmd(["shell", "wm", "dismiss-keyguard"])

                def launch():
                    self._icon_run_cmd(["shell", "am", "start", "-n", "com.drox.apkiconhelper/.MainActivity", "--ez", "autoExport", "true"])

                def done_flag():
                    return bool((self._icon_run_cmd(["shell", "cat", flag]).stdout or "").strip())

                completed = False
                for attempt in range(2):
                    launch()
                    for _ in range(60):
                        time.sleep(2)
                        if done_flag():
                            completed = True
                            break
                    if completed:
                        break
                    self.after(0, lambda: self._sec_log("[GeloTech] Icon export timed out; retrying once...", "#f39c12"))
                    self._icon_run_cmd(["shell", "am", "force-stop", "com.drox.apkiconhelper"])
                    time.sleep(2)

                self._icon_run_cmd(["shell", "svc", "power", "stayon", "false"])
                if not completed:
                    self.after(0, lambda: self._sec_log("[GeloTech] Icon export did not finish. Automatic retry waits for another device event.", "#e74c3c"))
                    return

                local = get_cache_dir()
                os.makedirs(local, exist_ok=True)
                self._icon_run_cmd(["pull", export, local], 120)
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
                                        shutil.copy2(src, os.path.join(local, f"{pkg}.png"))
                                        count += 1
                            except Exception:
                                continue

                self._icon_store_device_cache(serial, manifest, fingerprint, package_count)
                self._icon_run_cmd(["shell", "am", "force-stop", "com.drox.apkiconhelper"])
                self._sec_icon_cache = {}
                self._sec_tree_icon_cache = {}
                self._app_labels = None
                self.after(0, self._sec_render_rows)
                self.after(0, lambda: self._sec_log(f"[GeloTech] Icons synced: {count} apps; device cache updated.", "#2ecc71"))
            except Exception as exc:
                if serial:
                    try:
                        meta = self._icon_load_meta(serial)
                        meta["last_error"] = str(exc)
                        self._icon_save_meta(serial, meta)
                    except Exception:
                        pass
                self.after(0, lambda e=exc: self._sec_log(f"[GeloTech] Icon sync error: {e}", "#e74c3c"))
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

