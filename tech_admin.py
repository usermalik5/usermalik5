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
        dialog.title("Admin Panel - Accounts")
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
        ctk.CTkLabel(header, text="\U0001f511 ADMIN PANEL - ACCOUNTS",
                     font=ctk.CTkFont(size=15, weight="bold"), text_color="#d4af37").pack(anchor="w")
        ctk.CTkLabel(header,
                     text="Accounts are managed on GitHub by the maintainer.\n"
                          "This view is read-only and signature-verified against the update server.",
                     font=ctk.CTkFont(size=10), text_color="#8b949e", justify="left").pack(anchor="w", pady=(2, 8))

        status = ctk.CTkLabel(dialog, text="Loading accounts...",
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

        def render(users):
            for w in list_frame.winfo_children():
                w.destroy()
            if not users:
                ctk.CTkLabel(list_frame, text="No accounts found on the server.",
                             font=ctk.CTkFont(size=11), text_color="#8b949e").pack(pady=20)
                return
            for name in sorted(users):
                rec = users[name] or {}
                is_admin = (name == "admin")
                card = ctk.CTkFrame(list_frame, fg_color="#0d1117", corner_radius=6)
                card.pack(fill="x", padx=2, pady=3)
                title = ctk.CTkLabel(card, text=f"{name}   [{('ADMIN' if is_admin else 'USER')}]",
                                     font=ctk.CTkFont(size=11, weight="bold"),
                                     text_color="#d4af37" if is_admin else "#58a6ff")
                title.pack(anchor="w", padx=10, pady=(6, 0))
                if is_admin:
                    ctk.CTkLabel(card, text="Full access to all functions.",
                                 font=ctk.CTkFont(size=9), text_color="#8b949e").pack(anchor="w", padx=10, pady=(0, 6))
                    continue
                perms = rec.get("permissions") or {}
                perm_labels = [self.PERMISSIONS[k] for k in self.PERMISSIONS if perms.get(k)]
                tabs = rec.get("tabs") or []
                info = ""
                if perm_labels:
                    info += "Functions: " + ", ".join(perm_labels)
                if tabs:
                    info += ("\n" if info else "") + "Tabs: " + ", ".join(tabs)
                if not info:
                    info = "No functions or tabs enabled."
                ctk.CTkLabel(card, text=info, font=ctk.CTkFont(size=9), text_color="#c9d1d9",
                             justify="left", wraplength=560).pack(anchor="w", padx=10, pady=(0, 6))

        def load():
            status.configure(text="Verifying accounts against the update server...")
            for w in list_frame.winfo_children():
                w.destroy()
            threading.Thread(target=lambda: finish(_fetch_verified_users()), daemon=True).start()

        def finish(users):
            if users is None:
                status.configure(text="\u26a0 Could not reach or verify the update server.\n"
                                      "Check your internet connection and press Refresh.",
                                 text_color="#ff6b6b")
                return
            status.configure(text="\u2713 Accounts verified against the signed server manifest.",
                             text_color="#2ecc71")
            render(users)

        load()
