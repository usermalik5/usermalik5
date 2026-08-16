# GeloTechTool Process Guide — Qt6

This is the long-form process reference for the current application. The official desktop UI is **PySide6 / Qt6** and starts at `tech_qt_app.py`.

## 1. Documentation authority

- `README.md` — current user-facing behavior and supported workflows.
- `PROCESS_GUIDE.md` — architecture, execution flow, release and testing process.
- `AGENTS.md` — mandatory agent rules and release/documentation gates.
- `docs/README.md` — specialized subsystem guide index.
- `QT6_MIGRATION_STATUS.md` — completed migration record.
- `QT6_MIGRATION_TASK.md` — historical migration specification.

If documentation conflicts with source, stop and resolve the conflict before coding.

## 2. Qt architecture

```text
tech_qt_app.py
  ├─ QApplication / startup
  ├─ MainWindow + LoginDialog
  ├─ Qt compatibility installers
  ├─ visual/theme/icon installers
  ├─ device/app/icon automation
  └─ feature installers
        ├─ App Cleaner
        ├─ Monitor Apps
        ├─ DNS
        ├─ VirusTotal
        ├─ Backup/Restore
        ├─ ADB Drivers
        └─ scrcpy / phone frame
```

Shared authentication, data verification, database access and ADB helpers remain in the non-UI modules. The Cloudflare Worker remains the authority for account operations.

## 3. Startup flow

```text
python tech_qt_app.py
   ↓
QApplication
   ↓
load Qt themes/fonts/icons
   ↓
install feature/compatibility layers
   ↓
create MainWindow
   ↓
show LoginDialog
   ↓
auth proxy login / password request
   ↓
verified session database + permissions
   ↓
Dashboard selected
   ↓
ADB monitor starts
```

The legacy `techtool.py` entry point is not the current Qt launch path. Use `python tech_qt_app.py` or the Qt PyInstaller spec.

## 4. Automatic device flow

The existing ADB monitor detects connected authorized devices. A device transition triggers the full UI flow rather than only reporting detection:

```text
ADB device detected
  ↓
device status updated
  ↓
app/package list refresh
  ↓
icon fingerprint/cache check
  ↓
icon restore or ApkIconHelper export
  ↓
App Cleaner refresh
```

The same device is not repeatedly reloaded on every poll. Disconnect/reconnect resets the transition state.

## 5. App Cleaner

The current table is:

```text
APP NAME | PACKAGE ID | UAD LEVEL | DESCRIPTION
```

Features include Search, Select All, filtering, Scan Bloatware, Advanced Filter, Restore/Backup, Load Apps, right-click actions and batch actions.

Full descriptions remain in the table row and use a **horizontal scrollbar**. Do not introduce a permanent description panel below the table.

## 6. Icon synchronization

Ownership: `tech_qt_iconsync.py`.

- Verify/install `ApkIconHelper.apk` when needed.
- Launch helper automatic export.
- Wait for completion.
- Verify `adb pull` succeeded.
- Accept legacy flat and nested output layouts.
- Read `packages.jsonl` when available.
- Recover package PNGs when helper output differs.
- Store shared and per-device cache data.
- Re-render App Cleaner after sync.

See [`docs/ICON_SYNC.md`](docs/ICON_SYNC.md).

## 7. scrcpy flow

Ownership: `tech_qt_mirror.py`, `tech_qt_phone.py`, `tech_qt_bezel.py`.

The mirror uses **one existing Dashboard phone mockup**. scrcpy remains the native video surface and is embedded into the phone display area. A second floating phone frame must never be created.

A single authorized device can auto-start the mirror after the configured delay. The mirror stays open until stopped or until application shutdown. Shutdown must terminate the scrcpy process cleanly.

See [`docs/SCRCPY_GUIDE.md`](docs/SCRCPY_GUIDE.md).

## 8. Feature workspaces

- **Monitor Apps:** App Watch status, monitoring controls, event/history view, row actions and guide.
- **Block Ads DNS:** provider cards, meaningful provider descriptions, Apply/Disable status feedback and guide.
- **VirusTotal:** package/phone/running scans, pull/upload action, progress/results and guide.
- **Backup/Restore:** package-directory manifests; split APKs restore with `adb install-multiple -r`.
- **ADB Drivers:** repair/restart and device re-detection.

## 9. Appearance

Qt appearance is owned by `tech_qt_themes.py` and visual installers.

- 18 bundled **CTkThemesPack** palettes.
- **UI Font** selector with 22 Windows font families.
- Theme and font preferences persist.
- Logs, tables, inputs, dialogs and controls are themed.
- The phone display is treated as a physical/native surface and is not recolored by the generic theme pass.
- Current reference dark surfaces use the restrained gray styling derived from the reference UI rather than an all-black application shell.

## 10. Application icon and icons

`gelotech_icon.ico` is applied to the application and Login window and is included by `GeloTechTool_qt.spec`. UI controls use the bundled Tabler SVG icon set via `tech_qt_icons.py`.

## 11. Security/data flow

Login and account administration use the Cloudflare Worker. The desktop client does not contain the Worker write token, SMTP password, session secret or admin phrase.

Data updates use `version.json` plus `version.json.sig` and SHA-256 verification. Session database data is downloaded and verified at login.

See [`SECURITY.md`](SECURITY.md) and [`worker/README.md`](worker/README.md).

## 12. Verification

Minimum source checks:

```bash
python scripts/agent_preflight.py
python -m compileall -q .
python -m pytest -q
python tech_qt_app.py
```

For a device feature, use a real Android device and record the result separately from mocked/no-device validation.

## 13. Release process

The release workflow must be used rather than ad-hoc release builds. Before release:

1. Review current source changes.
2. Update `README.md`, `PROCESS_GUIDE.md` and `AGENTS.md` for user-visible or process changes.
3. Update specialized docs when a subsystem changes.
4. Run the documentation-sync gate through the release process.
5. Run compile/tests and the supported Qt packaging path when a Qt release is being built.
6. Respect the PyArmor Trial source-size limit; split oversized modules instead of using a non-obfuscated production workaround.

## 14. Documentation synchronization rule

Every major Qt change must update the smallest complete documentation set needed to keep all documents consistent:

```text
source behavior
   ↓
README.md
   ↓
PROCESS_GUIDE.md / AGENTS.md
   ↓
specialized docs under docs/
   ↓
QT6_MIGRATION_STATUS.md when migration status changes
```

A release is not ready while the documentation describes the old Tk UI, the old icon owner, a dead migration branch, or obsolete launch commands.
