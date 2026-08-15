# -*- coding: utf-8 -*-
"""Reference implementation for the GeloTech Dashboard phone mirror.

This is intentionally kept as a separate file while OpenCode integrates it
locally.  It fixes the current 45a4981 implementation by:

* deriving the native overlay position AND scale from the actual Tk phone
  widget instead of assuming a 396x824 1:1 desktop window;
* hiding the old Dashboard log textbox while mirroring so it cannot show
  through the transparent frame cutout;
* finding the real scrcpy HWND by PID without requiring a particular title;
* reporting scrcpy's exit code/log tail when no window is created;
* keeping the scrcpy window underneath the transparent frame;
* following Dashboard phone position/size changes.

The live video remains the native scrcpy window.  There is no screenshot or
PIL frame-copy loop.
"""

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import threading
import time
from PIL import Image

MIRROR_WINDOW_TITLE = "GeloTech Mirror"
OVERLAY_WINDOW_TITLE = "GeloTech iPhone"
PHONE_IMG_NATIVE = (396, 824)
DISPLAY_RECT = (14, 12, 368, 800)

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_POPUP = 0x80000000
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOOWNERZORDER = 0x0200
HWND_TOPMOST = -1
HTTRANSPARENT = -1
WM_NCHITTEST = 0x0084
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
ULW_ALPHA = 0x00000002
AC_SRC_ALPHA = 1


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_int32), ("cy", ctypes.c_int32)]


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_int32), ("top", ctypes.c_int32),
                ("right", ctypes.c_int32), ("bottom", ctypes.c_int32)]


class _BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte),
                ("AlphaFormat", ctypes.c_ubyte)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER),
                ("bmiColors", ctypes.c_uint32 * 3)]


class _MSG(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("message", ctypes.c_uint),
                ("wParam", ctypes.c_size_t), ("lParam", ctypes.c_ssize_t),
                ("time", ctypes.c_uint32), ("pt", _POINT),
                ("lPrivate", ctypes.c_uint32)]


_WNDPROC_T = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, ctypes.c_uint,
                                ctypes.c_size_t, ctypes.c_ssize_t)


class _WNDCLASS(ctypes.Structure):
    _fields_ = [("style", ctypes.c_uint), ("lpfnWndProc", _WNDPROC_T),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p), ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p), ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR)]


def _u():
    return ctypes.windll.user32


def _g():
    return ctypes.windll.gdi32


def _init_win32():
    u, g, k = _u(), _g(), ctypes.windll.kernel32
    k.GetModuleHandleW.restype = ctypes.c_void_p
    u.CreateWindowExW.restype = ctypes.c_void_p
    u.CreateWindowExW.argtypes = [ctypes.c_uint32, wt.LPCWSTR, wt.LPCWSTR,
                                  ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32,
                                  ctypes.c_int32, ctypes.c_int32, ctypes.c_void_p,
                                  ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    u.GetDC.restype = ctypes.c_void_p
    u.GetDC.argtypes = [ctypes.c_void_p]
    u.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    u.DefWindowProcW.restype = ctypes.c_ssize_t
    u.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                 ctypes.c_size_t, ctypes.c_ssize_t]
    u.PostMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                               ctypes.c_size_t, ctypes.c_ssize_t]
    u.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RECT)]
    u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32,
                               ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
                               ctypes.c_uint32]
    u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_ulong)]
    u.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    u.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int32]
    u.IsWindowVisible.argtypes = [ctypes.c_void_p]
    u.IsWindow.argtypes = [ctypes.c_void_p]
    u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    g.CreateCompatibleDC.restype = ctypes.c_void_p
    g.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    g.CreateDIBSection.restype = ctypes.c_void_p
    g.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
                                   ctypes.c_void_p, ctypes.c_uint32]
    g.SelectObject.restype = ctypes.c_void_p
    g.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    g.DeleteObject.argtypes = [ctypes.c_void_p]
    g.DeleteDC.argtypes = [ctypes.c_void_p]
    u.UpdateLayeredWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.POINTER(_SIZE),
                                      ctypes.c_void_p, ctypes.POINTER(_POINT),
                                      ctypes.c_uint32,
                                      ctypes.POINTER(_BLENDFUNCTION), ctypes.c_uint32]


_init_win32()


def _rect(hwnd):
    r = _RECT()
    if not hwnd or not _u().GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def _tail(path, lines=20):
    try:
        with open(path, "rb") as f:
            data = f.read()[-8192:]
        text = data.decode("utf-8", "replace")
        return "\n".join(text.splitlines()[-lines:])
    except Exception:
        return ""


class PhoneFrameOverlay:
    def __init__(self, image_path, scale, x, y, log):
        self.log = log
        self.scale = float(scale)
        self.image_path = image_path
        self.x, self.y = int(x), int(y)
        self.hwnd = None
        self._quit = False
        self._thread = None
        self._ready = threading.Event()
        self._wndproc = None
        self._load_bits()

    def _load_bits(self):
        img = Image.open(self.image_path).convert("RGBA")
        w = max(1, int(PHONE_IMG_NATIVE[0] * self.scale + .5))
        h = max(1, int(PHONE_IMG_NATIVE[1] * self.scale + .5))
        if img.size != (w, h):
            img = img.resize((w, h), Image.Resampling.LANCZOS)
        data = bytearray(img.tobytes())
        for i in range(0, len(data), 4):
            a = data[i + 3]
            data[i] = (data[i] * a) // 255
            data[i + 1] = (data[i + 1] * a) // 255
            data[i + 2] = (data[i + 2] * a) // 255
            data[i], data[i + 2] = data[i + 2], data[i]
        self.width, self.height = w, h
        self.bits = bytes(data)

    def show(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def _run(self):
        u = _u()
        self._wndproc = self._make_proc()
        cls = _WNDCLASS()
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        cls.lpszClassName = OVERLAY_WINDOW_TITLE
        try:
            u.RegisterClassW(ctypes.byref(cls))
        except Exception:
            pass
        self.hwnd = u.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST,
            OVERLAY_WINDOW_TITLE, OVERLAY_WINDOW_TITLE, WS_POPUP,
            self.x, self.y, self.width, self.height, None, None,
            cls.hInstance, None)
        if not self.hwnd:
            self.log("[PHONE ERROR] overlay CreateWindowExW failed")
            self._ready.set()
            return
        self._apply()
        u.ShowWindow(self.hwnd, 5)
        self._ready.set()
        self.raise_top()
        msg = _MSG()
        while not self._quit:
            r = u.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r <= 0:
                break
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))

    def _make_proc(self):
        @_WNDPROC_T
        def proc(hwnd, msg, wp, lp):
            if msg == WM_NCHITTEST:
                return HTTRANSPARENT
            if msg == WM_CLOSE:
                self._quit = True
                _u().DestroyWindow(hwnd)
                return 0
            if msg == WM_DESTROY:
                _u().PostQuitMessage(0)
                return 0
            return _u().DefWindowProcW(hwnd, msg, wp, lp)
        return proc

    def _apply(self):
        u, g = _u(), _g()
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self.width
        bmi.bmiHeader.biHeight = -self.height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bits = ctypes.c_void_p()
        screen_dc = u.GetDC(None)
        mem = g.CreateCompatibleDC(screen_dc)
        bmp = g.CreateDIBSection(screen_dc, ctypes.byref(bmi), 0,
                                 ctypes.byref(bits), None, 0)
        old = g.SelectObject(mem, bmp)
        ctypes.memmove(bits, self.bits, len(self.bits))
        size = _SIZE(self.width, self.height)
        src = _POINT(0, 0)
        blend = _BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
        ok = u.UpdateLayeredWindow(self.hwnd, screen_dc, None, ctypes.byref(size),
                                   mem, ctypes.byref(src), 0,
                                   ctypes.byref(blend), ULW_ALPHA)
        g.SelectObject(mem, old)
        g.DeleteObject(bmp)
        g.DeleteDC(mem)
        u.ReleaseDC(None, screen_dc)
        if not ok:
            self.log(f"[PHONE ERROR] UpdateLayeredWindow failed: {ctypes.get_last_error()}")

    def move_resize(self, x, y, scale):
        x, y, scale = int(x), int(y), float(scale)
        changed_scale = abs(scale - self.scale) > 0.005
        self.x, self.y = x, y
        if changed_scale:
            self.scale = scale
            self._load_bits()
            self._apply()
        if self.hwnd:
            _u().SetWindowPos(self.hwnd, HWND_TOPMOST, x, y,
                              self.width, self.height,
                              SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def raise_top(self):
        if self.hwnd:
            _u().SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                              SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def close(self):
        self._quit = True
        if self.hwnd:
            try:
                _u().PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(3)
        self.hwnd = None

    def alive(self):
        return bool(self.hwnd and _u().IsWindow(self.hwnd))

    def rect(self):
        return _rect(self.hwnd)


class ScrcpyWindow:
    @staticmethod
    def launch(exe, adb, cwd, x, y, w, h, log):
        cmd = [exe, "--adb", adb, "--window-title", MIRROR_WINDOW_TITLE,
               "--window-x", str(x), "--window-y", str(y),
               "--window-width", str(w), "--window-height", str(h),
               "--window-borderless", "--no-audio", "--max-size", "1280",
               "--no-power-on"]
        log_path = os.path.join(os.environ.get("TEMP") or ".", "gelotech_scrcpy.log")
        err = open(log_path, "wb")
        try:
            p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.DEVNULL, stderr=err)
        except Exception:
            err.close()
            raise
        log(f"[SCRCPY] log: {log_path}")
        return p, log_path

    @staticmethod
    def find_hwnd(proc, timeout=20.0):
        deadline = time.time() + timeout
        pid = getattr(proc, "pid", 0) if proc else 0
        while time.time() < deadline:
            found = []
            @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
            def cb(hwnd, _):
                if not _u().IsWindowVisible(hwnd):
                    return True
                p = ctypes.c_ulong()
                _u().GetWindowThreadProcessId(hwnd, ctypes.byref(p))
                if pid and p.value == pid:
                    found.append(hwnd)
                    return False
                return True
            try:
                _u().EnumWindows(cb, 0)
            except Exception:
                pass
            if found:
                return found[0]
            if proc and proc.poll() is not None:
                return 0
            time.sleep(.1)
        return 0

    @staticmethod
    def align(hwnd, x, y, w, h):
        style = _u().GetWindowLongW(hwnd, GWL_EXSTYLE)
        _u().SetWindowLongW(hwnd, GWL_EXSTYLE,
                            (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
        _u().SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), int(w), int(h),
                           SWP_NOACTIVATE | SWP_SHOWWINDOW)

    @staticmethod
    def raise_top(hwnd):
        if hwnd:
            _u().SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                              SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


class PhoneMirrorManager:
    def __init__(self, overlay_path, scale=1.0, log=None, on_state=None):
        self.overlay_path = overlay_path
        self.scale = scale
        self.log = log or (lambda *_: None)
        self.on_state = on_state
        self.overlay = None
        self.proc = None
        self.hwnd = 0
        self.log_path = None
        self.state = "off"
        self._stop = threading.Event()
        self._monitor = None
        self._dashboard = getattr(self.log, "__self__", None)
        self._hidden_console = None
        self._console_place = None

    def _set_state(self, state):
        self.state = state
        if self.on_state:
            try:
                self.on_state(state)
            except Exception:
                pass

    def _phone_geometry(self):
        d = self._dashboard
        phone = getattr(d, "dash_phone", None) if d else None
        if phone is None:
            return None
        try:
            phone.update_idletasks()
            w = max(1, int(phone.winfo_width()))
            h = max(1, int(phone.winfo_height()))
            x = int(phone.winfo_rootx())
            y = int(phone.winfo_rooty())
            scale = min(w / PHONE_IMG_NATIVE[0], h / PHONE_IMG_NATIVE[1])
            fw = int(PHONE_IMG_NATIVE[0] * scale + .5)
            fh = int(PHONE_IMG_NATIVE[1] * scale + .5)
            x += (w - fw) // 2
            y += (h - fh) // 2
            return x, y, scale, fw, fh
        except Exception:
            return None

    def _hide_dashboard_console(self):
        d = self._dashboard
        if not d or self._hidden_console is not None:
            return
        try:
            rect = getattr(d, "_dash_log_rect", None)
            consoles = getattr(d, "_log_consoles", [])
            if consoles:
                c = consoles[0]["frame"]
                self._hidden_console = c
                self._console_place = rect
                c.place_forget()
        except Exception:
            self._hidden_console = None

    def _restore_dashboard_console(self):
        c = self._hidden_console
        if c is None:
            return
        try:
            r = self._console_place
            if r:
                try:
                    c.configure(width=int(r[2]), height=int(r[3]))
                except Exception:
                    pass
                c.place(x=r[0], y=r[1])
        except Exception:
            pass
        self._hidden_console = None
        self._console_place = None

    def start(self, scrcpy_exe, scrcpy_adb, scrcpy_dir, spawn_x=None, spawn_y=None):
        if self.state != "off":
            self.stop()
        geom = self._phone_geometry()
        if geom:
            x, y, scale, fw, fh = geom
        else:
            x = int(spawn_x if spawn_x is not None and spawn_x >= 0 else 100)
            y = int(spawn_y if spawn_y is not None and spawn_y >= 0 else 50)
            scale = self.scale
            fw = int(PHONE_IMG_NATIVE[0] * scale + .5)
            fh = int(PHONE_IMG_NATIVE[1] * scale + .5)
        self.scale = scale
        dx = int(DISPLAY_RECT[0] * scale + .5)
        dy = int(DISPLAY_RECT[1] * scale + .5)
        dw = int(DISPLAY_RECT[2] * scale + .5)
        dh = int(DISPLAY_RECT[3] * scale + .5)
        self.log(f"[PHONE] Dashboard phone: {x},{y} {fw}x{fh} scale={scale:.3f}")
        self.log(f"[PHONE] Display area: {x+dx},{y+dy} {dw}x{dh}")
        self._hide_dashboard_console()
        try:
            self.overlay = PhoneFrameOverlay(self.overlay_path, scale, x, y, self.log)
            self.overlay.show()
            self.proc, self.log_path = ScrcpyWindow.launch(
                scrcpy_exe, scrcpy_adb, scrcpy_dir,
                x + dx, y + dy, dw, dh, self.log)
        except Exception as e:
            self.log(f"[SCRCPY ERROR] launch failed: {e}")
            self._restore_dashboard_console()
            if self.overlay:
                self.overlay.close()
            self.overlay = None
            self.state = "off"
            return False
        self._stop.clear()
        self._set_state("starting")
        self._monitor = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor.start()
        return True

    def stop(self):
        self._stop.set()
        p = self.proc
        if p is not None and p.poll() is None:
            try:
                p.terminate()
                p.wait(2)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        if self.overlay:
            self.overlay.close()
        if self._monitor and self._monitor is not threading.current_thread():
            self._monitor.join(2)
        self._monitor = None
        self.proc = None
        self.hwnd = 0
        self.overlay = None
        self.state = "off"
        self._restore_dashboard_console()
        if self.on_state:
            try:
                self.on_state("stopped")
            except Exception:
                pass

    def toggle(self, *args):
        if self.state != "off":
            self.stop()
        else:
            self.start(*args)

    def _expected(self):
        g = self._phone_geometry()
        if not g:
            return None
        x, y, scale, fw, fh = g
        dx = int(DISPLAY_RECT[0] * scale + .5)
        dy = int(DISPLAY_RECT[1] * scale + .5)
        dw = int(DISPLAY_RECT[2] * scale + .5)
        dh = int(DISPLAY_RECT[3] * scale + .5)
        return x, y, scale, (x + dx, y + dy, dw, dh)

    def _monitor_loop(self):
        self.hwnd = ScrcpyWindow.find_hwnd(self.proc, timeout=20.0)
        if not self.hwnd:
            code = None
            try:
                code = self.proc.poll()
            except Exception:
                pass
            self.log(f"[SCRCPY ERROR] no scrcpy window (exit={code})")
            tail = _tail(self.log_path) if self.log_path else ""
            if tail:
                for line in tail.splitlines()[-12:]:
                    self.log(f"[SCRCPY LOG] {line}")
            self._cleanup()
            return
        self.log(f"[SCRCPY] HWND found: {self.hwnd}")
        self._set_state("active")
        while not self._stop.is_set():
            if not self.proc or self.proc.poll() is not None:
                self.log("[SCRCPY] process exited")
                self._cleanup()
                return
            if not ScrcpyWindow.alive(self.hwnd) if hasattr(ScrcpyWindow, "alive") else not _u().IsWindowVisible(self.hwnd):
                self.log("[SCRCPY] window closed")
                self._cleanup()
                return
            expected = self._expected()
            if expected:
                x, y, scale, sr = expected
                ar = _rect(self.hwnd)
                if ar != sr:
                    ScrcpyWindow.align(self.hwnd, *sr)
                if self.overlay and self.overlay.alive():
                    orr = self.overlay.rect()
                    # Keep the native frame exactly over the Tk phone mockup.
                    if not orr or orr[:2] != (x, y) or orr[2:] != (int(PHONE_IMG_NATIVE[0]*scale+.5), int(PHONE_IMG_NATIVE[1]*scale+.5)):
                        self.overlay.move_resize(x, y, scale)
                    ScrcpyWindow.raise_top(self.hwnd)
                    self.overlay.raise_top()
            time.sleep(0.08)

    def _cleanup(self):
        self._stop.set()
        if self.overlay:
            self.overlay.close()
        p = self.proc
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        self.proc = None
        self.hwnd = 0
        self.overlay = None
        self.state = "off"
        self._restore_dashboard_console()
        self.log("[SCRCPY] Mirror stopped")
        if self.on_state:
            try:
                self.on_state("stopped")
            except Exception:
                pass

    @staticmethod
    def _alive(hwnd):
        return bool(hwnd and _u().IsWindow(hwnd) and _u().IsWindowVisible(hwnd))

ScrcpyWindow.alive = PhoneMirrorManager._alive
