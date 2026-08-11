# -*- coding: utf-8 -*-
"""Runtime hardening layer for GeloTech.

This module is intentionally isolated so safety/reliability improvements can be
reviewed independently from the existing UI/ADB/scrcpy implementation.
It does not change authentication or embedded credentials.
"""
from __future__ import annotations

import datetime as _dt
import glob
import hashlib
import json
import os
import platform
import re
import subprocess as _sp
import threading
import time
import webbrowser
from pathlib import Path

import customtkinter as ctk
from tkinter import messagebox

from tech_common import get_settings_dir, load_banking_apps


_APPLIED = False


def _log_path() -> Path:
    root = Path(get_settings_dir()) / "logs"
    root.mkdir(parents=True, exist_ok=True)
    return root / "app.log"


def _append_log(line: str) -> None:
    try:
        path = _log_path()
        if path.exists() and path.stat().st_size > 2 * 1024 * 1024:
            old = path.with_suffix(".1.log")
            try:
                old.unlink(missing_ok=True)
            except Exception:
                pass
            path.replace(old)
        with path.open("a", encoding="utf-8", errors="replace") as f:
            f.write(line.rstrip() + "\n")
    except Exception:
        pass


def _redact(text: str) -> str:
    text = str(text or "")
    patterns = [
        (r"github_pat_[A-Za-z0-9_]+", "<REDACTED_GITHUB_TOKEN>"),
        (r"x-apikey[:= ]+[A-Za-z0-9_-]+", "x-apikey=<REDACTED>"),
        (r"(?i)(smtp_password|password|token|api[_-]?key)\s*[:=]\s*[^\s,]+", r"\1=<REDACTED>"),
    ]
    for pattern, repl in patterns:
        text = re.sub(pattern, repl, text)
    return text


def _uad_level(self, pkg):
    try:
        rec = self._build_uad_lookup().get(pkg) or {}
        return str(rec.get("removal") or "Unknown")
    except Exception:
        return "Unknown"


def _safe_filter(self, packages, operation):
    packages = list(dict.fromkeys(packages or []))
    banking = load_banking_apps()
    excluded = set()
    try:
        if operation in ("uninstall", "disable"):
            excluded = self._load_excluded_uninstall()
        elif operation == "clean":
            excluded = self._load_excluded_clean()
    except Exception:
        pass

    allowed, blocked = [], []
    for pkg in packages:
        if pkg in banking:
            blocked.append((pkg, "protected banking app"))
            continue
        if pkg in excluded:
            blocked.append((pkg, "excluded by your GeloTech settings"))
            continue
        level = _uad_level(self, pkg)
        if getattr(self, "safe_mode", True) and level in ("Expert", "Unsafe"):
            blocked.append((pkg, f"{level} removal level is blocked by Safe Mode"))
            continue
        allowed.append(pkg)
    return allowed, blocked


def _install_safe_mode_ui(self):
    if getattr(self, "_hardening_ui_ready", False):
        return
    self.safe_mode = True
    self._hardening_ui_ready = True
    try:
        self._safe_mode_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="🛡 Safe Mode: ON",
            height=28,
            fg_color="#14532d",
            hover_color="#166534",
            text_color="#dcfce7",
            font=ctk.CTkFont(size=10, weight="bold"),
            command=lambda: _toggle_safe_mode(self),
        )
        self._safe_mode_btn.grid(row=998, column=0, padx=10, pady=(6, 2), sticky="ew")

        self._diagnostic_btn = ctk.CTkButton(
            self.sidebar_frame,
            text="🧰 Generate Diagnostic Report",
            height=26,
            fg_color="#10161e",
            hover_color="#1f6feb",
            font=ctk.CTkFont(size=9, weight="bold"),
            command=lambda: generate_diagnostic_report(self),
        )
        self._diagnostic_btn.grid(row=999, column=0, padx=10, pady=(0, 6), sticky="ew")

        try:
            btn = self.page_nav_btns.get("Adware Remover")
            if btn is not None:
                btn.configure(text="🧹  App Cleaner")
            btn = self.page_nav_btns.get("Monitor Running Apps")
            if btn is not None:
                btn.configure(text="🔎  Monitor Apps")
            btn = self.page_nav_btns.get("Block Ads via DNS")
            if btn is not None:
                btn.configure(text="🌐  Block Ads DNS")
        except Exception:
            pass
    except Exception:
        pass


def _toggle_safe_mode(self):
    self.safe_mode = not getattr(self, "safe_mode", True)
    btn = getattr(self, "_safe_mode_btn", None)
    if btn is not None:
        if self.safe_mode:
            btn.configure(text="🛡 Safe Mode: ON", fg_color="#14532d", hover_color="#166534", text_color="#dcfce7")
            self.log_message("[SECURITY] Safe Mode enabled. Expert/Unsafe destructive operations are blocked.")
        else:
            btn.configure(text="⚠ Safe Mode: OFF", fg_color="#78350f", hover_color="#92400e", text_color="#ffedd5")
            self.log_message("[SECURITY] Safe Mode disabled. Expert/Unsafe operations require extra confirmation.")


def _patch_settings_save(cls):
    if getattr(cls, "_hardening_settings_patched", False):
        return

    def atomic_save(self, data):
        path = Path(get_settings_dir()) / "exclusions.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {}
        for key, value in (data or {}).items():
            if key == "users":
                continue
            if isinstance(value, (list, set)):
                payload[key] = sorted(set(value))
            elif isinstance(value, (dict, str, bool, int, float)) or value is None:
                payload[key] = value
        tmp = path.with_suffix(".json.tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except Exception:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    cls._save_settings = atomic_save
    cls._hardening_settings_patched = True


def _patch_logging(cls):
    if getattr(cls, "_hardening_logging_patched", False):
        return
    original = cls.log_message

    def hardened_log(self, message):
        try:
            _append_log(f"{_dt.datetime.now().isoformat(timespec='seconds')} {_redact(message)}")
        except Exception:
            pass
        return original(self, message)

    cls.log_message = hardened_log
    cls._hardening_logging_patched = True


def _patch_destructive_ops(cls):
    # Security-page uninstall/disable/clean all get the same defense-in-depth gate.
    for name, operation in (("_sec_run_uninstall", "uninstall"), ("_sec_run_disable", "disable"), ("_sec_run_clean", "clean")):
        original = getattr(cls, name, None)
        marker = f"_hardening_{name}_patched"
        if original is None or getattr(cls, marker, False):
            continue

        def make_wrapper(orig, op):
            def wrapped(self, packages, *args, **kwargs):
                allowed, blocked = _safe_filter(self, packages, op)
                for pkg, reason in blocked:
                    try:
                        self._sec_log(f"[GeloTech] Skipped {pkg}: {reason}.", "#f39c12")
                    except Exception:
                        self.log_message(f"[SECURITY] Skipped {pkg}: {reason}.")
                if not allowed:
                    try:
                        self._sec_status("No selected apps are eligible for this operation.", "#f39c12")
                    except Exception:
                        pass
                    return
                return orig(self, allowed, *args, **kwargs)
            return wrapped

        setattr(cls, name, make_wrapper(original, operation))
        setattr(cls, marker, True)

    original_confirm = getattr(cls, "_confirm_and_run_debloat_operation", None)
    if original_confirm is not None and not getattr(cls, "_hardening_confirm_patched", False):
        def hardened_confirm(self, packages, operation):
            if operation in ("uninstall", "disable"):
                allowed, blocked = _safe_filter(self, packages, operation)
                for pkg, reason in blocked:
                    self.log_message(f"[SECURITY] Blocked {pkg}: {reason}.")
                if not allowed:
                    self.log_message("[SECURITY] No selected packages are eligible for this operation.")
                    return
                packages = allowed
            return original_confirm(self, packages, operation)
        cls._confirm_and_run_debloat_operation = hardened_confirm
        cls._hardening_confirm_patched = True


def _patch_popup_cleanup(cls):
    if getattr(cls, "_hardening_popup_patched", False):
        return

    def remove_popup_ads(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: App Cleaner is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to process. Check the apps you want to clean.", "#f39c12")
            return
        if not self._sec_typed_confirm(
            "Remove Suspected Adware",
            f"This will process {len(pkgs)} selected app(s).\n\n"
            "1. Clear app data for eligible apps.\n"
            "2. After the clear phase finishes, uninstall only the apps that cleared successfully.\n\n"
            "Protected banking apps, excluded apps, and Safe Mode blocked apps are skipped.\n"
            "Clearing app data may sign you out and delete local app data.",
        ):
            return

        def worker():
            eligible, blocked = _safe_filter(self, pkgs, "uninstall")
            for pkg, reason in blocked:
                self.after(0, lambda p=pkg, r=reason: self._sec_log(f"[GeloTech] Skipped {p}: {r}.", "#f39c12"))
            cleared = []
            for pkg in eligible:
                try:
                    r = __import__("tech_common").subprocess.run(
                        [self.scrcpy_adb, "shell", "pm", "clear", pkg],
                        stdout=__import__("tech_common").subprocess.PIPE,
                        stderr=__import__("tech_common").subprocess.PIPE,
                        text=True,
                        timeout=20,
                    )
                    if r.returncode == 0 and "Success" in (r.stdout + r.stderr):
                        cleared.append(pkg)
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Cleared data: {p}", "#2ecc71"))
                    else:
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Clear failed: {p}", "#e74c3c"))
                except Exception as e:
                    self.after(0, lambda p=pkg, e=e: self._sec_log(f"[GeloTech] Clear error {p}: {e}", "#e74c3c"))

            removed = []
            for pkg in cleared:
                try:
                    r = __import__("tech_common").subprocess.run(
                        [self.scrcpy_adb, "shell", "pm", "uninstall", "--user", "0", pkg],
                        stdout=__import__("tech_common").subprocess.PIPE,
                        stderr=__import__("tech_common").subprocess.PIPE,
                        text=True,
                        timeout=30,
                    )
                    if r.returncode == 0 and "Success" in (r.stdout + r.stderr):
                        removed.append(pkg)
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Removed: {p}", "#2ecc71"))
                    else:
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Remove failed: {p}", "#e74c3c"))
                except Exception as e:
                    self.after(0, lambda p=pkg, e=e: self._sec_log(f"[GeloTech] Remove error {p}: {e}", "#e74c3c"))
            if removed:
                self._record_debloated(removed)
            self.after(0, lambda: self._sec_log(f"[GeloTech] Cleanup finished: {len(cleared)} cleared, {len(removed)} removed.", "#58a6ff"))
            self.after(0, self._sec_refresh_current_list)

        threading.Thread(target=worker, daemon=True).start()

    cls.action_sec_remove_bugs = remove_popup_ads
    cls._hardening_popup_patched = True


def _backup_worker(self, packages):
    if not packages:
        return
    def worker():
        backup_root = Path(get_settings_dir()) / "apk_backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        ok = fail = 0
        adb = __import__("tech_common").subprocess
        for pkg in packages:
            try:
                paths = adb.run([self.scrcpy_adb, "shell", "pm", "path", pkg], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=20)
                apk_paths = [line[len("package:"):].strip() for line in paths.stdout.splitlines() if line.startswith("package:")]
                if not apk_paths:
                    fail += 1
                    self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Backup failed (APK not found): {p}", "#e74c3c"))
                    continue
                stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_dir = backup_root / pkg / stamp
                dest_dir.mkdir(parents=True, exist_ok=True)
                files = []
                for index, remote in enumerate(apk_paths):
                    name = "base.apk" if index == 0 else f"split_{index:02d}.apk"
                    dest = dest_dir / name
                    result = adb.run([self.scrcpy_adb, "pull", remote, str(dest)], stdout=adb.PIPE, stderr=adb.PIPE, timeout=120)
                    if result.returncode != 0 or not dest.is_file():
                        raise RuntimeError((result.stderr or result.stdout or "adb pull failed").strip())
                    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
                    files.append({"name": name, "remote": remote, "sha256": sha})
                manifest = {
                    "schema": 2,
                    "package": pkg,
                    "created": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                    "files": files,
                }
                (dest_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                # Keep a single-APK compatibility copy for older GeloTech builds.
                if len(files) == 1:
                    legacy = backup_root / f"{pkg}.apk"
                    try:
                        legacy.write_bytes((dest_dir / files[0]["name"]).read_bytes())
                    except Exception:
                        pass
                ok += 1
                self.after(0, lambda p=pkg, n=len(files): self._sec_log(f"[GeloTech] Backed up {p} ({n} APK part{'s' if n != 1 else ''}).", "#2ecc71"))
            except Exception as e:
                fail += 1
                self.after(0, lambda p=pkg, e=e: self._sec_log(f"[GeloTech] Backup error {p}: {e}", "#e74c3c"))
        self.after(0, lambda: self._sec_log(f"[GeloTech] Backup finished: {ok} saved, {fail} failed.", "#58a6ff"))
        self.after(0, lambda: self._sec_status(f"Backup finished: {ok} saved, {fail} failed.", "#58a6ff" if not fail else "#e74c3c"))
    threading.Thread(target=worker, daemon=True).start()


def _patch_backup_restore(cls):
    if getattr(cls, "_hardening_backup_patched", False):
        return
    cls._sec_run_backup = _backup_worker

    original_restore = getattr(cls, "_restore_debloated", None)
    if original_restore is not None:
        def restore(self, vars_, debloated, log, dialog):
            picked = [pkg for pkg in debloated if vars_.get(pkg, ctk.BooleanVar(value=False)).get()]
            if not picked:
                log("No packages checked.", "#f39c12")
                return
            def worker():
                restored, failed = [], []
                root = Path(get_settings_dir()) / "apk_backups"
                adb = __import__("tech_common").subprocess
                for pkg in picked:
                    try:
                        # First try Android's existing system package restore.
                        r = adb.run([self.scrcpy_adb, "shell", "cmd", "package", "install-existing", "--user", "0", pkg], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=30)
                        if "Success" in (r.stdout + r.stderr):
                            restored.append(pkg)
                            self.after(0, lambda p=pkg: log(f"Restored system package: {p}", "#2ecc71"))
                            continue

                        candidates = sorted(root.glob(f"{pkg}/*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if not candidates:
                            legacy = root / f"{pkg}.apk"
                            if legacy.is_file():
                                candidates = [legacy]
                        if not candidates:
                            raise FileNotFoundError("No APK backup found")

                        manifest = candidates[0]
                        if manifest.suffix == ".apk":
                            files = [manifest]
                        else:
                            meta = json.loads(manifest.read_text(encoding="utf-8"))
                            files = [manifest.parent / item["name"] for item in meta.get("files", [])]
                        files = [p for p in files if p.is_file()]
                        if not files:
                            raise FileNotFoundError("Backup manifest contains no APK files")
                        for p in files:
                            if manifest.suffix != ".apk":
                                expected = next((x.get("sha256") for x in meta.get("files", []) if x.get("name") == p.name), None)
                                if expected and hashlib.sha256(p.read_bytes()).hexdigest() != expected:
                                    raise ValueError(f"Backup checksum mismatch: {p.name}")
                        if len(files) == 1:
                            r = adb.run([self.scrcpy_adb, "install", "-r", "-d", str(files[0])], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=120)
                        else:
                            r = adb.run([self.scrcpy_adb, "install-multiple", "-r", "-d", *[str(p) for p in files]], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=180)
                        if "Success" not in (r.stdout + r.stderr):
                            raise RuntimeError((r.stderr or r.stdout or "adb install failed").strip())
                        restored.append(pkg)
                        self.after(0, lambda p=pkg, n=len(files): log(f"Restored {p} ({n} APK part{'s' if n != 1 else ''}).", "#2ecc71"))
                    except Exception as e:
                        failed.append(pkg)
                        self.after(0, lambda p=pkg, e=e: log(f"Restore failed: {p} — {e}", "#e74c3c"))
                if restored:
                    remaining = [p for p in debloated if p not in restored]
                    self._save_debloated(remaining)
                self.after(0, lambda: log(f"Restore finished: {len(restored)} ok, {len(failed)} failed.", "#58a6ff"))
                self.after(0, self._sec_render_rows)
            threading.Thread(target=worker, daemon=True).start()
        cls._restore_debloated = restore
    cls._hardening_backup_patched = True


def _patch_dns(cls):
    def apply(self):
        if not self._can("dns"):
            self.log_message("[DNS] Permission denied: Block Ads DNS is disabled for this account.")
            return
        label = self.dns_dropdown.get()
        hostname = self.dns_options.get(label, label.strip())
        if not hostname or hostname == label.strip():
            self.log_message("[DNS] Invalid DNS selection.")
            return
        adb = __import__("tech_common").subprocess
        def task():
            try:
                r1 = adb.run([self.scrcpy_adb, "shell", "settings", "put", "global", "private_dns_mode", "hostname"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8)
                r2 = adb.run([self.scrcpy_adb, "shell", "settings", "put", "global", "private_dns_specifier", hostname], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8)
                if r1.returncode != 0 or r2.returncode != 0:
                    raise RuntimeError((r1.stderr or r2.stderr or "Android rejected the DNS setting").strip())
                mode = adb.run([self.scrcpy_adb, "shell", "settings", "get", "global", "private_dns_mode"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8).stdout.strip()
                spec = adb.run([self.scrcpy_adb, "shell", "settings", "get", "global", "private_dns_specifier"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8).stdout.strip()
                if mode != "hostname" or spec != hostname:
                    raise RuntimeError(f"Verification failed (mode={mode!r}, hostname={spec!r})")
                self.log_message(f"[DNS] Private DNS verified: {hostname}")
                self.after(0, self.action_dns_refresh)
            except Exception as e:
                self.log_message(f"[DNS ERROR] Could not apply Private DNS: {e}")
                self.after(0, self.action_dns_refresh)
        threading.Thread(target=task, daemon=True).start()

    def disable(self):
        if not self._can("dns"):
            self.log_message("[DNS] Permission denied: Block Ads DNS is disabled for this account.")
            return
        adb = __import__("tech_common").subprocess
        def task():
            try:
                r1 = adb.run([self.scrcpy_adb, "shell", "settings", "put", "global", "private_dns_mode", "off"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8)
                r2 = adb.run([self.scrcpy_adb, "shell", "settings", "delete", "global", "private_dns_specifier"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8)
                if r1.returncode != 0 or r2.returncode != 0:
                    raise RuntimeError((r1.stderr or r2.stderr or "Android rejected the DNS setting").strip())
                mode = adb.run([self.scrcpy_adb, "shell", "settings", "get", "global", "private_dns_mode"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8).stdout.strip()
                spec = adb.run([self.scrcpy_adb, "shell", "settings", "get", "global", "private_dns_specifier"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8).stdout.strip()
                if mode == "hostname" or spec:
                    raise RuntimeError(f"Verification failed (mode={mode!r}, hostname={spec!r})")
                self.log_message("[DNS] Private DNS disabled and verified.")
                self.after(0, self.action_dns_refresh)
            except Exception as e:
                self.log_message(f"[DNS ERROR] Could not disable Private DNS: {e}")
                self.after(0, self.action_dns_refresh)
        threading.Thread(target=task, daemon=True).start()

    cls.action_dns_apply = apply
    cls.action_dns_disable = disable


def _patch_threat_scan(cls):
    def threat_scan(self, pkgs):
        try:
            adb = __import__("tech_common").subprocess
            res = adb.run([self.scrcpy_adb, "shell", "dumpsys", "package"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=45)
            overlay = set()
            current_pkg = None
            for line in res.stdout.splitlines():
                m = re.match(r"\s*Package\s+\[([^\]]+)\]", line)
                if m:
                    current_pkg = m.group(1)
                    continue
                if current_pkg in pkgs and "android.permission.SYSTEM_ALERT_WINDOW" in line:
                    overlay.add(current_pkg)

            installer = {}
            res = adb.run([self.scrcpy_adb, "shell", "pm", "list", "packages", "-i"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=20)
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line.startswith("package:"):
                    continue
                parts = line[len("package:"):].split()
                if not parts:
                    continue
                pkg = parts[0]
                inst = parts[1].split("=", 1)[1] if len(parts) > 1 and "=" in parts[1] else ""
                installer[pkg] = inst

            indicators = 0
            for entry in self.sec_packages:
                p = entry["id"]
                labels = []
                if p in overlay:
                    labels.append("OVERLAY PERMISSION")
                inst = installer.get(p, "")
                if inst and inst not in ("com.android.vending", "com.google.android.feedback"):
                    labels.append(f"INSTALLED VIA {inst}")
                if labels:
                    entry["threat_labels"] = labels
                    # Indicators are not proof of malware. Keep them below the
                    # old "High Risk" threshold so the UI does not overclaim.
                    entry["threat_level"] = 2
                    indicators += 1
                else:
                    entry["threat_labels"] = []
                    entry["threat_level"] = 0
            self.after(0, self._sec_render_rows)
            color = "#f39c12" if indicators else "#2ecc71"
            self.after(0, lambda n=indicators: self.sec_threats_label.configure(text=f"🔎 Security indicators: {n}", text_color=color))
            self.after(0, lambda n=indicators: self._sec_status(
                f"{len(pkgs)} user apps checked — {n} security indicator(s) found. Indicators are not proof of malware; review the details.",
                color,
            ))
            self.after(0, self._sec_animate_stop)
        except Exception as e:
            self.after(0, self._sec_animate_stop)
            self._sec_log(f"[GeloTech ERROR] security indicator scan: {e}", "#e74c3c")

    def detect_hidden(self, installed):
        hidden = []
        uad = self._build_uad_lookup()
        whitelist = self._load_whitelist()
        try:
            adb = __import__("tech_common").subprocess
            res = adb.run([self.scrcpy_adb, "shell", "cmd", "package", "query-activities", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=30)
            launcher_pkgs = {line.strip().split("/", 1)[0] for line in res.stdout.splitlines() if "/" in line and "." in line.split("/", 1)[0]}
            if not launcher_pkgs:
                res = adb.run([self.scrcpy_adb, "shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.LAUNCHER"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=30)
                launcher_pkgs = {line.strip().split("/", 1)[0] for line in res.stdout.splitlines() if "/" in line}
            for pkg in installed:
                if pkg in launcher_pkgs or pkg in whitelist:
                    continue
                entry = uad.get(pkg)
                if entry and entry.get("removal") in ("Unsafe", "Expert"):
                    continue
                hidden.append({"id": pkg, "label": pkg, "category": "No launcher activity", "description": "No launcher activity was found. This is not evidence of malware; many legitimate background/system apps have no icon.", "source": "Security Scan"})
        except Exception:
            pass
        return hidden

    def detect_popup(installed):
        popup = []
        uad = self._build_uad_lookup()
        try:
            adb = __import__("tech_common").subprocess
            res = adb.run([self.scrcpy_adb, "shell", "dumpsys", "package"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=45)
            current = None
            overlay = set()
            for line in res.stdout.splitlines():
                m = re.match(r"\s*Package\s+\[([^\]]+)\]", line)
                if m:
                    current = m.group(1)
                elif current in installed and "android.permission.SYSTEM_ALERT_WINDOW" in line:
                    overlay.add(current)
            for pkg in sorted(overlay):
                entry = uad.get(pkg)
                if entry and entry.get("removal") in ("Unsafe", "Expert"):
                    continue
                popup.append({"id": pkg, "label": pkg, "category": "Overlay indicator", "description": "Has overlay permission. Legitimate apps can use this too; review the app before taking action.", "source": "Security Scan"})
        except Exception:
            pass
        return popup

    cls._sec_threat_scan = threat_scan
    cls._detect_hidden_apps = detect_hidden
    cls._detect_popup_ads = detect_popup

    # Improve static level explanations without changing database semantics.
    cls._sec_level_hint = lambda self, level: {
        "Recommended": "Generally recommended by the package database; device-specific behavior can vary.",
        "Advanced": "Usually removable, but optional vendor features may depend on it.",
        "Expert": "Removal can affect device features or vendor integrations.",
        "Unsafe": "High-impact removal. Do not remove unless you understand the consequences.",
    }.get(level, "")


def _patch_vt(cls):
    original = getattr(cls, "action_vt_upload_apk", None)
    if original is None or getattr(cls, "_hardening_vt_patched", False):
        return
    def wrapped(self, *args, **kwargs):
        if not messagebox.askyesno(
            "VirusTotal privacy notice",
            "Uploading an APK sends the file to VirusTotal for analysis and may make it available to VirusTotal and its security partners.\n\nDo not upload proprietary, private, banking, or confidential APKs unless you are authorized to share them.\n\nContinue?",
            icon="warning",
        ):
            return
        return original(self, *args, **kwargs)
    cls.action_vt_upload_apk = wrapped
    cls._hardening_vt_patched = True


def _patch_icon_helper(cls):
    original = getattr(cls, "action_sec_show_icons", None)
    if original is None or getattr(cls, "_hardening_icons_patched", False):
        return
    def wrapped(self, *args, **kwargs):
        adb = __import__("tech_common").subprocess
        previous = None
        try:
            r = adb.run([self.scrcpy_adb, "shell", "settings", "get", "global", "stay_on_while_plugged_in"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8)
            previous = r.stdout.strip()
        except Exception:
            pass
        original(self, *args, **kwargs)
        if previous is None:
            return
        def restore_worker():
            seen = False
            deadline = time.time() + 420
            while time.time() < deadline:
                try:
                    r = adb.run([self.scrcpy_adb, "shell", "pidof", "com.drox.apkiconhelper"], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=5)
                    running = bool(r.stdout.strip())
                    seen = seen or running
                    if seen and not running:
                        break
                except Exception:
                    pass
                time.sleep(3)
            try:
                adb.run([self.scrcpy_adb, "shell", "settings", "put", "global", "stay_on_while_plugged_in", previous], stdout=adb.PIPE, stderr=adb.PIPE, text=True, timeout=8)
                self.log_message(f"[ADB] Restored original screen-awake setting: {previous}")
            except Exception as e:
                self.log_message(f"[ADB ERROR] Could not restore screen-awake setting: {e}")
        threading.Thread(target=restore_worker, daemon=True).start()
    cls.action_sec_show_icons = wrapped
    cls._hardening_icons_patched = True


def generate_diagnostic_report(self):
    """Generate a redacted local support report without credentials."""
    try:
        root = Path(get_settings_dir()) / "diagnostics"
        root.mkdir(parents=True, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = root / f"GeloTech_Diagnostic_{stamp}.txt"
        lines = [
            "GeloTech Diagnostic Report",
            f"Generated: {_dt.datetime.now().isoformat(timespec='seconds')}",
            f"Windows: {platform.platform()}",
            f"Python: {platform.python_version()}",
            f"Safe Mode: {'ON' if getattr(self, 'safe_mode', True) else 'OFF'}",
            f"App version: {getattr(__import__('tech_common'), 'APP_VERSION', 'unknown')}",
            "",
        ]
        adb = getattr(self, "scrcpy_adb", None)
        scrcpy = getattr(self, "scrcpy_exe", None)
        if adb and os.path.isfile(adb):
            for cmd in ([adb, "version"], [adb, "devices"]):
                try:
                    r = __import__("tech_common").subprocess.run(cmd, stdout=__import__("tech_common").subprocess.PIPE, stderr=__import__("tech_common").subprocess.PIPE, text=True, timeout=10)
                    lines.append(f"$ {' '.join(cmd)}\n{_redact(r.stdout)}{_redact(r.stderr)}")
                except Exception as e:
                    lines.append(f"$ {' '.join(cmd)}\nERROR: {e}")
        if scrcpy and os.path.isfile(scrcpy):
            try:
                r = __import__("tech_common").subprocess.run([scrcpy, "--version"], stdout=__import__("tech_common").subprocess.PIPE, stderr=__import__("tech_common").subprocess.PIPE, text=True, timeout=10)
                lines.append(f"$ scrcpy --version\n{_redact(r.stdout)}{_redact(r.stderr)}")
            except Exception as e:
                lines.append(f"$ scrcpy --version\nERROR: {e}")
        lines.append("\nRecent application log:")
        history = getattr(self, "_log_history", [])[-200:]
        lines.extend(_redact(msg) for _, msg in history)
        lines.append(f"\nFull log: {_log_path()}")
        path.write_text("\n".join(lines), encoding="utf-8")
        self.log_message(f"[SYSTEM] Diagnostic report created: {path}")
        try:
            os.startfile(str(path))
        except Exception:
            webbrowser.open(path.as_uri())
    except Exception as e:
        self.log_message(f"[SYSTEM ERROR] Could not create diagnostic report: {e}")


def _patch_init(cls):
    if getattr(cls, "_hardening_init_patched", False):
        return
    original = cls.__init__
    def wrapped(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.safe_mode = True
        try:
            _install_safe_mode_ui(self)
        except Exception:
            pass
        try:
            self.log_message("[SYSTEM] Reliability hardening enabled. Safe Mode is ON by default.")
        except Exception:
            pass
    cls.__init__ = wrapped
    cls._hardening_init_patched = True


def apply_hardening(cls):
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True
    _patch_settings_save(cls)
    _patch_logging(cls)
    _patch_destructive_ops(cls)
    _patch_popup_cleanup(cls)
    _patch_backup_restore(cls)
    _patch_dns(cls)
    _patch_threat_scan(cls)
    _patch_vt(cls)
    _patch_icon_helper(cls)
    _patch_init(cls)
