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
    APP_VERSION, DEFAULT_USER_PERMS,
)
from tech_reg import (_is_valid_email, _request_password, _fetch_verified_sources,
                      _login_user)

_FONT = "Segoe UI"


class SettingsLoginMixin:
    def _show_login(self):
        win = ctk.CTkToplevel(self)
        win.title(f"GeloTech Tool v{APP_VERSION} - Sign in")
        win.resizable(False, False)
        win.configure(fg_color="#0d1117")
        win.transient(self)
        win.grab_set()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        win.geometry(f"440x650+{(sw - 440) // 2}+{max(0, (sh - 650) // 3)}")
        self._login_win = win
        win.protocol("WM_DELETE_WINDOW", lambda: (self._purge_session_database(), win.destroy(), self.quit()))

        icon = None
        try:
            ico_path = os.path.join(get_bundle_dir(), "gelotech_icon.ico")
            if os.path.isfile(ico_path):
                icon = ctk.CTkImage(light_image=Image.open(ico_path).convert("RGBA"),
                                    dark_image=Image.open(ico_path).convert("RGBA"), size=(64, 64))
        except Exception:
            pass
        if icon:
            ctk.CTkLabel(win, text="", image=icon).pack(pady=(30, 4))

        heading_label = ctk.CTkLabel(win, text="Welcome back", font=ctk.CTkFont(family=_FONT, size=24, weight="bold"),
                                     text_color="#e6edf3")
        heading_label.pack()
        subtitle_label = ctk.CTkLabel(win, text="Sign in to continue to GeloTech Tool",
                                      font=ctk.CTkFont(family=_FONT, size=12), text_color="#8b949e")
        subtitle_label.pack(pady=(2, 14))

        error_label = ctk.CTkLabel(win, text="", font=ctk.CTkFont(family=_FONT, size=10),
                                   text_color="#ff6b6b", wraplength=380)
        error_label.pack(pady=(0, 8))

        def set_header(title, subtitle, color="#e6edf3"):
            heading_label.configure(text=title, text_color=color)
            subtitle_label.configure(text=subtitle)

        # --------------------------------------------------------
        # SIGN IN
        # --------------------------------------------------------
        step_login = ctk.CTkFrame(win, fg_color="#16191e", corner_radius=14)
        login_email_entry = ctk.CTkEntry(step_login, placeholder_text="you@example.com", fg_color="#0d1117",
                                         border_color="#30363d", height=38, font=ctk.CTkFont(family=_FONT, size=12),
                                         corner_radius=8)
        password_entry = ctk.CTkEntry(step_login, fg_color="#0d1117", border_color="#30363d", height=38,
                                      font=ctk.CTkFont(family=_FONT, size=12), show="\u2022", corner_radius=8)
        login_btn = ctk.CTkButton(step_login, text="Sign in", width=220, height=42, fg_color="#1a8cff",
                                  hover_color="#155bb5", corner_radius=8,
                                  font=ctk.CTkFont(family=_FONT, size=13, weight="bold"))
        forgot_btn = ctk.CTkButton(step_login, text="Forgot your password?", width=220, height=26,
                                   fg_color="transparent", hover_color="#1c2026",
                                   font=ctk.CTkFont(family=_FONT, size=11), text_color="#58a6ff")
        create_btn = ctk.CTkButton(step_login, text="New here?  Create an account", width=220, height=26,
                                   fg_color="transparent", hover_color="#1c2026",
                                   font=ctk.CTkFont(family=_FONT, size=11), text_color="#58a6ff")

        def show_login_step(email=""):
            step_email.pack_forget()
            step_login.pack(padx=32, fill="x")
            login_email_entry.configure(state="normal")
            login_email_entry.delete(0, "end")
            set_header("Welcome back", "Sign in to continue to GeloTech Tool")
            if email:
                login_email_entry.insert(0, email)
            password_entry.delete(0, "end")
            password_entry.focus_set()

        # --------------------------------------------------------
        # CREATE ACCOUNT / FORGOT PASSWORD
        # --------------------------------------------------------
        step_email = ctk.CTkFrame(win, fg_color="#16191e", corner_radius=14)
        email_entry = ctk.CTkEntry(step_email, placeholder_text="you@example.com", fg_color="#0d1117",
                                   border_color="#30363d", height=38, font=ctk.CTkFont(family=_FONT, size=12),
                                   corner_radius=8)
        send_btn = ctk.CTkButton(step_email, text="Send my password", width=220, height=42,
                                 fg_color="#1a8cff", hover_color="#155bb5", corner_radius=8,
                                 font=ctk.CTkFont(family=_FONT, size=13, weight="bold"))
        back_btn = ctk.CTkButton(step_email, text="\u2190  Back to sign in", width=220, height=26,
                                 fg_color="transparent", hover_color="#1c2026",
                                 font=ctk.CTkFont(family=_FONT, size=11), text_color="#58a6ff")

        def show_email_step(mode="create", prefill=""):
            step_login.pack_forget()
            step_email.pack(padx=32, fill="x")
            if mode == "reset":
                set_header("Forgot your password?", "Enter your email and we'll send you a new password.")
            else:
                set_header("Create an account", "Enter your email and we'll send you a password to sign in.")
            if prefill:
                email_entry.delete(0, "end")
                email_entry.insert(0, prefill)
            email_entry.focus_set()

        # --------------------------------------------------------
        # CREATE / RESET action: generate + email a password
        # --------------------------------------------------------
        def send_password(event=None):
            email = email_entry.get().strip()
            if not _is_valid_email(email):
                error_label.configure(text="\u26a0 Please enter a valid email address.", text_color="#ff6b6b")
                return
            error_label.configure(text="")
            send_btn.configure(state="disabled", text="Sending...")
            email_entry.configure(state="disabled")

            def worker():
                ok, msg = _request_password(email)
                self.after(0, lambda: finish_send(ok, msg))

            def finish_send(ok, msg):
                send_btn.configure(state="normal", text="Send my password")
                email_entry.configure(state="normal")
                if ok:
                    error_label.configure(text="\u2713 " + msg, text_color="#2ecc71")
                    self.after(1200, lambda: show_login_step(email=email))
                else:
                    error_label.configure(text="\u26a0 " + msg, text_color="#ff6b6b")

            threading.Thread(target=worker, daemon=True).start()

        email_entry.bind("<Return>", send_password)
        send_btn.configure(command=send_password)
        back_btn.configure(command=lambda: show_login_step())

        # --------------------------------------------------------
        # SIGN IN action: verify credentials + download database
        # --------------------------------------------------------
        def finish_login(ok, reason, user, session, db_bytes):
            if not ok:
                login_btn.configure(state="normal")
                message = {
                    "blocked": "This account has been blocked by the maintainer.",
                    "invalid-credentials": "Invalid email/username or password.",
                    "invalid-request": "Please enter both your email/username and password.",
                    "rate-limited": "Too many login attempts. Please wait a minute and try again.",
                    "server-error": "The auth server hit an error. Please try again in a moment.",
                }.get(reason, reason or "Login failed.")
                error_label.configure(text="\u26a0 " + message, text_color="#ff6b6b")
                return
            if db_bytes is None:
                login_btn.configure(state="normal")
                error_label.configure(text="\u26a0 Account verified, but the package database\ncould not be downloaded/verified from the update server.", text_color="#ff6b6b")
                return
            try:
                name = login_email_entry.get().strip()
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
                # The Worker decides the role: the client only displays what the
                # server-issued session grants (and the Worker enforces every
                # privileged operation regardless of the UI).
                self.is_admin = (user.get("role") == "admin")
                # Session token from the Worker: memory only, never persisted.
                self._auth_session = session
                if self.is_admin:
                    self.user_perms = None
                    self.user_tabs = None
                else:
                    self.user_perms = set((user.get("permissions") or {}).keys())
                    self.user_tabs = set(user.get("tabs") or []) or None
                    if not self.user_perms:
                        # No explicit perms in secret.json: grant everything
                        # except the admin-only features (VirusTotal).
                        self.user_perms = set(DEFAULT_USER_PERMS)
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
            name = login_email_entry.get().strip()
            # The maintainer account signs in with its own username + password;
            # the Worker verifies both and decides the admin role server-side.
            if name != "admin" and not _is_valid_email(name):
                error_label.configure(text="\u26a0 Please enter a valid email address.", text_color="#ff6b6b")
                return
            pw = password_entry.get()
            if not pw:
                error_label.configure(text="\u26a0 Please enter your password.", text_color="#ff6b6b")
                return
            login_btn.configure(state="disabled", text="Signing in...")
            self.after(0, lambda: self._purge_session_database())

            def fetch():
                ok, reason, user, session = _login_user(name, pw)
                db_bytes = _fetch_verified_sources()
                self.after(0, lambda: finish_login(ok, reason, user, session, db_bytes))

            threading.Thread(target=fetch, daemon=True).start()

        login_btn.configure(command=do_login)
        password_entry.bind("<Return>", do_login)
        login_email_entry.bind("<Return>", do_login)
        forgot_btn.configure(command=lambda: show_email_step("reset", login_email_entry.get().strip()))
        create_btn.configure(command=lambda: show_email_step("create"))

        # ---------------- SIGN IN card layout ----------------
        ctk.CTkLabel(step_login, text="Email address", font=ctk.CTkFont(family=_FONT, size=11, weight="bold"),
                     text_color="#7a8699").pack(anchor="w", padx=18, pady=(18, 4))
        login_email_entry.pack(fill="x", padx=18)
        ctk.CTkLabel(step_login, text="Password", font=ctk.CTkFont(family=_FONT, size=11, weight="bold"),
                     text_color="#7a8699").pack(anchor="w", padx=18, pady=(12, 4))
        password_entry.pack(fill="x", padx=18)
        login_btn.pack(pady=(18, 2))
        forgot_btn.pack(pady=(4, 0))
        create_btn.pack(pady=(0, 16))
        ctk.CTkLabel(step_login, text="Maintainers: sign in with the admin account.",
                     font=ctk.CTkFont(family=_FONT, size=9), text_color="#484f58").pack(pady=(0, 12))

        # ---------------- CREATE / RESET card layout ----------------
        ctk.CTkLabel(step_email, text="Email address", font=ctk.CTkFont(family=_FONT, size=11, weight="bold"),
                     text_color="#7a8699").pack(anchor="w", padx=18, pady=(18, 4))
        email_entry.pack(fill="x", padx=18)
        send_btn.pack(pady=(18, 2))
        back_btn.pack(pady=(0, 16))

        ctk.CTkLabel(win, text="Your account is verified securely on every sign-in.",
                     font=ctk.CTkFont(family=_FONT, size=9), text_color="#484f58").pack(pady=(10, 0))

        show_login_step()

        if getattr(self, "_theme_mode", "dark") != "dark":
            self._theme_walk(win)