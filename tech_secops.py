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


class SecOpsMixin:
    def _sec_on_search(self, event=None):
        self._sec_render_rows()

    REMOVAL_BADGE_COLORS = {
        "Recommended": "#2ea043",
        "Advanced": "#1f6feb",
        "Expert": "#bf8700",
        "Unsafe": "#e5534b",
    }

    def _sec_row_color(self, entry):
        if entry.get("threat_level", 0) >= 3:
            return "#2a1015", "red", "#3d1212"
        if entry.get("excluded_clean") and entry.get("excluded_uninstall"):
            return "#241a33", "#8957e5", "#2d1a4a"
        if entry.get("excluded_uninstall"):
            return "#2a1212", "red", "#3d1212"
        if entry.get("excluded_clean"):
            return "#2a2010", "orange", "#3d3210"
        return "#0f2017", "lightgreen", "#1f3d2a"

    def _sec_legend_category(self, entry):
        ex_c = entry.get("excluded_clean")
        ex_u = entry.get("excluded_uninstall")
        if ex_c and ex_u:
            return "both"
        if ex_u:
            return "uninstall"
        if ex_c:
            return "clean"
        return "removable"

    def _sec_toggle_legend_filter(self, mode):
        if getattr(self, "sec_legend_filter", None) == mode:
            self.sec_legend_filter = None
        else:
            self.sec_legend_filter = mode
        self.sec_removal_filter = None
        for m, (dot, lbl) in getattr(self, "sec_legend_widgets", {}).items():
            active = m == self.sec_legend_filter
            lbl.configure(text_color="#e6edf3" if active else "#8b949e",
                          font=ctk.CTkFont(size=9, weight="bold") if active else ctk.CTkFont(size=9))
            dot.configure(font=ctk.CTkFont(size=12 if active else 10))
        self._sec_render_rows()

    RENDER_CHUNK = 60

    def _sec_render_rows(self):
        """Render the app list into the virtualized ttk.Treeview. Only the
        visible rows exist at any time, so scrolling stays smooth with
        hundreds or thousands of apps. Rows are added in small batches so the
        UI stays responsive during the initial build."""
        if hasattr(self, "_sec_render_gen"):
            self._sec_render_gen += 1
        else:
            self._sec_render_gen = 0
        gen = self._sec_render_gen
        for item in self.sec_tree.get_children():
            self.sec_tree.delete(item)
        if not hasattr(self, "sec_packages") or not self.sec_packages:
            self._sec_show_empty("\U0001f4e6 Connect a device and press Refresh to load apps")
            return

        query = self.sec_search_entry.get().strip().lower()
        filtered = []
        removal_filter = getattr(self, "sec_removal_filter", None)
        for entry in self.sec_packages:
            label = entry.get("label", entry["id"])
            if query and query not in entry["id"].lower() and query not in label.lower():
                continue
            if removal_filter and entry.get("removal") != removal_filter:
                continue
            if getattr(self, "sec_legend_filter", None) and self._sec_legend_category(entry) != self.sec_legend_filter:
                continue
            filtered.append(entry)
        self._sec_display_list = filtered
        self._sec_tree_iids = [f"row{i}" for i in range(len(filtered))]
        old_vars = getattr(self, "sec_check_vars", {}) or {}
        self.sec_check_vars = {}
        for entry in filtered:
            var = old_vars.get(entry["id"])
            self.sec_check_vars[entry["id"]] = var if var is not None else ctk.BooleanVar(value=False)
        if not filtered:
            self._sec_show_empty("No apps match your search")
            return
        self._sec_show_tree()
        self._sec_render_chunk(0, gen)

    def _sec_show_tree(self):
        empty = self.__dict__.get("sec_list_empty")
        if empty is not None:
            empty.grid_remove()
        self.sec_tree.grid()
        if self.__dict__.get("sec_vsb") is not None:
            self.sec_vsb.grid()

    def _sec_show_empty(self, text):
        self.sec_tree.grid_remove()
        if self.__dict__.get("sec_vsb") is not None:
            self.sec_vsb.grid_remove()
        empty = self.__dict__.get("sec_list_empty")
        if empty is not None:
            empty.configure(text=text)
        else:
            self.sec_list_empty = ctk.CTkLabel(self.sec_list_frame, text=text, font=ctk.CTkFont(size=12), text_color="#484f58")
            self.sec_list_empty.grid(row=0, column=0, pady=30)

    def _sec_render_chunk(self, start, gen):
        if gen != getattr(self, "_sec_render_gen", None) or not hasattr(self, "_sec_display_list"):
            return
        lst = self._sec_display_list
        if start == 0:
            self._sec_status(f"Rendering {len(lst)} apps...", "#58a6ff")
        end = min(start + self.RENDER_CHUNK, len(lst))
        for i in range(start, end):
            self._sec_create_row(lst[i], i)
        if end < len(lst):
            self.after(1, lambda: self._sec_render_chunk(end, gen))
        else:
            mode = getattr(self, "sec_list_mode", "all")
            label = "ALL" if mode == "all" else "DISABLED" if mode == "disabled" else "FILTER"
            self._sec_status(f"{label} apps: {len(lst)} loaded. Use the action buttons below on the apps you check.", "#58a6ff")

    def _sec_tree_row_tag(self, entry, index):
        if entry.get("threat_level", 0) >= 3:
            return "threat"
        if entry.get("excluded_clean") and entry.get("excluded_uninstall"):
            return "both_excl"
        if entry.get("excluded_uninstall"):
            return "uninstall_excl"
        if entry.get("excluded_clean"):
            return "clean_excl"
        return "normal" if index % 2 == 0 else "normal_alt"

    def _sec_create_row(self, entry, index):
        label = entry.get("label", entry["id"])
        pkg = entry["id"]
        display = label
        desc = (entry.get("description") or "").strip().replace("\n", " ")
        if len(desc) > 110:
            desc = desc[:110].rsplit(" ", 1)[0] + "..."
        badges = []
        if entry.get("threat_level", 0) >= 3:
            badges.append("\U0001f6a8 High Risk")
        elif entry.get("threat_labels"):
            badges.append("\U0001f6a8")
        if entry.get("banking"):
            badges.append("\U0001f3e6 Banking")
        if entry.get("excluded_clean") and entry.get("excluded_uninstall"):
            badges.append("Both Excluded")
        elif entry.get("excluded_clean"):
            badges.append("Clean Excl")
        elif entry.get("excluded_uninstall"):
            badges.append("Uninstall Excl")
        elif entry.get("removal"):
            badges.append(entry["removal"])
        icon = self._sec_tree_icon(pkg, label)
        var = self.sec_check_vars.get(pkg)
        glyph = "\u2611" if (var is not None and var.get()) else "\u2610"
        self.sec_tree.insert("", "end", iid=f"row{index}", image=icon,
                             values=(glyph, display, pkg, "  ".join(badges), desc),
                             tags=(self._sec_tree_row_tag(entry, index),))

    def _sec_tree_pkg(self, row):
        try:
            return self._sec_display_list[int(row[3:])]["id"]
        except Exception:
            return None

    def _sec_tree_click(self, event):
        row = self.sec_tree.identify_row(event.y)
        if not row or self.sec_tree.identify_column(event.x) != "#1":
            return
        pkg = self._sec_tree_pkg(row)
        if not pkg or pkg not in self.sec_check_vars:
            return
        var = self.sec_check_vars[pkg]
        var.set(not var.get())
        values = list(self.sec_tree.item(row, "values"))
        values[0] = "\u2611" if var.get() else "\u2610"
        self.sec_tree.item(row, values=values)
        if var.get():
            entry = self._sec_display_list[int(row[3:])]
            self._sec_log(f"[GeloTech] {entry.get('label', pkg)}: {self._sec_description(pkg)}", "#8b949e")

    def _sec_tree_menu(self, event):
        row = self.sec_tree.identify_row(event.y)
        if not row:
            return
        try:
            entry = self._sec_display_list[int(row[3:])]
        except Exception:
            return
        self._sec_row_menu(event, entry)

    def _sec_tree_scroll_set(self, first, last):
        if self.__dict__.get("sec_vsb") is not None:
            self.sec_vsb.set(first, last)

