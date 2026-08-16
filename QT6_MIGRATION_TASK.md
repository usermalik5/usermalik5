# Qt6 Migration Task — Historical Specification

> **Status: COMPLETED.** This file is preserved as the historical migration specification. It is no longer an instruction to work on a `qt6-migration` branch. The Qt6 implementation is now on `main`.

## Objective that was completed

Port the Windows GeloTech desktop interface from CustomTkinter/Tkinter to **PySide6 / Qt6** while preserving the existing Android/ADB functionality and improving consistency, icons, themes, device status and feature usability.

## Acceptance criteria mapped to the current code

| Requirement | Current implementation |
|---|---|
| Qt6 entry point | `tech_qt_app.py` |
| Qt main shell / login | `tech_qt_mainwindow.py` |
| Tabler Qt icons | `tech_qt_icons.py` + `assets/icons/tabler/` |
| Themes and fonts | `tech_qt_themes.py` |
| Dashboard/App Cleaner | Qt main/UI/cleaner modules |
| Horizontal full-description scrollbar | App Cleaner Qt table |
| Monitor Apps | Qt Monitor workspace + guide |
| DNS | Qt DNS provider-card workspace + guide |
| VirusTotal | Qt VirusTotal workspace + guide |
| APK Backup/Restore | `tech_qt_backup.py`, including split APKs |
| ADB repair | `tech_qt_drivers.py` |
| Automatic device refresh | `tech_qt_auto_refresh.py` |
| Automatic icon sync/cache | `tech_qt_iconsync.py` |
| scrcpy embedding | `tech_qt_mirror.py`, `tech_qt_phone.py`, `tech_qt_bezel.py` |
| Login/application icon | `gelotech_icon.ico` + Qt styling/spec |
| Qt packaging | `GeloTechTool_qt.spec` |

## Important lessons retained

- Every new Qt installer must be explicitly wired from `tech_qt_app.py`.
- Foreign-window scrcpy geometry must use the existing phone mockup; do not create a second floating phone frame.
- The App Cleaner must keep the description in the table and use a horizontal scrollbar instead of a permanent description editor panel.
- A device detection event must continue through package refresh and icon preparation; detection alone is not enough.
- Icon sync completion must refresh the visible App Cleaner rows.
- Documentation is a release blocker, not an afterthought.

## Verification commands

```powershell
python -m compileall -q .
python -m pytest -q
python tech_qt_app.py
```

Use a real Android device for device-dependent verification. Keep real-device results separate from mocked or no-device results.

## Historical branch note

The original task was developed on `qt6-migration` and later merged. Agents working today should use `main` unless a new branch is explicitly requested.
