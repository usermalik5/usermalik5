# Scrcpy Mirror Notes (Qt6 Dashboard)

Reference for the live phone mirror embedded in the Qt Dashboard. Read this
before touching `tech_qt_mirror.py`, `tech_qt_phone.py`, or the mirror
installers. It records hard-won lessons from the 2026 keyboard-input rework;
do not "clean up" the native-window model without re-reading this file.

## Architecture (current, since v2.0)

The mirror is a **native top-level scrcpy window** over the Dashboard phone
mockup, plus a **transparent click-through bezel overlay**. This is the model
the legacy Tk dashboard (`tech_phone_mirror_host.py`) always used.

- `tech_qt_mirror.install_scrcpy(MainWindow)` monkey-patches the MainWindow:
  `_qt_start_scrcpy` / `_qt_stop_scrcpy` / `_qt_embed_scrcpy`
  (`_qt_reposition_scrcpy`) / `_qt_ensure_mirror_focus`, and wires the Screen
  Mirror button.
- Launch: `scrcpy.exe -s <serial> --window-x/y/width/height --window-borderless
  --no-audio --max-size=1280 --no-power-on --keyboard=sdk`. Size/position come
  from `_global_opening(host)` (the mockup display opening in GLOBAL screen
  pixels, DPI-scaled via `devicePixelRatioF`).
- **Ownership, not parenting**: `_own_window()` = `SetWindowLongPtrW(GWLP_HWNDPARENT)`
  on the scrcpy window, pointing at the Qt main window's `winId()`. scrcpy
  remains a native top-level window (never `SetParent`!), which is what keeps
  SDL keyboard input working. Ownership gives: z-order above the owner,
  minimize/hide inheritance quirks (handled by the monitor, below).
- `_MirrorOverlay`: an owned, frameless, translucent QWidget ABOVE the video
  that paints ONLY the bezel margins around the video opening (a "hole"
  rectangle) via `host.grab()`. It is fully click-through
  (`WA_TransparentForMouseEvents` + `WindowTransparentForInput`), never takes
  focus, and is **not** a `Qt.Tool` window (see lessons).
- `_qt_reposition_scrcpy` runs on a 50 ms `QTimer` and is **change-driven**:
  it repositions/restores only when the window rect differs, re-applies the
  rounded region (`SetWindowRgn`) only on size change, and re-raises the
  overlay above scrcpy only when it isn't already directly above it
  (`GetWindow(overlay, GW_HWNDPREV) != scrcpy_hwnd`).

## Glue rules (the video may ONLY float over the Dashboard)

The monitor hides the scrcpy window and the overlay whenever any of:

1. the Qt main window is minimized or hidden,
2. the user navigated to a non-Dashboard page (`QStackedWidget.currentChanged`
   sets `MainWindow._qt_dashboard_active = index == 0`, wired in
   `tech_qt_final_fixes._build_shell`; the handler is installed by
   `install_final_qt_fixes` — **remember the install line**),
3. scrcpy is still settling (first 1.5 s after embed).

and restores them when conditions are right again. This is enforced in the
monitor loop, so no event plumbing is required.

## Lessons learned (2026 keyboard-input saga) — DO NOT REGRESS

1. **`SetParent` breaks keyboard input.** SetParent-embedding the scrcpy window
   into the Qt app makes it a child window; clicks activate the host app, SDL
   never receives focus, and typed keys do not reach the phone. The legacy
   `_set_owner` docstring says exactly this. Proven by A/B test on device:
   native delivered every digit, embedded delivered none.
2. **Focus-healing doesn't reliably fix embedding.** `_ensure_mirror_focus`
   (SetForegroundWindow + SetFocus when the cursor is over the mirror, our app
   is foreground, and the scrcpy thread lost focus) was added and pushed
   (commit 72cf7d1) but never fired in practice. The native model makes it a
   harmless belt-and-suspenders guard only.
3. **`Qt.Tool` windows auto-hide when the app is deactivated.** The bezel
   overlay vanished the moment the user clicked the scrcpy window (activating
   it deactivates the Qt app). Use `Qt.FramelessWindowHint | Qt.Window`
   (owned windows are taskbar-invisible anyway).
4. **The overlay must paint a HOLE, not the full mockup.** Painting the whole
   grabbed widget covers the video. Paint only the four margin strips around
   the opening rect (hole = `gx - host.global.x`, etc.).
5. **`host.grab()` renders the mockup's true appearance** (works for
   stylesheet-drawn widgets where `pixmap()` returns null).
6. **Never fight SDL during startup.** The old monitor called
   `SetWindowPos(SWP_SHOWWINDOW)` + `SetWindowRgn` + `HWND_TOP` every 50 ms
   unconditionally, glitching the fresh window; users needed stop/start cycles.
   Keep the monitor change-driven and let SDL settle ~1.5 s.
7. **`GetWindow(hwnd, GW_HWNDPREV)` returns the window ABOVE** (verified
   empirically against EnumWindows order). Use insert-after (`hwndInsertAfter =
   scrcpy_hwnd`) instead of `HWND_TOP` so the bezel never floats above other
   applications.
8. **The debug log** is `%TEMP%\gelotech_qt_mirror_debug.log`
   (`_debug()` writes there); it logs the embed rect, host size, overlay hwnd,
   and reposition state every 0.5 s. Check it FIRST when the mirror misbehaves.
9. **Live window probing**: enumerate the app/scrcpy windows
   (`EnumWindows`, `GetWindowLongPtr`, `GetWindowRect`) to check ownership,
   visibility, rect, and z-order. A hidden (`IsWindowVisible == 0`) overlay or
   wrong owner tells you which glue rule failed.
10. **ADB in automation**: never run adb inline in a shell tool that waits on
    the console pipe (the daemon inherits it and the call gets killed). Always
    drive adb via `subprocess` with DEVNULL/file-redirected output. adb lives
    at `C:\Windows\adb.exe`; the scrcpy bundle has NO adb.exe.

## Device verification (keyboard reachability)

Do not trust dialer keypad labels (they contain every digit). Open a real
EditText via
`adb shell am start -a android.intent.action.SENDTO -d "sms:<number>"`
(Google Messages To field) and compare `uiautomator dump` text before/after
typing.

## Files

- `tech_qt_mirror.py` — Qt mirror manager + overlay + monitor (main file).
- `tech_phone_mirror.py` / `tech_phone_mirror_host.py` / `tech_phone_mirror_embedded.py`
  / `tech_phone_mirror/__init__.py` — legacy Tk mirror family (reference for
  ownership + overlay behavior).
- `tech_qt_final_fixes.py` — `_build_shell` wires the stack page-change glue;
  `install_final_qt_fixes` MUST install `_qt_dashboard_page_changed`.
- `tech_qt_phone.py` — mockup host widget (`phoneMockup`), display geometry.
- `docs/SCRCPY_GUIDE.md` — mirror model constraints (single mockup, no global
  runtime hook, transparent frame above the video; the native+overlay model
  satisfies them).