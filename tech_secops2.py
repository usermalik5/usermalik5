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
from tech_common import get_bundle_dir, get_app_dir, get_cache_dir, get_settings_dir, Tooltip, subprocess


class SecOps2Mixin:
    def _sec_typed_confirm(self, title, message):
        """Require the user to type YES before a destructive action proceeds."""
        result = {"ok": False}
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("+%d+%d" % (self.winfo_rootx() + 140, self.winfo_rooty() + 140))
        dlg.attributes("-topmost", True)
        dlg.resizable(False, False)
        dlg.transient(self)
        body = ctk.CTkFrame(dlg, fg_color="#161b22", corner_radius=8, border_width=1, border_color="#30363d")
        body.pack(padx=16, pady=16)
        ctk.CTkLabel(body, text=message, font=ctk.CTkFont(size=11), text_color="#e6edf3",
                     wraplength=420, justify="left").pack(padx=14, pady=(14, 6))
        ctk.CTkLabel(body, text="Type YES to confirm:", font=ctk.CTkFont(size=10), text_color="#8b949e").pack(padx=14, pady=(0, 2))
        entry = ctk.CTkEntry(body, width=220, font=ctk.CTkFont(size=12), fg_color="#0d1117", border_color="#30363d")
        entry.pack(padx=14, pady=4)
        entry.focus_set()

        def on_key(_=None):
            btn_ok.configure(state="normal" if entry.get().strip() == "YES" else "disabled")
        entry.bind("<KeyRelease>", on_key)

        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(pady=(8, 12))
        btn_ok = ctk.CTkButton(btn_row, text="Confirm", fg_color="#e74c3c", hover_color="#b91c1c",
                               width=110, state="disabled", command=lambda: (result.update(ok=True), dlg.destroy()))
        btn_ok.pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Cancel", fg_color="#21262d", hover_color="#30363d",
                      width=110, command=dlg.destroy).pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: (result.update(ok=True), dlg.destroy()) if entry.get().strip() == "YES" else None)
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        dlg.wait_window()
        return result["ok"]

    def action_sec_uninstall_checked(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Popup Ad Virus Cleaner is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to uninstall. Check apps you want to remove.", "#f39c12")
            return
        if not self._sec_typed_confirm("Uninstall (Checked)",
                f"Uninstall {len(pkgs)} checked 3rd-party app(s)?\n\nUsed to remove APK Pop-up Virus. "
                "Apps in your exclusion lists are safe.\n\nThis CANNOT be undone easily — a backup is recommended."):
            return
        self._sec_log(f"[GeloTech] Uninstalling {len(pkgs)} checked app(s)...", "#58a6ff")
        self._sec_run_uninstall(pkgs)

    def action_sec_disable_checked(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Popup Ad Virus Cleaner is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to disable. Check apps you want to disable.", "#f39c12")
            return
        if not self._sec_typed_confirm("Disable (Checked)",
                f"Disable {len(pkgs)} checked app(s) for the current user?\n\n"
                "Apps can be re-enabled later, but disabling critical system apps can make the phone unstable."):
            return
        self._sec_log(f"[GeloTech] Disabling {len(pkgs)} checked app(s)...", "#58a6ff")
        self._sec_run_disable(pkgs)

    def _sec_run_disable(self, packages):
        def worker():
            ok, fail = 0, 0
            for pkg in packages:
                try:
                    r = subprocess.run([self.scrcpy_adb, "shell", "pm", "disable-user", "--user", "0", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
                    if r.returncode == 0 and "new state: disabled" in (r.stdout + r.stderr):
                        ok += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Disabled: {p} \u2014 {self._sec_description(p)}", "#2ecc71"))
                    else:
                        fail += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Disable failed: {p}", "#e74c3c"))
                except Exception as e:
                    fail += 1
                    self.after(0, lambda p=pkg, e=e: self._sec_log(f"[GeloTech] Disable error {p}: {e}", "#e74c3c"))
            self.after(0, lambda: self._sec_log(f"[GeloTech] Disable finished: {ok} disabled, {fail} failed.", "#58a6ff"))
            self.after(0, self._sec_refresh_current_list)
        threading.Thread(target=worker, daemon=True).start()

    def action_sec_remove_bugs(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Popup Ad Virus Cleaner is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to process. Check apps first.", "#f39c12")
            return
        if not self._sec_typed_confirm("Fix Popup Ad",
            f"Fix Popup Ad will process {len(pkgs)} checked app(s).\n\n"
            "Phase 1: Clean (clear storage) checked apps + built-in browsers.\n"
            "Phase 2: Uninstall checked 3rd-party apps only (system/browsers are not removed).\n\n"
            "Only apps you check are affected — nothing runs by default."):
            return
        self._sec_log(f"[GeloTech] Fix Popup Ad: phase 1 cleaning {len(pkgs)} app(s)...", "#f39c12")
        self._sec_run_clean(pkgs, auto_refresh=False)
        self._sec_log("[GeloTech] Fix Popup Ad: phase 2 uninstalling 3rd-party apps...", "#f39c12")
        self._sec_run_uninstall(pkgs)

    def action_sec_add_excluded(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Popup Ad Virus Cleaner is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Check apps you want to exclude first.", "#f39c12")
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add to Excluded")
        dialog.geometry("360x170")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Exclude for:", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(16, 8))
        choice = ctk.StringVar(value="both")
        ctk.CTkRadioButton(dialog, text="Clean (keeps apps from being cleaned)", variable=choice, value="clean").pack(pady=2)
        ctk.CTkRadioButton(dialog, text="Uninstall (keeps apps from being uninstalled)", variable=choice, value="uninstall").pack(pady=2)
        ctk.CTkRadioButton(dialog, text="Both", variable=choice, value="both").pack(pady=2)
        def do():
            mode = choice.get()
            clean = self._load_excluded_clean()
            uninstall = self._load_excluded_uninstall()
            if mode in ("clean", "both"):
                clean.update(pkgs)
                self._save_excluded_clean(clean)
            if mode in ("uninstall", "both"):
                uninstall.update(pkgs)
                self._save_excluded_uninstall(uninstall)
            self._sec_log(f"[GeloTech] Added {len(pkgs)} app(s) to {mode} exclusion.", "#58a6ff")
            dialog.destroy()
            self._sec_render_rows()
        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(10, 12))
        ctk.CTkButton(btn_row, text="Save", width=90, command=do).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Cancel", width=90, fg_color="#3a3a3a", hover_color="#4a4a4a", command=dialog.destroy).pack(side="left", padx=6)

    _PERM_INFO = {
        # name: (danger color, human meaning)
        "SYSTEM_ALERT_WINDOW": ("#e74c3c", "Draws overlay/popup windows on top of other apps — classic adware technique"),
        "BIND_ACCESSIBILITY_SERVICE": ("#e74c3c", "Accessibility service — can read everything on screen and control the device"),
        "BIND_DEVICE_ADMIN": ("#e74c3c", "Device administrator — can lock the screen or wipe the phone"),
        "REQUEST_INSTALL_PACKAGES": ("#e74c3c", "Can install other apps (unknown sources)"),
        "REQUEST_DELETE_PACKAGES": ("#e74c3c", "Can request deletion of other apps"),
        "READ_SMS": ("#e74c3c", "Reads your SMS (OTP / banking codes)"),
        "RECEIVE_SMS": ("#e74c3c", "Receives SMS — commonly used to steal OTP codes"),
        "SEND_SMS": ("#e74c3c", "Can send SMS (premium numbers = charges)"),
        "READ_CALL_LOG": ("#e74c3c", "Reads your call history"),
        "WRITE_CALL_LOG": ("#e74c3c", "Can modify call history"),
        "RECORD_AUDIO": ("#e74c3c", "Records audio via the microphone"),
        "CAMERA": ("#e74c3c", "Takes photos / records video"),
        "ACCESS_BACKGROUND_LOCATION": ("#e74c3c", "Tracks your location even while in the background"),
        "READ_CONTACTS": ("#e74c3c", "Reads your contacts list"),
        "WRITE_CONTACTS": ("#e74c3c", "Can modify your contacts"),
        "READ_PHONE_STATE": ("#e74c3c", "Reads device identity: IMEI, phone number, SIM info"),
        "READ_PHONE_NUMBERS": ("#e74c3c", "Reads your phone numbers"),
        "CALL_PHONE": ("#e74c3c", "Can make phone calls directly"),
        "ANSWER_PHONE_CALLS": ("#e74c3c", "Answers incoming calls"),
        "DISABLE_KEYGUARD": ("#e74c3c", "Can disable your lock screen"),
        "MANAGE_EXTERNAL_STORAGE": ("#e74c3c", "Full access to all files ('All files access')"),
        "PACKAGE_USAGE_STATS": ("#f39c12", "Sees which apps you open and when (usage statistics)"),
        "QUERY_ALL_PACKAGES": ("#f39c12", "Can see the full list of installed apps"),
        "ACCESS_FINE_LOCATION": ("#f39c12", "Precise GPS location"),
        "ACCESS_COARSE_LOCATION": ("#f39c12", "Approximate location (network / Wi-Fi)"),
        "READ_EXTERNAL_STORAGE": ("#f39c12", "Reads files on shared storage"),
        "WRITE_EXTERNAL_STORAGE": ("#f39c12", "Writes files to shared storage"),
        "READ_MEDIA_IMAGES": ("#f39c12", "Reads your photos (Android 13+)"),
        "READ_MEDIA_VIDEO": ("#f39c12", "Reads your videos (Android 13+)"),
        "READ_MEDIA_AUDIO": ("#f39c12", "Reads your music & audio (Android 13+)"),
        "ACCESS_NOTIFICATION_POLICY": ("#f39c12", "Can read & silence your notifications"),
        "GET_ACCOUNTS": ("#f39c12", "Sees accounts registered on the device"),
        "AUTHENTICATE_ACCOUNTS": ("#f39c12", "Acts as the account authenticator"),
        "BODY_SENSORS": ("#f39c12", "Accesses body sensors (heart rate, etc.)"),
        "ACTIVITY_RECOGNITION": ("#f39c12", "Detects your physical activity (walking, driving)"),
        "WRITE_SETTINGS": ("#f39c12", "Can change system settings"),
        "REQUEST_IGNORE_BATTERY_OPTIMIZATIONS": ("#f39c12", "Asks to ignore battery optimization (runs freely in background)"),
        "RECEIVE_BOOT_COMPLETED": ("#f39c12", "Auto-starts when the phone reboots"),
        "SCHEDULE_EXACT_ALARM": ("#f39c12", "Can fire exact alarms"),
        "USE_BIOMETRIC": ("#f39c12", "Uses fingerprint / face unlock"),
        "USE_FINGERPRINT": ("#f39c12", "Uses the fingerprint sensor"),
        "BLUETOOTH_SCAN": ("#f39c12", "Scans for nearby Bluetooth devices"),
        "NEARBY_WIFI_DEVICES": ("#f39c12", "Connects to nearby Wi-Fi devices"),
        "READ_CALENDAR": ("#f39c12", "Reads calendar events"),
        "WRITE_CALENDAR": ("#f39c12", "Modifies calendar events"),
        "READ_VOICEMAIL": ("#f39c12", "Reads voicemail messages"),
        "FOREGROUND_SERVICE": ("#58a6ff", "Runs as a foreground service (keeps working in background)"),
        "WAKE_LOCK": ("#58a6ff", "Keeps the screen on / prevents the device from sleeping"),
        "INTERNET": ("#58a6ff", "Access to the internet"),
        "ACCESS_NETWORK_STATE": ("#58a6ff", "Checks network connection status"),
        "CHANGE_NETWORK_STATE": ("#58a6ff", "Changes network state"),
        "ACCESS_WIFI_STATE": ("#58a6ff", "Checks Wi-Fi status"),
        "CHANGE_WIFI_STATE": ("#58a6ff", "Turns Wi-Fi on / off"),
        "BLUETOOTH": ("#58a6ff", "Connects to paired Bluetooth devices"),
        "BLUETOOTH_CONNECT": ("#58a6ff", "Connects to paired Bluetooth devices (Android 12+)"),
        "BLUETOOTH_ADVERTISE": ("#58a6ff", "Makes the device visible to nearby Bluetooth devices"),
        "VIBRATE": ("#58a6ff", "Controls the vibration motor"),
        "NFC": ("#58a6ff", "Reads / controls NFC (payments, tags)"),
        "MODIFY_AUDIO_SETTINGS": ("#58a6ff", "Adjusts audio volume / settings"),
        "SET_ALARM": ("#58a6ff", "Sets alarms"),
        "POST_NOTIFICATIONS": ("#58a6ff", "Shows notifications"),
        "EXPAND_STATUS_BAR": ("#58a6ff", "Expands / collapses the status bar"),
        "KILL_BACKGROUND_PROCESSES": ("#58a6ff", "Can stop other apps' background processes"),
        "FLASHLIGHT": ("#58a6ff", "Controls the camera flashlight"),
        "INSTALL_SHORTCUT": ("#58a6ff", "Adds shortcuts to the home screen"),
        "UNINSTALL_SHORTCUT": ("#58a6ff", "Removes shortcuts from the home screen"),
        "REORDER_TASKS": ("#58a6ff", "Rearranges recent-apps order"),
        "GET_TASKS": ("#58a6ff", "Sees recently used apps (legacy)"),
        "READ_SYNC_SETTINGS": ("#58a6ff", "Reads account sync settings"),
        "WRITE_SYNC_SETTINGS": ("#58a6ff", "Modifies account sync settings"),
        "USE_SIP": ("#58a6ff", "Uses VoIP calls (SIP)"),
    }

    def action_sec_apk_info(self):
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Check an app to view its APK info.", "#f39c12")
            return
        self._sec_show_apk_info(pkgs[0])

    def _sec_show_apk_info(self, pkg):
        entry = next((e for e in self.sec_packages if e["id"] == pkg), None)
        label = entry["label"] if entry else self._resolve_label(pkg)
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"📋 APK Info — {label}")
        dialog.geometry("580x600")
        dialog.transient(self)
        dialog.grab_set()
        outer = ctk.CTkFrame(dialog, fg_color="#111622", corner_radius=12, border_width=1, border_color="#303645")
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        icon = self._sec_get_icon(pkg, label)
        ctk.CTkLabel(outer, text="", image=icon, width=48, height=48).pack(pady=(16, 4))
        ctk.CTkLabel(outer, text=label, font=ctk.CTkFont(size=14, weight="bold"), text_color="#e6edf3").pack()
        ctk.CTkLabel(outer, text=pkg, font=ctk.CTkFont(size=9), text_color="#8b949e").pack(pady=(2, 6))
        meta = ctk.CTkLabel(outer, text="⏳ Fetching details...", font=ctk.CTkFont(size=10), text_color="#c9d1d9", wraplength=520, justify="left")
        meta.pack(padx=16, pady=2)
        ctk.CTkLabel(outer, text="Permissions", font=ctk.CTkFont(size=11, weight="bold"), text_color="#58a6ff").pack(pady=(8, 2))
        scroll = ctk.CTkScrollableFrame(outer, fg_color="#0d1117", corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        def adb(args):
            return subprocess.run([self.scrcpy_adb] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=20).stdout

        def fetch():
            try:
                out = adb(["shell", "dumpsys", "package", pkg])
                meta_lines = []
                vm = re.search(r"versionName=(\S+)", out)
                vc = re.search(r"versionCode=(\d+)", out)
                tgt = re.search(r"targetSdk(?:Version)?=(\d+)", out)
                mn = re.search(r"minSdk(?:Version)?=(\d+)", out)
                fi = re.search(r"firstInstallTime=([^\n]+)", out)
                lu = re.search(r"lastUpdateTime=([^\n]+)", out)
                if vm: meta_lines.append(f"Version   : {vm.group(1)}")
                if vc: meta_lines.append(f"Build     : {vc.group(1)}")
                if mn and tgt: meta_lines.append(f"SDK       : min {mn.group(1)} / target {tgt.group(1)}")
                elif tgt: meta_lines.append(f"SDK       : target {tgt.group(1)}")
                if fi: meta_lines.append(f"Installed : {fi.group(1).strip()}")
                if lu: meta_lines.append(f"Updated   : {lu.group(1).strip()}")
                try:
                    pr = adb(["shell", "pm", "path", pkg])
                    apk = next((l[len("package:"):].strip() for l in pr.splitlines() if l.startswith("package:")), None)
                    if apk:
                        lr = adb(["shell", "ls", "-l", apk])
                        tokens = lr.split()
                        idx = next((i for i, t in enumerate(tokens) if re.match(r"\d{4}-\d{2}-\d{2}", t)), None)
                        if idx and idx > 0 and tokens[idx - 1].isdigit():
                            meta_lines.append(f"Size      : {self._format_sec_bytes(int(tokens[idx - 1]))}")
                except Exception:
                    pass
                ir = adb(["shell", "cmd", "package", "get-install-source", pkg]).strip()
                if not ir or "Exception" in ir or "Unknown" in ir.lower():
                    ir = adb(["shell", "pm", "get-installer", pkg]).strip()
                if ir and ir.lower() not in ("none", "unknown", "null"):
                    pretty = {"com.android.vending": "Google Play Store", "com.sec.android.app.samsungapps": "Galaxy Store",
                              "com.huawei.appmarket": "AppGallery", "com.xiaomi.market": "GetApps",
                              "com.oppo.market": "OPPO Store", "com.heytap.market": "HeyTap Store",
                              "com.bbk.appstore": "vivo App Store", "com.transsion.market": "Palm Store", "adb": "ADB / sideload"}.get(ir, ir)
                    meta_lines.append(f"Installer : {pretty} {'🚨' if ir == 'adb' else ''}")

                granted = dict(re.findall(r"^\s*([a-z0-9_.]+\.permission\.[A-Z0-9_]+):\s*granted=(true|false)", out, re.M))
                requested = set(re.findall(r"^\s*([a-z0-9_.]+\.permission\.[A-Z0-9_]+)\s*$", out, re.M))
                requested |= set(granted.keys())

                rows = []
                for perm in sorted(requested):
                    if perm.startswith("android.permission."):
                        short = perm[len("android.permission."):]
                        display = short.replace("_", " ").title()
                    else:
                        short = perm
                        display = perm
                    color, meaning = self._PERM_INFO.get(short, ("#8b949e", "Custom or uncommon permission"))
                    if short not in self._PERM_INFO and not perm.startswith("android.permission."):
                        meaning = "Vendor / app-specific permission"
                    if perm in granted:
                        status = ("granted", "#2ecc71") if granted[perm] == "true" else ("revoked", "#f39c12")
                    else:
                        status = ("declared", "#8b949e")
                    rows.append((display, color, meaning, status))

                def apply():
                    meta.configure(text="\n".join(meta_lines), text_color="#c9d1d9")
                    for child in scroll.winfo_children():
                        child.destroy()
                    if not rows:
                        ctk.CTkLabel(scroll, text="No permissions found.", text_color="#8b949e").pack(pady=10)
                    for display, color, meaning, (status, scolor) in rows:
                        row = ctk.CTkFrame(scroll, fg_color="#161b22", corner_radius=6)
                        row.pack(fill="x", padx=4, pady=3)
                        head = ctk.CTkFrame(row, fg_color="transparent")
                        head.pack(fill="x", padx=8, pady=(5, 0))
                        ctk.CTkLabel(head, text="●", text_color=color, font=ctk.CTkFont(size=10)).pack(side="left")
                        ctk.CTkLabel(head, text=display, font=ctk.CTkFont(size=10, weight="bold"), text_color="#e6edf3").pack(side="left", padx=6)
                        ctk.CTkLabel(head, text=status, font=ctk.CTkFont(size=8), text_color=scolor).pack(side="right", padx=6)
                        ctk.CTkLabel(row, text=meaning, font=ctk.CTkFont(size=9), text_color="#8b949e", wraplength=480, justify="left").pack(fill="x", padx=8, pady=(0, 6))
                self.after(0, apply)
            except Exception as e:
                self.after(0, lambda: meta.configure(text=f"Error: {e}", text_color="#e74c3c"))
        threading.Thread(target=fetch, daemon=True).start()
        ctk.CTkButton(dialog, text="❌ Close", width=100, fg_color="#3a3a3a", hover_color="#4a4a4a", command=dialog.destroy).pack(pady=(0, 12))

    def action_sec_show_icons(self):
        def run_cmd(args, timeout=15):
            return subprocess.run([self.scrcpy_adb] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)

        def worker():
            try:
                r = run_cmd(["shell", "pm", "path", "com.drox.apkiconhelper"])
                if "package:" not in r.stdout:
                    helper = os.path.join(get_bundle_dir(), "ApkIconHelper.apk")
                    if not os.path.isfile(helper):
                        self.after(0, lambda: self._sec_log("[GeloTech] Missing helper APK: ApkIconHelper.apk", "#e74c3c"))
                        return
                    self.after(0, lambda: self._sec_log("[GeloTech] Installing APKIconHelper on device...", "#58a6ff"))
                    inst = run_cmd(["install", "-r", "-t", helper], 60)
                    if "Success" not in (inst.stdout + inst.stderr):
                        self.after(0, lambda: self._sec_log(f"[GeloTech] Helper install failed: {inst.stdout[-200:]}", "#e74c3c"))
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
                self._app_labels = None
                self.after(0, lambda: self._sec_render_rows())
                self.after(0, lambda: self._sec_log(f"[GeloTech] Icons synced: {count} apps (helper closed automatically).", "#2ecc71"))
            except Exception as e:
                self.after(0, lambda: self._sec_log(f"[GeloTech] Icon sync error: {e}", "#e74c3c"))
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
                    self.after(0, lambda p=pkg: log(f"Restore error {p}: {e}", "#e74c3c"))
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
                state = "✅ Device connected"
                try:
                    d = subprocess.run([self.scrcpy_adb, "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                    lines = d.stdout.splitlines()
                    if len(lines) < 2 or "device" not in lines[1]:
                        state = "🔐 No device (check USB debugging)"
                except Exception:
                    state = "🔐 No device (check USB debugging)"
                def apply():
                    self.sec_dev_model.configure(text=f"Model: {vals['model']}", text_color="#ffd27f")
                    self.sec_dev_android.configure(text=f"Android: {vals['android']}", text_color="#ffd27f")
                    self.sec_dev_patch.configure(text=f"Security Patch: {vals['patch']}", text_color="#ffd27f")
                    self.sec_dev_build.configure(text=f"Build ID: {vals['build']}", text_color="#ffd27f")
                    if "connected" in state:
                        self.sec_dev_conn.configure(text=state, text_color="#2ecc71")
                    else:
                        self.sec_dev_conn.configure(text=state, text_color="#e74c3c")
                self.after(0, apply)
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

