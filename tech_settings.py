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
import base64
import datetime
import shutil
from PIL import Image, ImageDraw, ImageFont
from tech_common import get_bundle_dir, get_app_dir, get_cache_dir, get_settings_dir, get_live_database_path, get_session_database_path, Tooltip, subprocess, load_package_database, EMBEDDED_UPDATE_URL, EMBEDDED_UPDATE_TOKEN, UPDATE_SIGN_PUBLIC_KEY
from tech_admin import AdminPanelMixin


def _parse_repo(base):
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?(?:\?|$|/tree/([^/]+))", base)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    branch = m.group(3) or "main"
    return owner, repo, branch


def _api_fetch(owner, repo, branch, fname, headers):
    """Fetch a file's exact committed bytes from GitHub over TLS. Uses the
    contents API to resolve the blob sha, then the git blobs API to download
    the bytes (the contents API returns EMPTY content for files larger than
    1 MB, so the blobs API is the reliable path). Falls back to
    raw.githubusercontent.com for public repos when no token is set."""
    if headers:
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{fname}?ref={branch}"
        resp = requests.get(url, headers={**headers, "Accept": "application/vnd.github+json"}, timeout=60)
        resp.raise_for_status()
        meta = resp.json()
        content = meta.get("content") or ""
        if content:
            return base64.b64decode(content)
        sha = meta.get("sha")
        if not sha:
            raise RuntimeError(f"no blob sha returned for {fname}")
        blob_url = f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}"
        resp2 = requests.get(blob_url, headers={**headers, "Accept": "application/vnd.github+json"}, timeout=120)
        resp2.raise_for_status()
        return base64.b64decode(resp2.json()["content"])
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{fname}"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def _verify_manifest_sig(manifest_bytes, sig_b64):
    """Verify the Ed25519 signature over version.json with the embedded
    public key. Returns True only for a valid signature."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        pub = ed25519.Ed25519PublicKey.from_public_bytes(
            base64.b64decode(UPDATE_SIGN_PUBLIC_KEY))
        pub.verify(base64.b64decode(sig_b64.strip()), manifest_bytes)
        return True
    except Exception:
        return False


def _fetch_verified_sources():
    """Fetch the signed manifest once from the pinned update server, then
    fetch the users list (secret.json) and the package database
    (gelotech_database_v3.json), verifying the manifest signature and each
    file's sha256. Returns (users_dict, db_bytes) or (None, None) if the
    server is unreachable or any verification fails. NEVER writes anything
    to disk — the results exist only in memory."""
    base = EMBEDDED_UPDATE_URL.strip().rstrip("/")
    tok = EMBEDDED_UPDATE_TOKEN.strip()
    parsed = _parse_repo(base)
    if not parsed:
        return None, None
    owner, repo, branch = parsed
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
    try:
        manifest_bytes = _api_fetch(owner, repo, branch, "version.json", headers)
        sig_bytes = _api_fetch(owner, repo, branch, "version.json.sig", headers)
        if not _verify_manifest_sig(manifest_bytes, sig_bytes.decode("utf-8")):
            return None, None
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        sha_map = manifest.get("sha256")
        if not isinstance(sha_map, dict) or not sha_map.get("secret.json"):
            return None, None
        users_bytes = _api_fetch(owner, repo, branch, "secret.json", headers)
        if hashlib.sha256(users_bytes).hexdigest() != sha_map["secret.json"]:
            return None, None
        parsed = json.loads(users_bytes.decode("utf-8"))
        users = parsed.get("users")
        if not isinstance(users, dict):
            return None, None
        expected_db = sha_map.get("gelotech_database_v3.json")
        if not expected_db:
            return None, None
        db_bytes = _api_fetch(owner, repo, branch, "gelotech_database_v3.json", headers)
        if hashlib.sha256(db_bytes).hexdigest() != expected_db:
            return None, None
        return users, db_bytes
    except Exception:
        return None, None


def _fetch_verified_users():
    """Return just the signed users list from the update server (used by the
    read-only admin panel), or None on failure. Never writes to disk."""
    users, _ = _fetch_verified_sources()
    return users


def _purge_session_database():
    """Delete the per-login database copy. Called before each login's fetch
    and on app close, so the database is never left on disk between sessions
    and the next login always pulls the latest version."""
    try:
        path = get_session_database_path()
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        pass


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
        if hasattr(self, '_uad_cache'):
            return self._uad_cache
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
        """First-run: consolidate legacy state into secret.json (credentials +
        runtime debloated history). Exclusion lists now live in the database."""
        app = get_app_dir()
        sfile = os.path.join(get_settings_dir(), "secret.json")
        old_sfile = os.path.join(app, "secret.json")
        legacy_app_sfile = os.path.join(app, "gelotech_settings.json")
        legacy_sfile = os.path.join(get_settings_dir(), "gelotech_settings.json")
        if os.path.isfile(legacy_app_sfile) and not os.path.isfile(legacy_sfile) and not os.path.isfile(sfile):
            try:
                shutil.copy2(legacy_app_sfile, legacy_sfile)
            except Exception:
                pass
        if os.path.isfile(legacy_sfile) and not os.path.isfile(sfile):
            try:
                with open(legacy_sfile, "r", encoding="utf-8") as f:
                    legacy = json.load(f)
            except Exception:
                legacy = None
            if isinstance(legacy, dict):
                # Exclusions now live in the database as per-package flags;
                # drop the legacy lists so only banking apps are seeded.
                # Credentials never live on disk: users are fetched from the
                # signed update server on every login.
                legacy.pop("clean_excluded", None)
                legacy.pop("uninstall_excluded", None)
                legacy.pop("users", None)
                try:
                    with open(sfile, "w", encoding="utf-8") as f:
                        json.dump(legacy, f, indent=2, ensure_ascii=False)
                    os.remove(legacy_sfile)
                except Exception:
                    pass
            else:
                try:
                    os.rename(legacy_sfile, sfile)
                except Exception:
                    shutil.copy2(legacy_sfile, sfile)
                    try:
                        os.remove(legacy_sfile)
                    except Exception:
                        pass
        if os.path.isfile(old_sfile) and not os.path.isfile(sfile):
            shutil.copy2(old_sfile, sfile)
        if not os.path.isfile(sfile):
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
        for name in ("clean_excluded.txt", "uninstall_excluded.txt", "uad_debloat_backup.json"):
            p = os.path.join(app, name)
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def _drop_settings_copy(self):
        """Copy the AppData settings json next to the exe after login, so the
        user can grab it and ship it to another PC. On the other PC, the first
        run of _migrate_settings imports it into AppData automatically.
        The copy is set as a hidden Windows file. It only contains runtime
        state (exclusions, debloated history) - login credentials are never
        stored on disk, so the file contains no secrets."""
        try:
            src = os.path.join(get_settings_dir(), "secret.json")
            if os.path.isfile(src):
                dest = os.path.join(get_app_dir(), "secret.json")
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
    def _hash_pw(pw):
        salt = os.urandom(16).hex()
        iters = 100_000
        digest = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), iters).hex()
        return f"{iters}${salt}${digest}"

    @staticmethod
    def _verify_pw(pw, stored):
        if not stored:
            return False
        if stored.count("$") == 2:
            iters, salt, digest = stored.split("$")
            try:
                calc = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), int(iters)).hex()
            except Exception:
                return False
            return calc == digest
        return hashlib.sha256(pw.encode("utf-8")).hexdigest() == stored

    def _can(self, perm):
        if getattr(self, "is_admin", True):
            return True
        return perm in (self.user_perms or set())

    def _set_tab_visible(self, name, visible):
        try:
            tab = self.tabview._tab_dict.get(name)
            btn = self.tabview._segmented_button._buttons_dict.get(name)
            if tab is not None:
                if visible:
                    tab.grid()
                else:
                    tab.grid_remove()
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
        if visible:
            try:
                self.tabview.set(visible[0])
            except Exception:
                pass

    def _login_gate(self):
        self.withdraw()
        self._show_login()

    def _logout(self):
        self.withdraw()
        _purge_session_database()
        self._show_login()

    def _show_login(self):
        win = ctk.CTkToplevel(self)
        win.title("GeloTech Tool - Login")
        win.resizable(False, False)
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win.geometry(f"440x580+{(sw - 440) // 2}+{max(0, (sh - 580) // 3)}")
        self._login_win = win
        win.protocol("WM_DELETE_WINDOW", lambda: (_purge_session_database(), win.destroy(), self.quit()))

        icon = None
        try:
            ico_path = os.path.join(get_bundle_dir(), "gelotech_icon.ico")
            if os.path.isfile(ico_path):
                icon = ctk.CTkImage(light_image=Image.open(ico_path).convert("RGBA"),
                                    dark_image=Image.open(ico_path).convert("RGBA"), size=(72, 72))
        except Exception:
            pass
        if icon:
            ctk.CTkLabel(win, text="", image=icon).pack(pady=(28, 6))
        ctk.CTkLabel(win, text="GELOTECH", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1a8cff").pack()
        ctk.CTkLabel(win, text="TECH TOOL v1.0 - Restricted Access", font=ctk.CTkFont(size=11), text_color="#a6a6a6").pack(pady=(0, 16))

        role_var = ctk.StringVar(value="Admin")
        role_seg = ctk.CTkSegmentedButton(win, values=["Admin", "User"], variable=role_var,
                                          font=ctk.CTkFont(size=11, weight="bold"), fg_color="#1c2026",
                                          selected_color="#1a8cff", selected_hover_color="#155bb5",
                                          unselected_color="#1c2026", unselected_hover_color="#2a3038",
                                          command=lambda _: self._login_role_changed(win, role_var))
        role_seg.pack(pady=(0, 14))

        form = ctk.CTkFrame(win, fg_color="#16191e", corner_radius=10)
        form.pack(padx=32, fill="x")
        ctk.CTkLabel(form, text="USERNAME", font=ctk.CTkFont(size=9, weight="bold"), text_color="#7a8699").pack(anchor="w", padx=16, pady=(14, 2))
        username_entry = ctk.CTkEntry(form, fg_color="#0d1117", border_color="#30363d", height=34, font=ctk.CTkFont(size=12))
        username_entry.pack(fill="x", padx=16)
        ctk.CTkLabel(form, text="PASSWORD", font=ctk.CTkFont(size=9, weight="bold"), text_color="#7a8699").pack(anchor="w", padx=16, pady=(12, 2))
        password_entry = ctk.CTkEntry(form, fg_color="#0d1117", border_color="#30363d", height=34, font=ctk.CTkFont(size=12), show="\u2022")
        password_entry.pack(fill="x", padx=16, pady=(0, 14))

        error_label = ctk.CTkLabel(win, text="", font=ctk.CTkFont(size=10), text_color="#ff6b6b")
        error_label.pack(pady=(10, 0))
        info_label = ctk.CTkLabel(win, text="Login accounts are verified against the update server.",
                                  font=ctk.CTkFont(size=9), text_color="#484f58")
        info_label.pack(pady=(0, 8))

        login_btn = ctk.CTkButton(win, text="\U0001f511  LOGIN", width=220, height=40, fg_color="#1a8cff",
                                  hover_color="#155bb5", font=ctk.CTkFont(size=13, weight="bold"))
        login_btn.pack(pady=(14, 4))

        def finish_login(users, db_bytes):
            if users is None:
                login_btn.configure(state="normal")
                error_label.configure(text="\u26a0 Could not reach/verify the update server.\nCheck your internet connection and try again.")
                return
            try:
                role = role_var.get()
                name = "admin" if role == "Admin" else username_entry.get().strip()
                pw = password_entry.get()
                rec = users.get(name)
                if not rec or not self._verify_pw(pw, rec.get("hash")):
                    error_label.configure(text="\u26a0 Invalid username or password.")
                    login_btn.configure(state="normal")
                    return
                if db_bytes is None:
                    login_btn.configure(state="normal")
                    error_label.configure(text="\u26a0 Accounts verified, but the package database\ncould not be downloaded/verified from the update server.")
                    return
                try:
                    with open(get_session_database_path(), "wb") as f:
                        f.write(db_bytes)
                except Exception as e:
                    login_btn.configure(state="normal")
                    error_label.configure(text=f"\u26a0 Could not write database cache: {type(e).__name__}: {e}")
                    return
                # Fresh per-login database: drop stale lookups, re-seed lists.
                if hasattr(self, "_uad_cache"):
                    self._uad_cache = None
                if hasattr(self, "_debloat_cache"):
                    self._debloat_cache = None
                self._seed_database_defaults()
                self.current_user = name
                self.is_admin = (name == "admin")
                self.user_perms = None if self.is_admin else set((rec.get("permissions") or {}).keys())
                self.user_tabs = None if self.is_admin else set(rec.get("tabs") or [])
                self._server_users = users
                win.destroy()
                self._apply_permissions()
                self._drop_settings_copy()
                self.deiconify()
                self.lift()
                self.focus_force()
                self.after(1500, self._check_updates)
                self.log_message(f"Logged in as: {name} ({'ADMIN' if self.is_admin else 'USER'}). Access granted.\n" + "=" * 85)
            except Exception as e:
                error_label.configure(text=f"\u26a0 Login error: {type(e).__name__}: {e}")
                login_btn.configure(state="normal")

        def do_login(event=None):
            error_label.configure(text="")
            login_btn.configure(state="disabled", text="\u23f3  CHECKING SERVER...")
            self.after(0, lambda: _purge_session_database())

            def fetch():
                users, db_bytes = _fetch_verified_sources()
                self.after(0, lambda: finish_login(users, db_bytes))

            threading.Thread(target=fetch, daemon=True).start()

        login_btn.configure(command=do_login)

        username_entry.bind("<Return>", do_login)
        password_entry.bind("<Return>", do_login)
        username_entry.focus_set()
        self._login_role_changed(win, role_var)
        self._login_entry_username = username_entry

    def _login_role_changed(self, win, role_var):
        try:
            if role_var.get() == "Admin":
                self._login_entry_username.configure(state="disabled")
                self._login_entry_username.delete(0, "end")
                self._login_entry_username.insert(0, "admin")
            else:
                self._login_entry_username.configure(state="normal")
                if self._login_entry_username.get() == "admin":
                    self._login_entry_username.delete(0, "end")
        except Exception:
            pass

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
        path = os.path.join(get_settings_dir(), "secret.json")
        data = {"clean_excluded": [], "uninstall_excluded": [], "debloated": []}
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
        path = os.path.join(get_settings_dir(), "secret.json")
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
        """Check the embedded update server (EMBEDDED_UPDATE_URL /
        EMBEDDED_UPDATE_TOKEN, pinned in tech_common.py). The update source
        is NEVER read from settings/secret.json, so a compromised local or
        repo settings file cannot redirect clients to a malicious server.
        Expects version.json hosting {"database": N, "banking": N,
        "sha256": {file: hex}} plus a version.json.sig (base64 Ed25519
        signature over the exact bytes of version.json) and the data files
        at the repo root. The manifest signature is verified with the
        embedded public key (tech_common.UPDATE_SIGN_PUBLIC_KEY), and every
        downloaded file's SHA-256 must match the signed manifest before it
        is applied. Only banking_apps.json is distributed via updates: the
        package database is pulled fresh, signature-verified, and cached for
        the session on EVERY login (and deleted on app close / next login),
        and secret.json is NOT distributed at all - login credentials are
        fetched and verified on every login and never written to disk.
        Runs in a background thread."""
        def report(msg):
            if status_cb is not None:
                self.after(0, lambda: status_cb(msg))

        def work():
            data = self._load_settings()
            # Update source is pinned to the embedded constants only.
            base = EMBEDDED_UPDATE_URL.strip().rstrip("/")
            tok = EMBEDDED_UPDATE_TOKEN.strip()
            if not base:
                if manual:
                    report("\u26a0 No update URL embedded. Rebuild the exe.")
                return
            parsed = _parse_repo(base)
            if not parsed:
                if manual:
                    report("\u26a0 Embedded update URL is not a GitHub repo URL.")
                return
            owner, repo, branch = parsed
            headers = {"Authorization": f"Bearer {tok}"} if tok else {}
            try:
                manifest_bytes = _api_fetch(owner, repo, branch, "version.json", headers)
                sig_text = _api_fetch(owner, repo, branch, "version.json.sig", headers)
            except Exception as e:
                if manual:
                    msg = f"\u26a0 Could not reach update server: {type(e).__name__}"
                    if isinstance(e, requests.HTTPError) and e.response is not None:
                        msg += f" (HTTP {e.response.status_code})"
                        if e.response.status_code == 404:
                            msg += " - file missing, or token lacks access"
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
                    raw = _api_fetch(owner, repo, branch, fname, headers)
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
                report("\u2713 Update downloaded. Restart GeloTechTool to apply it.")
                if not manual:
                    self.after(0, lambda: messagebox.showinfo(
                        "Update Ready",
                        "A new database/banking version was downloaded.\nRestart GeloTechTool to apply it."))
            elif manual:
                report("\u2713 You are up to date.")

        threading.Thread(target=work, daemon=True).start()

