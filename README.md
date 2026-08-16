# GeloTechTool

**GeloTechTool v1.7.8** is a Windows Android maintenance and debloating utility built around **PySide6 / Qt6**. The Qt application is now the official desktop UI and starts from `tech_qt_app.py`.

## What it does

- **Dashboard** with device status, iPhone-style phone mockup, live logs, and App Cleaner.
- **App Cleaner** with UAD levels, bloatware scanning, Advanced Filter, batch actions, per-app actions, and a four-column table: `APP NAME | PACKAGE ID | UAD LEVEL | DESCRIPTION`.
- Long descriptions remain readable in-place with the table's **horizontal scrollbar**; there is no permanent description editor panel.
- **Automatic ADB detection** loads the app list on connect/reconnect without requiring a manual Refresh.
- **Automatic per-device icon sync** using `ApkIconHelper.apk`, package fingerprints, cached PNGs, and cache restore on reconnect.
- **Monitor Apps** with foreground-app monitoring, history, actions, and a dedicated guide.
- **Block Ads DNS** with curated provider cards, Apply/Disable feedback, and a DNS guide.
- **VirusTotal** scanning workflow with package/phone/running-app actions and a dedicated guide.
- **APK Backup/Restore**, including split-APK packages with manifests and `adb install-multiple` restoration.
- **ADB repair**, re-authorization, recovery/fastboot actions, Accounts, and Logout.
- **scrcpy screen mirroring** embedded into the single Dashboard phone mockup and cleaned up when the app exits.
- **18 bundled palettes** derived from CTkThemesPack and a **UI Font** selector with 22 Windows font families.
- `gelotech_icon.ico` is used by the Qt application, Login window, and packaged executable.

## Qt6 architecture

| Area | Current owner |
|---|---|
| Qt entry point | `tech_qt_app.py` |
| Main window / login | `tech_qt_mainwindow.py` |
| Qt styling / visual parity | `tech_qt_ui.py`, `tech_qt_visual_polish.py` |
| Themes / fonts | `tech_qt_themes.py` |
| Tabler icons | `tech_qt_icons.py` |
| App Cleaner | `tech_qt_cleaner.py` |
| Automatic device refresh | `tech_qt_auto_refresh.py` |
| Icon sync/cache | `tech_qt_iconsync.py`, `tech_qt_iconfix.py` |
| scrcpy / phone frame | `tech_qt_mirror.py`, `tech_qt_phone.py`, `tech_qt_bezel.py` |
| Monitor / DNS / VirusTotal UI | `tech_qt_mainwindow.py`, `tech_qt_help_pages.py`, feature installers |
| APK backup/restore | `tech_qt_backup.py` |
| ADB driver workflow | `tech_qt_drivers.py` |
| Shared authentication/data logic | `tech_reg.py`, `tech_common.py` |
| Auth service | `worker/` Cloudflare Worker |

Legacy Tk modules may remain for compatibility/history, but they are **not the official UI entry point**. Use `python tech_qt_app.py` for the current application.

## Dashboard and device automation

After login, GeloTech returns to Dashboard. The ADB monitor watches for authorized devices. A new or reconnected single device automatically triggers package loading and icon preparation. The same device is not repeatedly reloaded on every poll; a disconnect clears the state so a reconnect can trigger synchronization again.

The screen mirror uses the existing Dashboard phone mockup. scrcpy is the real native video surface; the phone bezel sits above it and the video is clipped to the display opening. See [`docs/SCRCPY_GUIDE.md`](docs/SCRCPY_GUIDE.md).

## App icons

The Qt icon pipeline mirrors the legacy ApkIconHelper workflow: verify/install the helper when needed, launch its automatic export, wait for completion, pull the export, accept both legacy flat and nested output layouts, read `packages.jsonl` when present, store package PNGs in the per-device cache, and refresh the Cleaner rows. See [`docs/ICON_SYNC.md`](docs/ICON_SYNC.md).

## Themes and appearance

The Qt UI keeps the 18 bundled **CTkThemesPack** palette choices and the **UI Font** selector. Themes affect Qt surfaces, logs, tables, dialogs and controls while preserving the phone display. User appearance choices persist across launches.

## Security and accounts

Authentication and account management remain server-side through the Cloudflare Worker. The desktop client contains no GitHub write token, SMTP credential, session secret, or admin phrase. See [`SECURITY.md`](SECURITY.md) and [`worker/README.md`](worker/README.md).

## Development

Before coding:

```bash
python scripts/agent_preflight.py
```

Minimum verification:

```bash
python -m compileall -q .
python -m pytest -q
python tech_qt_app.py
```

For real-device work, explicitly test with an authorized Android device. Do not report a mocked test as a real-device result.

## Release

The Qt6 production packaging definition is [`GeloTechTool_qt.spec`](GeloTechTool_qt.spec).

The release helper remains the authoritative release workflow:

```bash
python scripts/release.py
```

The repository uses a hard documentation-sync gate. Before release, update `README.md`, `PROCESS_GUIDE.md`, and `AGENTS.md` whenever current behavior changes. The gate also checks important markers including **CTkThemesPack**, **UI Font**, **horizontal scrollbar**, **app icon**, and **automatic** behavior.

The PyArmor Trial file-size limit is a release constraint; do not use an un-obfuscated build as a workaround for a production release.

## Documentation map

- [`README.md`](README.md) — current user-facing behavior and supported workflow.
- [`PROCESS_GUIDE.md`](PROCESS_GUIDE.md) — long-form architecture, execution flow, testing and release process.
- [`AGENTS.md`](AGENTS.md) — mandatory agent rules and release/documentation gates.
- [`QT6_MIGRATION_STATUS.md`](QT6_MIGRATION_STATUS.md) — completed Qt6 migration status and validation notes.
- [`QT6_MIGRATION_TASK.md`](QT6_MIGRATION_TASK.md) — historical migration specification and acceptance criteria.
- [`SECURITY.md`](SECURITY.md) — current security/authentication model.
- [`docs/DASHBOARD_LAYOUT.md`](docs/DASHBOARD_LAYOUT.md) — Dashboard/App Cleaner layout rules.
- [`docs/ICON_SYNC.md`](docs/ICON_SYNC.md) — automatic icon export/cache process.
- [`docs/SCRCPY_GUIDE.md`](docs/SCRCPY_GUIDE.md) — native scrcpy embedding rules.
- [`docs/README.md`](docs/README.md) — documentation index and authority map.
- [`worker/README.md`](worker/README.md) — Cloudflare auth Worker API and deployment.

## Download

Latest public release: [GeloTechTool v1.7.8](https://github.com/usermalik5/usermalik5/releases/latest)

Windows only. The private source repository is for development; the public download repository hosts user-facing releases.
