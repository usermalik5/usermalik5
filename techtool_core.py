# -*- coding: utf-8 -*-
"""Core GeloTechTool behavior split out of techtool.py so each source module
stays under the PyArmor per-file size limit used by the obfuscated build.
These remain mixin methods of GeloTechTool (resolved via the normal MRO).
"""
import customtkinter as ctk
import os
from tkinter import ttk
import tech_themes
from tech_themes import PALETTES
from tech_common import (THEME, THEMES, COLOR_SWAP, CANONICAL_DARK, get_bundle_dir)


class TechToolCore:
    def _build_log_panel(self, parent, fixed_height=None, place_rect=None,
                         log_font_size=10, minimal=False):
        # Live log console rendered INSIDE the Android phone screen on the
        # Dashboard, and (compacted) on top of the App Cleaner page.
        # place_rect=(x, y, w, h): instead of grid(), position the console
        # with place() at the given rect (used for the phone-image screen
        # cutout on the Dashboard). log_font_size scales the log text to
        # the console's on-screen width. minimal=True renders ONLY the log
        # stream (no header/chips/stats bar) to look like a phone UI.
        console = ctk.CTkFrame(parent, fg_color="#01030a", corner_radius=6,
                               border_width=0 if (place_rect or minimal) else 1, border_color="#131a22",
                               width=(place_rect[2] if place_rect else 0),
                               height=(place_rect[3] if place_rect else 0))
        if place_rect:
            console.place(x=place_rect[0], y=place_rect[1])
            console.grid_propagate(False)
        else:
            console.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

        TAG_COLORS = {
            "ADB": "#00ff41", "SECURITY": "#7cff00", "VT": "#29ffbf",
            "DNS": "#00d8ff", "EXEC": "#b8ff66", "SYSTEM": "#33ff99",
            "ERROR": "#ff3355", "INFO": "#00cc55", "HINT": "#338844",
            "DEFAULT": "#00ff41",
        }

        def _style_textbox(tb):
            for name, color in TAG_COLORS.items():
                tb.tag_config(name, foreground=color)

        if minimal:
            console.grid_columnconfigure(0, weight=1)
            console.grid_rowconfigure(0, weight=1)
            main_log = ctk.CTkTextbox(console, font=ctk.CTkFont(family="Consolas", size=log_font_size),
                                      fg_color="#000200", text_color="#00ff41",
                                      border_width=0, wrap="word", corner_radius=0)
            main_log.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
            _style_textbox(main_log)
            entry = {
                "frame": console, "text": main_log,
                "count_label": None, "filter_label": None,
                "filter": "ALL",
            }
            if not hasattr(self, "_log_consoles"):
                self._log_consoles = []
                self._log_console = console
                self.main_log = main_log
                self.log_line_count_label = None
                self.log_filter_label = None
                self._log_filter_active = "ALL"
                self._log_clear_btn = None
            self._log_consoles.append(entry)
            return

        console.grid_columnconfigure(0, weight=1)
        console.grid_rowconfigure(1, weight=1)
        if fixed_height:
            console.configure(height=fixed_height)
            console.grid_propagate(False)

        # Header bar: title + clear
        hdr = ctk.CTkFrame(console, fg_color="#03160d", corner_radius=6, height=24)
        hdr.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 2))
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="\u25a0 LIVE LOGS", font=ctk.CTkFont(size=9, weight="bold"),
                     text_color="#00ff66").grid(row=0, column=0, padx=(8, 4), pady=2, sticky="w")
        clear_btn = ctk.CTkButton(hdr, text="\u2715", width=22, height=20,
                      fg_color="#3a2a2a", hover_color="#5a3a3a",
                      font=ctk.CTkFont(size=9, weight="bold"),
                      command=self.clear_logs)
        clear_btn.grid(row=0, column=1, padx=(0, 4), pady=2)

        # Log display (color-coded by process)
        main_log = ctk.CTkTextbox(console, font=ctk.CTkFont(family="Consolas", size=log_font_size),
                                  fg_color="#000200", text_color="#00ff41",
                                  border_color="#0a5a24", border_width=1,
                                  wrap="word")
        main_log.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
        main_log.tag_config("ADB", foreground="#00ff41")       # adb / device commands
        main_log.tag_config("SECURITY", foreground="#7cff00")  # Adware Remover / cleaner
        main_log.tag_config("VT", foreground="#29ffbf")        # VirusTotal
        main_log.tag_config("DNS", foreground="#00d8ff")       # DNS / ad blocking
        main_log.tag_config("EXEC", foreground="#b8ff66")      # system command execution
        main_log.tag_config("SYSTEM", foreground="#33ff99")    # system / login events
        main_log.tag_config("ERROR", foreground="#ff3355")     # errors
        main_log.tag_config("INFO", foreground="#00cc55")
        main_log.tag_config("HINT", foreground="#338844")
        main_log.tag_config("DEFAULT", foreground="#00ff41")

        # Filter chips row
        # Stats bar at bottom (phone home indicator strip)
        entry = {
            "frame": console, "text": main_log,
            "count_label": None, "filter_label": None,
            "filter": "ALL",
        }
        if not hasattr(self, "_log_consoles"):
            self._log_consoles = []
            # Backward-compat: the first console (Dashboard phone) keeps the
            # original attribute names used by the rest of the app.
            self._log_console = console
            self.main_log = main_log
            self.log_line_count_label = None
            self.log_filter_label = None
            self._log_filter_active = "ALL"
            self._log_clear_btn = clear_btn
        self._log_consoles.append(entry)

    def _set_log_filter(self, f, entry=None):
        if entry is None:
            consoles = getattr(self, "_log_consoles", None)
            entry = consoles[0] if consoles else None
            if entry is None:
                return
        entry["filter"] = f
        if entry.get("filter_label") is not None:
            entry["filter_label"].configure(text=f"Filter: {f}")
        # Re-display all log entries with new filter
        if hasattr(self, '_log_history') and self._log_history:
            entry["text"].delete("1.0", "end")
            for tag, msg in self._log_history:
                if f == "ALL" or f == tag or (f == "ADB" and tag in ("ADB", "EXEC", "SYSTEM")):
                    entry["text"].insert("end", msg + "\n", tag)
            entry["text"].see("end")

    def _extract_scrcpy(self):
        """Extract scrcpy zip to a temp directory and set paths."""
        import zipfile
        import tempfile
        base_path = get_bundle_dir()
        zip_path = os.path.join(base_path, "scrcpy-win64-v3.3.4.zip")
        if not os.path.exists(zip_path):
            # NOTE: log_message() silently no-ops here since main_log hasn't been
            # created yet at this point in __init__, so print to console too.
            print(f"[ADB ERROR] scrcpy zip not found at {zip_path}")
            self.log_message(f"[ADB ERROR] scrcpy zip not found at {zip_path}")
            self.scrcpy_dir = os.path.join(base_path, "scrcpy-win64-v3.3.4")
            self.scrcpy_exe = os.path.join(self.scrcpy_dir, "scrcpy.exe")
            self.scrcpy_adb = os.path.join(self.scrcpy_dir, "adb.exe")
            if not os.path.exists(self.scrcpy_adb):
                print(f"[ADB ERROR] adb.exe also not found at {self.scrcpy_adb} -- all ADB features will fail until scrcpy-win64-v3.3.4.zip is placed next to techtool.py")
            return
        self.scrcpy_dir = tempfile.mkdtemp(prefix="gelotech_scrcpy_")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.scrcpy_dir)

        # The zip's internal layout may not be flat (e.g. everything nested inside
        # an extra subfolder), so search for the actual exe locations rather than
        # assuming they sit directly at the extraction root.
        found_adb, found_scrcpy = None, None
        for root, _dirs, files in os.walk(self.scrcpy_dir):
            if found_adb and found_scrcpy:
                break
            if not found_adb and "adb.exe" in files:
                found_adb = os.path.join(root, "adb.exe")
            if not found_scrcpy and "scrcpy.exe" in files:
                found_scrcpy = os.path.join(root, "scrcpy.exe")

        if found_adb:
            self.scrcpy_adb = found_adb
            self.scrcpy_dir = os.path.dirname(found_adb)  # so PATH env var / cwd point at the real bin folder
        else:
            self.scrcpy_adb = os.path.join(self.scrcpy_dir, "adb.exe")
            print(f"[ADB ERROR] adb.exe not found anywhere under extracted scrcpy folder: {self.scrcpy_dir}")

        self.scrcpy_exe = found_scrcpy or os.path.join(self.scrcpy_dir, "scrcpy.exe")
        self.log_message(f"[ADB] scrcpy extracted to {self.scrcpy_dir}")

    # ----------------------------------------------------
    # TAB INTERFACE CONFIGURATIONS
    # ----------------------------------------------------
    def _apply_theme(self, palette):
        """Recolor the whole widget tree for the chosen palette.

        ``palette`` is a CTkThemesPack palette name (e.g. ``"orange"``).
        Appearance stays dark (the app ships dark-mode surface palettes and
        light text on dark surfaces throughout). The palette's accent
        overrides the blue accent slots so buttons/accents use the pack
        colors, while every surface text color is forced contrast-readable
        via the luminance-aware ``_fix_button_text_colors`` pass (so text
        adapts to each palette/background automatically).
        Phone screen / log console colors are intentionally absent (a phone
        display stays dark)."""
        if palette not in PALETTES:
            palette = tech_themes.DEFAULT_THEME
        THEME.update(THEMES["light"])
        # Inject this palette's accent into the shared theme slots so the
        # custom widgets use the pack color instead of the default blue.
        accent = tech_themes.accent_for(palette)
        THEME["accent"] = accent
        THEME["accent_h"] = tech_themes.hover_for(palette)
        ctk.set_appearance_mode("Light")
        # CTk default widgets get the pack's JSON theme (buttons/entries/labels).
        try:
            tech_themes.apply_ctk_theme(palette)
        except Exception:
            pass
        # Swap any already-wired blue-accent hexes onto this palette's accent
        # so existing custom widgets repaint without hard-coding a new palette.
        palette_swap = dict(COLOR_SWAP)
        palette_swap["#3b82f6"] = accent          # default dark accent -> palette accent
        palette_swap["#2f6fe4"] = THEME["accent_h"]
        palette_swap["#2563c2"] = accent          # light-mode accent twin
        self._theme_walk(self, palette_swap)
        try:
            self.theme_btn.configure(text=palette.capitalize())
        except Exception:
            pass
        try:
            style = ttk.Style()
            style.configure("AppList.Treeview", background="#0d1117", fieldbackground="#0d1117",
                            foreground="#e6edf3")
            style.configure("AppList.Vertical.Tscrollbar", background="#21262d", troughcolor="#0d1117",
                            arrowcolor="#8b949e", bordercolor="#0d1117")
            tags = {
                "threat": ("#2a1015", "#ff6b6b"), "both_excl": ("#241a33", "#d2a8ff"),
                "uninstall_excl": ("#2a1212", "#ff8f8f"), "clean_excl": ("#2a2010", "#ffd08a"),
                "normal": ("#0f2017", "#e6edf3"), "normal_alt": ("#0c1b13", "#e6edf3"),
            }
            for tag, (bg, fg) in tags.items():
                try:
                    self.sec_tree.tag_configure(tag, background=bg, foreground=fg)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self._fix_button_text_colors("light")
        except Exception:
            pass
        except Exception:
            pass
        try:
            self._fix_button_text_colors(mode)
        except Exception:
            pass

    @staticmethod
    def _theme_walk(root, swap=COLOR_SWAP):
        stack = list(root.winfo_children())
        while stack:
            w = stack.pop()
            try:
                stack.extend(w.winfo_children())
            except Exception:
                pass
            for attr in ("fg_color", "text_color", "border_color", "hover_color",
                         "progress_color", "button_color", "button_hover_color",
                         "dropdown_fg_color", "dropdown_hover_color",
                         "dropdown_text_color", "trough_color", "arrow_color",
                         "scrollbar_button_color", "scrollbar_button_hover_color"):
                try:
                    v = w.cget(attr)
                except Exception:
                    continue
                if isinstance(v, str) and v in swap:
                    try:
                        w.configure(**{attr: swap[v]})
                    except Exception:
                        pass

    @staticmethod
    def _color_luminance(hexc):
        """Approximate sRGB relative luminance (0=black .. 1=white)."""
        try:
            h = hexc.lstrip("#")
            if len(h) == 3:
                h = "".join(c * 2 for c in h)
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))

            def _f(c):
                c /= 255.0
                return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

            return 0.2126 * _f(r) + 0.7152 * _f(g) + 0.0722 * _f(b)
        except Exception:
            return 0.0

    def _fix_button_text_colors(self, mode):
        """CTk's *default* button text_color is the same light gray (#DCE4EE)
        in BOTH appearance modes. After the theme walker swaps a button's
        background to a light color for Light mode, that light text becomes
        faint/invisible on the light background -- so active controls look
        disabled. Force a contrast-aware text color on every CTkButton based
        on its (already swapped) background. Dark-only surfaces (log console,
        phone screen) keep light text because their background stays dark."""
        try:
            from customtkinter import CTkButton
        except Exception:
            return
        light_text = THEME.get("text", "#e6edf3")
        dark_text = "#1b2530" if mode == "light" else THEME.get("text", "#e6edf3")
        if mode == "dark":
            text_for = lambda fg: light_text
        else:
            text_for = lambda fg: dark_text if self._color_luminance(fg) > 0.45 else light_text
        seen = set()
        stack = list(self.winfo_children())
        while stack:
            w = stack.pop()
            try:
                stack.extend(w.winfo_children())
            except Exception:
                pass
            if not isinstance(w, CTkButton):
                continue
            wid = getattr(w, "winfo_id", None)
            if wid is not None:
                wid = wid()
                if wid in seen:
                    continue
                seen.add(wid)
            try:
                fg = w.cget("fg_color")
            except Exception:
                fg = None
            if isinstance(fg, (tuple, list)):
                fg = fg[0] if fg else None
            try:
                w.configure(text_color=text_for(fg) if fg else light_text)
            except Exception:
                pass

