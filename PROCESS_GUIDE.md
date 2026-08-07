# GeloTechTool — Process Tree Visual Guide

Internal reference only. Shows how the app works step by step and how the
code is organised. Updated on major code changes.

---

## 1. App Architecture (Who Owns What)

```
GeloTechTool (techtool.py)
  └─ GeloTechTool(ctk.CTk, UiMixin, SettingsMixin, SecScanMixin,
                  SecOpsMixin, SecOps2Mixin, VtOpsMixin, MiscMixin)
```

| File | Class / Role | Owns |
|---|---|---|
| `techtool.py` | `GeloTechTool` | entry point, window, sidebar, tabview, log console, hint banner, ADB device monitor, scrcpy extraction, debloat safety checks |
| `tech_common.py` | helpers | `EMBEDDED_UPDATE_URL`/`TOKEN`, `UPDATE_SIGN_PUBLIC_KEY`, paths (bundle/app/settings/cache dirs), `load_package_database`, `Tooltip` (routes to hint banner), adb subprocess wrapper |
| `tech_settings.py` | `SettingsMixin(AdminPanelMixin)` | settings JSON load/save (runtime state only), email-based login UI (two-step: email → password), PBKDF2 password verify, permissions (non-admin users with no explicit perms in secret.json get `DEFAULT_USER_PERMS` = everything except admin-only `virustotal`), `_check_updates` (pinned GitHub API pull + Ed25519 sig + SHA-256 verify, banking list only), first-run migration + seeding |
| `tech_reg.py` | helpers | self-service account flow + server fetching: `_fetch_verified_sources` (signed manifest + live accounts + DB sha256), `_request_password` (generate PBKDF2 password → write to repo secret.json via write token → email via SMTP), `hash_password`/`verify_password`, `_purge_session_database` |
| `tech_admin.py` | `AdminPanelMixin` | Admin Panel dialog: READ-ONLY account list fetched + signature-verified from the update server (passwords managed by maintainer in repo) |
| `tech_ui.py` | `UiMixin` | tab UIs: cleaner header/toolbar/legend, monitor, DNS, VirusTotal |
| `tech_secscan.py` | `SecScanMixin` | background threat scans (popup-ads, sideloaded apps, risk permissions) |
| `tech_secops.py` | `SecOpsMixin` | cleaner list rows, color coding, legend filter, right-click menu, clean/uninstall/backup runners, DB filter dialog |
| `tech_secops2.py` | `SecOps2Mixin` | typed-YES confirmations, batch checked actions, disable, Fix Popup Ad, APK Info (+permissions), Restore/Backup dialog, device info |
| `tech_vtop.py` | `VtOpsMixin` | Monitor Running Apps tab (process/package tables) |
| `tech_misc.py` | `MiscMixin` | package list loading (All / Disabled / Filter), scrcpy mirror, driver fixes, reboots, logout, ADB kill/restart |
| `bump_version.py` | helper script | bumps `version.json`, computes data-file SHA-256, signs into `version.json.sig`, pushes |

---

## 2. Startup Sequence (Program Flow)

```
python techtool.py
  │
  ├─ GeloTechTool.__init__()
  │    ├─ 1. Window: title, icon, size/minsize, scaling
  │    ├─ 2. Layout columns: [0] sidebar fixed | [1] tabs weight=3 | [2] log weight=1 (min 340)
  │    ├─ 3. _extract_scrcpy()        → unzip scrcpy-win64-v3.3.4.zip to temp, locate adb.exe/scrcpy.exe
  │    ├─ 4. _migrate_settings()      → first run: import old settings/exclusion files into AppData JSON
  │    ├─ 5. _seed_database_defaults()→ pre-check packages flagged in DB into exclusion/debloated lists
  │    ├─ 6. Build sidebar (DISPLAY / POWER / CONNECTION / SESSION buttons)
  │    ├─ 7. Build tabs: Cleaner, Monitor, DNS, VirusTotal (build_*_tab())
  │    ├─ 8. _build_log_panel()  → Matrix-style console + filter chips
  │    └─ 9. _build_hint_banner() → red attention strip (auto-hide 6s)
  │
  ├─ _login_gate()  → login window (withdraw main window)
  │    ├─ STEP A (email only): user enters email
  │    │    ├─ typing ADMIN_SECRET_PHRASE into the email field → unlocks
  │    │    │  MAINTAINER login (step B with username fixed to "admin")
  │    │    └─ SEND PASSWORD → background thread:
  │    │         ├─ fetch version.json + sig → verify signature; fetch
  │    │         │  secret.json (live accounts) + DB (verify sha256)
  │    │         ├─ generate 14-char password → PBKDF2 hash
  │    │         ├─ write account (email + hash) to repo secret.json via
  │    │         │  the write token (retry on 422 conflict)
  │    │         ├─ email password via embedded SMTP sender
  │    │         └─ "Password sent to your email - check inbox/spam" → step B
  │    └─ STEP B (email + password): verify against live accounts
  │         ├─ purge stale per-login database copy (temp)
  │         ├─ fetch users + DB (as above) → verify credentials (PBKDF2)
  │         ├─ write verified DB to temp session cache → clear stale lookups → re-seed
  │         └─ main thread: apply permissions, show window, after(1500, _check_updates)
  │
  └─ on_close() → purge session database copy, destroy window
```

---

## 3. Runtime Loop

```
UI events (clicks / right-click / keypress)
  │
  ├─ Sidebar: mirror, reboots, ADB fix, admin panel, logout
  ├─ Cleaner tab: Refresh → load packages → color rows → check apps
  │     ├─ Clean / Uninstall Virus / Fix Popup Ad / Restore/Backup (typed YES on destructive)
  │     ├─ Right-click menu: disable / uninstall / clean / backup / exclude / APK info
  │     │     └─ batch rows appear when apps are checked (Disable/Uninstall/Backup ALL)
  │     └─ Legend click → filter list to group; click again → reset
  ├─ Monitor tab: live process/package tables from dumpsys/ps
  ├─ DNS tab: pick DNS server → set via ADB (adb shell settings put global private_dns_*)
  └─ VirusTotal tab: scan APK files via API, show detections

Background threads (all ADB calls, UI updated via after(0)):
  ├─ scan_adb_devices() every 3s   → Connected / Unauthorized / No device
  ├─ security scans (threats, popup ads, sideloaded, risk perms)
  └─ every bulk operation: worker thread → subprocess adb → log line per package

Every action:
  [self.scrcpy_adb, "shell", ...]  →  result parsed  →  log_message()  →  settings saved
```

---

## 4. Update / Release Cycle

```
DATA update (no new exe needed):
  edit gelotech_database_v3.json / banking_apps.json
  → python bump_version.py        (bump + re-hash + SIGN; --no-commit to stage)
  → git push (bump_version.py does this unless --no-commit)
  → user app: on EVERY login → fetch + verify
       → verify version.json.sig with embedded Ed25519 public key (reject if bad)
       → secret.json (LIVE accounts) fetched as-is; DB verified vs manifest
       → gelotech_database_v3.json → verify SHA-256 → session cache in temp
         (deleted on app close / logout / before next login's fetch)
       → after login: _check_updates() → banking_apps.json only (version-based,
         .bak kept in settings dir, SHA-256 verified)
  NOTE: update_url / update_token are PINNED to EMBEDDED_* in tech_common.py;
        never read from settings or the repo secret.json.
  NOTE: .gitattributes forces eol=lf for *.json + version.json.sig so the
        signed hashes match the exact bytes GitHub serves; renormalizing
        line endings REQUIRES re-signing.
  NOTE: secret.json is NOT in the signed manifest - the app writes it
        directly (self-registration / password reset, see EMAIL flow below).

EMAIL account flow (self-service, no maintainer action):
  user enters email on login screen
  → app: fetch+verify server → generate 14-char password → PBKDF2 hash
  → PUT users[email] = {hash, permissions:{}} into repo secret.json
    (contents API + EMBEDDED_UPDATE_WRITE_TOKEN, retry on 422 conflict)
  → SMTP email with the password (EMBEDDED SMTP_* constants, dedicated
    low-privilege sender) → "check inbox/spam" → user logs in

ADMIN access (maintainer only):
  type ADMIN_SECRET_PHRASE into the email field on the login screen
  → step B opens with username locked to "admin"
  → sign in with the admin PBKDF2 password (maintainer-managed in repo)

CODE update (needs new exe):
  edit *.py
  → update README.md + PROCESS_GUIDE.md (project rules)
  → pyarmor gen -O build/pyarmor_out techtool.py tech_common.py tech_ui.py
    tech_settings.py tech_admin.py tech_reg.py tech_secscan.py tech_secops.py
    tech_secops2.py tech_vtop.py tech_misc.py
        tech_settings.py tech_admin.py tech_secscan.py tech_secops.py
        tech_secops2.py tech_vtop.py tech_misc.py
        (ALWAYS re-run over ALL modules; obfuscation applies to all builds)
  → python -m PyInstaller GeloTechTool_obf.spec --noconfirm
  → dist\GeloTechTool.exe  → distribute
```

---

## 5. Settings & Data Locations

```
AppData settings dir (get_settings_dir())  → persistent, writable (RUNTIME STATE ONLY):
  secret.json          (exclusions, debloated history, update_state — NO user accounts)
  banking_apps.json    (downloaded via update flow, .bak kept)
  apk_backups\*.apk
  sec_whitelist.txt

Temp session cache (get_session_database_path(), temp\GeloTechTool\)  → per-login, wiped:
  gelotech_database_v3.json  (pulled + verified on every login; deleted on
                              app close / logout / before next login's fetch)

Bundled (inside exe / repo root):
  banking_apps.json          (banking apps auto-protection list; also served via updates)
  scrcpy-win64-v3.3.4.zip, ApkIconHelper.apk, gelotech_icon.ico
  (gelotech_database_v3.json and secret.json are NOT bundled — GitHub only)

Repo root (update source):
  version.json, version.json.sig, gelotech_database_v3.json, secret.json (live accounts, app-written), banking_apps.json
```

---

## 6. Security Notes (embedded in app)

- GitHub tokens (`tech_common.py`) — `EMBEDDED_UPDATE_TOKEN` read-only fetch;
  `EMBEDDED_UPDATE_WRITE_TOKEN` (fine-grained, Contents Read+Write, THIS repo
  only) used solely to persist self-registered accounts. Update source is
  PINNED to embedded constants; never overridable via settings or repo files.
- SMTP sender (`SMTP_*`) — dedicated low-privilege account + app password.
  Anything embedded in the exe can be extracted: rotate write token + SMTP
  app password regularly, never use personal credentials.
- Updates are signed (Ed25519): `version.json.sig` verified against
  `UPDATE_SIGN_PUBLIC_KEY`, then per-file SHA-256 verified against the signed
  manifest (database + banking) — tampered or unsigned updates are rejected.
  Signed hashes must cover the exact bytes GitHub serves (`.gitattributes` = LF).
- Accounts and the package database are fetched fresh and verified on every
  login; credentials are never written to the user's PC and the DB is wiped at
  the end of each session. Accounts are stored in the repo's `secret.json`
  as PBKDF2 hashes (`100000$salt$digest`) only.
- Admin access: `ADMIN_SECRET_PHRASE` typed into the email field unlocks the
  maintainer login; the real gate is the admin PBKDF2 password.
- Admin Panel is read-only (server-verified account list; no local edits).
- Type-YES confirmation gates destructive batch actions.
- All release builds are PyArmor-obfuscated (`GeloTechTool_obf.spec`).
```
