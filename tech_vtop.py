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


class VtOpsMixin:
    def action_vt_upload_apk(self):
        if not self._can("virustotal"):
            self.log_message("[VT] Permission denied: VirusTotal is disabled for this account.")
            return
        # Ask for package name instead of file picker
        dialog = ctk.CTkInputDialog(text="Enter the package name to pull & upload to VirusTotal:", title="Pull APK from Device")
        pkg = dialog.get_input()
        if not pkg or not pkg.strip():
            return
        pkg = pkg.strip()
        self.log_message(f"[VT] Pulling APK for {pkg}...")
        self.vt_status_label.configure(text=f"Pulling {pkg}...", text_color="#f39c12")

        def worker():
            try:
                # Get APK path from device
                path_res = subprocess.run([self.scrcpy_adb, "shell", "pm", "path", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                apk_paths = [l[len("package:"):].strip() for l in path_res.stdout.splitlines() if l.startswith("package:")]
                if not apk_paths:
                    self.after(0, lambda: self.log_message(f"[VT ERROR] Package '{pkg}' not found on device."))
                    self.after(0, lambda: self.vt_status_label.configure(text="Package not found", text_color="#e74c3c"))
                    return
                apk_path = apk_paths[0]

                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".apk")
                tmp.close()
                pull_res = subprocess.run([self.scrcpy_adb, "pull", apk_path, tmp.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
                if pull_res.returncode != 0:
                    self.after(0, lambda: self.log_message(f"[VT ERROR] Failed to pull APK: {pull_res.stderr}"))
                    self.after(0, lambda: self.vt_status_label.configure(text="Pull failed", text_color="#e74c3c"))
                    try: os.unlink(tmp.name)
                    except: pass
                    return

                filepath = tmp.name
                filename = f"{pkg}.apk"
                self.after(0, lambda: self.log_message(f"[VT] Pulled {apk_path} ({os.path.getsize(filepath)} bytes)"))
                self.after(0, lambda: self.vt_status_label.configure(text="Hashing...", text_color="#f39c12"))

                with open(filepath, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                try: os.unlink(filepath)
                except: pass

                # Check if already in VT database
                url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
                headers = {"x-apikey": self.virustotal_api_key}
                resp = requests.get(url, headers=headers, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                    self.after(0, lambda: self.add_vt_result(pkg, file_hash, stats, "pulled"))
                elif resp.status_code == 404:
                    # Upload for scanning - re-pull APK since we deleted it
                    tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".apk")
                    tmp2.close()
                    subprocess.run([self.scrcpy_adb, "pull", apk_path, tmp2.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
                    upload_url = "https://www.virustotal.com/api/v3/files"
                    with open(tmp2.name, "rb") as f:
                        files = {"file": (filename, f, "application/vnd.android.package-archive")}
                        upload_resp = requests.post(upload_url, headers=headers, files=files, timeout=60)
                    try: os.unlink(tmp2.name)
                    except: pass

                    if upload_resp.status_code == 200:
                        analysis_id = upload_resp.json().get("data", {}).get("id")
                        self.after(0, lambda: self.log_message(f"[VT] Uploaded {pkg}. Analysis ID: {analysis_id}. Waiting..."))
                        self.after(0, lambda: self.vt_status_label.configure(text="Analyzing...", text_color="#f39c12"))
                        self.poll_vt_analysis(analysis_id, pkg, file_hash)
                    else:
                        self.after(0, lambda: self.log_message(f"[VT ERROR] Upload failed: {upload_resp.text}"))
                else:
                    self.after(0, lambda: self.log_message(f"[VT ERROR] {resp.status_code}: {resp.text}"))
            except Exception as e:
                self.after(0, lambda e=e: self.log_message(f"[VT ERROR] {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def poll_vt_analysis(self, analysis_id, filename, file_hash):
        def worker():
            url = f"https://www.virustotal.com/api/v3/analyses/{analysis_id}"
            headers = {"x-apikey": self.virustotal_api_key}
            for _ in range(30):
                try:
                    resp = requests.get(url, headers=headers, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json()
                        status = data.get("data", {}).get("attributes", {}).get("status")
                        if status == "completed":
                            stats = data.get("data", {}).get("attributes", {}).get("stats", {})
                            self.after(0, lambda: self.add_vt_result(filename, file_hash, stats, "file"))
                            return
                    time.sleep(5)
                except:
                    time.sleep(5)
            self.after(0, lambda: self.log_message(f"[VT] Timeout waiting for {filename} analysis"))
        threading.Thread(target=worker, daemon=True).start()

    def action_vt_scan_installed(self):
        if not self._can("virustotal"):
            self.log_message("[VT] Permission denied: VirusTotal is disabled for this account.")
            return
        if self.background_scan_running:
            return
        self.background_scan_running = True
        self.vt_scan_results = {}
        self.vt_selected = {}
        self.vt_scan_btn.configure(state="disabled", text="Scanning...")
        self.vt_scan_running_btn.configure(state="disabled")
        self.vt_status_label.configure(text="Scanning installed packages...", text_color="#f39c12")
        self.vt_progress_frame.grid()
        self.vt_stop_btn.configure(state="normal", text="Stop")
        self.vt_progress_bar.set(0)
        self.vt_progress_label.configure(text="Enumerating packages...")
        self.vt_scanning_label.configure(text="Initializing...")
        self.log_message("[VT] Scanning installed packages...")

        def get_apk_hash(pkg, apk_path):
            """Compute SHA-256 of an APK on-device via sha256sum."""
            try:
                result = subprocess.run([self.scrcpy_adb, "shell", "sha256sum", apk_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                if result.returncode == 0 and result.stdout:
                    return result.stdout.split()[0].strip()
            except:
                pass
            return None

        def worker():
            try:
                res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                installed = [line[len("package:"):].strip() for line in res.stdout.splitlines() if line.startswith("package:")]

                total = len(installed)
                scanned = 0
                malicious = 0
                for i, pkg in enumerate(installed):
                    if not self.background_scan_running:
                        break
                    path_res = subprocess.run([self.scrcpy_adb, "shell", "pm", "path", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                    apk_paths = [l[len("package:"):].strip() for l in path_res.stdout.splitlines() if l.startswith("package:")]
                    if not apk_paths:
                        continue

                    file_hash = get_apk_hash(pkg, apk_paths[0])
                    if not file_hash:
                        continue

                    url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
                    headers = {"x-apikey": self.virustotal_api_key}
                    vt_resp = requests.get(url, headers=headers, timeout=20)

                    if vt_resp.status_code == 200:
                        stats = vt_resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                        self.vt_scan_results[pkg] = {"hash": file_hash, "stats": stats, "type": "installed"}
                        scanned += 1
                        if stats.get("malicious", 0) > 0 or stats.get("suspicious", 0) > 0:
                            malicious += 1
                    elif vt_resp.status_code == 404:
                        self.vt_scan_results[pkg] = {"hash": file_hash, "stats": {}, "type": "installed", "not_found": True}
                        scanned += 1

                    progress = (i + 1) / total if total else 0
                    if i % 2 == 0 or i == total - 1:
                        self.after(0, lambda c=i+1, t=total, p=progress, pkg=pkg, sc=scanned, mc=malicious:
                            self._update_vt_progress(c, t, p, pkg, sc, mc))

                self.after(0, lambda: self.set_vt_results(scanned, malicious))
            except Exception as e:
                self.after(0, lambda e=e: self.log_message(f"[VT ERROR] {e}"))
            finally:
                self.background_scan_running = False
                self.after(0, lambda: self.vt_scan_btn.configure(state="normal", text="Scan Phone"))
                self.after(0, lambda: self.vt_scan_running_btn.configure(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def action_vt_scan_running(self):
        """Scan only currently running apps via VirusTotal hash lookup."""
        if self.background_scan_running:
            return
        self.background_scan_running = True
        self.vt_scan_results = {}
        self.vt_selected = {}
        self.vt_scan_btn.configure(state="disabled")
        self.vt_scan_running_btn.configure(state="disabled", text="Running...")
        self.vt_status_label.configure(text="Scanning running apps...", text_color="#f39c12")
        self.vt_progress_frame.grid()
        self.vt_stop_btn.configure(state="normal", text="Stop")
        self.vt_progress_bar.set(0)
        self.vt_progress_label.configure(text="Getting running processes...")
        self.vt_scanning_label.configure(text="Initializing...")
        self.log_message("[VT] Scanning running apps...")

        def get_apk_hash(pkg, apk_path):
            try:
                result = subprocess.run([self.scrcpy_adb, "shell", "sha256sum", apk_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                if result.returncode == 0 and result.stdout:
                    return result.stdout.split()[0].strip()
            except:
                pass
            return None

        def worker():
            try:
                # Get running processes
                ps_res = subprocess.run([self.scrcpy_adb, "shell", "ps", "-A", "-o", "NAME"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                running_names = set()
                for line in ps_res.stdout.splitlines():
                    line = line.strip()
                    if '.' in line and not line.startswith('[') and len(line) > 5:
                        running_names.add(line)

                pm_res = subprocess.run([self.scrcpy_adb, "shell", "pm", "list", "packages"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                installed = [line[len("package:"):].strip() for line in pm_res.stdout.splitlines() if line.startswith("package:")]
                to_scan = [p for p in installed if p in running_names]
                self.log_message(f"[VT] Found {len(to_scan)} running packages to scan")

                total = len(to_scan)
                scanned = 0
                malicious = 0
                for i, pkg in enumerate(to_scan):
                    if not self.background_scan_running:
                        break
                    path_res = subprocess.run([self.scrcpy_adb, "shell", "pm", "path", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                    apk_paths = [l[len("package:"):].strip() for l in path_res.stdout.splitlines() if l.startswith("package:")]
                    if not apk_paths:
                        continue

                    file_hash = get_apk_hash(pkg, apk_paths[0])
                    if not file_hash:
                        continue

                    url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
                    headers = {"x-apikey": self.virustotal_api_key}
                    vt_resp = requests.get(url, headers=headers, timeout=20)

                    if vt_resp.status_code == 200:
                        stats = vt_resp.json().get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
                        self.vt_scan_results[pkg] = {"hash": file_hash, "stats": stats, "type": "running"}
                        scanned += 1
                        if stats.get("malicious", 0) > 0 or stats.get("suspicious", 0) > 0:
                            malicious += 1
                    elif vt_resp.status_code == 404:
                        self.vt_scan_results[pkg] = {"hash": file_hash, "stats": {}, "type": "running", "not_found": True}
                        scanned += 1

                    progress = (i + 1) / total if total else 0
                    self.after(0, lambda c=i+1, t=total, p=progress, pkg=pkg, sc=scanned, mc=malicious:
                        self._update_vt_progress(c, t, p, pkg, sc, mc))

                self.after(0, lambda: self.set_vt_results(scanned, malicious))
            except Exception as e:
                self.after(0, lambda e=e: self.log_message(f"[VT ERROR] {e}"))
            finally:
                self.background_scan_running = False
                self.after(0, lambda: self.vt_scan_btn.configure(state="normal", text="Scan Phone"))
                self.after(0, lambda: self.vt_scan_running_btn.configure(state="normal", text="Scan Running"))

        threading.Thread(target=worker, daemon=True).start()

    def _update_vt_progress(self, count, total, progress, current_pkg, scanned, malicious):
        self.vt_progress_bar.set(progress)
        self.vt_progress_label.configure(text=f"Scanned {count}/{total}")
        display = current_pkg if len(current_pkg) < 45 else current_pkg[:42] + "..."
        self.vt_scanning_label.configure(text=f"Checking: {display}")
        self.vt_scanned_label.configure(text=f"Scanned: {scanned}")
        self.vt_malicious_label.configure(text=f"Malicious: {malicious}")

    def action_vt_stop(self):
        self.background_scan_running = False
        self.vt_stop_btn.configure(state="disabled", text="Stopping...")
        self.log_message("[VT] Scan stopped by user.")
        self.after(500, lambda: self.vt_stop_btn.configure(state="normal", text="Stop"))

    def set_vt_results(self, scanned, malicious):
        self.vt_scanned_label.configure(text=f"Scanned: {scanned}")
        self.vt_malicious_label.configure(text=f"Malicious: {malicious}")
        self.vt_status_label.configure(text="Done", text_color="#2ecc71")
        self.vt_progress_frame.grid_remove()
        self.vt_stop_btn.configure(state="normal", text="Stop")
        self.vt_scan_btn.configure(state="normal", text="Scan Phone")
        self.vt_scan_running_btn.configure(state="normal", text="Scan Running")
        self.render_vt_rows()

    def render_vt_rows(self):
        for child in self.vt_rows_frame.winfo_children():
            child.destroy()

        fonts = self._fonts
        for row, (pkg, data) in enumerate(self.vt_scan_results.items()):
            rf = ctk.CTkFrame(self.vt_rows_frame, fg_color="#1b232d" if row % 2 else "#222c37", corner_radius=4)
            rf.grid(row=row, column=0, sticky="ew", pady=1)
            rf.grid_columnconfigure(0, minsize=42, weight=0)
            rf.grid_columnconfigure(1, minsize=250, weight=5)
            rf.grid_columnconfigure(2, minsize=100, weight=0)
            rf.grid_columnconfigure(3, minsize=100, weight=0)
            rf.grid_columnconfigure(4, minsize=300, weight=0)

            self.vt_selected[pkg] = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(rf, text="", width=30, variable=self.vt_selected[pkg], border_color="#93a2b1").grid(row=0, column=0, padx=8, pady=10)

            stats = data.get("stats", {})
            malicious = stats.get("malicious", 0)
            suspicious = stats.get("suspicious", 0)
            undetected = stats.get("undetected", 0)
            harmless = stats.get("harmless", 0)
            total = malicious + suspicious + undetected + harmless

            if data.get("not_found"):
                detection_text = "Not in VT"
                detection_color = "#66727e"
            elif malicious > 0:
                detection_text = f"MALICIOUS ({malicious})"
                detection_color = "#c0392b"
            elif suspicious > 0:
                detection_text = f"SUSPICIOUS ({suspicious})"
                detection_color = "#d35400"
            elif total > 0:
                detection_text = f"Clean ({harmless}/{total})"
                detection_color = "#27ae60"
            else:
                detection_text = "Unknown"
                detection_color = "#66727e"

            ctk.CTkLabel(rf, text=pkg, anchor="w", font=fonts["row_name"], text_color="#edf3f8").grid(row=0, column=1, padx=6, pady=6, sticky="ew")
            ctk.CTkLabel(rf, text=detection_text, width=90, height=26, fg_color=detection_color, corner_radius=8, font=fonts["row_badge"]).grid(row=0, column=2, padx=6, pady=10)
            ctk.CTkLabel(rf, text=f"{malicious}/{total}" if total else "—", width=90, height=26, fg_color="#34495e", corner_radius=8, font=fonts["row_badge"]).grid(row=0, column=3, padx=6, pady=10)

            detail = f"MD: {malicious} | SP: {suspicious} | HD: {harmless} | UD: {undetected}" if total else "Not scanned"
            ctk.CTkLabel(rf, text=detail, anchor="w", font=fonts["row_desc"], text_color="#d8e0e7").grid(row=0, column=4, padx=6, pady=8, sticky="ew")

    def action_vt_selected(self, operation):
        if not self._can("virustotal"):
            self.log_message("[VT] Permission denied: VirusTotal is disabled for this account.")
            return
        pkgs = [pid for pid, var in self.vt_selected.items() if var.get()]
        if not pkgs:
            self.log_message("[VT] Select at least one package.")
            return
        self._confirm_and_run_debloat_operation(pkgs, operation)

    def clear_vt_selection(self):
        for var in self.vt_selected.values():
            var.set(False)
        self.render_vt_rows()

    def add_vt_result(self, name, file_hash, stats, ftype):
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        undetected = stats.get("undetected", 0)
        harmless = stats.get("harmless", 0)
        total = malicious + suspicious + undetected + harmless

        if malicious > 0:
            detection_text = f"MALICIOUS ({malicious})"
            detection_color = "#c0392b"
        elif suspicious > 0:
            detection_text = f"SUSPICIOUS ({suspicious})"
            detection_color = "#d35400"
        elif total > 0:
            detection_text = f"Clean ({harmless}/{total})"
            detection_color = "#27ae60"
        else:
            detection_text = "Unknown"
            detection_color = "#66727e"

        self.vt_scan_results[name] = {"hash": file_hash, "stats": stats, "type": ftype}
        self.vt_selected[name] = ctk.BooleanVar(value=False)
        self.render_vt_rows()
        self.vt_status_label.configure(text="Done", text_color="#2ecc71")
        self.log_message(f"[VT] {name}: {detection_text}")

    # ----------------------------------------------------
    # DEVICE OPERATIONAL OPERATIONS ENGINE
    # ----------------------------------------------------
