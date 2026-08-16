# Qt6 Migration Status

## Current state

The Qt6 / PySide6 migration is **complete and merged into `main`**. `main` is the official application line. The old `qt6-migration` branch is historical work, not the current development target.

## Completed migration

- Qt entry point: `tech_qt_app.py`.
- Login and password-request flow.
- Dashboard and device-status presentation.
- App Cleaner, UAD levels, bloatware scan, Advanced Filter, batch actions and context actions.
- Four-column App Cleaner table with a horizontal scrollbar for full descriptions.
- Automatic ADB device detection and automatic package-list refresh on connect/reconnect.
- Automatic per-device icon export/cache synchronization and cache restoration.
- Monitor Apps, DNS and VirusTotal workspaces with user-facing guides.
- APK Backup/Restore, including split-APK manifests and `install-multiple` restore.
- ADB repair/re-authorization and recovery/fastboot actions.
- Native scrcpy embedding inside the existing phone mockup with safe process cleanup.
- Accounts, permissions and logout.
- Qt themes, CTkThemesPack palette data, UI-font selection and persisted appearance.
- Application/login `.ico` integration and Tabler icons.

## Current architecture

The Qt shell is composed through focused modules such as `tech_qt_mainwindow.py`, `tech_qt_ui.py`, `tech_qt_visual_polish.py`, `tech_qt_themes.py`, `tech_qt_cleaner.py`, `tech_qt_iconsync.py`, `tech_qt_mirror.py`, `tech_qt_backup.py`, `tech_qt_drivers.py`, `tech_qt_help_pages.py` and the other `tech_qt_*` feature installers. Shared authentication, database, update verification and ADB helpers remain outside the UI layer.

## Validation

The migration task history recorded successful source compile, automated tests and clean-CWD Qt startup. Real-device testing is tracked separately: backup/restore, ADB repair and icon synchronization were exercised on a Windows Android device; scrcpy embedding still requires a machine with scrcpy available.

Do not claim a real-device behavior is verified unless it was tested with a real connected device.

## Canonical documentation

Start with [`README.md`](README.md), then [`PROCESS_GUIDE.md`](PROCESS_GUIDE.md) and [`AGENTS.md`](AGENTS.md). Specialized subsystem guides are indexed in [`docs/README.md`](docs/README.md).
