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
from tech_dashboard_redesign import install_dashboard_redesign


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
    _patch_dashboard_navigation(cls)
    _patch_phone_mirror_visibility(__import__("tech_phone_mirror").PhoneMirrorManager)


from tech_hardening_ops import (
    generate_diagnostic_report,
    _patch_backup_restore,
    _patch_dns,
    _patch_threat_scan,
    _patch_vt,
    _patch_icon_helper,
    _patch_dashboard_navigation,
    _patch_phone_mirror_visibility,
)
