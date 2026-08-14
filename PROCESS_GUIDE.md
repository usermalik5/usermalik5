# GeloTechTool — Process Tree Visual Guide

Internal reference only. Shows how the app works step by step and how the
code is organised. Updated on major code changes.

---

## 1. App Architecture (Who Owns What)

```
GeloTechTool (techtool.py)
  └─ GeloTechTool(ctk.CTk, UiMixin, SettingsMixin, SecScanMixin,
                  SecOpsMixin, BloatwareFilterMixin, SecOps3Mixin, SecOps2Mixin, SecOps4Mixin,
                  DashboardMixin, VtOpsMixin, MiscMixin)
  └─ apply_hardening(GeloTechTool)  ← tech_hardening.py (import-time patches)
```

| File | Class / Role | Owns |
|---|---|---|
| `techtool.py` | `GeloTechTool` | entry point, window, sidebar, page stack/navigation, log console, hint banner, ADB device monitor, scrcpy extraction, debloat safety checks, dark/light theme toggle (sidebar) + `_theme_walk` color apply |
| `tech_dash.py` | `DashboardMixin` | Dashboard page: iPhone mockup (left) + App Cleaner UI (right, built via `build_security_tab(parent=...)`), phone log-console placement, plus Refresh and screen-mirror buttons under the phone |
| `tech_common.py` | helpers | `AUTH_WORKER_URL`, `UPDATE_SIGN_PUBLIC_KEY`, paths (bundle/app/settings/cache dirs), `load_package_database`, app-list cache helpers (`load_apps_cache`/`save_apps_cache`/`fmt_cache_time`), `Tooltip` (routes to hint banner), adb subprocess wrapper |
| `tech_settings.py` | `SettingsMixin(AdminPanelMixin)` | settings JSON load/save (runtime state only), email-based login UI (two-step: email → password), PBKDF2 password verify, permissions, `_check_updates`, first-run migration + seeding |
| `tech_reg.py` | helpers | auth proxy client + server fetching: `_worker_call`/`_worker_fetch` (via Worker `AUTH_WORKER_URL`, Bearer session for admin routes), `_login_user` (returns ok/reason/user/session), `_request_password`, `_set_user_blocked`, `_fetch_verified_users` (sanitized account list, admin session only), `_fetch_verified_sources` (signed manifest + DB via Worker `/files` + sha256), `hash_password`/`verify_password`, `_purge_session_database` |
| `tech_admin.py` | `AdminPanelMixin` | Account management dialog (admin only): account list with Block/Unblock per account (via auth proxy Worker) |
| `tech_ui.py` | `UiMixin` | tab/page UIs: cleaner header/toolbar/legend, monitor, DNS, VirusTotal |
| `tech_secscan.py` | `SecScanMixin` | background threat scans |
| `tech_secops.py` | `SecOpsMixin` | cleaner list and rendering |
| `tech_secops3.py` | `SecOps3Mixin` | right-click row menu, per-app actions, batch actions, scan/bloatware controls |
| tech_bloatware.py | Bloatware filter/scan module: Scan Bloatware UAD-level filtering and row marking that backs the Dashboard App Cleaner UI |
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
| `sitecustomize.py` | compatibility hooks | Mirror compatibility and URL-tooltip behavior only; never owns login/navigation |
| `runtime_hook_gelotech.py` | PyInstaller runtime hook | Explicitly loads `sitecustomize.py` for packaged compatibility behavior |
| `bump_version.py` | helper script | bumps `version.json`, computes data-file SHA-256, signs into `version.json.sig`, pushes |

**Bloatware subsystem ownership:** `tech_bloatware.py` owns `_sec_action_recommendation()` and the complete-device UAD-level scan. Do not duplicate `_sec_action_recommendation()` in another module. Release validation (`scripts/release.py`) requires exactly one definition.

---

## 2. Startup Sequence (Program Flow)

```
python techtool.py
  │
  ├─ GeloTechTool.__init__()
  │    ├─ create window/layout + sidebar/navigation shell
  │    ├─ create lightweight page factories
  │    └─ build login gate (withdraw main window) → wait for authentication
  │
  ├─ _login_gate()  → login window (DEFAULT VIEW = LOGIN: email + password)
  │    └─ login success:
  │         ├─ verify credentials (PBKDF2) server-side via auth proxy Worker
  │         ├─ purge stale per-login database copy
  │         ├─ fetch signed manifest + DB via Worker /files → verify DB hash
  │         ├─ write verified DB to temp session cache
  │         ├─ repoint the package DatabaseService to the verified session DB
  │         ├─ clear stale lookups
  │         ├─ re-seed
  │         ├─ initialize runtime resources (scrcpy extraction, settings migration, DB defaults)
  │         ├─ initialize Dashboard (phone mockup + App Cleaner, Monitor, DNS, VirusTotal pages)
  │         ├─ apply permissions
  │         ├─ show Dashboard through the normal navigation controller
  │         └─ start background ADB monitoring
  │
  └─ on_close() → stop mirror, purge session database copy, destroy window
```

**Post-login default:** Dashboard is the intended first visible page after a
successful login. The page-stack method is `_show_page("Dashboard")`; the
normal navigation controller selects Dashboard after successful authentication.

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
  ├─   Sidebar: mirror, reboots, ADB fix, accounts, logout
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
       → login + signed files (manifest, DB, banking) via auth proxy Worker
         (AUTH_WORKER_URL; /files public allowlist, /login, Bearer sessions)
       → secret.json (LIVE accounts) fetched as-is (Worker-written)
       → DB verified vs manifest → session cache in temp
       → after login: _check_updates() → banking_apps.json only

AUTH PROXY deploy (Worker in worker/, one-time):
  cd worker
  → npx wrangler secret put GITHUB_TOKEN / SMTP_PASSWORD / SESSION_SECRET
  → npx wrangler deploy
  → copy printed URL into AUTH_WORKER_URL in tech_common.py
  → rebuild + release the exe

CODE update (needs new exe):
  edit *.py
  → update README.md + PROCESS_GUIDE.md for major changes
  → verify SECURITY.md wording matches the current security model
       (release.py enforces this in preflight — cannot be skipped)
  → check PyArmor Trial module sizes before release
       → 32 KB+: review/extract cohesive responsibilities
       → 35 KB+: stop and split the module before obfuscation
  → python scripts/release.py
       → preflight + compile + tests
       → PyArmor obfuscation of every required module
       → verify obfuscated outputs exist
       → PyInstaller GeloTechTool_obf.spec
       → verify the packaged EXE contains required obfuscated modules
  → dist\GeloTechTool.exe
```

### PyArmor Trial release constraint

The current development environment uses the **PyArmor Trial** edition with an
approximate **35 KB per-source-file limit**. This is a hard production-build
constraint.

- Treat **32 KB** as a warning threshold: review the module before adding more
  code and extract a cohesive responsibility when practical.
- Treat **35 KB** as a hard stop: split the module before attempting a
  production obfuscated build.
- `scripts/release.py` is the authoritative build entry point. It should fail
  early with the exact oversized filename and byte size rather than relying on
  PyArmor to fail later with a generic license/size error.
- A PyArmor Trial limit failure is a release blocker. Never use the standard
  non-obfuscated build as a workaround unless the user explicitly requests a
  debug build.
- After splitting a module, update the PyArmor `MODULES` list and the
  `GeloTechTool_obf.spec` hidden imports, then rerun the full release checks.

The supported production path is therefore:

```text
source modules
   ↓
size gate (≈35 KB hard limit)
   ↓
PyArmor obfuscation
   ↓
obfuscated module verification
   ↓
PyInstaller obfuscated spec
   ↓
EXE verification
```

A PyInstaller EXE built without successful PyArmor obfuscation is a debug
artifact, not a production release.

### Release bookkeeping

Every release must also update the repo's user-facing release metadata in the
same commit as the `APP_VERSION` bump:

- `tech_common.py` `APP_VERSION` must match the release tag (`v<APP_VERSION>`).
- README.md "Latest release" label `(vX.Y.Z)` in the Download section must be
  bumped to the new version (the `releases/latest` URL redirects
  automatically, but the static label does not).
- The release notes must state the new version.

A stale `(vX.Y.Z)` label in README.md after a release is a release defect.

The release spec includes `runtime_hook_gelotech.py`, which explicitly loads
`sitecustomize.py` for packaged compatibility behavior (mirror/restore and
URL-tooltip). This avoids relying on CPython's normal `sitecustomize`
auto-import behavior in frozen applications.

---

## 6. Settings & Data Locations

```
AppData settings dir (get_settings_dir())  → persistent, writable runtime state:
  exclusions.json
  banking_apps.json
  app_list_cache.json
  apk_backups\*.apk
  sec_whitelist.txt

Temp session cache (get_session_database_path(), %TEMP%\GeloTechTool\):
  gelotech_database_v3.json
  → downloaded and verified at login
  → used by DatabaseService
  → removed at session cleanup

Bundled / repo build resources:
  scrcpy-win64-v3.3.4.zip
  ApkIconHelper.apk
  gelotech_icon.ico
  banking_apps.json

Repo root / GitHub:
  gelotech_database_v3.json
  secret.json
  version.json
  version.json.sig
  banking_apps.json

EXE bundle:
  NO package database
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
- GitHub write token, SMTP credentials and session-signing key live ONLY as
  Cloudflare Worker secrets (`worker/`, `wrangler secret put`); the exe holds
  only the Worker URL and the signing public key (both public). Rotate the
  Worker secrets regularly.

## Fast architecture workflow

For normal code work, use this short path instead of repeating subsystem-wide setup:

1. Run `python scripts/agent_preflight.py` and read `AGENTS.md` plus the relevant README/docs sections.
2. Inspect and reproduce the actual execution path.
3. Make the smallest root-cause fix. Avoid speculative retries, timing hacks, and global compatibility patches.
4. Run `python scripts/agent_check.py` to verify the dev environment, then `python -m compileall -q .` and `python -m pytest -q`; add `python -m ruff check .` for lint.
5. For login/navigation changes, run `python techtool.py`; for mirror work, also read `docs/SCRCPY_GUIDE.md` and record whether testing used a real device.
6. For a release build, run `python scripts/release.py`. Do not manually repeat the PyArmor/PyInstaller sequence unless debugging the build itself.
7. Review the diff before commit/push.
