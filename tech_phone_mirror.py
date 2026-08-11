# -*- coding: utf-8 -*-
"""Two-window Android screen mirror wed to the iPhone 17 frame.

WINDOW 1 : native scrcpy window (the LIVE interactive stream).
WINDOW 2 : transparent iPhone frame overlay (WS_EX_LAYERED, per-pixel
           alpha) placed ABOVE the scrcpy window.

The frame PNG already ships with a fully transparent display opening
(alpha=0 everywhere inside the screen bbox), so the scrcpy stream shows
through the cutout while the bezel, dynamic island and rounded frame stay
unmodified on top.

Input: the overlay is fully click-through (WM_NCHITTEST -> HTTRANSPARENT
everywhere), so every mouse event falls through to scrcpy underneath. The
overlay never activates, so scrcpy keeps focus/keyboard.

No screenshots, no PIL compositing loops, no reparenting: the live stream
stays a plain native window the whole time.
"""
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import threading
import time
from PIL import Image

# ---------------------------------------------------------------------------
# Constants (native image px, scale = PHONE_SCALE)
# ---------------------------------------------------------------------------
MIRROR_WINDOW_TITLE = "GeloTech Mirror"
OVERLAY_WINDOW_TITLE = "GeloTech iPhone"
PHONE_IMG_NATIVE = (396, 824)
PHONE_SCALE = 1.0
# Display opening of the frame, measured from the PNG alpha channel
# (all fully transparent pixels bounded by opaque bezel). x, y, w, h.
DISPLAY_RECT = (14, 12, 368, 800)

# ---------------------------------------------------------------------------
# Win32 plumbing
# ---------------------------------------------------------------------------
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
HWND_TOPMOST = -1
HTTRANSPARENT = -1
WM_NCHITTEST = 0x0084
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
ULW_ALPHA = 0x00000002
AC_SRC_ALPHA = 1
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SW_SHOW = 5


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


def _user32():
    return ctypes.windll.user32


def _gdi32():
    return ctypes.windll.gdi32


def _init_win32():
    """Set explicit arg/return types so 64-bit handles never truncate."""
    u = _user32()
    g = _gdi32()
    k = ctypes.windll.kernel32
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
    g.CreateCompatibleDC.restype = ctypes.c_void_p
    g.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    g.CreateDIBSection.restype = ctypes.c_void_p
    g.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_uint32,
                                   ctypes.POINTER(ctypes.c_void_p),
                                   ctypes.c_void_p, ctypes.c_uint32]
    g.SelectObject.restype = ctypes.c_void_p
    g.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    g.DeleteObject.argtypes = [ctypes.c_void_p]
    g.DeleteDC.argtypes = [ctypes.c_void_p]
    g.CreateRectRgn.restype = ctypes.c_void_p
    g.CreateRectRgn.argtypes = [ctypes.c_int32, ctypes.c_int32,
                                ctypes.c_int32, ctypes.c_int32]
    u.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
    u.UpdateLayeredWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                      ctypes.c_void_p, ctypes.POINTER(_SIZE),
                                      ctypes.c_void_p, ctypes.POINTER(_POINT),
                                      ctypes.c_uint32,
                                      ctypes.POINTER(_BLENDFUNCTION),
                                      ctypes.c_uint32]


_init_win32()


def _get_rect(hwnd):
    r = _RECT()
    try:
        _user32().GetWindowRect(hwnd, ctypes.byref(r))
    except Exception:
        return None
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def _signed16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _screen_center():
    w = _user32().GetSystemMetrics(SM_CXSCREEN)
    h = _user32().GetSystemMetrics(SM_CYSCREEN)
    fw = int(PHONE_IMG_NATIVE[0] * PHONE_SCALE + 0.5)
    fh = int(PHONE_IMG_NATIVE[1] * PHONE_SCALE + 0.5)
    return max(0, (w - fw) // 2), max(0, (h - fh) // 2)


# ---------------------------------------------------------------------------
# PhoneFrameOverlay: transparent WS_EX_LAYERED window running the PNG
# ---------------------------------------------------------------------------
class PhoneFrameOverlay(object):
    """Transparent layered window showing the iPhone frame PNG.

    Fully click-through (HTTRANSPARENT): every mouse event falls through to
    scrcpy underneath, no forwarding code involved. Runs its own thread and
    message loop.
    """

    def __init__(self, image_path, scale=PHONE_SCALE, log=None):
        self.log = log or (lambda *a, **k: None)
        img = Image.open(image_path).convert("RGBA")
        if scale != 1.0:
            img = img.resize((max(1, int(img.width * scale + 0.5)),
                              max(1, int(img.height * scale + 0.5))),
                             Image.LANCZOS)
        self.scale = img.width / float(PHONE_IMG_NATIVE[0])
        self._bits = self._premultiplied_bgra(img)
        self.hwnd = None
        self._quit = False
        self._thread = None
        self._ready = threading.Event()
        self._wndproc = None

    @staticmethod
    def _premultiplied_bgra(img):
        data = bytearray(img.tobytes())  # RGBA bytes
        n = len(data)
        for i in range(0, n, 4):
            a = data[i + 3]
            if a != 255:
                data[i] = (data[i] * a) // 255
                data[i + 1] = (data[i + 1] * a) // 255
                data[i + 2] = (data[i + 2] * a) // 255
            data[i], data[i + 2] = data[i + 2], data[i]  # -> BGRA
        return bytes(data)

    def show(self, x, y):
        self._x, self._y = int(x), int(y)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def _run(self):
        user32 = _user32()
        cls = _WNDCLASS()
        self._wndproc = _make_wndproc(self)
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        cls.lpszClassName = OVERLAY_WINDOW_TITLE
        try:
            user32.RegisterClassW(ctypes.byref(cls))
        except Exception:
            pass
        hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST,
            OVERLAY_WINDOW_TITLE, OVERLAY_WINDOW_TITLE, WS_POPUP,
            self._x, self._y, int(PHONE_IMG_NATIVE[0] * self.scale + 0.5),
            int(PHONE_IMG_NATIVE[1] * self.scale + 0.5), None, None,
            cls.hInstance, None)
        if not hwnd:
            self._ready.set()
            self.log("[PHONE ERROR] overlay CreateWindowExW failed")
            return
        self.hwnd = hwnd
        try:
            self._apply_image()
        except Exception as e:
            self.log(f"[PHONE ERROR] overlay image apply failed: {e}")
            self.hwnd = None
            user32.DestroyWindow(hwnd)
            self._ready.set()
            return
        user32.ShowWindow(hwnd, SW_SHOW)
        self._ready.set()
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        msg = _MSG()
        while not self._quit:
            r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _apply_image(self):
        user32 = _user32()
        gdi = _gdi32()
        w = int(PHONE_IMG_NATIVE[0] * self.scale + 0.5)
        h = int(PHONE_IMG_NATIVE[1] * self.scale + 0.5)
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        buf = ctypes.c_void_p()
        hdc = user32.GetDC(None)
        try:
            memdc = gdi.CreateCompatibleDC(hdc)
            hbmp = gdi.CreateDIBSection(hdc, ctypes.byref(bmi), 0,
                                        ctypes.byref(buf), None, 0)
            old = gdi.SelectObject(memdc, hbmp)
            ctypes.memmove(buf, self._bits, len(self._bits))
            size = _SIZE(w, h)
            src = _POINT(0, 0)
            blend = _BLENDFUNCTION(0, 0, 255, AC_SRC_ALPHA)
            ok = user32.UpdateLayeredWindow(
                self.hwnd, hdc, None, ctypes.byref(size), memdc,
                ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA)
            if not ok:
                self.log(f"[PHONE ERROR] UpdateLayeredWindow failed "
                         f"({ctypes.get_last_error()})")
            gdi.SelectObject(memdc, old)
            gdi.DeleteObject(hbmp)
            gdi.DeleteDC(memdc)
        finally:
            user32.ReleaseDC(None, hdc)

    def rect(self):
        r = _RECT()
        try:
            _user32().GetWindowRect(self.hwnd, ctypes.byref(r))
        except Exception:
            return None
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)

    def alive(self):
        return bool(self.hwnd and _user32().IsWindow(self.hwnd))

    def close(self):
        self._quit = True
        hwnd = self.hwnd
        if hwnd:
            try:
                _user32().PostMessageW(hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass
        t = self._thread
        if t is not None and t is not threading.current_thread():
            t.join(3)
        self.hwnd = None

    def _on_message(self, hwnd, msg, wparam, lparam):
        user32 = _user32()
        if msg == WM_NCHITTEST:
            # full click-through: every mouse event falls to scrcpy below
            return HTTRANSPARENT
        if msg == WM_CLOSE:
            self._quit = True
            user32.DestroyWindow(hwnd)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def _make_wndproc(owner):
    @_WNDPROC_T
    def _proc(hwnd, msg, wparam, lparam):
        try:
            return owner._on_message(hwnd, msg, wparam, lparam)
        except Exception:
            return 0
    return _proc


# ---------------------------------------------------------------------------
# ScrcpyWindowManager: launch / find / align the native scrcpy window
# ---------------------------------------------------------------------------
class ScrcpyWindowManager(object):
    """Launches scrcpy borderless and manages its native window."""

    @staticmethod
    def launch(exe, adb, cwd, x, y, w, h, log=None):
        log = log or (lambda *a, **k: None)
        cmd = [exe,
               "--adb", adb,
               "--window-title", MIRROR_WINDOW_TITLE,
               "--window-x", str(x), "--window-y", str(y),
               "--window-width", str(w), "--window-height", str(h),
               "--window-borderless",
               "--always-on-top",
               "--no-audio", "--max-size", "1280", "--no-power-on"]
        log_file = os.path.join(
            os.environ.get("TEMP") or os.environ.get("TMP") or ".", "gelotech_scrcpy.log")
        err = open(log_file, "wb")
        try:
            proc = subprocess.Popen(cmd, cwd=cwd,
                                    stdout=subprocess.DEVNULL, stderr=err)
        except Exception:
            err.close()
            raise
        log(f"[SCRCPY] log: {log_file}")
        return proc

    @staticmethod
    def find_hwnd(proc, timeout=15.0, poll=0.2):
        """Find the scrcpy window by its process PID (title fallback)."""
        user32 = _user32()
        pid = None
        if proc is not None and proc.poll() is None:
            try:
                pid = proc.pid
            except Exception:
                pid = None
        deadline = time.time() + timeout
        while time.time() < deadline:
            hwnd = _enum_scrcpy_window(pid, user32)
            if hwnd:
                return hwnd
            time.sleep(poll)
        return 0

    @staticmethod
    def align(hwnd, x, y, w, h):
        """Move/resize to the display opening; hide from taskbar; topmost."""
        user32 = _user32()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              (style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, int(x), int(y), int(w), int(h),
                            SWP_NOACTIVATE | SWP_SHOWWINDOW)

    @staticmethod
    def rect(hwnd):
        return _get_rect(hwnd)

    @staticmethod
    def alive(hwnd):
        if not hwnd or not _user32().IsWindow(hwnd):
            return False
        return bool(_user32().IsWindowVisible(hwnd))

    @staticmethod
    def raise_top(hwnd):
        # NOTE: SetWindowPos with hWndInsertAfter=<other topmost hwnd> silently
        # fails to reorder windows inside the topmost band on Win10/11, so we
        # raise the overlay to the top of the whole topmost band instead.
        _user32().SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                               SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def _enum_scrcpy_window(pid, user32):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if pid:
            wpid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid:
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                txt = buf.value
                if txt == MIRROR_WINDOW_TITLE or not txt.strip():
                    found.append(hwnd)
                    return False
        else:
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if buf.value == MIRROR_WINDOW_TITLE:
                found.append(hwnd)
                return False
        return True

    try:
        user32.EnumWindows(_cb, 0)
    except Exception:
        pass
    return found[0] if found else 0


# ---------------------------------------------------------------------------
# PhoneMirrorManager: orchestration + lightweight alignment monitor
# ---------------------------------------------------------------------------
class PhoneMirrorManager(object):
    """Owns overlay + scrcpy window for the whole mirror session.

    - 'starting' -> 'active' -> 'stopped'/off.
    - on_state(state) callback is invoked from a worker thread; callers must
      marshal it to their UI thread (e.g. Tk .after(0, ...)).
    - monitor loop (50ms) keeps scrcpy glued under the overlay's display
      opening, follows overlay drags, and cleans up when scrcpy exits.
    """

    def __init__(self, overlay_path, scale=PHONE_SCALE,
                 log=None, on_state=None):
        self.overlay_path = overlay_path
        self.scale = scale
        self.log = log or (lambda *a, **k: None)
        self.on_state = on_state
        self.overlay = None
        self.proc = None
        self.hwnd = 0
        self.scrcpy_exe = None
        self.scrcpy_adb = None
        self.scrcpy_dir = None
        self.state = "off"
        self._stop = threading.Event()
        self._monitor = None

    # ---------------- public API ----------------
    def start(self, scrcpy_exe, scrcpy_adb, scrcpy_dir, spawn_x, spawn_y):
        if self.state != "off":
            self.stop()
        self.scrcpy_exe = scrcpy_exe
        self.scrcpy_adb = scrcpy_adb
        self.scrcpy_dir = scrcpy_dir
        self._stop.clear()
        fw = int(PHONE_IMG_NATIVE[0] * self.scale + 0.5)
        fh = int(PHONE_IMG_NATIVE[1] * self.scale + 0.5)
        if spawn_x is None or spawn_x < 0 or spawn_y is None or spawn_y < 0:
            spawn_x, spawn_y = _screen_center()
        dx = int(DISPLAY_RECT[0] * self.scale)
        dy = int(DISPLAY_RECT[1] * self.scale)
        dw = int(DISPLAY_RECT[2] * self.scale)
        dh = int(DISPLAY_RECT[3] * self.scale)
        self._log("[SCRCPY] Starting screen mirror")
        self._log("[PHONE] Creating iPhone frame overlay")
        try:
            self.overlay = PhoneFrameOverlay(self.overlay_path, self.scale,
                                             self._log)
            self.overlay.show(spawn_x, spawn_y)
        except Exception as e:
            self._log(f"[PHONE ERROR] overlay creation failed: {e}")
            self.state = "off"
            return False
        self._log(f"[PHONE] Frame size: {fw}x{fh}")
        self._log(f"[PHONE] Display area: x={dx} y={dy} w={dw} h={dh} "
                  f"(scale {self.scale})")
        self._log(f"[PHONE] Positioning scrcpy: {spawn_x + dx},{spawn_y + dy} "
                  f"{dw}x{dh}")
        try:
            self.proc = ScrcpyWindowManager.launch(
                scrcpy_exe, scrcpy_adb, scrcpy_dir,
                spawn_x + dx, spawn_y + dy, dw, dh, self._log)
        except Exception as e:
            self._log(f"[SCRCPY ERROR] scrcpy launch failed: {e}")
            self.overlay.close()
            self.overlay = None
            self.state = "off"
            return False
        self._set_state("starting")
        self._monitor = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor.start()
        return True

    def stop(self):
        if self.state == "off" and not self.proc and not self.overlay:
            return
        self._stop.set()
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(2)
                except Exception:
                    proc.kill()
            except Exception:
                pass
        if self.overlay is not None:
            self.overlay.close()
        t = self._monitor
        if t is not None and t is not threading.current_thread():
            t.join(2)
        self._monitor = None
        self.proc = None
        self.overlay = None
        self.hwnd = 0
        self.state = "off"
        if self.on_state:
            try:
                self.on_state("stopped")
            except Exception:
                pass

    def toggle(self, scrcpy_exe, scrcpy_adb, scrcpy_dir, spawn_x, spawn_y):
        if self.state != "off":
            self.stop()
        else:
            self.start(scrcpy_exe, scrcpy_adb, scrcpy_dir, spawn_x, spawn_y)

    # ---------------- internals ----------------
    def _log(self, message):
        self.log(message)

    def _set_state(self, state):
        self.state = state
        if self.on_state:
            try:
                self.on_state(state)
            except Exception:
                pass

    def _expected_scrcpy_rect(self):
        rect = self.overlay.rect() if self.overlay else None
        if not rect:
            return None
        dx = int(DISPLAY_RECT[0] * self.scale)
        dy = int(DISPLAY_RECT[1] * self.scale)
        dw = int(DISPLAY_RECT[2] * self.scale)
        dh = int(DISPLAY_RECT[3] * self.scale)
        return (rect[0] + dx, rect[1] + dy, dw, dh)

    def _monitor_loop(self):
        timeout = 15.0
        t0 = time.time()
        while not self._stop.is_set():
            if not self.hwnd:
                self.hwnd = ScrcpyWindowManager.find_hwnd(
                    self.proc, timeout=timeout, poll=0.2)
                if self.hwnd:
                    self._log(f"[SCRCPY] scrcpy HWND found: {self.hwnd}")
                    self._log("[PHONE] Positioning frame")
                    self._align_all()
                    self._log("[PHONE] Mirror ready")
                    self._set_state("active")
                elif self._stop.is_set() or time.time() - t0 > timeout:
                    self._log("[SCRCPY ERROR] scrcpy window not found "
                              "- is the phone connected?")
                    self._cleanup()
                    return
                continue
            if not ScrcpyWindowManager.alive(self.hwnd):
                self._log("[SCRCPY] scrcpy window closed")
                self._cleanup()
                return
            if self.overlay is None or not self.overlay.alive():
                self._log("[PHONE] Overlay closed")
                self._cleanup()
                return
            expected = self._expected_scrcpy_rect()
            actual = ScrcpyWindowManager.rect(self.hwnd)
            if expected and actual and actual != expected:
                self._align_all()
            else:
                # keep both windows on top at all times: window activation
                # (e.g. scrcpy's own SetForegroundWindow on startup, or the
                # user clicking another app) silently reorders topmost
                # windows otherwise - and the overlay's transparent display
                # would then show whatever window got between them. Order
                # matters: scrcpy first, overlay on top of it.
                ScrcpyWindowManager.raise_top(self.hwnd)
                ScrcpyWindowManager.raise_top(self.overlay.hwnd)
            time.sleep(0.05)

    def _align_all(self):
        expected = self._expected_scrcpy_rect()
        if not expected:
            return
        ScrcpyWindowManager.align(self.hwnd, *expected)
        if self.overlay is not None and self.overlay.alive():
            # re-raise after every align: aligning scrcpy (HWND_TOPMOST)
            # would otherwise put it back on top of the overlay
            ScrcpyWindowManager.raise_top(self.hwnd)
            ScrcpyWindowManager.raise_top(self.overlay.hwnd)

    def _cleanup(self):
        self._stop.set()
        if self.overlay is not None:
            self.overlay.close()
        proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
        self.proc = None
        self.overlay = None
        self.hwnd = 0
        self.state = "off"
        self._log("[SCRCPY] Mirror stopped")
        if self.on_state:
            try:
                self.on_state("stopped")
            except Exception:
                pass