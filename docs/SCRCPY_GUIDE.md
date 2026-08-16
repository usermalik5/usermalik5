# GeloTech scrcpy / Phone Mirror Guide — Qt6

Read this file when changing the phone-mirror subsystem. The current desktop UI is PySide6 / Qt6 and the mirror is owned by the Qt mirror modules.

## Scope and ownership

- `tech_qt_mirror.py` — scrcpy process/window ownership and positioning.
- `tech_qt_phone.py` — existing Dashboard phone-frame integration.
- `tech_qt_bezel.py` — bezel/frame aliasing and overlay support.
- `tech_qt_app.py` — installs the mirror subsystem during Qt startup.
- `tech_qt_mainwindow.py` — Dashboard actions and close lifecycle.

Do not use a global runtime hook or create a second phone mockup to solve a mirror issue.

## Current mirror model

The **existing single Dashboard iPhone mockup** is the host. scrcpy remains the real native video renderer. The Qt mirror positions the native scrcpy child window inside the phone display opening and keeps the bezel above it.

```text
Dashboard phone mockup
        │
        ├─ native scrcpy video surface
        │      ↓
        │   display opening
        │
        └─ iPhone bezel/frame above the video
```

There is **no second floating phone frame** and no screenshot-based video compositing.

## Start flow

- The user can start/stop the mirror from the Dashboard.
- A single authorized Android device may trigger the automatic mirror flow after the configured connection delay.
- The mirror remains open until the user stops it, the device is lost, or the application closes.
- The application must clean up the scrcpy process on shutdown.

## Positioning rules

- Position the scrcpy child using **parent-relative coordinates** derived from the phone frame's display opening.
- Keep the stream clipped to the screen opening and maintain the rounded display boundary.
- Reapply the opening rectangle when the Dashboard is resized or moved.
- Do not use fragile global-screen coordinates as the primary positioning model.
- Do not create a new `QWidget` containing another full phone image just to host scrcpy.

## Common failure modes

### Video is invisible

Check that scrcpy is parented to the **actual phone image/frame widget** and is not placed behind a sibling surface. The phone host must be the existing Dashboard mockup.

### Two phone mockups appear

A mirror adapter has created a second phone frame. Remove that extra frame and point the mirror at the existing Dashboard phone widget.

### Video floats outside the mockup

The mirror is probably using global coordinates or the wrong host. Return to parent-relative display geometry and the existing phone frame.

### Bezel disappears

The native scrcpy surface has been raised above the bezel. Keep the transparent frame above the video after each reposition.

## Validation

Source checks:

```powershell
python -m compileall -q .
python -m pytest -q
python tech_qt_app.py
```

Real-device checks:

1. Connect an authorized Android device.
2. Start Screen Mirror.
3. Confirm the phone video is visible inside the **single** iPhone mockup.
4. Resize/move the window and confirm the video stays glued to the display opening.
5. Stop the mirror and confirm the process terminates.
6. Close GeloTech and confirm no scrcpy process remains.

Do not claim an embedding fix from a source-only or mocked test.
