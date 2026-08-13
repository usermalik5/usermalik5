# -*- coding: utf-8 -*-
"""Login UI for SettingsMixin.

Split out of tech_settings.py so each source module stays under the PyArmor
per-file size limit used by the obfuscated production build. The method is
still a mixin of GeloTechTool, so it resolves via the normal MRO.
"""
import customtkinter as ctk
import os
import threading
from PIL import Image
from tech_common import (
    get_bundle_dir, get_session_database_path, get_live_database_path,
    APP_VERSION, ADMIN_SECRET_PHRASE, DEFAULT_USER_PERMS,
)
from tech_reg import (_is_valid_email, _request_password, _fetch_verified_sources)


class SettingsLoginMixin:
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
        win.protocol("WM_DELETE_WINDOW", lambda: (self._purge_session_database(), win.destroy(), self.quit()))

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
                # Point the package-database service at the freshly downloaded,
                # verified session database (not the stale startup/live path) so
                # the bloatware UAD lookup uses the exact verified DB. Done before
                # anything calls _build_uad_lookup().
                if hasattr(self, "database_service"):
                    self.database_service.set_path(get_live_database_path())
                    self.database_service.clear()
                # Fresh per-login database: drop stale lookups, re-seed lists.
                if hasattr(self, "_uad_cache"):
                    self._uad_cache = None
                if hasattr(self, "_debloat_cache"):
                    self._debloat_cache = None
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
                self._initialize_runtime_after_login()
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
            self.after(0, lambda: self._purge_session_database())

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

        if getattr(self, "_theme_mode", "dark") != "dark":
            self._theme_walk(win)

