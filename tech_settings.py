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
from tech_common import get_bundle_dir, get_app_dir, get_cache_dir, get_settings_dir, get_live_database_path, Tooltip, subprocess, load_package_database, EMBEDDED_UPDATE_URL, EMBEDDED_UPDATE_TOKEN
from tech_admin import AdminPanelMixin


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
        """First-run: consolidate exclusion lists + UAD backup into one settings JSON."""
        app = get_app_dir()
        sfile = os.path.join(get_settings_dir(), "gelotech_settings.json")
        old_sfile = os.path.join(app, "gelotech_settings.json")
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
                "clean_excluded": sorted(clean),
                "uninstall_excluded": sorted(uninstall),
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
        The copy is set as a hidden Windows file, and passwords inside are
        stored as salted PBKDF2 hashes, so exposing the file is not a risk."""
        try:
            src = os.path.join(get_settings_dir(), "gelotech_settings.json")
            if os.path.isfile(src):
                dest = os.path.join(get_app_dir(), "gelotech_settings.json")
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

    def _ensure_default_users(self):
        data = self._load_settings()
        users = data.get("users") or {}
        if not isinstance(users, dict):
            users = {}
        if "admin" not in users:
            users["admin"] = {"hash": self._hash_pw("admin123"), "permissions": {}}
            data["users"] = users
            self._save_settings(data)

    def _save_users(self, users):
        data = self._load_settings()
        data["users"] = users
        self._save_settings(data)

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
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), self.quit()))

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

        def do_login(event=None):
            try:
                role = role_var.get()
                name = username_entry.get().strip()
                pw = password_entry.get()
                users = self._load_settings().get("users") or {}
                if role == "Admin":
                    name = "admin"
                rec = users.get(name)
                if not rec or not self._verify_pw(pw, rec.get("hash")):
                    error_label.configure(text="\u26a0 Invalid username or password.")
                    return
                if rec.get("hash") and "$" not in str(rec.get("hash")):
                    users[name]["hash"] = self._hash_pw(pw)
                    self._save_settings({**self._load_settings(), "users": users})
                self.current_user = name
                self.is_admin = (name == "admin")
                self.user_perms = None if self.is_admin else set((rec.get("permissions") or {}).keys())
                self.user_tabs = None if self.is_admin else set(rec.get("tabs") or [])
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

        ctk.CTkButton(win, text="\U0001f511  LOGIN", width=220, height=40, fg_color="#1a8cff", hover_color="#155bb5",
                      font=ctk.CTkFont(size=13, weight="bold"), command=do_login).pack(pady=(14, 4))
        ctk.CTkLabel(win, text="Default admin: admin / admin123  \u00b7  change it in the Admin Panel after login",
                     font=ctk.CTkFont(size=9), text_color="#484f58").pack(pady=(6, 14))

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
        path = os.path.join(get_settings_dir(), "gelotech_settings.json")
        data = {"clean_excluded": [], "uninstall_excluded": [], "debloated": [], "users": {}}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    for key in data:
                        if isinstance(loaded.get(key), type(data[key])):
                            data[key] = loaded[key]
                    for key in ("update_url", "update_token", "update_state"):
                        if isinstance(loaded.get(key), type(data.get(key, ""))):
                            data[key] = loaded[key]
            except Exception:
                pass
        return data

    def _save_settings(self, data):
        path = os.path.join(get_settings_dir(), "gelotech_settings.json")
        try:
            payload = {}
            for key, value in data.items():
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
        """Check the update server configured in settings ('update_url', a
        GitHub repo URL like https://github.com/USER/REPO). Expects
        version.json hosting {"database": N, "settings": N} plus the two
        files at the repo root. Downloads a newer database or settings into
        the settings folder so it overrides the bundled copy; restarting the
        app applies them. Private repos need 'update_token' (a classic GitHub
        PAT with repo scope). Runs in a background thread."""
        def report(msg):
            if status_cb is not None:
                self.after(0, lambda: status_cb(msg))

        def parse_repo(base):
            m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?(?:\?|$|/tree/([^/]+))", base)
            if not m:
                return None
            owner, repo = m.group(1), m.group(2)
            branch = m.group(3) or "main"
            return owner, repo, branch

        def api_fetch(owner, repo, branch, fname, headers):
            if headers:
                url = f"https://api.github.com/repos/{owner}/{repo}/contents/{fname}?ref={branch}"
                resp = requests.get(url, headers={**headers, "Accept": "application/vnd.github+json"}, timeout=60)
                resp.raise_for_status()
                return base64.b64decode(resp.json()["content"]).decode("utf-8")
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{fname}"
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return resp.text

        def work():
            data = self._load_settings()
            base = (data.get("update_url") or EMBEDDED_UPDATE_URL).strip().rstrip("/")
            tok = (data.get("update_token") or EMBEDDED_UPDATE_TOKEN).strip()
            if not base:
                if manual:
                    report("\u26a0 No update URL configured. Set it in the Admin Panel first.")
                return
            parsed = parse_repo(base)
            if not parsed:
                if manual:
                    report("\u26a0 That URL is not a GitHub repo URL.")
                return
            owner, repo, branch = parsed
            headers = {"Authorization": f"Bearer {tok}"} if tok else {}
            try:
                manifest = json.loads(api_fetch(owner, repo, branch, "version.json", headers))
            except Exception as e:
                if manual:
                    msg = f"\u26a0 Could not reach update server: {type(e).__name__}"
                    if isinstance(e, requests.HTTPError) and e.response is not None:
                        msg += f" (HTTP {e.response.status_code})"
                        if e.response.status_code == 404:
                            msg += " - file missing, or token lacks access"
                    report(msg)
                return
            last = self._load_settings().get("update_state") or {}
            changed = False
            new_state = dict(last)
            for fname, key in (("gelotech_database_v3.json", "database"),
                               ("gelotech_settings.json", "settings"),
                               ("banking_apps.json", "banking")):
                new_v = manifest.get(key)
                if new_v is None or last.get(key) == new_v:
                    continue
                try:
                    text = api_fetch(owner, repo, branch, fname, headers)
                    parsed = json.loads(text)
                    dest = os.path.join(get_settings_dir(), fname)
                    if os.path.exists(dest):
                        with open(dest, "rb") as f:
                            data_bak = f.read()
                        bak = dest + ".bak"
                        with open(bak, "wb") as f:
                            f.write(data_bak)
                    with open(dest, "w", encoding="utf-8") as f:
                        json.dump(parsed, f, indent=2)
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
                        "A new database/settings version was downloaded.\nRestart GeloTechTool to apply it."))
            elif manual:
                report("\u2713 You are up to date.")

        threading.Thread(target=work, daemon=True).start()

