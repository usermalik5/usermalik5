# Qt6 migration status

This branch is the active PySide6 migration. `main` remains untouched.

## Functional migration status

The functional Qt6 migration is complete and has already been merged to `main` separately. This branch contains the follow-up visual-parity work only.

Completed functional areas include login, Dashboard/App Cleaner, bloatware scanning, Advanced Filter, batch actions, APK backup/restore, VirusTotal, ADB repair, scrcpy embedding with fallback, automatic device icon synchronization/cache reuse, themes/fonts, Accounts, DNS, and Task Manager.

## Visual parity pass

- Added `tech_qt_ui.py` as the visual composition layer so layout changes do not rewrite feature implementations.
- Dashboard is now the primary App Cleaner workspace, matching the legacy application's composition: fixed sidebar, large iPhone mockup, live logs, guidance, status row, package table, and bottom action toolbar.
- Sidebar follows the compact legacy hierarchy and keeps the USB debugging / How to use guidance below Logout.
- App Cleaner keeps the four-column table and horizontal scrollbar for long descriptions; no always-visible description editor is used.
- QSS now gives the phone area, logs, table, controls, side navigation, headings, and guide panels consistent legacy-style proportions and typography while retaining the 18 CTkThemesPack palettes and UI-font selector.
- `GeloTechTool_qt.spec` now bundles `tech_qt_ui.py`.
- Qt migration tests now import-check the visual parity installer without creating a window.

## Remaining visual verification

- Run `python tech_qt_app.py` from a clean working directory and visually compare the Qt Dashboard/App Cleaner against the legacy Tk screenshot at approximately the same window size.
- Run `python -m pytest -q` and `python -m compileall -q .` after the visual changes.
- Confirm all 18 themes and the UI-font selector preserve the same layout without clipping.
- Confirm the real-device mirror/icon/backup behaviors remain unchanged after the layout-only pass.
- Do not modify `scripts/release.py` during this parity pass.

## Validation rule

Do not claim visual parity until the source boots from a clean working directory, `python -m pytest -q` and `python -m compileall -q .` pass, and the Qt UI has been visually compared against the legacy layout. The existing production release path remains unchanged until the parity pass is accepted.
