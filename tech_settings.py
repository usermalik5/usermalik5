# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox, ttk
import threading
import os
import json
import re
import hashlib
import sys
import requests
import shutil
from PIL import Image, ImageDraw, ImageFont
from tech_common import get_bundle_dir, get_app_dir, get_cache_dir, get_settings_dir, get_live_database_path, get_session_database_path, Tooltip, subprocess, load_package_database, EMBEDDED_UPDATE_URL, EMBEDDED_UPDATE_TOKEN, ADMIN_SECRET_PHRASE, DEFAULT_USER_PERMS, APP_VERSION
from tech_admin import AdminPanelMixin

from tech_reg import (_parse_repo, _api_fetch, _verify_manifest_sig, _fetch_verified_sources,
                      _fetch_verified_users, _purge_session_database, _is_valid_email,
                      _request_password, hash_password, verify_password)

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
        disk: users are fetched from the signed update server on every login."""
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
    def _hash_pw(pw):
        return hash_password(pw)

    @staticmethod
    def _verify_pw(pw, stored):
        return verify_password(pw, stored)

    @staticmethod
    def _purge_session_database():
        _purge_session_database()

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
        win.title(f"GeloTech Tool v{APP_VERSION} - Login")
        win.resizable(False, False)
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win.geometry(f"440x600+{(sw - 440) // 2}+{max(0, (sh - 600) // 3)}")
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
            ctk.CTkLabel(win, text="", image=icon).pack(pady=(28, 4))
        ctk.CTkLabel(win, text="GELOTECH", font=ctk.CTkFont(size=22, weight="bold"), text_color="#1a8cff").pack()
        ctk.CTkLabel(win, text=f"TECH TOOL v{APP_VERSION}", font=ctk.CTkFont(size=11), text_color="#a6a6a6").pack(pady=(0, 14))

        admin_mode = {"on": False}

        error_label = ctk.CTkLabel(win, text="", font=ctk.CTkFont(size=10), text_color="#ff6b6b", wraplength=380)
        error_label.pack(pady=(6, 0))

        # --------------------------------------------------------
        # STEP A - enter email to receive a generated password
        # --------------------------------------------------------
        step_email = ctk.CTkFrame(win, fg_color="#16191e", corner_radius=10)
        step_email.pack(padx=32, fill="x")
        ctk.CTkLabel(step_email, text="ENTER YOUR EMAIL ADDRESS", font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#7a8699").pack(anchor="w", padx=16, pady=(14, 2))
        email_entry = ctk.CTkEntry(step_email, placeholder_text="you@example.com", fg_color="#0d1117",
                                   border_color="#30363d", height=34, font=ctk.CTkFont(size=12))
        email_entry.pack(fill="x", padx=16)
        ctk.CTkLabel(step_email, text="New here or forgot your password? Enter your email and we will\n"
                                      "send you a generated password. Check your inbox AND spam folder.",
                     font=ctk.CTkFont(size=9), text_color="#8b949e", justify="left").pack(anchor="w", padx=16, pady=(8, 12))
        send_btn = ctk.CTkButton(step_email, text="\u2709  SEND PASSWORD TO MY EMAIL", width=220, height=38,
                                 fg_color="#1a8cff", hover_color="#155bb5", font=ctk.CTkFont(size=12, weight="bold"))
        send_btn.pack(pady=(0, 14))

        # --------------------------------------------------------
        # STEP B - log in with email + password
        # --------------------------------------------------------
        step_login = ctk.CTkFrame(win, fg_color="#16191e", corner_radius=10)
        login_email_entry = ctk.CTkEntry(step_login, placeholder_text="you@example.com", fg_color="#0d1117",
                                         border_color="#30363d", height=34, font=ctk.CTkFont(size=12))
        password_entry = ctk.CTkEntry(step_login, fg_color="#0d1117", border_color="#30363d", height=34,
                                      font=ctk.CTkFont(size=12), show="\u2022")
        login_btn = ctk.CTkButton(step_login, text="\U0001f511  LOGIN", width=220, height=40, fg_color="#1a8cff",
                                  hover_color="#155bb5", font=ctk.CTkFont(size=13, weight="bold"))
        forgot_btn = ctk.CTkButton(step_login, text="Forgot password? Get a new one by email", width=220, height=28,
                                   fg_color="transparent", hover_color="#1c2026", font=ctk.CTkFont(size=10),
                                   text_color="#58a6ff")

        def show_email_step(prefill=""):
            step_login.pack_forget()
            step_email.pack(padx=32, fill="x")
            admin_mode["on"] = False
            if prefill:
                email_entry.delete(0, "end")
                email_entry.insert(0, prefill)
            email_entry.focus_set()

        def show_login_step(admin=False, email=""):
            step_email.pack_forget()
            step_login.pack(padx=32, fill="x")
            login_email_entry.configure(state="normal")
            login_email_entry.delete(0, "end")
            if admin:
                admin_mode["on"] = True
                login_email_entry.insert(0, "admin")
                login_email_entry.configure(state="disabled")
                error_label.configure(text="\U0001f511  MAINTAINER ACCESS", text_color="#d4af37")
            else:
                login_email_entry.configure(state="normal")
                if email:
                    login_email_entry.insert(0, email)
            password_entry.delete(0, "end")
            password_entry.focus_set()

        def check_secret(event=None):
            # Typing the secret phrase into the email field unlocks admin login.
            if (event and event.keysym in ("Return", "Tab")) or not event:
                if email_entry.get().strip() == ADMIN_SECRET_PHRASE:
                    show_login_step(admin=True)

        def check_secret_login(event=None):
            # Same secret-phrase unlock on the LOGIN page's email field:
            # lock the username to "admin" so the password check works.
            if (event and event.keysym in ("Return", "Tab")) or not event:
                if login_email_entry.get().strip() == ADMIN_SECRET_PHRASE:
                    admin_mode["on"] = True
                    login_email_entry.delete(0, "end")
                    login_email_entry.insert(0, "admin")
                    login_email_entry.configure(state="disabled")
                    error_label.configure(text="\U0001f511  MAINTAINER ACCESS", text_color="#d4af37")
                    password_entry.focus_set()

        # --------------------------------------------------------
        # STEP A action: generate + email a password
        # --------------------------------------------------------
        def send_password(event=None):
            email = email_entry.get().strip()
            if email == ADMIN_SECRET_PHRASE:
                show_login_step(admin=True)
                return
            if not _is_valid_email(email):
                error_label.configure(text="\u26a0 Please enter a valid email address.", text_color="#ff6b6b")
                return
            error_label.configure(text="")
            send_btn.configure(state="disabled", text="\u23f3  SENDING PASSWORD...")
            email_entry.configure(state="disabled")

            def worker():
                ok, msg = _request_password(email)
                self.after(0, lambda: finish_send(ok, msg))

            def finish_send(ok, msg):
                send_btn.configure(state="normal", text="\u2709  SEND PASSWORD TO MY EMAIL")
                email_entry.configure(state="normal")
                if ok:
                    error_label.configure(text="\u2713 " + msg, text_color="#2ecc71")
                    self.after(1200, lambda: show_login_step(admin=False, email=email))
                else:
                    error_label.configure(text="\u26a0 " + msg, text_color="#ff6b6b")

            threading.Thread(target=worker, daemon=True).start()

        email_entry.bind("<KeyRelease>", check_secret)
        email_entry.bind("<Return>", lambda e: check_secret(e) or send_password(e))
        send_btn.configure(command=send_password)

        # --------------------------------------------------------
        # STEP B action: verify credentials + download database
        # --------------------------------------------------------
        def finish_login(users, db_bytes):
            if users is None:
                login_btn.configure(state="normal")
                error_label.configure(text="\u26a0 Could not reach/verify the update server.\nCheck your internet connection and try again.", text_color="#ff6b6b")
                return
            try:
                name = "admin" if admin_mode["on"] else login_email_entry.get().strip()
                if not admin_mode["on"] and not _is_valid_email(name):
                    error_label.configure(text="\u26a0 Please enter a valid email address.", text_color="#ff6b6b")
                    login_btn.configure(state="normal")
                    return
                pw = password_entry.get()
                rec = users.get(name)
                if rec and rec.get("blocked"):
                    if admin_mode["on"]:
                        admin_mode["on"] = False
                        login_email_entry.configure(state="normal")
                        login_email_entry.delete(0, "end")
                    error_label.configure(text="\u26a0 This account has been blocked by the maintainer.", text_color="#ff6b6b")
                    login_btn.configure(state="normal")
                    return
                if not rec or not self._verify_pw(pw, rec.get("hash")):
                    if admin_mode["on"]:
                        # Wrong admin password: release the locked field so the
                        # user can retry as a normal account or re-enter phrase.
                        admin_mode["on"] = False
                        login_email_entry.configure(state="normal")
                        login_email_entry.delete(0, "end")
                    error_label.configure(text="\u26a0 Invalid email/username or password.", text_color="#ff6b6b")
                    login_btn.configure(state="normal")
                    return
                if db_bytes is None:
                    login_btn.configure(state="normal")
                    error_label.configure(text="\u26a0 Accounts verified, but the package database\ncould not be downloaded/verified from the update server.", text_color="#ff6b6b")
                    return
                try:
                    with open(get_session_database_path(), "wb") as f:
                        f.write(db_bytes)
                except Exception as e:
                    login_btn.configure(state="normal")
                    error_label.configure(text=f"\u26a0 Could not write database cache: {type(e).__name__}: {e}", text_color="#ff6b6b")
                    return
                # Fresh per-login database: drop stale lookups, re-seed lists.
                if hasattr(self, "_uad_cache"):
                    self._uad_cache = None
                if hasattr(self, "_debloat_cache"):
                    self._debloat_cache = None
                self._seed_database_defaults()
                self.current_user = name
                self.is_admin = (name == "admin")
                if self.is_admin:
                    self.user_perms = None
                    self.user_tabs = None
                else:
                    self.user_perms = set((rec.get("permissions") or {}).keys())
                    self.user_tabs = set(rec.get("tabs") or []) or None
                    if not self.user_perms:
                        # No explicit perms in secret.json: grant everything
                        # except the admin-only features (VirusTotal).
                        self.user_perms = set(DEFAULT_USER_PERMS)
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
                error_label.configure(text=f"\u26a0 Login error: {type(e).__name__}: {e}", text_color="#ff6b6b")
                login_btn.configure(state="normal")

        def do_login(event=None):
            error_label.configure(text="")
            if login_email_entry.get().strip() == ADMIN_SECRET_PHRASE:
                admin_mode["on"] = True
                error_label.configure(text="\U0001f511  MAINTAINER ACCESS", text_color="#d4af37")
            login_btn.configure(state="disabled", text="\u23f3  CHECKING SERVER...")
            self.after(0, lambda: _purge_session_database())

            def fetch():
                users, db_bytes = _fetch_verified_sources()
                self.after(0, lambda: finish_login(users, db_bytes))

            threading.Thread(target=fetch, daemon=True).start()

        login_btn.configure(command=do_login)
        password_entry.bind("<Return>", do_login)
        login_email_entry.bind("<Return>", do_login)
        login_email_entry.bind("<KeyRelease>", check_secret_login)
        forgot_btn.configure(command=lambda: show_email_step(login_email_entry.get().strip()))

        ctk.CTkLabel(step_login, text="EMAIL ADDRESS", font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#7a8699").pack(anchor="w", padx=16, pady=(14, 2))
        login_email_entry.pack(fill="x", padx=16)
        ctk.CTkLabel(step_login, text="PASSWORD", font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#7a8699").pack(anchor="w", padx=16, pady=(12, 2))
        password_entry.pack(fill="x", padx=16, pady=(0, 14))
        login_btn.pack(pady=(0, 4))
        forgot_btn.pack(pady=(0, 10))

        ctk.CTkLabel(win, text="Accounts are verified against the update server on every login.",
                     font=ctk.CTkFont(size=9), text_color="#484f58").pack(pady=(8, 0))

        show_login_step()

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

