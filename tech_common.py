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

# Windows cp1252 locale cannot decode arbitrary adb output (UTF-8 multibyte,
# dumpsys dumps, app names...). Force UTF-8 + lossless-ish decoding on every
# text-mode subprocess call so reader threads never crash.
def _utf8_text(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if (kwargs.get("text") or kwargs.get("universal_newlines")) and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
        if kwargs.get("encoding") and kwargs.get("errors") is None:
            kwargs["errors"] = "replace"
        return func(*args, **kwargs)
    return wrapper

_subprocess.run = _utf8_text(_subprocess.run)
_subprocess.check_output = _utf8_text(_subprocess.check_output)
_subprocess.check_call = _utf8_text(_subprocess.check_call)
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
import tech_qt_themes as _tthemes
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme(
    os.path.join(_tthemes.THEME_DIR, f"{_tthemes.DEFAULT_THEME}.json"))

# Scale UI for high-DPI / small font compensation
ctk.set_widget_scaling(1.15)

# ---------------------------------------------------------------------------
# AUTH PROXY WORKER (baked into the exe so users need zero configuration)
# ALL privileged operations go through this Cloudflare Worker: login,
# registration/password reset, admin sessions, admin block/unblock, and the
# update files (version.json + signature + package database + banking list).
# The Worker holds the GitHub read/write token, the SMTP sender and the
# session-signing key as server-side secrets (wrangler secret put in
# worker/; deploy with `npx wrangler deploy`). The client contains NO
# credentials of any kind.
# ---------------------------------------------------------------------------
AUTH_WORKER_URL = "https://gelotech-auth-proxy.angeloespinosa985.workers.dev"

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
APP_VERSION = "1.7.8"

# 3uTools-style theme palettes (shared by all UI modules)
THEMES = {
    "dark": {
        "bg": "#0e1217",        # window / page background
        "panel": "#141b24",     # panels & cards
        "panel2": "#10161e",    # darker nested panels (toolbars/stats)
        "card": "#1a2330",      # header cards
        "border": "#26303d",
        "input": "#0a0e13",
        "accent": "#3b82f6",    # 3uTools blue
        "accent_h": "#2f6fe4",
        "green": "#22c55e",
        "red": "#ef4444",
        "amber": "#f59e0b",
        "text": "#e6edf3",
        "muted": "#8b98a9",
        "sidebar": "#0c1015",
    },
    "light": {
        "bg": "#eef1f5",        # window / page background
        "panel": "#ffffff",     # panels & cards
        "panel2": "#f2f4f7",    # lighter nested panels (toolbars/stats)
        "card": "#ffffff",      # header cards
        "border": "#d4dae1",
        "input": "#ffffff",
        "accent": "#3b82f6",    # 3uTools blue (both modes)
        "accent_h": "#2f6fe4",
        "green": "#16a34a",
        "red": "#dc2626",
        "amber": "#d97706",
        "text": "#1b2530",
        "muted": "#5a6673",
        "sidebar": "#e4e8ee",
    },
}

THEME = THEMES["light"]

# Dark -> light hex swap used by the runtime theme walker. Phone screen / log
# console colors are intentionally absent (a phone display stays dark).
COLOR_SWAP = {
    "#0e1217": "#eef1f5",
    "#0c1015": "#e4e8ee",
    "#141b24": "#ffffff",
    "#10161e": "#f2f4f7",
    "#1a2330": "#ffffff",
    "#26303d": "#d4dae1",
    "#0a0e13": "#ffffff",
    "#1b222c": "#ffffff",
    "#131921": "#eef1f5",
    "#0d1117": "#fbfcfd",
    "#16191e": "#e8ebf0",
    "#11151c": "#e8ebf0",
    "#21262d": "#dde2e8",
    "#27313d": "#dde2e8",
    "#30363d": "#c2c9d2",
    "#2c3340": "#c2c9d2",
    "#282e37": "#c2c9d2",
    "#1c2026": "#e8ebf0",
    "#1f2a3a": "#e2e6eb",
    "#2a3340": "#d4dae1",
    "#395670": "#d4dae1",
    "#e6edf3": "#1b2530",
    "#e8ecf2": "#1b2530",
    "#d9e5ee": "#263140",
    "#d1d5db": "#263140",
    "#cbd9e6": "#33404f",
    "#aab7c4": "#566170",
    "#aeb8c2": "#566170",
    "#8da1b8": "#4a5a6b",
    "#8b949e": "#566170",
    "#8b98a9": "#5a6673",
    "#a6a6a6": "#6a7480",
    "#7a8699": "#66707d",
    "#484f58": "#7a838d",
    "#5b6773": "#8a94a0",
    "#e67e22": "#c2570b",
    "#1abc9c": "#0e9480",
    "#2980b9": "#1f6cb0",
    "#8e44ad": "#7a3ba0",
    "#16a085": "#0f8270",
    "#138d75": "#0f7a64",
    "#d35400": "#b84500",
    "#c0392b": "#a93226",
    "#2ecc71": "#16a34a",
    "#e74c3c": "#dc2626",
    "#f39c12": "#d97706",
    "#2ea043": "#1a8a3a",
    "#58a6ff": "#2563c2",
    "#1f6feb": "#2563c2",
    "#1a5fd0": "#1f58b8",
    "#0f7489": "#0e6478",
    "#0c5f70": "#0b5566",
    "#1497ab": "#13849a",
    "#0d0f12": "#e4e8ee",
    "#161b22": "#eef1f5",
    "#111622": "#f2f4f7",
    "#303645": "#d4dae1",
    "#1b232d": "#ffffff",
    "#222c37": "#eef1f5",
    "#3d1212": "#fbe9e9",
    "#c9d1d9": "#263140",
    "#66727e": "#566170",
    "#3a3a3a": "#6b7684",
    "#4a4a4a": "#7a838d",
    "#3d444d": "#6b7684",
    "#a82521": "#a93226",
    "#71368a": "#7a3ba0",
    "#a8420f": "#b84500",
    "#bf8700": "#9c6f00",
    "#e5534b": "#d64545",
    "#e3b341": "#c79a1a",
    "#d4af37": "#b8960c",
    "#2d1a4a": "#f3eafa",
    "#3d3210": "#faf5e3",
    "#1f3d2a": "#e9f6ee",
    "#edf3f8": "#1b2530",
    "#d8e0e7": "#263140",
    "#34495e": "#566170",
    "#27ae60": "#16a34a",
    "#da3633": "#d64545",
    "#b62324": "#a93226",
    "#b91c1c": "#a93226",
    "#bc4c00": "#b84500",
    "#1f618d": "#1f6cb0",
    "#117a65": "#0e9480",
    "#ff4d4d": "#d64545",
    "#2ecc71": "#16a34a",
}

# Canonical dark color for each shared light color, so the theme walker
# round-trips exactly (several dark colors share one light twin).
CANONICAL_DARK = {
    "#eef1f5": "#0e1217",
    "#ffffff": "#141b24",
    "#e8ebf0": "#16191e",
    "#d4dae1": "#26303d",
    "#dde2e8": "#21262d",
    "#c2c9d2": "#30363d",
    "#f2f4f7": "#10161e",
    "#263140": "#d9e5ee",
    "#566170": "#8b949e",
    "#1b2530": "#e6edf3",
    "#d64545": "#e5534b",
    "#a93226": "#c0392b",
    "#16a34a": "#2ecc71",
    "#b84500": "#bc4c00",
    "#1f6cb0": "#2980b9",
    "#0e9480": "#1abc9c",
    "#7a3ba0": "#8e44ad",
    "#6b7684": "#3a3a3a",
    "#5a6673": "#8b98a9",
    "#7a838d": "#484f58",
    "#6a7480": "#a6a6a6",
    "#8a94a0": "#5b6773",
    "#dc2626": "#e74c3c",
    "#2563c2": "#1f6feb",
    "#e4e8ee": "#0c1015",
}


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
    """Directory for persistent settings (exclusions.json, whitelist).
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

