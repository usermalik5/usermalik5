# -*- coding: utf-8 -*-
# Dashboard page (3uTools-style): Android phone mockup whose SCREEN shows the
# live log console, plus a device info card with real ADB stats.
import customtkinter as ctk
import threading
import re
from tech_common import THEME, subprocess


class DashboardMixin:
    def build_dashboard_page(self):
        page = self.page("Dashboard")
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)

        outer = ctk.CTkFrame(page, fg_color="transparent")
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        # ------------------------------------------------------------
        # LEFT: ANDROID PHONE MOCKUP (screen = live log console)
        # ------------------------------------------------------------
        phone_col = ctk.CTkFrame(outer, fg_color="transparent")
        phone_col.grid(row=0, column=0, padx=(14, 8), pady=10, sticky="n")
        phone_col.grid_rowconfigure(0, weight=1)

        phone_h = min(700, max(560, self.winfo_screenheight() - 240))
        self.dash_phone = ctk.CTkFrame(phone_col, fg_color="#05080c", corner_radius=26,
                                       width=330, height=phone_h, border_width=3,
                                       border_color="#223040")
        self.dash_phone.pack(expand=True)
        self.dash_phone.grid_propagate(False)
        self.dash_phone.grid_columnconfigure(0, weight=1)
        self.dash_phone.grid_rowconfigure(1, weight=1)

        # earpiece + camera
        top = ctk.CTkFrame(self.dash_phone, fg_color="transparent")
        top.grid(row=0, column=0, pady=(10, 0))
        ctk.CTkFrame(top, width=60, height=5, corner_radius=3, fg_color="#223040").pack(side="left", padx=(0, 8))
        ctk.CTkFrame(top, width=7, height=7, corner_radius=4, fg_color="#1a2430").pack(side="left")

        # screen
        screen = ctk.CTkFrame(self.dash_phone, fg_color="#010409", corner_radius=10,
                              border_width=1, border_color="#131a22")
        screen.grid(row=1, column=0, sticky="nsew", padx=7, pady=8)
        screen.grid_columnconfigure(0, weight=1)
        screen.grid_rowconfigure(1, weight=1)

        # phone status bar (cosmetic)
        ph = ctk.CTkFrame(screen, fg_color="transparent")
        ph.grid(row=0, column=0, sticky="ew", padx=10, pady=(4, 0))
        ctk.CTkLabel(ph, text="GeloTechOS", font=ctk.CTkFont(size=8, weight="bold"), text_color="#4b5563").pack(side="left")
        ctk.CTkLabel(ph, text="\u25c9 \u25c9 \u25c9  \U0001f4f6  86%", font=ctk.CTkFont(size=8), text_color="#4b5563").pack(side="right")

        # live log console lives inside the phone screen
        self._build_log_panel(screen)

        # home indicator
        ctk.CTkFrame(self.dash_phone, width=110, height=4, corner_radius=2,
                     fg_color="#223040").grid(row=2, column=0, pady=(0, 8))

        # ------------------------------------------------------------
        # RIGHT: DEVICE INFO CARD
        # ------------------------------------------------------------
        card = ctk.CTkFrame(outer, fg_color=THEME["panel"], corner_radius=12,
                            border_width=1, border_color=THEME["border"])
        card.grid(row=0, column=1, padx=(8, 14), pady=10, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        # card header
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="\U0001f4f1 DEVICE INFO", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=THEME["text"]).pack(side="left")
        self.dash_conn_badge = ctk.CTkLabel(hdr, text="\u25cf NO DEVICE", font=ctk.CTkFont(size=11, weight="bold"),
                                            text_color=THEME["red"])
        self.dash_conn_badge.pack(side="right")
        ctk.CTkLabel(hdr, text="\U0001f9f9 \U0001f50e GeloTech Phone Manager", font=ctk.CTkFont(size=10),
                     text_color=THEME["muted"]).pack(side="left", padx=(12, 0))

        # storage bar
        storage = ctk.CTkFrame(card, fg_color=THEME["panel2"], corner_radius=8)
        storage.grid(row=1, column=0, padx=16, pady=(6, 2), sticky="ew")
        storage.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(storage, text="Storage", font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME["muted"]).grid(row=0, column=0, padx=(10, 6), pady=(8, 0), sticky="w")
        self.dash_storage_label = ctk.CTkLabel(storage, text="\u2014", font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME["text"])
        self.dash_storage_label.grid(row=0, column=1, padx=(0, 10), pady=(8, 0), sticky="e")
        self.dash_storage_bar = ctk.CTkProgressBar(storage, height=10, corner_radius=5,
                                                   fg_color=THEME["input"], progress_color=THEME["accent"])
        self.dash_storage_bar.grid(row=1, column=0, columnspan=2, padx=10, pady=(4, 8), sticky="ew")
        self.dash_storage_bar.set(0)

        # info table
        rows = [
            ("Model", "dash_model"),
            ("Brand", "dash_brand"),
            ("Android Version", "dash_android"),
            ("Security Patch", "dash_patch"),
            ("Build ID", "dash_build"),
            ("Serial Number", "dash_serial"),
            ("CPU ABI", "dash_cpu"),
            ("RAM", "dash_ram"),
            ("Battery Level", "dash_battery"),
            ("Battery Health", "dash_health"),
            ("Battery Status", "dash_batt_status"),
            ("Battery Temp", "dash_batt_temp"),
            ("WiFi MAC", "dash_wifi"),
            ("Bluetooth MAC", "dash_bt"),
            ("USB Debugging", "dash_usb"),
        ]
        tbl = ctk.CTkFrame(card, fg_color=THEME["panel2"], corner_radius=8)
        tbl.grid(row=2, column=0, padx=16, pady=(4, 8), sticky="ew")
        tbl.grid_columnconfigure(1, weight=1)
        self._dash_vals = {}
        for i, (label, key) in enumerate(rows):
            ctk.CTkLabel(tbl, text=label, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=THEME["muted"], anchor="w").grid(row=i, column=0,
                         padx=(12, 10), pady=3, sticky="w")
            val = ctk.CTkLabel(tbl, text="\u2014", font=ctk.CTkFont(size=10),
                               text_color=THEME["text"], anchor="w")
            val.grid(row=i, column=1, padx=(0, 12), pady=3, sticky="w")
            self._dash_vals[key] = val

        # status badges row
        badges = ctk.CTkFrame(card, fg_color="transparent")
        badges.grid(row=3, column=0, padx=16, pady=(0, 10), sticky="ew")
        self.dash_usb_badge = ctk.CTkLabel(badges, text="USB DEBUGGING: \u2014", font=ctk.CTkFont(size=10, weight="bold"),
                                           text_color=THEME["muted"],
                                           fg_color=THEME["panel2"], corner_radius=6, width=170, height=26)
        self.dash_usb_badge.pack(side="left", padx=(0, 8))
        self.dash_conn2_badge = ctk.CTkLabel(badges, text="CONNECTION: \u2014", font=ctk.CTkFont(size=10, weight="bold"),
                                             text_color=THEME["muted"],
                                             fg_color=THEME["panel2"], corner_radius=6, width=170, height=26)
        self.dash_conn2_badge.pack(side="left")

        # footer: refresh
        foot = ctk.CTkFrame(card, fg_color="transparent")
        foot.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="ew")
        foot.grid_columnconfigure(0, weight=1)
        self.dash_last_label = ctk.CTkLabel(foot, text="Last refresh: \u2014", font=ctk.CTkFont(size=9), text_color=THEME["muted"])
        self.dash_last_label.pack(side="left")
        ctk.CTkButton(foot, text="\U0001f504 Refresh", width=110, height=32,
                      fg_color=THEME["accent"], hover_color=THEME["accent_h"],
                      font=ctk.CTkFont(size=11, weight="bold"),
                      command=self._dash_refresh_click).pack(side="right")

        self.log_message("[Dashboard] Device dashboard ready. Connect a phone via USB debugging.")

    # ------------------------------------------------------------
    # DATA: periodic refresh while the Dashboard page is visible
    # ------------------------------------------------------------
    def _dash_refresh_click(self):
        self._dash_fetch_stats()

    def _dash_refresh_if_visible(self):
        if not self.winfo_exists():
            return
        if self._current_page == "Dashboard":
            self._dash_fetch_stats()
        self._dash_refresh_after = self.after(10000, self._dash_refresh_if_visible)

    def _dash_fetch_stats(self):
        threading.Thread(target=self._dash_fetch_worker, daemon=True).start()

    def _dash_fetch_worker(self):
        adb = self.scrcpy_adb

        def run(args, timeout=8):
            try:
                r = subprocess.run([adb] + args, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, timeout=timeout)
                return r.stdout or ""
            except Exception:
                return ""

        connected = False
        serial = ""
        for line in run(["devices"]).splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                connected = True
                serial = parts[0]

        vals = {k: "\u2014" for k in (
            "model", "brand", "android", "patch", "build", "serial",
            "cpu", "ram", "battery", "health", "batt_status", "batt_temp",
            "wifi", "bt", "usb")}
        storage_pct = 0.0
        storage_text = "\u2014"

        if connected:
            props = run(["shell", "getprop"])
            if props:
                def p(name):
                    m = re.search(r"\[" + re.escape(name) + r"\]:\s*\[([^\]]*)\]", props)
                    return m.group(1).strip() if m else ""
                vals["model"] = p("ro.product.model") or p("ro.product.device") or serial
                vals["brand"] = (p("ro.product.brand") or p("ro.product.manufacturer") or "\u2014")
                vals["android"] = p("ro.build.version.release") or "\u2014"
                vals["patch"] = p("ro.build.version.security_patch") or "\u2014"
                vals["build"] = p("ro.build.display.id") or "\u2014"
                vals["serial"] = p("ro.serialno") or serial or "\u2014"
                vals["cpu"] = p("ro.product.cpu.abi") or "\u2014"

            combo = run(["shell",
                         "printf 'W|'; cat /sys/class/net/wlan0/address 2>/dev/null; "
                         "printf 'B|'; settings get secure bluetooth_address 2>/dev/null; "
                         "printf 'U|'; settings get global adb_enabled 2>/dev/null; "
                         "df -k /data 2>/dev/null; "
                         "cat /proc/meminfo 2>/dev/null; "
                         "dumpsys battery 2>/dev/null; "
                         "dumpsys bluetooth_manager 2>/dev/null | grep -i 'address:' | head -1"])
            if combo:
                mac_re = re.compile(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", re.I)
                for line in combo.splitlines():
                    if line.startswith("W|"):
                        m = mac_re.search(line[2:])
                        if m:
                            vals["wifi"] = m.group(0).upper()
                    elif line.startswith("B|"):
                        m = mac_re.search(line[2:])
                        if m:
                            vals["bt"] = m.group(0).upper()
                    elif line.startswith("U|"):
                        vals["usb"] = "ON" if line[2:].strip() == "1" else "OFF"
                if vals["bt"] == "\u2014":
                    m = re.search(r"address:\s*([0-9a-fA-F:]{17})", combo)
                    if m:
                        vals["bt"] = m.group(1).upper()
                m = re.search(r"MemTotal:\s*(\d+)", combo)
                if m:
                    total_kb = int(m.group(1))
                    vals["ram"] = f"{total_kb // 1048576:.1f} GB"
                m = re.search(r"level:\s*(\d+)", combo)
                if m:
                    vals["battery"] = f"{m.group(1)}%"
                m = re.search(r"health:\s*(\d+)", combo)
                if m:
                    vals["health"] = {
                        "1": "Unknown", "2": "Good", "3": "Overheat",
                        "4": "Dead", "5": "Overvoltage", "6": "Failure",
                        "7": "Cold"}.get(m.group(1), m.group(1))
                m = re.search(r"status:\s*(\d+)", combo)
                if m:
                    vals["batt_status"] = {
                        "1": "Unknown", "2": "Charging", "3": "Discharging",
                        "4": "Not charging", "5": "Full"}.get(m.group(1), m.group(1))
                m = re.search(r"temperature:\s*(\d+)", combo)
                if m:
                    vals["batt_temp"] = f"{int(m.group(1)) / 10:.1f}\u00b0C"
                lines = combo.splitlines()
                for i, line in enumerate(lines):
                    if line.startswith("Filesystem") and i + 1 < len(lines):
                        parts = lines[i + 1].split()
                        if len(parts) >= 4:
                            total = int(parts[1]) * 1024
                            used = int(parts[2]) * 1024
                            if total > 0:
                                storage_pct = used / total
                                storage_text = f"{_fmt_bytes(used)} / {_fmt_bytes(total)}"

        def apply():
            try:
                for key, label in self._dash_vals.items():
                    lookup = key[5:] if key.startswith("dash_") else key
                    label.configure(text=vals.get(lookup, "\u2014"))
                if connected:
                    self.dash_conn_badge.configure(text="\u25cf CONNECTED", text_color=THEME["green"])
                    self.dash_conn2_badge.configure(text="CONNECTION: CONNECTED", text_color=THEME["green"])
                else:
                    self.dash_conn_badge.configure(text="\u25cf NO DEVICE", text_color=THEME["red"])
                    self.dash_conn2_badge.configure(text="CONNECTION: NONE", text_color=THEME["red"])
                usb = vals.get("usb", "\u2014")
                self.dash_usb_badge.configure(
                    text=f"USB DEBUGGING: {usb}",
                    text_color=THEME["green"] if usb == "ON" else (THEME["amber"] if usb != "\u2014" else THEME["muted"]))
                self.dash_storage_bar.set(storage_pct)
                self.dash_storage_label.configure(text=storage_text)
                try:
                    import datetime as _dt
                    self.dash_last_label.configure(
                        text=f"Last refresh: {_dt.datetime.now().strftime('%H:%M:%S')} (auto every 10s)")
                except Exception:
                    pass
            except Exception:
                pass

        try:
            self.after(0, apply)
        except Exception:
            pass


def _fmt_bytes(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"
