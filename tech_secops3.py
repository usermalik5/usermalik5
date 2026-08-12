# -*- coding: utf-8 -*-
import customtkinter as ctk
from tkinter import messagebox, ttk
import tkinter as tk
import threading
import os
import json
import time
import re
import tempfile
import hashlib
import sys
import requests
import datetime
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageTk
from tech_common import get_bundle_dir, get_app_dir, get_cache_dir, get_settings_dir, load_banking_apps, Tooltip, subprocess


class SecOps3Mixin:
    def _sec_build_row_menu(self, entry):
        pkg = entry["id"]
        label = entry.get("label", pkg)
        checked_count = len(self._sec_checked_packages())
        menu = tk.Menu(self, tearoff=0, bg="#161b22", fg="#e6edf3",
                       activebackground="#1f6feb", activeforeground="#ffffff",
                       selectcolor="#1f6feb", font=ctk.CTkFont(size=12))
        menu.add_command(label=f"\u2b07 Disable {label}", command=lambda: self._sec_menu_disable(pkg))
        menu.add_command(label=f"\u274c Uninstall {label}", command=lambda: self._sec_menu_uninstall(pkg, label))
        menu.add_command(label=f"\U0001f9f9 Clean data {label}", command=lambda: self._sec_menu_clean(pkg))
        menu.add_separator()
        menu.add_command(label=f"\U0001f4be Backup {label}", command=lambda: self._sec_menu_backup(pkg))
        menu.add_separator()
        menu.add_command(label="Exclude from Clean", command=lambda: self._sec_menu_exclude(pkg, "clean"))
        menu.add_command(label="Exclude from Uninstall", command=lambda: self._sec_menu_exclude(pkg, "uninstall"))
        menu.add_separator()
        menu.add_command(label="APK Info", command=lambda: self._sec_show_apk_info(pkg))
        if checked_count:
            menu.add_separator()
            menu.add_command(label=f"\u2b07 Disable ALL {checked_count} checked",
                             command=lambda: self._sec_menu_disable_checked())
            menu.add_command(label=f"\u274c Uninstall ALL {checked_count} checked",
                             command=lambda: self._sec_menu_uninstall_checked())
            menu.add_command(label=f"\U0001f4be Backup ALL {checked_count} checked",
                             command=lambda: self._sec_menu_backup_checked())
        return menu

    def _sec_row_menu(self, event, entry):
        menu = self._sec_build_row_menu(entry)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _sec_menu_disable(self, pkg):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return
        if not messagebox.askyesno("Disable App", f"Disable {pkg} for the current user?\n\nIt can be re-enabled later from the Disabled list."):
            return
        self._sec_log(f"[GeloTech] Disabling: {pkg}", "#58a6ff")
        self._sec_run_disable([pkg])

    def _sec_menu_uninstall(self, pkg, label):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return
        if not messagebox.askyesno("Uninstall App", f"Uninstall {label} ({pkg})?\n\n3rd-party apps only. Excluded apps are skipped."):
            return
        self._sec_log(f"[GeloTech] Uninstalling: {pkg}", "#58a6ff")
        self._sec_run_uninstall([pkg])

    def _sec_menu_clean(self, pkg):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return
        if not messagebox.askyesno("Clean Data", f"Clear storage/data of {pkg}?\n\nThe app itself stays installed."):
            return
        self._sec_log(f"[GeloTech] Cleaning: {pkg}", "#58a6ff")
        self._sec_run_clean([pkg])

    def _sec_menu_backup(self, pkg):
        if not self._can("restore"):
            self._sec_status("Permission denied: Backup / Restore is disabled for this account.", "#e74c3c")
            return
        self._sec_log(f"[GeloTech] Backing up: {pkg}", "#58a6ff")
        self._sec_run_backup([pkg])

    def _sec_menu_disable_checked(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to disable. Check apps you want to disable.", "#f39c12")
            return
        if not self._sec_typed_confirm("Disable (Checked)",
                f"Disable {len(pkgs)} checked app(s) for the current user?\n\n"
                "Apps can be re-enabled later, but disabling critical system apps can make the phone unstable."):
            return
        self._sec_log(f"[GeloTech] Disabling {len(pkgs)} checked app(s)...", "#58a6ff")
        self._sec_run_disable(pkgs)

    def _sec_menu_uninstall_checked(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to uninstall. Check apps you want to remove.", "#f39c12")
            return
        if not self._sec_typed_confirm("Uninstall (Checked)",
                f"Uninstall {len(pkgs)} checked 3rd-party app(s)?\n\nUsed to remove APK Pop-up Virus. "
                "Apps in your exclusion lists are safe.\n\nThis CANNOT be undone easily — a backup is recommended."):
            return
        self._sec_log(f"[GeloTech] Uninstalling {len(pkgs)} checked app(s)...", "#58a6ff")
        self._sec_run_uninstall(pkgs)

    def _sec_menu_backup_checked(self):
        if not self._can("restore"):
            self._sec_status("Permission denied: Backup / Restore is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to backup. Check apps you want to backup.", "#f39c12")
            return
        if not messagebox.askyesno("Backup (Checked)", f"Backup APK(s) of {len(pkgs)} checked app(s) to your computer?\n\nSaves the original .apk file(s) so you can restore later if needed."):
            return
        self._sec_log(f"[GeloTech] Backing up {len(pkgs)} checked app(s)...", "#58a6ff")
        self._sec_run_backup(pkgs)

    def _sec_run_backup(self, packages):
        if not packages:
            return
        def worker():
            backup_dir = os.path.join(get_settings_dir(), "apk_backups")
            os.makedirs(backup_dir, exist_ok=True)
            ok, fail = 0, 0
            for pkg in packages:
                try:
                    path_res = subprocess.run([self.scrcpy_adb, "shell", "pm", "path", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
                    apk_paths = [l[len("package:"):].strip() for l in path_res.stdout.splitlines() if l.startswith("package:")]
                    if not apk_paths:
                        fail += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Backup failed (APK not found): {p}", "#e74c3c"))
                        continue
                    dest = os.path.join(backup_dir, f"{pkg}.apk")
                    r = subprocess.run([self.scrcpy_adb, "pull", apk_paths[0], dest], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                    if r.returncode == 0 and os.path.isfile(dest):
                        ok += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Backed up: {p} \u2014 {self._sec_description(p)}", "#2ecc71"))
                    else:
                        fail += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Backup failed: {p}", "#e74c3c"))
                except Exception as e:
                    fail += 1
                    self.after(0, lambda p=pkg, e=e: self._sec_log(f"[GeloTech] Backup error {p}: {e}", "#e74c3c"))
            self.after(0, lambda: self._sec_log(f"[GeloTech] Backup finished: {ok} saved, {fail} failed.", "#58a6ff"))
            self.after(0, lambda: self._sec_status(f"Backup finished: {ok} saved, {fail} failed.", "#58a6ff" if not fail else "#e74c3c"))
        threading.Thread(target=worker, daemon=True).start()

    def _sec_menu_exclude(self, pkg, mode):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return
        if mode == "clean":
            excl = self._load_excluded_clean()
            excl.add(pkg)
            self._save_excluded_clean(excl)
            self._sec_log(f"[GeloTech] Excluded from Clean: {pkg}", "#58a6ff")
        else:
            excl = self._load_excluded_uninstall()
            excl.add(pkg)
            self._save_excluded_uninstall(excl)
            self._sec_log(f"[GeloTech] Excluded from Uninstall: {pkg}", "#58a6ff")
        self._sec_render_rows()

    def _sec_get_icon(self, pkg, label):
        cached = getattr(self, "_sec_icon_cache", {})
        if pkg in cached:
            return cached[pkg]
        img = self._sec_make_letter_tile(pkg, label)
        try:
            cache_dir = get_cache_dir()
            icon_path = os.path.join(cache_dir, f"{pkg}.png")
            if os.path.isfile(icon_path):
                pil = Image.open(icon_path).convert("RGBA")
                pil = pil.resize((32, 32), Image.LANCZOS)
                img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(32, 32))
        except Exception:
            pass
        if not hasattr(self, "_sec_icon_cache"):
            self._sec_icon_cache = {}
        self._sec_icon_cache[pkg] = img
        return img

    def _sec_letter_pil(self, pkg, label, size, radius, font_size):
        letter = label[0].upper() if label else pkg[0].upper() if pkg else "?"
        if not letter.isalnum():
            letter = "?"
        h = hashlib.md5(pkg.encode("utf-8")).hexdigest()
        palette = ["#1f6feb", "#2ea043", "#bf8700", "#bc4c00", "#8957e5", "#d1242f", "#0f7489", "#d03592"]
        color = palette[int(h[:2], 16) % len(palette)]
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=color)
        try:
            font = ImageFont.truetype("segoeui.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        bbox = d.textbbox((0, 0), letter, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), letter, font=font, fill="white")
        return img

    def _sec_make_letter_tile(self, pkg, label):
        pil = self._sec_letter_pil(pkg, label, 64, 14, 34)
        return ctk.CTkImage(light_image=pil, dark_image=pil, size=(32, 32))

    def _sec_make_letter_photo(self, pkg, label):
        return ImageTk.PhotoImage(self._sec_letter_pil(pkg, label, 56, 12, 30))

    def _sec_tree_icon(self, pkg, label):
        cached = getattr(self, "_sec_tree_icon_cache", None)
        if cached and pkg in cached:
            return cached[pkg]
        img = None
        try:
            cache_dir = get_cache_dir()
            icon_path = os.path.join(cache_dir, f"{pkg}.png")
            if os.path.isfile(icon_path):
                pil = Image.open(icon_path).convert("RGBA").resize((28, 28), Image.LANCZOS)
                img = ImageTk.PhotoImage(pil)
        except Exception:
            img = None
        if img is None:
            img = self._sec_make_letter_photo(pkg, label)
        if not hasattr(self, "_sec_tree_icon_cache"):
            self._sec_tree_icon_cache = {}
        self._sec_tree_icon_cache[pkg] = img
        return img

    def action_sec_toggle_all(self):
        if not hasattr(self, "sec_check_vars") or not self.sec_check_vars:
            return
        btn = self.__dict__.get("sec_select_all_btn")
        if btn is not None and btn.cget("text").startswith("\u2611"):
            state, glyph = False, "\u2610"
            btn.configure(text="\u2610 Select All")
        else:
            state, glyph = True, "\u2611"
            if btn is not None:
                btn.configure(text="\u2611 Unselect All")
        for var in self.sec_check_vars.values():
            var.set(state)
        for iid in self.sec_tree.get_children():
            values = list(self.sec_tree.item(iid, "values"))
            if values:
                values[0] = glyph
                self.sec_tree.item(iid, values=values)

    def _sec_open_load_menu(self, button):
        """'Load Apps' button: popup menu to pick which package list to load."""
        menu = tk.Menu(self, tearoff=0)
        menu.configure(bg="#161b22", fg="#e6edf3", activebackground="#1f6feb",
                       activeforeground="#ffffff", borderwidth=1, relief="solid",
                       font=("Segoe UI", 10))
        menu.add_command(label="\U0001f4e6 Load All Apps", command=self.action_list_all_packages)
        menu.add_command(label="\U0001f4f1 User Apps (3rd-party)", command=self.action_list_user_packages)
        menu.add_command(label="\U0001f5a5 System Apps", command=self.action_list_system_packages)
        menu.add_command(label="\U0001f4e5 Disabled Apps", command=self.action_list_disabled_packages)
        self._sec_load_menu = menu
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            if x == 0 and y == 0:
                x = self.winfo_pointerx()
                y = self.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _sec_open_action_menu(self, button):
        """'Scan Bloatware' button: popup menu of UAD recommendation levels."""
        self._sec_bloat_button = button
        menu = tk.Menu(self, tearoff=0)
        menu.configure(bg="#161b22", fg="#e6edf3", activebackground="#1f6feb",
                       activeforeground="#ffffff", borderwidth=1, relief="solid",
                       font=("Segoe UI", 10))
        for label, level in (("\U0001f7e2 Recommended", "Recommended"),
                             ("\U0001f535 Advanced", "Advanced"),
                             ("\U0001f7e0 Expert", "Expert"),
                             ("\U0001f534 Unsafe", "Unsafe")):
            menu.add_command(label=label, command=lambda l=level: self._sec_action_recommendation(l))
        self._sec_bloat_menu = menu
        self._sec_bloat_menu_sub = None
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            if x == 0 and y == 0:
                x = self.winfo_pointerx()
                y = self.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()


    def _sec_show_level_actions(self, level, count):
        """Popup after a Scan Bloatware level pick: bulk actions for the checked apps."""
        menu = tk.Menu(self, tearoff=0, bg="#161b22", fg="#e6edf3",
                       activebackground="#1f6feb", activeforeground="#ffffff",
                       selectcolor="#1f6feb", font=ctk.CTkFont(size=12))
        menu.add_command(label=f"\U0001f50e {count} '{level}' app(s) checked \u2014 what next?",
                         state="disabled")
        menu.add_separator()
        menu.add_command(label=f"\u2b07 Disable ALL checked ({count})",
                         command=lambda: self._sec_menu_disable_checked())
        menu.add_command(label=f"\u274c Uninstall ALL checked ({count})",
                         command=lambda: self._sec_menu_uninstall_checked())
        menu.add_command(label=f"\U0001f4be Backup ALL checked ({count})",
                         command=lambda: self._sec_menu_backup_checked())
        menu.add_separator()
        menu.add_command(label="\U0001f441 Show all apps again (clear filter)",
                         command=lambda: self._sec_clear_removal_filter(level))
        try:
            btn = getattr(self, "_sec_bloat_button", None)
            if btn is not None:
                x = btn.winfo_rootx()
                y = btn.winfo_rooty() + btn.winfo_height()
            else:
                x = self.winfo_pointerx()
                y = self.winfo_pointery()
            if x == 0 and y == 0:
                x = self.winfo_pointerx()
                y = self.winfo_pointery()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def _sec_clear_removal_filter(self, level=None):
        if getattr(self, "sec_removal_filter", None) is None and level is None:
            return
        self.sec_removal_filter = None
        self.after(0, self._sec_render_rows)
        self._sec_status("\U0001f441 Filter cleared \u2014 showing all loaded apps.", "#58a6ff")
        self._sec_log(f"[GeloTech] Scan Bloatware filter removed ({level or 'manual'}).", "#8b949e")

    def _sec_check_level(self, level):
        """Auto-check every loaded app whose UAD removal level matches, and sync the row glyphs."""
        vars_map = getattr(self, "sec_check_vars", {}) or {}
        matched = set()
        for entry in getattr(self, "sec_packages", []) or []:
            if entry.get("removal") == level:
                matched.add(entry["id"])
                if entry["id"] in vars_map:
                    vars_map[entry["id"]].set(True)
        for iid in self.sec_tree.get_children():
            pkg = self._sec_tree_pkg(iid)
            if pkg and pkg in matched:
                values = list(self.sec_tree.item(iid, "values"))
                if values:
                    values[0] = "\u2611"
                    self.sec_tree.item(iid, values=values)
        return matched

    def _sec_level_hint(self, level):
        return {
            "Recommended": "safe to remove \u2014 pure bloatware",
            "Advanced": "mostly safe \u2014 may remove things you occasionally use",
            "Expert": "may break specific features",
            "Unsafe": "dangerous \u2014 can break core Android features",
        }.get(level, "")

    def _sec_checked_packages(self):
        if not hasattr(self, "sec_check_vars"):
            return []
        return [pkg for pkg, var in self.sec_check_vars.items() if var.get()]

    def _sec_run_clean(self, packages, auto_refresh=True):
        if not packages:
            self._sec_status("Nothing to clean. Check apps you want to clean.", "#f39c12")
            self._sec_log("[GeloTech] No apps to clean.", "#f39c12")
            return
        excluded = self._load_excluded_clean()
        banking = load_banking_apps()
        def worker():
            ok, fail = 0, 0
            for pkg in packages:
                if pkg in banking:
                    self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Skipped (banking app): {p}", "#2ecc71"))
                    continue
                if pkg in excluded:
                    self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Skipped (clean excluded): {p}", "#f39c12"))
                    continue
                try:
                    r = subprocess.run([self.scrcpy_adb, "shell", "pm", "clear", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
                    if r.returncode == 0 and "Success" in (r.stdout + r.stderr):
                        ok += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Cleaned: {p} \u2014 {self._sec_description(p)}", "#2ecc71"))
                    else:
                        fail += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Clean failed: {p}", "#e74c3c"))
                except Exception as e:
                    fail += 1
                    self.after(0, lambda p=pkg, e=e: self._sec_log(f"[GeloTech] Clean error {p}: {e}", "#e74c3c"))
            self.after(0, lambda: self._sec_log(f"[GeloTech] Clean finished: {ok} cleaned, {fail} failed.", "#58a6ff"))
            if auto_refresh:
                self.after(0, self._sec_refresh_current_list)
        threading.Thread(target=worker, daemon=True).start()

    def _sec_run_uninstall(self, packages):
        if not packages:
            self._sec_status("Nothing to uninstall. Check apps you want to remove.", "#f39c12")
            self._sec_log("[GeloTech] No apps to uninstall.", "#f39c12")
            return
        excluded = self._load_excluded_uninstall()
        banking = load_banking_apps()
        def worker():
            ok, fail = 0, 0
            removed = []
            for pkg in packages:
                if pkg in banking:
                    self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Skipped (banking app): {p}", "#2ecc71"))
                    continue
                if pkg in excluded:
                    self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Skipped (uninstall excluded): {p}", "#f39c12"))
                    continue
                try:
                    r = subprocess.run([self.scrcpy_adb, "shell", "pm", "uninstall", "--user", "0", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                    if r.returncode == 0 and "Success" in (r.stdout + r.stderr):
                        ok += 1
                        removed.append(pkg)
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Uninstalled: {p} \u2014 {self._sec_description(p)}", "#2ecc71"))
                    else:
                        fail += 1
                        self.after(0, lambda p=pkg: self._sec_log(f"[GeloTech] Uninstall failed: {p}", "#e74c3c"))
                except Exception as e:
                    fail += 1
                    self.after(0, lambda p=pkg, e=e: self._sec_log(f"[GeloTech] Uninstall error {p}: {e}", "#e74c3c"))
            if removed:
                self._record_debloated(removed)
            self.after(0, lambda: self._sec_log(f"[GeloTech] Uninstall finished: {ok} removed, {fail} failed.", "#58a6ff"))
            self.after(0, self._sec_refresh_current_list)
        threading.Thread(target=worker, daemon=True).start()

    def action_sec_clean_checked(self):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return
        pkgs = self._sec_checked_packages()
        if not pkgs:
            self._sec_status("Nothing to clean. Check apps you want to clean.", "#f39c12")
            return
        if not messagebox.askyesno("Clean (Checked)", f"Clear data for {len(pkgs)} checked app(s)?\n\nFixes full storage problems. Apps themselves are NOT removed."):
            return
        self._sec_log(f"[GeloTech] Cleaning {len(pkgs)} checked app(s)...", "#58a6ff")
        self._sec_run_clean(pkgs)

    def action_sec_db_filter(self):
        if not self._can("device_info"):
            self._sec_status("Permission denied: package lists disabled for this account.", "#e74c3c")
            return
        uad = self._build_uad_lookup()
        if not uad:
            self._sec_status("Database not available.", "#e74c3c")
            return

        def distinct(field, exclude_values):
            values = {str(entry.get(field) or "").strip() for entry in uad.values()}
            values.discard("")
            for v in exclude_values:
                values.discard(v)
            return ["Any"] + sorted(values)

        dialog = ctk.CTkToplevel(self)
        dialog.title("DB Filter")
        dialog.geometry("+%d+%d" % (self.winfo_rootx() + 130, self.winfo_rooty() + 130))
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        body = ctk.CTkFrame(dialog, fg_color="#161b22", corner_radius=8)
        body.pack(padx=14, pady=14, fill="both", expand=True)
        ctk.CTkLabel(body, text="Load apps from the database by criteria", font=ctk.CTkFont(size=13, weight="bold"), text_color="#e6edf3").grid(row=0, column=0, columnspan=2, pady=(0, 10))

        rows = [
            ("Removal level", "removal", ["Any", "Recommended", "Advanced", "Expert", "Unsafe"]),
            ("Risk", "risk", ["Any", "low", "medium", "high", "critical", "unknown"]),
            ("Category", "category", distinct("category", ["Other"])),
            ("Manufacturer", "manufacturer", distinct("manufacturer", ["Unknown"])),
            ("Source", "source", distinct("source", ["Unknown"])),
        ]
        menus = {}
        for i, (label, key, values) in enumerate(rows):
            ctk.CTkLabel(body, text=label, font=ctk.CTkFont(size=11), text_color="#8b949e").grid(row=1 + i, column=0, padx=(10, 10), pady=6, sticky="w")
            menus[key] = ctk.CTkOptionMenu(body, values=values, width=220, height=28, font=ctk.CTkFont(size=11), fg_color="#21262d", button_color="#30363d", button_hover_color="#3d444d")
            menus[key].grid(row=1 + i, column=1, padx=(0, 10), pady=6, sticky="ew")
        respect_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(body, text="Respect database uninstall-exclusion flags + banking apps list", variable=respect_var, font=ctk.CTkFont(size=11), text_color="#c9d1d9").grid(row=1 + len(rows), column=0, columnspan=2, padx=10, pady=(10, 4), sticky="w")
        ctk.CTkLabel(body, text="Matching apps load into the list (unchecked). Review, then use Check All / Uninstall.", font=ctk.CTkFont(size=9), text_color="#8b949e").grid(row=2 + len(rows), column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w")

        def apply():
            criteria = {
                "removal": menus["removal"].get(),
                "risk": menus["risk"].get(),
                "category": menus["category"].get(),
                "manufacturer": menus["manufacturer"].get(),
                "source": menus["source"].get(),
                "respect_exclude": respect_var.get(),
            }
            dialog.destroy()
            self._sec_load_db_filter(criteria)

        footer = ctk.CTkFrame(dialog, fg_color="#0d1117", corner_radius=0)
        footer.pack(fill="x")
        ctk.CTkButton(footer, text="Apply", fg_color="#1f6feb", hover_color="#1a5fd0", width=110, height=32, command=apply).pack(side="right", padx=(6, 12), pady=10)
        ctk.CTkButton(footer, text="Cancel", fg_color="#21262d", hover_color="#30363d", width=110, height=32, command=dialog.destroy).pack(side="right", pady=10)
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.transient(self)
        dialog.grab_set()


