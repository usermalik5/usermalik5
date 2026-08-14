# -*- coding: utf-8 -*-
import customtkinter as ctk
import threading


class AdminPanelMixin:

    # ----------------------------------------------------
    # ACCOUNT MANAGEMENT (read-only account overview)
    # ----------------------------------------------------
    def _open_admin_panel(self):
        if not getattr(self, "is_admin", False):
            return
        from tech_settings import _fetch_verified_users
        dialog = ctk.CTkToplevel(self)
        dialog.title("Account management")
        dialog.configure(fg_color="#0d1117")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        dialog.geometry(f"{int(sw * 0.55)}x{int(sh * 0.7)}+{int(sw * 0.225)}+{int(sh * 0.15)}")
        dialog.minsize(480, 380)

        header = ctk.CTkFrame(dialog, fg_color="#0d1117")
        header.pack(fill="x", padx=14, pady=(12, 0))
        ctk.CTkLabel(header, text="Account management",
                     font=ctk.CTkFont(size=16, weight="bold"), text_color="#d4af37").pack(anchor="w")
        ctk.CTkLabel(header,
                     text="Manage who can sign in to the tool.\n"
                          "Blocking an account locks it out until you unblock it.",
                     font=ctk.CTkFont(size=10), text_color="#8b949e", justify="left").pack(anchor="w", pady=(2, 8))

        status = ctk.CTkLabel(dialog, text="Loading accounts\u2026",
                              font=ctk.CTkFont(size=10), text_color="#8b949e")
        status.pack(anchor="w", padx=14)

        search_row = ctk.CTkFrame(dialog, fg_color="#0d1117")
        search_row.pack(fill="x", padx=14, pady=(8, 0))
        search_entry = ctk.CTkEntry(search_row, placeholder_text="Search accounts\u2026 (email / username)",
                                    fg_color="#0d1117", border_color="#30363d", height=32,
                                    font=ctk.CTkFont(size=11), corner_radius=8)
        search_entry.pack(side="left", fill="x", expand=True)
        count_label = ctk.CTkLabel(search_row, text="", font=ctk.CTkFont(size=10), text_color="#8b949e")
        count_label.pack(side="right", padx=(10, 0))

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color="#16191e", corner_radius=8)
        list_frame.pack(fill="both", expand=True, padx=14, pady=8)

        btn_row = ctk.CTkFrame(dialog, fg_color="#0d1117")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(btn_row, text="\u21bb  Refresh", width=110, height=32, fg_color="#1f6feb",
                      hover_color="#1a5fd0", font=ctk.CTkFont(size=11, weight="bold"),
                      command=lambda: load()).pack(side="left")
        ctk.CTkButton(btn_row, text="Close", width=90, height=32, fg_color="#21262d", hover_color="#30363d",
                      font=ctk.CTkFont(size=11), command=dialog.destroy).pack(side="right")

        def change_password(name):
            from tech_reg import _admin_set_password
            session = getattr(self, "_auth_session", None)
            dlg = ctk.CTkToplevel(dialog)
            dlg.title(f"Change password - {name}")
            dlg.configure(fg_color="#0d1117")
            dlg.transient(dialog)
            dlg.grab_set()
            dlg.resizable(False, False)
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            dlg.geometry(f"360x260+{(sw - 360) // 2}+{max(0, (sh - 260) // 3)}")
            ctk.CTkLabel(dlg, text=f"New password for {name}",
                         font=ctk.CTkFont(size=12, weight="bold"), text_color="#e6edf3").pack(pady=(16, 2))
            ctk.CTkLabel(dlg, text="8-256 characters. Hashed server-side by the auth server.",
                         font=ctk.CTkFont(size=9), text_color="#8b949e").pack()
            pw1 = ctk.CTkEntry(dlg, show="\u2022", fg_color="#0d1117", border_color="#30363d", height=34)
            pw2 = ctk.CTkEntry(dlg, show="\u2022", fg_color="#0d1117", border_color="#30363d", height=34)
            pw1.pack(fill="x", padx=24, pady=(12, 6))
            pw2.pack(fill="x", padx=24, pady=(0, 10))
            err = ctk.CTkLabel(dlg, text="", font=ctk.CTkFont(size=9), text_color="#ff6b6b")
            err.pack()
            row = ctk.CTkFrame(dlg, fg_color="#0d1117")
            row.pack(fill="x", padx=24, pady=(4, 14))
            ok_btn = ctk.CTkButton(row, text="Change password", width=130, height=32, fg_color="#1f6feb",
                                   hover_color="#1a5fd0", font=ctk.CTkFont(size=11, weight="bold"))
            ok_btn.pack(side="left")
            ctk.CTkButton(row, text="Cancel", width=80, height=32, fg_color="#21262d", hover_color="#30363d",
                          font=ctk.CTkFont(size=11), command=dlg.destroy).pack(side="right")

            def ok():
                p1, p2 = pw1.get(), pw2.get()
                if len(p1) < 8:
                    err.configure(text="Password must be at least 8 characters.")
                    return
                if p1 != p2:
                    err.configure(text="Passwords do not match.")
                    return
                ok_btn.configure(state="disabled", text="Saving...")

                def worker():
                    e = _admin_set_password(name, p1, session)
                    self.after(0, lambda: done(e))

                def done(e):
                    if e:
                        ok_btn.configure(state="normal", text="Change password")
                        err.configure(text="\u26a0 " + e)
                    else:
                        dlg.destroy()
                        status.configure(text="\u2713 Password changed for %s." % name, text_color="#2ecc71")

                threading.Thread(target=worker, daemon=True).start()

            ok_btn.configure(command=ok)
            pw1.bind("<Return>", lambda e: ok())
            pw2.bind("<Return>", lambda e: ok())
            pw1.focus_set()

        def toggle_blocked(name, blocked):
            from tech_reg import _set_user_blocked
            status.configure(text=("\u23f3 Blocking %s\u2026" % name) if blocked
                             else ("\u23f3 Unblocking %s\u2026" % name), text_color="#8b949e")
            for w in list_frame.winfo_children():
                w.destroy()
            session = getattr(self, "_auth_session", None)

            def worker():
                err = _set_user_blocked(name, blocked, session)
                self.after(0, lambda: finish_toggle(err, name, blocked))

            def finish_toggle(err, name, blocked):
                if err:
                    status.configure(text="\u26a0 " + err, text_color="#ff6b6b")
                else:
                    status.configure(text="\u2713 %s has been %s."
                                          % (name, "blocked" if blocked else "unblocked"),
                                     text_color="#2ecc71")
                load()

            threading.Thread(target=worker, daemon=True).start()

        def render(users, query=""):
            for w in list_frame.winfo_children():
                w.destroy()
            names = sorted(users) if users else []
            q = query.strip().lower()
            if q:
                names = [n for n in names if q in n.lower()]
            if not users:
                count_label.configure(text="0 accounts")
            else:
                count_label.configure(text="%d / %d accounts" % (len(names), len(users)))
            if not names:
                ctk.CTkLabel(list_frame, text=("No accounts match your search."
                                               if q and users else "No accounts yet."),
                             font=ctk.CTkFont(size=11), text_color="#8b949e").pack(pady=20)
                return
            for name in names:
                rec = users[name] or {}
                is_admin = (name == "admin")
                blocked = bool(rec.get("blocked"))
                card = ctk.CTkFrame(list_frame, fg_color="#0d1117", corner_radius=6)
                card.pack(fill="x", padx=2, pady=3)
                title = ctk.CTkLabel(card, text=f"{name}   [{'Admin' if is_admin else 'User'}]",
                                     font=ctk.CTkFont(size=11, weight="bold"),
                                     text_color="#d4af37" if is_admin else "#58a6ff")
                title.pack(anchor="w", padx=10, pady=(6, 0))
                if is_admin:
                    ctk.CTkLabel(card, text="Full access to all features.",
                                 font=ctk.CTkFont(size=9), text_color="#8b949e").pack(anchor="w", padx=10, pady=(0, 6))
                else:
                    perms = rec.get("permissions") or {}
                    perm_labels = [self.PERMISSIONS[k] for k in self.PERMISSIONS if perms.get(k)]
                    tabs = rec.get("tabs") or []
                    info = ""
                    if perm_labels:
                        info += "Features: " + ", ".join(perm_labels)
                    if tabs:
                        info += ("\n" if info else "") + "Tabs: " + ", ".join(tabs)
                    if not info:
                        info = "No features or tabs enabled."
                    ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=9), text_color="#c9d1d9",
                                 justify="left", wraplength=560).pack(anchor="w", padx=10, pady=(0, 6))

                controls = ctk.CTkFrame(card, fg_color="#0d1117")
                controls.pack(fill="x", padx=10, pady=(0, 6))
                badge_text = ("\u25cf  Blocked" if blocked else "\u25cf  Active")
                ctk.CTkLabel(controls, text=badge_text,
                             font=ctk.CTkFont(size=9, weight="bold"),
                             text_color="#ff6b6b" if blocked else "#2ecc71").pack(side="left")
                ctk.CTkButton(controls, text="Change password", width=110, height=26,
                              fg_color="#21262d", hover_color="#30363d",
                              font=ctk.CTkFont(size=10, weight="bold"),
                              command=lambda n=name: change_password(n)).pack(side="right")
                if not is_admin:
                    action_text = "Unblock" if blocked else "Block"
                    action_color = "#2ea043" if blocked else "#da3633"
                    action_hover = "#238636" if blocked else "#b62324"
                    ctk.CTkButton(controls, text=action_text, width=90, height=26,
                                  fg_color=action_color, hover_color=action_hover,
                                  font=ctk.CTkFont(size=10, weight="bold"),
                                  command=lambda n=name, b=not blocked: toggle_blocked(n, b)).pack(side="right", padx=(6, 0))

        all_users = {}

        def load():
            status.configure(text="Loading accounts from the auth server\u2026")
            for w in list_frame.winfo_children():
                w.destroy()
            session = getattr(self, "_auth_session", None)
            threading.Thread(target=lambda: finish(*_fetch_verified_users(session)), daemon=True).start()

        search_entry.bind("<KeyRelease>", lambda e: render(all_users, search_entry.get()))

        def finish(users, err):
            if err:
                status.configure(text="\u26a0 " + err, text_color="#ff6b6b")
                return
            if users is None:
                status.configure(text="\u26a0 Could not reach the auth server.\n"
                                      "Check your connection and press Refresh.",
                                 text_color="#ff6b6b")
                return
            all_users.clear()
            all_users.update(users)
            status.configure(text="\u2713 Accounts loaded from the auth server.",
                             text_color="#2ecc71")
            render(users, search_entry.get())

        load()
