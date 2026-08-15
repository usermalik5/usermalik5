# -*- coding: utf-8 -*-
import customtkinter as ctk
import threading
import os
import json
import re
import hashlib
import sys
import requests
import shutil
from PIL import Image, ImageDraw, ImageFont
from tech_common import get_bundle_dir, get_app_dir, get_cache_dir, get_settings_dir, get_live_database_path, get_session_database_path, Tooltip, subprocess, load_package_database, DEFAULT_USER_PERMS, APP_VERSION
from tech_admin import AdminPanelMixin

from tech_reg import (_worker_fetch, _verify_manifest_sig, _fetch_verified_sources,
                      _fetch_verified_users, _purge_session_database, _is_valid_email,
                      _request_password)

# Local runtime settings file (exclusions + debloated history). Deliberately NOT
# named secret.json: that name is reserved for the live accounts file on GitHub.
SETTINGS_FILE = "exclusions.json"





class SettingsMixin(AdminPanelMixin):
    def _load_whitelist(self):
        path = os.path.join(get_settings_dir(), "sec_whitelist.txt")
        if os.path.isfile(path):
            with open(path, "r") as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_whitelist(self, whitelist):
        path = os.path.join(get_settings_dir(), "sec_whitelist.txt")
        with open(path, "w") as f:
            for pkg in sorted(whitelist):
                f.write(pkg + "\n")

    def _filter_whitelisted(self, results):
        whitelist = self._load_whitelist()
        if not whitelist:
            return results
        return [r for r in results if r["id"] not in whitelist]

    def _load_app_labels(self):
        if hasattr(self, '_app_labels') and self._app_labels is not None:
            return self._app_labels
        labels = {}
        # 1) Real labels from the helper APK export (packages.jsonl via loadLabel)
        for cand in (os.path.join(get_cache_dir(), "packages.jsonl"),
                     os.path.join(get_cache_dir(), "apk_icon_export", "packages.jsonl")):
            if os.path.isfile(cand):
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                item = json.loads(line)
                                if item.get("package") and item.get("label"):
                                    labels[item["package"]] = item["label"]
                            except Exception:
                                pass
                    break
                except Exception:
                    pass
        # 2) Fallback: full dumpsys package dump (ApplicationLabel per package block)
        if not labels:
            try:
                res = subprocess.run([self.scrcpy_adb, "shell", "dumpsys", "package"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
                pkg, buf = None, []
                for line in res.stdout.splitlines():
                    m = re.search(r'Package\s+\[([^\]]+)\]', line)
                    if m:
                        if pkg and buf:
                            lm = re.search(r'ApplicationLabel=([^,}\n]+)', " ".join(buf))
                            if lm:
                                labels[pkg] = lm.group(1).strip()
                        pkg = m.group(1)
                        buf = [line]
                    elif pkg:
                        buf.append(line)
                if pkg and buf:
                    lm = re.search(r'ApplicationLabel=([^,}\n]+)', " ".join(buf))
                    if lm:
                        labels[pkg] = lm.group(1).strip()
            except Exception:
                pass
        self._app_labels = labels
        return labels

    def _build_uad_lookup(self):
        if hasattr(self, '_uad_cache') and self._uad_cache is not None:
            return self._uad_cache
        service = getattr(self, "database_service", None)
        if service is not None:
            self._uad_cache = service.load()
        else:
            self._uad_cache = load_package_database(get_live_database_path())
        return self._uad_cache

    def _filter_by_uad(self, results):
        uad = self._build_uad_lookup()
        out = []
        for r in results:
            pid = r["id"]
            entry = uad.get(pid)
            if entry is None:
                out.append(r)
                continue
            removal = entry.get("removal", "")
            if removal in ("Recommended", "Advanced"):
                r["description"] = f"[UAD: {removal}] {entry.get('description', r['description'])}"
                out.append(r)
        return out

    def _resolve_label(self, pid):
        labels = self._load_app_labels()
        if pid in labels:
            return labels[pid]
        parts = pid.rsplit(".", 1)
        if len(parts) > 1:
            name = parts[1]
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
            name = name.replace("_", " ").replace("-", " ").title()
            return name
        return pid

    # ----------------------------------------------------
    # APK CLEANER STYLE PACKAGE LIST
    # ----------------------------------------------------
    def _migrate_settings(self):
        """First-run: consolidate legacy runtime state into exclusions.json
        (exclusions + debloated history). Runtime settings live in
        exclusions.json, NEVER secret.json — that name is reserved for the
        live accounts file on GitHub and must never be treated as local
        settings (or written next to the exe). Credentials never live on
        disk: users are fetched from the auth proxy Worker on every login."""
        app = get_app_dir()
        sfile = os.path.join(get_settings_dir(), SETTINGS_FILE)
        old_sfile = os.path.join(app, "secret.json")
        settings_old = os.path.join(get_settings_dir(), "secret.json")
        legacy_app_sfile = os.path.join(app, "gelotech_settings.json")
        legacy_sfile = os.path.join(get_settings_dir(), "gelotech_settings.json")

        def _is_runtime(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                return None
            if not isinstance(data, dict):
                return None
            # The accounts file (users key) must NEVER be treated as runtime
            # settings or deleted, even if it sits at a legacy path.
            if data.get("users") is not None:
                return None
            return data

        if not os.path.isfile(sfile):
            data = _is_runtime(old_sfile)
            if data is None:
                data = _is_runtime(settings_old)
            if data is None and os.path.isfile(legacy_sfile):
                try:
                    with open(legacy_sfile, "r", encoding="utf-8") as f:
                        legacy = json.load(f)
                    if isinstance(legacy, dict):
                        # Exclusions now live in the database as per-package
                        # flags; drop the legacy lists so only banking apps
                        # are seeded. Credentials never live on disk.
                        legacy.pop("clean_excluded", None)
                        legacy.pop("uninstall_excluded", None)
                        legacy.pop("users", None)
                        data = legacy
                except Exception:
                    data = None
            if data is None and os.path.isfile(legacy_app_sfile):
                try:
                    with open(legacy_app_sfile, "r", encoding="utf-8") as f:
                        legacy = json.load(f)
                    if isinstance(legacy, dict):
                        legacy.pop("clean_excluded", None)
                        legacy.pop("uninstall_excluded", None)
                        legacy.pop("users", None)
                        data = legacy
                except Exception:
                    data = None
            if data is not None:
                self._save_settings(data)
            else:
                clean = self._read_lines_file(os.path.join(app, "clean_excluded.txt"))
                if not clean:
                    clean = self._read_lines_file(os.path.join(get_bundle_dir(), "clean_excluded.txt"))
                uninstall = self._read_lines_file(os.path.join(app, "uninstall_excluded.txt"))
                if not uninstall:
                    uninstall = self._read_lines_file(os.path.join(get_bundle_dir(), "uninstall_excluded.txt"))
                debloated = []
                uad = os.path.join(app, "uad_debloat_backup.json")
                if os.path.isfile(uad):
                    try:
                        with open(uad, "r", encoding="utf-8") as f:
                            debloated = json.load(f).get("packages", []) or []
                    except Exception:
                        debloated = []
                self._save_settings({
                    "clean_excluded": [],
                    "uninstall_excluded": [],
                    "debloated": sorted(set(debloated)),
                })
            # Remove migrated legacy runtime files ONLY (never an accounts file).
            for p in (old_sfile, settings_old, legacy_sfile, legacy_app_sfile):
                if os.path.isfile(p) and _is_runtime(p) is not None:
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        for name in ("clean_excluded.txt", "uninstall_excluded.txt", "uad_debloat_backup.json"):
            p = os.path.join(app, name)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def _drop_settings_copy(self):
        """Copy the AppData exclusions.json next to the exe after login, so the
        user can grab it and ship it to another PC. On the other PC, the first
        run of _migrate_settings imports it into AppData automatically.
        The copy is named exclusions.json (NOT secret.json — that name is
        reserved for the live accounts file on GitHub) and is set as a hidden
        Windows file. It only contains runtime state (exclusions, debloated
        history) - login credentials are never stored on disk."""
        try:
            src = os.path.join(get_settings_dir(), SETTINGS_FILE)
            if os.path.isfile(src):
                dest = os.path.join(get_app_dir(), SETTINGS_FILE)
                shutil.copy2(src, dest)
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(dest, 0x2)
                except Exception:
                    pass
        except Exception:
            pass

    def _seed_database_defaults(self):
        """Seed runtime exclusion / debloated lists from the bundled database flags.
        Adds any package flagged in gelotech_database_v3.json that is not already
        in the user's runtime lists; lists stay editable afterwards."""
        lookup = self._build_uad_lookup()
        if not lookup:
            return
        data = self._load_settings()
        clean = set(data.get("clean_excluded") or [])
        uninstall = set(data.get("uninstall_excluded") or [])
        debloated = set(data.get("debloated") or [])
        changed = False
        for pid, entry in lookup.items():
            if entry.get("exclude_clean") and pid not in clean:
                clean.add(pid)
                changed = True
            if entry.get("exclude_uninstall") and pid not in uninstall:
                uninstall.add(pid)
                changed = True
            if entry.get("debloated") and pid not in debloated:
                debloated.add(pid)
                changed = True
        if changed:
            data["clean_excluded"] = sorted(clean)
            data["uninstall_excluded"] = sorted(uninstall)
            data["debloated"] = sorted(debloated)
            self._save_settings(data)

    def _sec_description(self, pkg, maxlen=160):
        uad = self._build_uad_lookup()
        entry = uad.get(pkg) or {}
        desc = (entry.get("description") or "").strip()
        if len(desc) > maxlen:
            desc = desc[:maxlen].rsplit(" ", 1)[0] + "..."
        return desc

    # ----------------------------------------------------
    # LOGIN / USER ACCOUNTS / PERMISSIONS
    # ----------------------------------------------------
    @staticmethod
    def _purge_session_database():
        _purge_session_database()

    def _can(self, perm):
        if getattr(self, "is_admin", True):
            return True
        return perm in (self.user_perms or set())

    def _set_tab_visible(self, name, visible):
        try:
            btn = self.page_nav_btns.get(name)
            if btn is not None:
                if visible:
                    btn.grid()
                else:
                    btn.grid_remove()
        except Exception:
            pass

    def _apply_permissions(self):
        is_admin = bool(getattr(self, "is_admin", True))
        perms = self.user_perms or set()
        for perm, btns in self._perm_sidebar_btns.items():
            allowed = is_admin or perm in perms
            for b in btns:
                try:
                    b.configure(state="normal" if allowed else "disabled")
                except Exception:
                    pass
        try:
            if is_admin:
                self._admin_panel_btn.grid()
            else:
                self._admin_panel_btn.grid_remove()
        except Exception:
            pass
        visible = []
        user_tabs = getattr(self, "user_tabs", None)
        for name, perm in self.TAB_PERMS.items():
            if is_admin:
                allowed = True
            elif user_tabs is not None:
                allowed = name in user_tabs
            else:
                allowed = perm in perms
            self._set_tab_visible(name, allowed)
            if allowed:
                visible.append(name)
        # Dashboard is the universal post-login landing page.
        try:
            self._show_page("Dashboard")
        except Exception:
            pass

    def _login_gate(self):
        self.withdraw()
        self._show_login()

    def _logout(self):
        self.withdraw()
        # Destroy the session state: the Worker-issued token lives only in
        # memory and is discarded on logout, along with permissions/admin
        # state. The per-login database copy is also removed.
        self._auth_session = None
        self.is_admin = False
        self.user_perms = None
        self.user_tabs = None
        _purge_session_database()
        self._show_login()

    @staticmethod
    def _read_lines_file(path):
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception:
            return []

    def _load_settings(self):
        path = os.path.join(get_settings_dir(), SETTINGS_FILE)
        data = {"clean_excluded": [], "uninstall_excluded": [], "debloated": [], "theme": "orange"}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for key in data:
                        if isinstance(loaded.get(key), type(data[key])):
                            data[key] = loaded[key]
                    for key in ("update_state",):
                        if isinstance(loaded.get(key), type(data.get(key, ""))):
                            data[key] = loaded[key]
            except Exception:
                pass
        return data

    def _save_settings(self, data):
        path = os.path.join(get_settings_dir(), SETTINGS_FILE)
        try:
            payload = {}
            for key, value in data.items():
                if key == "users":
                    # Credentials are managed on GitHub; never stored locally.
                    continue
                if isinstance(value, (list, set)):
                    payload[key] = sorted(set(value))
                elif isinstance(value, (dict, str, bool, int, float)) or value is None:
                    payload[key] = value
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def _load_excluded_clean(self):
        return set(self._load_settings().get("clean_excluded", []))

    def _load_excluded_uninstall(self):
        return set(self._load_settings().get("uninstall_excluded", []))

    def _save_excluded_clean(self, s):
        data = self._load_settings()
        data["clean_excluded"] = sorted(s)
        self._save_settings(data)

    def _save_excluded_uninstall(self, s):
        data = self._load_settings()
        data["uninstall_excluded"] = sorted(s)
        self._save_settings(data)

    def _load_debloated(self):
        return set(self._load_settings().get("debloated", []))

    def _save_debloated(self, s):
        data = self._load_settings()
        data["debloated"] = sorted(s)
        self._save_settings(data)

    def _record_debloated(self, pkgs):
        data = self._load_settings()
        data["debloated"] = sorted(set(data["debloated"]) | set(pkgs))
        self._save_settings(data)

    # ----------------------------------------------------
    # WEB UPDATES (pull from GitHub repo)
    # ----------------------------------------------------
    def _check_updates(self, manual=False, status_cb=None):
        """Check for data updates through the auth proxy Worker's /files
        endpoints (AUTH_WORKER_URL, pinned in tech_common.py). The update
        source is NEVER read from settings/secret.json, so a compromised
        local or repo settings file cannot redirect clients to a malicious
        server. The Worker serves version.json, version.json.sig and the
        data files (it owns the GitHub read token; the client has none).
        Expects version.json hosting {"database": N, "banking": N,
        "sha256": {file: hex}} plus a version.json.sig (base64 Ed25519
        signature over the exact bytes of version.json) and the data files.
        The manifest signature is verified with the embedded public key
        (tech_common.UPDATE_SIGN_PUBLIC_KEY), and every downloaded file's
        SHA-256 must match the signed manifest before it is applied. Only
        banking_apps.json is distributed via updates: the package database
        is pulled fresh, signature-verified, and cached for the session on
        EVERY login (and deleted on app close / next login), and secret.json
        is NOT distributed at all - login credentials are fetched and
        verified on every login and never written to disk. Runs in a
        background thread."""
        def report(msg):
            if status_cb is not None:
                self.after(0, lambda: status_cb(msg))

        def work():
            data = self._load_settings()
            # Update source is pinned to the embedded Worker URL only.
            try:
                manifest_bytes = _worker_fetch("files/version.json")
                sig_text = _worker_fetch("files/version.json.sig")
            except Exception as e:
                if manual:
                    msg = f"\u26a0 Could not reach update server: {type(e).__name__}"
                    report(msg)
                return
            if not _verify_manifest_sig(manifest_bytes, sig_text.decode("utf-8")):
                report("\u26a0 Update rejected: manifest signature is invalid.")
                return
            try:
                manifest = json.loads(manifest_bytes.decode("utf-8"))
            except Exception:
                report("\u26a0 Update rejected: corrupt version.json.")
                return
            sha_map = manifest.get("sha256")
            if not isinstance(sha_map, dict):
                report("\u26a0 Update rejected: manifest has no signed sha256 map.")
                return
            last = self._load_settings().get("update_state") or {}
            changed = False
            new_state = dict(last)
            for fname, key in (("banking_apps.json", "banking"),):
                new_v = manifest.get(key)
                if new_v is None or last.get(key) == new_v:
                    continue
                try:
                    raw = _worker_fetch(f"files/{fname}")
                    expected = sha_map.get(fname)
                    if not expected or hashlib.sha256(raw).hexdigest() != expected:
                        report(f"\u26a0 Update rejected: sha256 mismatch for {fname}.")
                        continue
                    dest = os.path.join(get_settings_dir(), fname)
                    if os.path.exists(dest):
                        with open(dest, "rb") as f:
                            data_bak = f.read()
                        bak = dest + ".bak"
                        with open(bak, "wb") as f:
                            f.write(data_bak)
                    with open(dest, "wb") as f:
                        f.write(raw)
                    new_state[key] = new_v
                    changed = True
                except Exception:
                    continue
            if changed:
                data = self._load_settings()
                data["update_state"] = new_state
                self._save_settings(data)
                # The banking list is read fresh on every load (load_banking_apps),
                # so a downloaded update applies on the next list refresh - no
                # restart is needed, and no popup is shown for these data updates.
                report("\u2713 Banking list updated. It will apply on the next list refresh (no restart needed).")
            elif manual:
                report("\u2713 You are up to date.")

        threading.Thread(target=work, daemon=True).start()
