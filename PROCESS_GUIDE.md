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
| `tech_settings.py` | `SettingsMixin(AdminPanelMixin)` | settings JSON load/save, login + PBKDF2 password hashes, forced password change, permissions, users, `_check_updates` (pinned GitHub API pull + Ed25519 sig + SHA-256 verify), first-run migration + seeding |
| `tech_admin.py` | `AdminPanelMixin` | Admin Panel dialog: add/edit users, per-user permissions + tabs |
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
  │    ├─ 6. _ensure_default_users()  → create admin/admin123 if no users exist
  │    ├─ 7. Build sidebar (DISPLAY / POWER / CONNECTION / SESSION buttons)
  │    ├─ 8. Build tabs: Cleaner, Monitor, DNS, VirusTotal (build_*_tab())
  │    ├─ 9. _build_log_panel()  → Matrix-style console + filter chips
  │    └─ 10. _build_hint_banner() → red attention strip (auto-hide 6s)
  │
  ├─ do_login()  → verify PBKDF2 hash, load permissions, show tabs/buttons
  │
  └─ after(1500, _check_updates)   → background update check (see §4)
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
  edit gelotech_database_v3.json / secret.json / banking_apps.json
  → python bump_version.py        (bump + re-hash + SIGN; --no-commit to stage)
  → git push (bump_version.py does this unless --no-commit)
  → user app: on login → _check_updates() → GitHub API fetch version.json
       → verify version.json.sig with embedded Ed25519 public key (reject if bad)
       → for each newer file: fetch → verify SHA-256 vs signed manifest sha256
       → write to settings dir (+ .bak of old)
       → secret.json users MERGED per-user (local password hash/must_change_pw
         always win; new repo users added; local lists/debloated/update_state
         preserved)
       → record only verified+successful files in update_state → prompt restart
  NOTE: update_url / update_token are PINNED to EMBEDDED_* in tech_common.py;
        never read from settings or the repo secret.json.

CODE update (needs new exe):
  edit *.py
  → update README.md + PROCESS_GUIDE.md (project rules)
  → pyarmor gen -O build/pyarmor_out techtool.py tech_common.py tech_ui.py
        tech_settings.py tech_admin.py tech_secscan.py tech_secops.py
        tech_secops2.py tech_vtop.py tech_misc.py
        (ALWAYS re-run over ALL modules; obfuscation applies to all builds)
  → python -m PyInstaller GeloTechTool_obf.spec --noconfirm
  → dist\GeloTechTool.exe  → distribute
```

---

## 5. Settings & Data Locations

```
AppData settings dir (get_settings_dir())  → persistent, writable:
  secret.json          (users + runtime state: exclusions, debloated, update_state; repo copy has users only, merged on update)
  gelotech_database_v3.json (downloaded override, .bak kept)
  banking_apps.json        (downloaded override, .bak kept)
  apk_backups\*.apk
  sec_whitelist.txt

Bundled (inside exe / repo root):
  gelotech_database_v3.json  (fallback if not in AppData; carries user-app +
                              banking exclusion flags per package)
  banking_apps.json          (banking apps auto-protection list)
  secret.json                (hashed login credentials only, at repo root for updates)
  scrcpy-win64-v3.3.4.zip, ApkIconHelper.apk, gelotech_icon.ico

Repo root (update source):
  version.json, version.json.sig, gelotech_database_v3.json, secret.json, banking_apps.json
```

---

## 6. Security Notes (embedded in app)

- GitHub token (`tech_common.py::EMBEDDED_UPDATE_TOKEN`) — fine-grained READ-ONLY
  pull from the public repo. Update source is PINNED to embedded constants;
  never overridable via settings or the repo secret.json.
- Updates are signed (Ed25519): `version.json.sig` verified against
  `UPDATE_SIGN_PUBLIC_KEY`, then per-file SHA-256 verified against the signed
  manifest — tampered or unsigned updates are rejected.
- Signing private key: `%USERPROFILE%\.gelotech_signing\update_ed25519.pem`
  (never committed; loaded by bump_version.py).
- Passwords: salted PBKDF2 hashes only, never plaintext.
- Default `admin` account is forced to change its password on first login
  (`must_change_pw` flag); no credential hints shown in the app.
- Settings copy next to exe is set as a hidden Windows file.
- Type-YES confirmation gates destructive batch actions.
- All release builds are PyArmor-obfuscated (`GeloTechTool_obf.spec`).
```
