# -*- coding: utf-8 -*-
import customtkinter as ctk
import threading


class AdminPanelMixin:

    # ----------------------------------------------------
    # ADMIN PANEL (read-only account overview)
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

        list_frame = ctk.CTkScrollableFrame(dialog, fg_color="#16191e", corner_radius=8)
        list_frame.pack(fill="both", expand=True, padx=14, pady=8)

        btn_row = ctk.CTkFrame(dialog, fg_color="#0d1117")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(btn_row, text="\u21bb  Refresh", width=110, height=32, fg_color="#1f6feb",
                      hover_color="#1a5fd0", font=ctk.CTkFont(size=11, weight="bold"),
                      command=lambda: load()).pack(side="left")
        ctk.CTkButton(btn_row, text="Close", width=90, height=32, fg_color="#21262d", hover_color="#30363d",
                      font=ctk.CTkFont(size=11), command=dialog.destroy).pack(side="right")

        def toggle_blocked(name, blocked):
            from tech_reg import _set_user_blocked
            status.configure(text=("\u23f3 Blocking %s\u2026" % name) if blocked
                             else ("\u23f3 Unblocking %s\u2026" % name), text_color="#8b949e")
            for w in list_frame.winfo_children():
                w.destroy()

            def worker():
                err = _set_user_blocked(name, blocked)
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

        def render(users):
            for w in list_frame.winfo_children():
                w.destroy()
            if not users:
                ctk.CTkLabel(list_frame, text="No accounts yet.",
                             font=ctk.CTkFont(size=11), text_color="#8b949e").pack(pady=20)
                return
            for name in sorted(users):
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
                    continue
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
                action_text = "Unblock" if blocked else "Block"
                action_color = "#2ea043" if blocked else "#da3633"
                action_hover = "#238636" if blocked else "#b62324"
                ctk.CTkButton(controls, text=action_text, width=90, height=26,
                              fg_color=action_color, hover_color=action_hover,
                              font=ctk.CTkFont(size=10, weight="bold"),
                              command=lambda n=name, b=not blocked: toggle_blocked(n, b)).pack(side="right")

        def load():
            status.configure(text="Loading accounts from the auth server\u2026")
            for w in list_frame.winfo_children():
                w.destroy()
            threading.Thread(target=lambda: finish(_fetch_verified_users()), daemon=True).start()

        def finish(users):
            if users is None:
                status.configure(text="\u26a0 Could not reach the auth server.\n"
                                      "Check your connection and press Refresh.",
                                 text_color="#ff6b6b")
                return
            status.configure(text="\u2713 Accounts loaded from the auth server.",
                             text_color="#2ecc71")
            render(users)

        load()
