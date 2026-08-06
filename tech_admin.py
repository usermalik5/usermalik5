# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox


class AdminPanelMixin:

    # ----------------------------------------------------
    # ADMIN PANEL (user management)
    # ----------------------------------------------------
    def _open_admin_panel(self):
        if not getattr(self, "is_admin", False):
            return
        users = dict((self._load_settings().get("users") or {}))
        dialog = ctk.CTkToplevel(self)
        dialog.title("Admin Panel - User Management")
        dialog.configure(fg_color="#0d1117")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        dialog.geometry(f"{int(sw * 0.8)}x{int(sh * 0.85)}+{int(sw * 0.1)}+{int(sh * 0.07)}")
        dialog.minsize(560, 480)

        outer = ctk.CTkScrollableFrame(dialog, fg_color="#0d1117")
        outer.pack(fill="both", expand=True, padx=14, pady=12)

        ctk.CTkLabel(outer, text="\U0001f511 ADMIN PANEL", font=ctk.CTkFont(size=15, weight="bold"), text_color="#d4af37").pack(anchor="w")
        ctk.CTkLabel(outer, text="Manage user accounts and their enabled functions. Admin always has everything.",
                     font=ctk.CTkFont(size=10), text_color="#8b949e").pack(anchor="w", pady=(0, 10))

        admin_pw_frame = None  # consolidated into the Edit User section below

        users_frame = ctk.CTkFrame(outer, fg_color="#16191e", corner_radius=8)
        users_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(users_frame, text="User Accounts", font=ctk.CTkFont(size=11, weight="bold"), text_color="#58a6ff").pack(anchor="w", padx=12, pady=(10, 2))

        add_row = ctk.CTkFrame(users_frame, fg_color="transparent")
        add_row.pack(fill="x", padx=12, pady=(0, 4))
        new_name_entry = ctk.CTkEntry(add_row, placeholder_text="New username", fg_color="#0d1117", border_color="#30363d", height=30, width=150)
        new_name_entry.pack(side="left", padx=(0, 6))
        new_pw_entry = ctk.CTkEntry(add_row, placeholder_text="Password", fg_color="#0d1117", border_color="#30363d", height=30, width=130, show="\u2022")
        new_pw_entry.pack(side="left", padx=(0, 6))
        add_msg = ctk.CTkLabel(users_frame, text="", font=ctk.CTkFont(size=9), text_color="#ff6b6b")

        def add_user():
            name = new_name_entry.get().strip().lower()
            pw = new_pw_entry.get()
            if not name or name == "admin":
                add_msg.configure(text="\u26a0 Username is invalid.")
                return
            if name in users:
                add_msg.configure(text="\u26a0 User already exists.")
                return
            if len(pw) < 4:
                add_msg.configure(text="\u26a0 Password must be at least 4 characters.")
                return
            if not messagebox.askyesno("Confirm Add User", f"Create user '{name}' with the entered password?"):
                return
            users[name] = {"hash": self._hash_pw(pw), "permissions": {}, "tabs": []}
            self._save_users(users)
            add_msg.configure(text=f"\u2713 User '{name}' added. Select it to edit.", text_color="#2ecc71")
            self._admin_refresh_user_list(dialog, users, selected=name)

        ctk.CTkButton(add_row, text="+ Add User", width=90, height=30, fg_color="#238636", hover_color="#1f7a30",
                      font=ctk.CTkFont(size=10, weight="bold"), command=add_user).pack(side="left")
        add_msg.pack(anchor="w", padx=12, pady=(0, 4))

        list_frame = ctk.CTkScrollableFrame(users_frame, fg_color="#0d1117", corner_radius=6, height=140)
        list_frame.pack(fill="x", padx=12, pady=(0, 10))

        selected_user = ctk.StringVar(value="")

        edit_frame = ctk.CTkFrame(outer, fg_color="#16191e", corner_radius=8)
        edit_frame.pack(fill="x", pady=(0, 12))
        edit_title = ctk.CTkLabel(edit_frame, text="Edit User \u2014 select a user above", font=ctk.CTkFont(size=11, weight="bold"), text_color="#58a6ff")
        edit_title.pack(anchor="w", padx=12, pady=(10, 2))

        perm_vars = {}
        perm_grid = ctk.CTkFrame(edit_frame, fg_color="transparent")
        perm_grid.pack(fill="x", padx=12, pady=(0, 4))
        for i, (key, label) in enumerate(self.PERMISSIONS.items()):
            perm_vars[key] = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(perm_grid, text=label, variable=perm_vars[key], font=ctk.CTkFont(size=10),
                            text_color="#c9d1d9", fg_color="#1f6feb", hover_color="#1a5fd0"
                            ).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 12), pady=3)

        tab_vars = {}
        tab_grid = ctk.CTkFrame(edit_frame, fg_color="transparent")
        tab_grid.pack(fill="x", padx=12, pady=(4, 4))
        for i, (tab_name, _perm) in enumerate(self.TAB_PERMS.items()):
            tab_vars[tab_name] = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(tab_grid, text=tab_name, variable=tab_vars[tab_name], font=ctk.CTkFont(size=10),
                            text_color="#c9d1d9", fg_color="#1f6feb", hover_color="#1a5fd0"
                            ).grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 12), pady=3)

        edit_pw_row = ctk.CTkFrame(edit_frame, fg_color="transparent")
        edit_pw_row.pack(fill="x", padx=12, pady=(4, 4))
        reset_pw_entry = ctk.CTkEntry(edit_pw_row, placeholder_text="New password (leave blank to keep current)", fg_color="#0d1117", border_color="#30363d", height=30, show="\u2022")
        reset_pw_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def save_user():
            name = selected_user.get()
            if not name or name not in users:
                return
            is_admin_user = (name == "admin")
            if not is_admin_user:
                users[name]["permissions"] = {k: True for k, v in perm_vars.items() if v.get()}
                users[name]["tabs"] = [t for t, v in tab_vars.items() if v.get()]
            pw = reset_pw_entry.get()
            if pw:
                if len(pw) < 4:
                    save_msg.configure(text="\u26a0 Password must be at least 4 characters.", text_color="#ff6b6b")
                    return
                users[name]["hash"] = self._hash_pw(pw)
            self._save_users(users)
            save_msg.configure(text=f"\u2713 Changes saved for {name}.", text_color="#2ecc71")
            reset_pw_entry.delete(0, "end")
            messagebox.showinfo("User Saved", f"Changes saved for user:\n\n{name}")

        ctk.CTkButton(edit_pw_row, text="Save", width=90, height=30, fg_color="#1f6feb", hover_color="#1a5fd0",
                      font=ctk.CTkFont(size=10, weight="bold"), command=save_user).pack(side="left", padx=(8, 0))
        save_msg = ctk.CTkLabel(edit_frame, text="", font=ctk.CTkFont(size=9))
        save_msg.pack(anchor="w", padx=12, pady=(0, 4))

        def delete_user():
            name = selected_user.get()
            if not name or name == "admin" or name not in users:
                return
            if not messagebox.askyesno("Delete User", f"Delete user '{name}'?"):
                return
            users.pop(name)
            self._save_users(users)
            save_msg.configure(text=f"\u2713 User '{name}' deleted.", text_color="#2ecc71")
            self._admin_refresh_user_list(dialog, users, selected="")

        ctk.CTkButton(edit_frame, text="\U0001f5d1 Delete Selected User", width=200, height=30, fg_color="#c0392b", hover_color="#a82521",
                      font=ctk.CTkFont(size=10, weight="bold"), command=delete_user).pack(anchor="w", padx=12, pady=(0, 10))

        def on_select(name):
            selected_user.set(name)
            if not name or name not in users:
                edit_title.configure(text="Edit User \u2014 select a user above", text_color="#58a6ff")
                return
            rec = users[name]
            for key, var in perm_vars.items():
                var.set(bool((rec.get("permissions") or {}).get(key)))
            allowed_tabs = set(rec.get("tabs") or [])
            for tab, var in tab_vars.items():
                var.set(tab in allowed_tabs)
            edit_title.configure(text=f"Edit User \u2014 {name} {'(ADMIN \u2014 always has everything)' if name == 'admin' else ''}",
                                 text_color="#d4af37" if name == "admin" else "#58a6ff")
            save_msg.configure(text="")
            reset_pw_entry.delete(0, "end")
            render()

        def render():
            sel = selected_user.get()
            for w in list_frame.winfo_children():
                w.destroy()
            for name in users:
                tag = "ADMIN" if name == "admin" else "USER"
                mark = "\u2611" if name == sel else "\u2610"
                ctk.CTkButton(list_frame, text=f"{mark} {name}   [{tag}]", anchor="w", height=26,
                              fg_color="#1f6feb" if name == sel else "#1c2026",
                              hover_color="#2a3038",
                              font=ctk.CTkFont(size=10, weight="bold"),
                              command=lambda n=name: on_select(n)).pack(fill="x", padx=2, pady=2)

        upd_frame = ctk.CTkFrame(outer, fg_color="#16191e", corner_radius=8)
        upd_frame.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(upd_frame, text="\U0001f504 Updates (pull from your GitHub repo)", font=ctk.CTkFont(size=11, weight="bold"), text_color="#58a6ff").pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(upd_frame, text="Host gelotech_settings.json, gelotech_database_v3.json and version.json in a repo, then paste the raw base URL below.",
                     font=ctk.CTkFont(size=9), text_color="#8b949e").pack(anchor="w", padx=12, pady=(0, 6))
        upd_row = ctk.CTkFrame(upd_frame, fg_color="transparent")
        upd_row.pack(fill="x", padx=12, pady=(0, 6))
        upd_url_entry = ctk.CTkEntry(upd_row, fg_color="#0d1117", border_color="#30363d", height=30)
        upd_url_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        upd_url_entry.insert(0, (self._load_settings().get("update_url") or ""))
        upd_msg = ctk.CTkLabel(upd_frame, text="", font=ctk.CTkFont(size=9))

        def save_update_url():
            val = upd_url_entry.get().strip().rstrip("/")
            if val and not val.startswith(("http://", "https://")):
                upd_msg.configure(text="\u26a0 URL must start with http:// or https://", text_color="#ff6b6b")
                return
            data = self._load_settings()
            data["update_url"] = val
            self._save_settings(data)
            upd_msg.configure(text="\u2713 Update URL saved. The app checks it on every login.", text_color="#2ecc71")

        def check_now():
            upd_msg.configure(text="\u23f3 Checking...", text_color="#58a6ff")
            self._check_updates(manual=True, status_cb=lambda m: upd_msg.configure(
                text=m, text_color="#2ecc71" if "\u2713" in m else "#ff6b6b"))

        ctk.CTkButton(upd_row, text="Save URL", width=90, height=30, fg_color="#1f6feb", hover_color="#1a5fd0",
                      font=ctk.CTkFont(size=10, weight="bold"), command=save_update_url).pack(side="left", padx=(8, 6))
        ctk.CTkButton(upd_row, text="Check Now", width=90, height=30, fg_color="#238636", hover_color="#1f7a30",
                      font=ctk.CTkFont(size=10, weight="bold"), command=check_now).pack(side="left")
        upd_msg.pack(anchor="w", padx=12, pady=(0, 8))

        self._admin_refresh_user_list = lambda dlg, u, selected="": (users.clear(), users.update(u), render(),
                                                                    on_select(selected) if selected else None)
        render()
        on_select("")
