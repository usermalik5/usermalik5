# Qt6 migration status

This branch is the active PySide6 migration. `main` remains untouched.

## Completed in the current slice

- Added `requirements-qt.txt` with PySide6 support.
- Added `tech_qt_app.py` as the Qt entry point.
- Added `tech_qt_bootstrap.py` so the shared core can be imported even on a machine without CustomTkinter installed.
- Added `tech_qt_icons.py` with native Qt SVG loading from `assets/icons/tabler/`.
- Added `tech_qt_themes.py` with the 18 bundled palettes and 22 UI-font choices converted to Qt QSS.
- Added `tech_qt_mainwindow.py` with the Qt shell, login/registration surface, Dashboard, App Cleaner, Monitor Apps, DNS, VirusTotal surface, Task Manager, Accounts, ADB controls, screen-mirror fallback, automatic new-device detection, per-device icon-cache reuse, and automatic helper preparation when the cache is missing.
- Added `tech_qt_cleaner.py` and wired it into the Qt entry point. The cleaner parity slice now performs a complete-device UAD-level scan, checks matching rows, provides an expanded Advanced Filter (text, UAD level, user/system scope, category, source), and restores the package-list context/batch actions (disable, uninstall, clear data, APK backup, exclusions, APK info, and typed-YES confirmations).
- The Qt cleaner uses the existing four-column table and a real horizontal scrollbar for long descriptions.
- Added `GeloTechTool_qt.spec` as a migration/debug packaging spec. It does not replace the existing production release spec.
- Added `tests/test_qt_migration.py` for Qt imports and bundled-resource checks.

## Still to port before calling the migration feature-complete

- Port the full APK Backup/Restore dialog and verify its tested backup storage behavior against the legacy implementation.
- Port the existing VirusTotal hash lookup, upload, analysis polling, installed-app scan, and running-app scan workflows.
- Port the tested ADB driver repair/download workflow.
- Replace the scrcpy fallback window with Qt foreign-window embedding where practical, while retaining the safe external-window fallback.
- Port device icon export/import itself; the current slice restores existing per-device cache data and installs `ApkIconHelper.apk` for a device with no cache, but does not yet drive the helper's complete export pipeline.
- Add Qt release-module verification to `scripts/release.py` only after parity is reached. Do not change the production release path yet.

## Validation rule

Do not claim feature parity until `python -m compileall -q .`, `python -m pytest -q`, Ruff, BasedPyright, and a real Windows source run of `python tech_qt_app.py` have all been checked. The migration task also requires testing from a clean working directory with no `themes/` directory in the current working directory.
