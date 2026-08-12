# GeloTechTool — Process Tree Visual Guide

Internal reference only. Shows how the app works step by step and how the
code is organised. Updated on major code changes.

---

## 1. App Architecture (Who Owns What)

```
GeloTechTool (techtool.py)
  └─ GeloTechTool(ctk.CTk, UiMixin, SettingsMixin, SecScanMixin,
                  SecOpsMixin, SecOps3Mixin, SecOps2Mixin, SecOps4Mixin,
                  DashboardMixin, VtOpsMixin, MiscMixin)
  └─ apply_hardening(GeloTechTool)  ← tech_hardening.py (import-time patches)
```

| File | Class / Role | Owns |
|---|---|---|
| `techtool.py` | `GeloTechTool` | entry point, window, sidebar, page stack/navigation, log console, hint banner, ADB device monitor, scrcpy extraction, debloat safety checks, dark/light theme toggle (sidebar) + `_theme_walk` color apply |
| `tech_dash.py` | `DashboardMixin` | Dashboard page: iPhone mockup, device quick info, live ADB stats, quick actions, live refresh, phone log-console placement, screen-mirror entry |
| `tech_common.py` | helpers | `EMBEDDED_UPDATE_URL`/`TOKEN`, `UPDATE_SIGN_PUBLIC_KEY`, paths (bundle/app/settings/cache dirs), `load_package_database`, app-list cache helpers (`load_apps_cache`/`save_apps_cache`/`fmt_cache_time`), `Tooltip` (routes to hint banner), adb subprocess wrapper |
| `tech_settings.py` | `SettingsMixin(AdminPanelMixin)` | settings JSON load/save (runtime state only), email-based login UI (two-step: email → password), PBKDF2 password verify, permissions, `_check_updates`, first-run migration + seeding |
| `tech_reg.py` | helpers | self-service account flow + server fetching: `_fetch_verified_sources` (signed manifest + live accounts + DB sha256), `_request_password`, `hash_password`/`verify_password`, `_purge_session_database` |
| `tech_admin.py` | `AdminPanelMixin` | Admin Panel dialog: server-verified account list with BLOCK/UNBLOCK per account |
| `tech_ui.py` | `UiMixin` | tab/page UIs: cleaner header/toolbar/legend, monitor, DNS, VirusTotal |
| `tech_secscan.py` | `SecScanMixin` | background threat scans |
| `tech_secops.py` | `SecOpsMixin` | cleaner list and rendering |
| `tech_secops3.py` | `SecOps3Mixin` | right-click row menu, per-app actions, batch actions, scan/bloatware controls |
| `tech_secops2.py` | `SecOps2Mixin` | typed-YES confirmations, batch actions, APK Info, Restore/Backup dialog |
| `tech_secops4.py` | `SecOps4Mixin` | icon generation, Restore/Backup dialog, device info strip |
| `tech_vtop.py` | `VtOpsMixin` | Monitor Running Apps page |
| `tech_misc.py` | `MiscMixin` | package-list loading/cache, scrcpy mirror entry, driver fixes, reboots, logout, ADB kill/restart |
| `tech_phone_mirror/` | `PhoneMirrorManager` compatibility entry point | Routes the Dashboard mirror import to the embedded child-window implementation while retaining legacy scrcpy helpers |
| `tech_phone_mirror_embedded.py` | `PhoneMirrorManager` | True Dashboard embedding: native scrcpy child window + transparent iPhone frame inside `dash_phone`; Dashboard log hide/restore |
| `tech_phone_mirror_host.py` | host mirror manager | Captures Dashboard HWNDs, manages native mirror lifetime/visibility, alignment and clipping |
| `tech_phone_mirror.py` | legacy native mirror implementation | Native scrcpy process/window and transparent iPhone-frame primitives used by the embedded manager |
| `tech_phone_mirror_restore_patch.py` | mirror restore compatibility patch | Retries Dashboard log remapping on Tk's UI thread after native mirror shutdown |
| `tech_hardening.py` | `apply_hardening()` | runtime safety/reliability patches |
| `tech_dashboard_redesign.py` | helpers | 3uTools-style dashboard layout integration |
| `sitecustomize.py` | compatibility hooks | Selects embedded mirror/restore behavior, suppresses URL hover tooltips, and forces Dashboard navigation after login |
| `runtime_hook_gelotech.py` | PyInstaller runtime hook | Explicitly loads the same compatibility hooks in packaged release builds; frozen apps do not rely on CPython auto-loading `sitecustomize.py` |
| `bump_version.py` | helper script | bumps `version.json`, computes data-file SHA-256, signs into `version.json.sig`, pushes |

---

## 2. Startup Sequence (Program Flow)

```
python techtool.py
  │
  ├─ GeloTechTool.__init__()
  │    ├─ 1. Window: title, icon, size/minsize, scaling
  │    ├─ 2. Layout: fixed sidebar | weighted page container
  │    ├─ 3. _extract_scrcpy()        → unzip scrcpy-win64-v3.3.4.zip to temp, locate adb.exe/scrcpy.exe
  │    ├─ 4. _migrate_settings()      → first run: import old settings/exclusion files into AppData JSON
  │    ├─ 5. _seed_database_defaults()→ pre-check packages flagged in DB into exclusion/debloated lists
  │    ├─ 6. Build sidebar and page navigation
  │    ├─ 7. Build Dashboard, Cleaner, Monitor, DNS, VirusTotal pages
  │    ├─ 8. _build_log_panel()  → Dashboard phone log console + other console views
  │    └─ 9. _build_hint_banner() → red attention strip (auto-hide 6s)
  │
  ├─ _login_gate()  → login window (withdraw main window)
  │    ├─ DEFAULT VIEW = LOGIN (email + password)
  │    ├─ verify credentials (PBKDF2) against live accounts from server
  │    └─ login success:
  │         ├─ purge stale per-login database copy
  │         ├─ fetch users + DB → verify credentials and DB hash
  │         ├─ write verified DB to temp session cache → clear stale lookups → re-seed
  │         ├─ apply permissions
  │         ├─ compatibility hook schedules `_show_page("Dashboard")`
  │         └─ show main window
  │
  └─ on_close() → stop mirror, purge session database copy, destroy window
```

**Post-login default:** Dashboard is the intended first visible page after a
successful login. The page-stack method is `_show_page("Dashboard")`; the
compatibility hook explicitly selects it after permissions are applied so the
sidebar selection and `_current_page` stay synchronized.

---

## 3. Dashboard Screen Mirror Flow

```
Dashboard → Screen Mirror
  │
  ├─ capture `dash_phone` HWND
  ├─ hide the existing Dashboard log console with `place_forget()`
  ├─ start native scrcpy process
  ├─ find scrcpy HWND
  ├─ embed scrcpy as a child of `dash_phone`
  ├─ embed transparent iPhone frame as a child of `dash_phone`
  └─ position stream at the frame display opening

Stop / scrcpy exit / device loss
  │
  ├─ close overlay + terminate scrcpy
  ├─ schedule console restoration on Tk's UI thread
  ├─ reuse the existing Dashboard log widget
  ├─ use the Dashboard's current `_dash_log_rect`
  ├─ remap/lift the console and force Tk geometry update
  ├─ verify `winfo_ismapped()` and retry briefly if necessary
  └─ clear mirror state only after restoration succeeds
```

The native scrcpy stream remains the video renderer; the iPhone frame is a
transparent Win32 overlay/child window. No screenshot-based video compositing
is used.

---

## 4. Runtime Loop

```
UI events (clicks / right-click / keypress)
  │
  ├─ Sidebar: mirror, reboots, ADB fix, admin panel, logout
  ├─ Dashboard: device info, quick actions, screen mirror
  ├─ Cleaner page: Refresh → load packages → render/filter/check apps
  ├─ Monitor page: live process/package tables
  ├─ DNS page: pick DNS server → set via ADB
  └─ VirusTotal page: scan APK files via API

Background threads (all ADB calls, UI updated via after(0)):
  ├─ scan_adb_devices() every 3s
  ├─ security scans
  └─ bulk operations: worker thread → subprocess adb → log line per package
```

Every action follows the same basic pattern:

```
ADB/subprocess operation → parse result → log_message() → update runtime state
```

---

## 5. Update / Release Cycle

```
DATA update (no new exe needed):
  edit gelotech_database_v3.json / banking_apps.json
  → python bump_version.py        (bump + re-hash + SIGN; --no-commit to stage)
  → git push
  → user app: on EVERY login → fetch + verify
       → verify version.json.sig with embedded Ed25519 public key
       → secret.json (LIVE accounts) fetched as-is
       → DB verified vs manifest → session cache in temp
       → after login: _check_updates() → banking_apps.json only

CODE update (needs new exe):
  edit *.py
  → update README.md + PROCESS_GUIDE.md for major changes
  → pyarmor gen -O build/pyarmor_out techtool.py tech_common.py tech_ui.py
    tech_settings.py tech_admin.py tech_reg.py tech_secscan.py tech_secops.py
    tech_secops3.py tech_secops2.py tech_secops4.py tech_dash.py tech_vtop.py
    tech_misc.py tech_hardening.py tech_dashboard_redesign.py
    tech_phone_mirror.py tech_phone_mirror_embedded.py tech_phone_mirror_host.py
    tech_phone_mirror_fix.py tech_phone_mirror_restore_patch.py
    tech_phone_mirror/__init__.py runtime_hook_gelotech.py sitecustomize.py
  → python -m PyInstaller GeloTechTool_obf.spec --noconfirm
  → dist\GeloTechTool.exe
```

The release spec includes `runtime_hook_gelotech.py`, which explicitly loads
the compatibility hooks inside the frozen application. This keeps the
Dashboard-default, URL-tooltip, and mirror-restore behavior from depending on
CPython's normal `sitecustomize` auto-import behavior.

---

## 6. Settings & Data Locations

```
AppData settings dir (get_settings_dir())  → persistent, writable runtime state:
  exclusions.json
  banking_apps.json
  app_list_cache.json
  apk_backups\*.apk
  sec_whitelist.txt

Temp session cache (get_session_database_path(), temp\GeloTechTool\):
  gelotech_database_v3.json  → pulled + verified per login, then wiped

Bundled / repo build resources:
  banking_apps.json
  scrcpy-win64-v3.3.4.zip
  ApkIconHelper.apk
  gelotech_icon.ico

Repo root / update source:
  version.json
  version.json.sig
  gelotech_database_v3.json
  secret.json
  banking_apps.json
```

---

## 7. Security Notes

- Update manifests are signed with Ed25519 and downloaded data files are
  checked against signed SHA-256 hashes.
- `secret.json` is the live server-side account source and is not a local
  runtime settings file.
- Passwords are PBKDF2 hashes and are not stored as local login credentials.
- Destructive package operations use typed-YES confirmation where required.
- Release builds are PyArmor-obfuscated according to `AGENTS.md`.
- Embedded credentials/tokens remain a separate security-hardening item and
  must be rotated/scoped appropriately before distribution.

## Fast architecture workflow

For normal code work, use this short path instead of repeating subsystem-wide setup:

1. Run `python scripts/agent_preflight.py` and read `AGENTS.md` plus the relevant README/docs sections.
2. Inspect and reproduce the actual execution path.
3. Make the smallest root-cause fix. Avoid speculative retries, timing hacks, and global compatibility patches.
4. Run `python -m compileall -q .` and `python -m pytest -q`.
5. For login/navigation changes, run `python techtool.py`; for mirror work, also read `docs/SCRCPY_GUIDE.md` and record whether testing used a real device.
6. For a release build, run `python scripts/release.py`. Do not manually repeat the PyArmor/PyInstaller sequence unless debugging the build itself.
7. Review the diff before commit/push.
