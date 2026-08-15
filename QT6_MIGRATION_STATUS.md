# Qt6 migration status

This branch is the active PySide6 migration. `main` remains untouched.

## Completed in the current slice

- Added `requirements-qt.txt` with PySide6 support.
<<<<<<< HEAD
- Added `tech_qt_app.py` as the Qt entry point. Every feature installer is explicitly called from this entry point before `MainWindow` is created.
=======
- Added `tech_qt_app.py` as the Qt entry point.
>>>>>>> fd80b6ee672e54c068efff818356e64791be562f
- Added `tech_qt_bootstrap.py` so the shared core can be imported even on a machine without CustomTkinter installed.
- Added `tech_qt_icons.py` with native Qt SVG loading from `assets/icons/tabler/`.
- Added `tech_qt_themes.py` with the 18 bundled palettes and 22 UI-font choices converted to Qt QSS.
- Added `tech_qt_mainwindow.py` with the Qt shell, login/registration surface, Dashboard, App Cleaner, Monitor Apps, DNS, VirusTotal surface, Task Manager, Accounts, ADB controls, screen-mirror fallback, automatic new-device detection, per-device icon-cache reuse, and automatic helper preparation when the cache is missing.
- Added `tech_qt_cleaner.py` and wired it into the Qt entry point. The cleaner parity slice performs a complete-device UAD-level scan, checks matching rows, provides Advanced Filter (text, UAD level, user/system scope, category, source), and restores package-list context/batch actions (disable, uninstall, clear data, APK backup, exclusions, APK info, and typed-YES confirmations).
<<<<<<< HEAD
- Added `tech_qt_backup.py` and wired it into the Qt entry point. The consolidated APK Backup / Restore dialog uses the existing `AppData\\GeloTechTool\\apk_backups` storage location and supports checked-app backups plus APK restore.
- Added `tech_qt_virustotal.py` and explicitly wired `install_virustotal(MainWindow)`. It provides package/hash lookup, installed-app scans, running-app filtering, pull+hash, upload when missing, and analysis polling.
- Added `tech_qt_drivers.py` and wired `install_driver_workflow(MainWindow)` with the existing tested ADB kill-server/start-server/recheck behavior.
- Added `tech_qt_mirror.py` and wired `install_scrcpy(MainWindow)`. It attempts Qt foreign-window embedding through `QWindow.fromWinId`/`createWindowContainer`, with a safe external scrcpy fallback when embedding is unavailable.
- Added `tech_qt_iconsync.py` and wired `install_icon_sync(MainWindow)`. It verifies the per-device persistent cache using a SHA-256 serial key, verifies whether `ApkIconHelper` is already installed before installing, restores matching icon caches, and runs the complete helper export/import flow when the cache is absent or stale.
- The Qt cleaner uses the existing four-column table and a real horizontal scrollbar for long descriptions.
- Updated `GeloTechTool_qt.spec` with all Qt migration modules and bundled `ApkIconHelper.apk`/assets.
- Added/updated `tests/test_qt_migration.py` to import-check every Qt installer module without creating a window.

## Still to complete before calling the migration feature-complete

- Run final Ruff cleanup across all new/modified Qt modules, including the existing semicolon-heavy `tech_qt_mainwindow.py`, without hiding real lint errors.
- Resolve or narrowly annotate the remaining BasedPyright false positives from PySide6 enum stubs.
- Run the complete Windows validation again after the latest backup/driver/mirror/icon-sync changes.
- Verify the Qt scrcpy embedding visually on Windows; the external-window fallback must remain reliable if foreign-window parenting is rejected by the OS or scrcpy build.
- Verify the complete ApkIconHelper export/import pipeline against a genuinely uncached device and a reconnect with a matching cache.
=======
- The Qt cleaner uses the existing four-column table and a real horizontal scrollbar for long descriptions.
- Added `tech_qt_virustotal.py` and wired it into the Qt entry point. The Qt VirusTotal surface now supports installed-package hash lookup, individual package lookup, installed-app scanning, running-app filtering, pull-and-upload for packages missing from VirusTotal, analysis polling, progress, and stop behavior.
- Added `GeloTechTool_qt.spec` as a migration/debug packaging spec. It does not replace the existing production release spec.
- Added `tests/test_qt_migration.py` for Qt imports and bundled-resource checks.

## Still to port before calling the migration feature-complete

- Verify the Qt APK Backup/Restore dialog and its tested backup storage behavior against the legacy implementation.
- Port the tested ADB driver repair/download workflow.
- Replace the scrcpy fallback window with Qt foreign-window embedding where practical, while retaining the safe external-window fallback.
- Port device icon export/import itself; the current slice restores existing per-device cache data and installs `ApkIconHelper.apk` for a device with no cache, but does not yet drive the helper's complete export pipeline.
- Clean the remaining Ruff/BasedPyright diagnostics in the Qt modules. Do not silence them merely to make the checks green; PySide6 stub-only enum diagnostics should be handled with narrow, documented type-checker suppressions where necessary, while E702/style findings should be fixed in source.
>>>>>>> fd80b6ee672e54c068efff818356e64791be562f
- Add Qt release-module verification to `scripts/release.py` only after parity is reached. Do not change the production release path yet.

## Validation rule

Do not claim feature parity until `python -m compileall -q .`, `python -m pytest -q`, Ruff, BasedPyright, and a real Windows source run of `python tech_qt_app.py` have all been checked. The migration task also requires testing from a clean working directory with no `themes/` directory in the current working directory.
