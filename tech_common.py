import customtkinter as ctk
from tkinter import messagebox, ttk
import subprocess as _subprocess
import functools

def _no_window(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        kwargs.setdefault('creationflags', 0x08000000)
        return func(*args, **kwargs)
    return wrapper

_subprocess.Popen = _no_window(_subprocess.Popen)
subprocess = _subprocess

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

# Application Global Styling Configurations
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Scale UI for high-DPI / small font compensation
ctk.set_widget_scaling(1.15)

# ---------------------------------------------------------------------------
# EMBEDDED UPDATE SERVER (baked into the exe so users need zero configuration)
# Only editing these in the source + pushing to the repo changes what users see.
# ---------------------------------------------------------------------------
EMBEDDED_UPDATE_URL = "https://github.com/usermalik5/GeloTech-Tool"
EMBEDDED_UPDATE_TOKEN = "REDACTED"

# Write-capable token used ONLY to persist self-registered user accounts
# (email + PBKDF2 hash) back into the repo's secret.json. Keep it scoped
# to this single repository (Contents: Read+Write). Rotate it regularly:
# whoever extracts it can modify this repo's files.
EMBEDDED_UPDATE_WRITE_TOKEN = "REDACTED"

# SMTP sender used to email generated passwords to users. Use a DEDICATED
# low-privilege account with an app password; never your personal account.
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "angeloespinosa985@gmail.com"
SMTP_PASSWORD = "REDACTED"
SMTP_FROM = "angeloespinosa985@gmail.com"

# Secret phrase that reveals the maintainer (admin) login on the login
# screen. Type it into the email field to unlock the admin option.
ADMIN_SECRET_PHRASE = "REDACTED"

# Ed25519 public key (base64, raw 32-byte key) used to verify the signed
# update manifest (version.json + version.json.sig) fetched from the update
# server. The matching private key lives ONLY on the maintainer's machine
# (outside this repo) and is used by bump_version.py to sign releases.
UPDATE_SIGN_PUBLIC_KEY = "UtgC4BXYtuFX4GfEhxmXTpThdY0g1av1GQ7KEU/79K4="

# Permission model. Every feature maps to a permission name (mirror, power,
# connection, device_info, cleaner, monitor, dns, virustotal, restore).
# Non-admin users without explicit permissions in secret.json get
# DEFAULT_USER_PERMS: everything except the admin-only ones (currently only
# VirusTotal).
ALL_PERMS = frozenset({"cleaner", "monitor", "dns", "virustotal",
                       "mirror", "power", "connection", "device_info",
                       "restore"})
ADMIN_ONLY_PERMS = frozenset({"virustotal"})
DEFAULT_USER_PERMS = frozenset(ALL_PERMS - ADMIN_ONLY_PERMS)

# Bump this on every iteration; shown in the window title and the sidebar
# tool name, and must match the release tag (v<APP_VERSION>).
APP_VERSION = "1.1.0"


def get_bundle_dir():
    """Directory for bundled read-only resources (gelotech_database_v3.json, scrcpy zip).
    When frozen by PyInstaller (--onefile), this is the temp extraction folder
    (sys._MEIPASS), which is created fresh and deleted after each run. When
    running as a plain .py script, this is just the script's own directory."""
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


def get_app_dir():
    """Directory for persistent, writable app data (APK backups, whitelist file).
    _MEIPASS is wrong for this: it's temporary and wiped after every run, so
    anything written there would vanish. When frozen, this instead resolves to
    the folder containing the actual .exe, so data survives between launches.
    When running as a plain .py script, this is the script's own directory."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_cache_dir():
    """Directory for temporary cache files (app icons) in the user's temp
    folder, so the exe directory stays clean."""
    return os.path.join(tempfile.gettempdir(), "GeloTechTool", "icon_cache")


def get_settings_dir():
    """Directory for persistent settings (secret.json, whitelist).
    Lives in the hidden per-user AppData folder so it survives reboots and
    disk cleanup, while keeping the exe directory clean. Falls back to the
    exe/script folder if APPDATA is unavailable."""
    base = os.environ.get("APPDATA")
    if base:
        path = os.path.join(base, "GeloTechTool")
        os.makedirs(path, exist_ok=True)
        return path
    return get_app_dir()


def get_session_database_path():
    """Path of the per-login database copy. The package database lives ONLY
    on the update server: every login pulls it, signature-verifies it, and
    writes it here for the session. It is deleted when the app closes (and
    again before the next login's fetch), so users always get the latest DB
    with zero manual intervention."""
    return os.path.join(tempfile.gettempdir(), "GeloTechTool", "gelotech_database_v3.json")


def get_live_database_path():
    """Directory holding the newest available database. The per-login copy
    fetched from the update server wins; if it is missing (e.g. running the
    plain .py source), the bundled copy is used as fallback."""
    session = get_session_database_path()
    if os.path.isfile(session):
        return os.path.dirname(session)
    return get_bundle_dir()


def has_icon_cache():
    """True if an icon export manifest already exists (root or subfolder),
    so the helper APK sync only runs once instead of every launch."""
    root = get_cache_dir()
    return os.path.isfile(os.path.join(root, "packages.jsonl")) or os.path.isfile(
        os.path.join(root, "apk_icon_export", "packages.jsonl"))


def get_apps_cache_path():
    """Path of the local app-list cache so the Security tab can render from
    Windows instantly instead of waiting on the phone every time."""
    return os.path.join(get_settings_dir(), "app_list_cache.json")


def load_apps_cache():
    """Return {'mode', 'timestamp', 'entries'} from the local app-list cache,
    or None if it is missing, corrupt, or empty."""
    try:
        with open(get_apps_cache_path(), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("entries"), list) and data["entries"]:
            data.setdefault("timestamp", 0)
            return data
    except Exception:
        pass
    return None


def save_apps_cache(mode, entries):
    """Atomically persist a package list (mode + entries) to the Windows
    app-data cache so a later launch renders instantly, even without the
    phone connected."""
    if not entries:
        return
    try:
        path = get_apps_cache_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"mode": mode, "timestamp": time.time(), "entries": entries}, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        pass


def fmt_cache_time(ts):
    """Short human-readable timestamp for cache-staleness messages."""
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    except Exception:
        return "earlier"


def get_live_banking_path():
    """Path of the newest banking-apps exclusion list. A copy pulled from the
    update server (beside the settings file) wins over the bundled copy,
    unless the bundled copy is newer (e.g. a fresh exe build)."""
    live = os.path.join(get_settings_dir(), "banking_apps.json")
    bundled = os.path.join(get_bundle_dir(), "banking_apps.json")
    if os.path.isfile(live):
        if not os.path.isfile(bundled):
            return live
        if os.path.getmtime(live) >= os.path.getmtime(bundled):
            return live
    return bundled


def load_banking_apps():
    """Return {package_id: display_name} from the newest banking-apps list.
    These packages are protected: uninstall skips them and the cleaner shows
    a banking badge. Returns {} if the file is missing or invalid."""
    try:
        with open(get_live_banking_path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(k).strip(): str(v).strip() for k, v in data.items() if str(k).strip()}
    except Exception:
        return {}

class Tooltip:
    """Hover hint that shows help text in a dedicated attention banner
    (red strip at the bottom of the window) instead of flooding the log
    console. Falls back to log_message() if the toplevel has no show_hint().
    Drops to no-op on toplevels without either (e.g. dialogs)."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        widget.bind("<Enter>", self._show)

    def _show(self, _event=None):
        if not self.text:
            return
        try:
            tl = self.widget.winfo_toplevel()
            if self.text == getattr(tl, "_last_hint", None):
                return
            tl._last_hint = self.text
            sh = getattr(tl, "show_hint", None)
            if callable(sh):
                sh(self.text)
                return
            lm = getattr(tl, "log_message", None)
            if callable(lm):
                lm(f"[HINT] {self.text}")
        except Exception:
            pass


REMOVAL_DISPLAY_MAP = {
    "delete": "Recommended", "replace": "Advanced",
    "caution": "Expert", "unsafe": "Unsafe",
}
REMOVAL_DISPLAY_VALUES = {"Recommended", "Advanced", "Expert", "Unsafe"}


def _display_removal(raw):
    if not isinstance(raw, str) or not raw.strip():
        return "Unknown"
    value = raw.strip()
    if value in REMOVAL_DISPLAY_VALUES:
        return value
    return REMOVAL_DISPLAY_MAP.get(value, "Unknown")


def _first_line(value):
    text = (value or "").strip()
    return text.splitlines()[0].strip() if "\n" in text else text


def load_package_database(base_directory):
    """Load package metadata from the bundled merged database
    (gelotech_database_v3.json). Falls back to gelotech_database_v2.json when
    the v3 file is absent. Returns {package_name: record} with display-string
    removal levels, or {} if the database is missing."""
    db_path = os.path.join(base_directory, "gelotech_database_v3.json")
    if not os.path.isfile(db_path):
        db_path = os.path.join(base_directory, "gelotech_database_v2.json")
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return {}
    packages = payload.get("packages") or {}
    out = {}
    for pid, p in packages.items():
        if not pid or not isinstance(p, dict):
            continue
        gelotech = p.get("gelotech") if isinstance(p.get("gelotech"), dict) else {}
        exclude = p.get("exclude") if isinstance(p.get("exclude"), dict) else {}
        status = p.get("status") if isinstance(p.get("status"), dict) else {}
        label = _first_line(p.get("label") or p.get("name"))
        name = _first_line(p.get("name"))
        warnings = list(p.get("warnings") or [])
        suggestions = p.get("suggestions")
        if isinstance(suggestions, list):
            suggestions = ", ".join(str(item) for item in suggestions)
        out[pid] = {
            "id": pid,
            "label": label,
            "labels": [label] if label else [],
            "name": name or label,
            "description": (p.get("description") or "").strip(),
            "removal": _display_removal(p.get("removal")),
            "risk": p.get("risk") or "unknown",
            "manufacturer": p.get("manufacturer") or "Unknown",
            "category": p.get("category") or "Other",
            "source": (p.get("source") or "Unknown").strip(),
            "warning": (p.get("notes") or "").strip(),
            "web": [],
            "dependencies": list(p.get("dependencies") or []),
            "required_by": warnings,
            "suggestions": suggestions or "",
            "tags": list(p.get("tags") or []),
            "safe_alternatives": list(p.get("alternatives") or p.get("safe_alternatives") or []),
            "exclude_clean": bool(gelotech.get("clean_excluded", exclude.get("clean", False))),
            "exclude_uninstall": bool(gelotech.get("uninstall_excluded", exclude.get("uninstall", False))),
            "debloated": bool(gelotech.get("debloated", status.get("debloated", False))),
        }
    return out

