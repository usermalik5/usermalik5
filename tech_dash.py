# -*- coding: utf-8 -*-
# Dashboard page (3uTools-style): real iPhone 17 PNG mockup whose transparent
# SCREEN shows the live log console. "Screen Mirror" runs the REAL scrcpy
# stream in a two-window setup (see tech_phone_mirror): the native scrcpy
# window is glued under a transparent iPhone frame overlay.
import os
import ctypes
import customtkinter as ctk
from PIL import Image
from tech_common import THEME, get_bundle_dir
from tech_phone_mirror import PhoneMirrorManager, PHONE_SCALE

# Phone mockup image: bundled in assets/phone_devices (720x824 @2x, screen
# area is transparent). SCREEN_RECT is the transparent cutout in image px,
# SCREEN_RADIUS the cutout corner radius @2x (measured from the PNG alpha).
PHONE_IMG_DIR = os.path.join(get_bundle_dir(), "assets", "phone_devices")
PHONE_IMG = os.path.join(PHONE_IMG_DIR, "iPhone17_P_PM_CosmicOrange@2x.png")
PHONE_IMG_NATIVE = (396, 824)
PHONE_SCREEN_RECT = (14, 12, 368, 800)    # x, y, w, h in image px (2x)
PHONE_SCREEN_RADIUS = 24                  # screen corner radius at 2x
DASH_PHONE_MAX_H = 760                    # displayed height cap in px

# The phone PNG keeps its dynamic island as OPAQUE pixels inside the
# transparent screen cutout, so the console must start below it to not
# cover the island (native 2x px).
ISLAND_BOTTOM_NATIVE = 55
SCREEN_TOP_INSET_NATIVE = 61             # island bottom + small gap

# Mirror overlay asset (derived from the frame PNG; the display opening is
# already fully transparent, so the live scrcpy window shows through it).
PHONE_OVERLAY_IMG = os.path.join(PHONE_IMG_DIR, "iphone_frame_overlay.png")


def clip_hwnd_rounded(hwnd, width, height, radius):
    """Win32: round ALL corners of a window (used for the phone screen
    cutout). Must run after the window exists."""
    try:
        rgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1,
                                                     radius * 2, radius * 2)
        if rgn:
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
    except Exception:
        pass


def clip_widget_rounded(widget, width, height, radius):
    """Win32: round a widget window's corners to match the phone screen
    cutout. Must run after the widget is mapped."""
    try:
        hwnd = widget.winfo_id()
        if hwnd:
            clip_hwnd_rounded(hwnd, width, height, radius)
    except Exception:
        pass


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
        # LEFT: PHONE MOCKUP (real image, transparent screen = live log console)
        # ------------------------------------------------------------
        phone_col = ctk.CTkFrame(outer, fg_color="transparent")
        phone_col.grid(row=0, column=0, padx=(14, 8), pady=10, sticky="n")
        phone_col.grid_rowconfigure(0, weight=1)

        img_h = min(DASH_PHONE_MAX_H, max(520, self.winfo_screenheight() - 260))
        s = img_h / PHONE_IMG_NATIVE[1]
        phone_w = int(PHONE_IMG_NATIVE[0] * s)
        self.dash_phone = ctk.CTkFrame(phone_col, fg_color="transparent",
                                       width=phone_w, height=img_h)
        self.dash_phone.pack(expand=True)
        self.dash_phone.grid_propagate(False)
        self.dash_phone.bind("<Configure>", self._dash_phone_configure)

        try:
            self._dash_phone_img = ctk.CTkImage(light_image=Image.open(PHONE_IMG),
                                                dark_image=Image.open(PHONE_IMG),
                                                size=(phone_w, img_h))
            ctk.CTkLabel(self.dash_phone, image=self._dash_phone_img,
                         text="", fg_color="transparent").place(x=0, y=0)
        except Exception:
            pass

        # live log console sits inside the transparent screen cutout, below
        # the phone's dynamic island (the cutout's own pixels stay visible)
        sx, sy, sw, sh = PHONE_SCREEN_RECT
        cx, cy, cw, ch = int(sx * s), int(sy * s), int(sw * s), int(sh * s)
        top_inset = int(SCREEN_TOP_INSET_NATIVE * s)
        console_h = ch - top_inset
        self._dash_log_rect = (cx, cy + top_inset, cw, console_h)
        self._build_log_panel(self.dash_phone,
                              place_rect=self._dash_log_rect,
                              log_font_size=max(6, round(cw / 24)), minimal=True)
        self.after(300, lambda: self._clip_dash_console(cw, console_h,
                                                        int(PHONE_SCREEN_RADIUS * s)))

        btn_row = ctk.CTkFrame(phone_col, fg_color="transparent")
        btn_row.pack(pady=(8, 0))
        self.dash_refresh_btn = ctk.CTkButton(btn_row, text="\U0001f504 Refresh",
                                              width=140, height=32,
                                              fg_color=THEME["accent"],
                                              hover_color=THEME["accent_h"],
                                              text_color=THEME["text"],
                                              font=ctk.CTkFont(size=11, weight="bold"),
                                              command=self.action_sec_refresh)
        self.dash_refresh_btn.pack(side="left", padx=(0, 6))
        self.dash_mirror_btn = ctk.CTkButton(btn_row, text="\U0001f4f1 Screen Mirror",
                                             width=140, height=32,
                                             fg_color=THEME["panel2"],
                                             hover_color=THEME["input"],
                                             border_width=1,
                                             border_color=THEME["border"],
                                             text_color=THEME["text"],
                                             font=ctk.CTkFont(size=11, weight="bold"),
                                             command=self._dash_mirror_toggle)
        self.dash_mirror_btn.pack(side="left")

        # ------------------------------------------------------------
        # RIGHT: APP CLEANER (phone mockup sits next to the cleaner)
        # ------------------------------------------------------------
        right_col = ctk.CTkFrame(outer, fg_color="transparent")
        right_col.grid(row=0, column=1, padx=(8, 14), pady=10, sticky="nsew")
        right_col.grid_columnconfigure(0, weight=1)
        right_col.grid_rowconfigure(0, weight=1)
        self.build_security_tab(parent=right_col)

        self.log_message("[Dashboard] Dashboard ready: App Cleaner + phone.")

    # ------------------------------------------------------------
    # DATA: periodic refresh while the Dashboard page is visible
    # ------------------------------------------------------------
    # ------------------------------------------------------------
    # SCREEN MIRROR (two-window): real scrcpy stream + transparent iPhone
    # frame overlay on top (tech_phone_mirror). The overlay spawns over
    # this phone mockup; SHIFT+drag (or dragging the bezel) moves it.
    # ------------------------------------------------------------
    def _dash_mirror_toggle(self):
        mgr = getattr(self, "_phone_mirror", None)
        if mgr is not None and mgr.state != "off":
            self.log_message("[SCRCPY] Stopping screen mirror")
            mgr.stop()
            return
        exc = getattr(self, "scrcpy_exe", None)
        if not exc or not os.path.exists(exc):
            self.log_message("[SCRCPY ERROR] scrcpy not available - mirror unavailable")
            return
        sx = sy = -1
        phone = getattr(self, "dash_phone", None)
        try:
            if phone is not None and phone.winfo_ismapped():
                fw = int(PHONE_IMG_NATIVE[0] * PHONE_SCALE)
                fh = int(PHONE_IMG_NATIVE[1] * PHONE_SCALE)
                sx = phone.winfo_rootx() - max(0, (fw - phone.winfo_width()) // 2)
                sy = phone.winfo_rooty() - max(0, (fh - phone.winfo_height()) // 2)
        except Exception:
            pass
        if mgr is None:
            mgr = self._phone_mirror = PhoneMirrorManager(
                PHONE_OVERLAY_IMG, scale=PHONE_SCALE,
                log=self.log_message, on_state=self._dash_mirror_state)
        if not mgr.start(self.scrcpy_exe, self.scrcpy_adb, self.scrcpy_dir, sx, sy):
            self._dash_mirror_ui("stopped")

    def _dash_phone_configure(self, _event=None):
        try:
            mgr = getattr(self, "_phone_mirror", None)
            if mgr is not None:
                mgr.geometry_updated()
        except Exception:
            pass

    def _dash_mirror_state(self, state):
        # callback runs on manager threads -> marshal onto the Tk main thread
        try:
            self.after(0, lambda: self._dash_mirror_ui(state))
        except Exception:
            pass

    def _dash_mirror_ui(self, state):
        if state == "starting":
            text = "\u23f3 Starting..."
        elif state == "active":
            text = "\U0001f6d1 Stop Mirror"
        else:
            text = "\U0001f4f1 Screen Mirror"
        try:
            btn = getattr(self, "dash_mirror_btn", None)
            if btn is not None and btn.winfo_exists():
                btn.configure(text=text)
        except Exception:
            pass

    def _clip_dash_console(self, cw, ch, radius, attempts=10):
        try:
            console = self._log_console
            if console.winfo_ismapped():
                # Widget may be DPI-scaled (CTk scaling); clip to its ACTUAL
                # on-screen size and scale the cutout radius to match.
                rw = console.winfo_width()
                rh = console.winfo_height()
                r = max(1, int(radius * rw / cw))
                clip_widget_rounded(console, rw, rh, r)
            elif attempts > 0:
                self.after(500, lambda: self._clip_dash_console(cw, ch, radius,
                                                                attempts - 1))
        except Exception:
            pass

    def _dash_refresh_if_visible(self):
        # Device-info polling was removed with the DEVICE INFO card; kept as
        # a no-op because NavigationController schedules it after login.
        pass

