# GeloTech scrcpy / phone-mirror guide (Qt)

Read this file only when changing the phone-mirror subsystem.

## Scope

The Dashboard owns the native scrcpy mirror host (`tech_qt_mirror.py`,
installed by `install_scrcpy` in `tech_qt_app.py`). Mirror behavior stays
isolated to the mirror module: do not use `sitecustomize.py`, import-time
patches, or navigation hooks to fix ordinary Dashboard/page behavior.

## How the Qt mirror works

1. **Launch** — `start_mirror` is a toggle (Screen Mirror <-> Stop Mirror).
   scrcpy is started borderless with the device serial and a known window
   title (`GeloTech Mirror - <serial>`); `--always-on-top` is NOT used.
2. **Embed** — the scrcpy window is found by title and converted into a real
   native *child window* of the phone bezel widget (`phone_image`) with
   `SetParent` + `WS_CHILD` (same approach as the legacy
   `tech_phone_mirror_embedded.py`). The child is positioned at the frame's
   display opening with **parent-relative coordinates only**
   (`_display_geometry`, derived from `DISPLAY_RECT`/`PHONE_NATIVE`) — no
   global screen math, so the stream cannot drift outside the mockup.
3. **Bezel over video** — the child window renders above the bezel's painted
   content, so the video appears through the PNG's transparent screen opening
   while the bezel edges stay visible. The square child surface is clipped to
   the rounded opening with `SetWindowRgn`
   (`DISPLAY_CORNER_RADIUS = 30`, scaled to the widget).
4. **Monitor loop** — a 50 ms `QTimer` re-applies the parent-relative opening
   rect and the rounded clip, keeping the stream glued during layout changes.
5. **Stop** — `_qt_stop_scrcpy` stops the timer and terminates the process
   (terminate, then kill after a 2 s grace) and resets the button state.
   `closeEvent` in `tech_qt_mainwindow.py` also stops the mirror on app exit.

Because the child window is owned by the app, it minimizes/hides/closes with
the application and can never float as an independent desktop window.

## Development checks

1. Test `python tech_qt_app.py` with a real supported Android device when
   possible.
2. Verify the mirror is embedded in the Dashboard phone screen (video inside
   the mockup opening, bezel visible around it).
3. Verify the toggle: Screen Mirror starts, Stop Mirror stops, process is
   gone from Task Manager.
4. Verify no scrcpy process survives closing the whole app.
5. Test the packaged EXE separately when the build/spec changes.

## Failure reporting

Record whether a failure was observed with a real device, with scrcpy only,
or in a mocked/no-device environment. Do not claim a real-device fix from a
mocked test.

## Known traps

- **Embed into `phone_image`, not `phone_host`.** Forcing `WA_NativeWindow`
  on one sibling makes Qt promote overlapping siblings to native windows
  too; `phone_host` stacks *below* the bezel, so a child embedded there is
  hidden behind the painted PNG. The video child must live inside the bezel
  widget itself.
- **Parent-relative coordinates only.** `mapToGlobal` + `SetWindowPos`
  breaks when the window is hidden or not yet laid out (e.g. auto-mirror
  firing before login). The embedded child model is immune.
- **DPI.** `_display_geometry` multiplies by `devicePixelRatioF` so the
  physical child rect matches the parent's physical client area on scaled
  displays.

## Architecture rule

New mirror behavior belongs in the mirror subsystem. Do not add another
global runtime hook just because the packaged build behaves differently;
first trace the source execution path and the PyInstaller resource/spec path
separately.