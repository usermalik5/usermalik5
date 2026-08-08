# GeloTechTool

Android debloating / security tool for Windows. Scans connected ADB devices,
classifies packages against the merged GeloTech + UAD database, and supports
debloating (disable / uninstall for user / restore), exclusion lists, APK
backup & restore, screen mirroring via scrcpy, VirusTotal scanning, popup
virus cleanup, and DNS-based ad blocking.

Access is protected by a login system with per-user permissions and tabs
(admin always has everything). Logs stream to a Matrix-style console, and
hover hints appear in a red attention banner at the bottom of the window.
The package-list context menu (right-click) offers per-app actions plus
batch actions for all checked apps (disable / uninstall / APK backup /
exclude).
Destructive batch actions ask you to type YES to confirm, and clicking a
color in the list legend filters the list to that group (click again to
reset). The toolbar keeps Clean, Uninstall Virus, Fix Popup Ad, Restore/Backup,
All, Disabled, and Filter. A permanent legend in the sidebar explains the app
removal levels (Recommended = safe to remove, Advanced = mostly safe,
Expert = may break features, Unsafe = dangerous) and the list row colors
(green = removable, orange = clean excluded, red = uninstall excluded,
purple = both excluded) — rows in the app list follow the same color scheme,
and removal-level badges use the same colors. The sidebar header shows
`© 2026 GeloTech` with clickable links to Gsmcodeph.com and
facebook.com/gelotechxyz, and the title/tool name always shows the current
version (e.g. v1.0.9).

Loading the app list is fast even without the phone plugged in: the first
successful scan caches the package list locally on the PC, later loads render
that cached list instantly and then refresh from the device in the background
(stale-while-revalidate), and any load falls back to the cache whenever the
phone is unreachable. List rows are rendered lazily in small batches so the UI
stays responsive with hundreds of apps loaded.

## Download

**Latest release:** [GeloTechTool.exe (v1.1.0)](https://github.com/usermalik5/GeloTech-Tool/releases/latest)

Windows only. Download the exe and run it — no installation needed. Login is
verified against this repo on every launch (needs internet), and the package
database is pulled fresh from here on every login — users always get the
latest data with zero manual intervention.

## What's in this folder

| Item | Purpose |
|---|---|
| `techtool.py` + `tech_*.py` | Application source (entry point: `techtool.py`) |
| `GeloTechTool.spec` | PyInstaller build spec (onefile, windowed) |
| `GeloTechTool_obf.spec` | PyInstaller spec for the PyArmor-obfuscated build (needs `build/pyarmor_out` from `pyarmor gen`) |
| `gelotech_database_v3.json` | **The package database** (merged UAD + GeloTech data; user-app exclusions live here as per-package flags). Lives ONLY on GitHub — every login pulls it fresh, verifies it, caches it for the session, and deletes it on app close |
| `banking_apps.json` | Banking apps exclusion list — banking apps are auto-protected (never cleaned/uninstalled, shown with a 🏦 badge, can be filter-excluded) |
| `secret.json` | **The live accounts file** — email + PBKDF2 hash per user. The app writes new/self-registered accounts here via the write token; fetched + used in-memory at login, never stored on users' PCs |
| `version.json` | Update manifest: bump `database` / `banking` to publish a new release; carries the signed SHA-256 hashes of the data files (database + banking only) |
| `version.json.sig` | Ed25519 signature (base64) over `version.json` — the app rejects unsigned/tampered manifests |
| `bump_version.py` | Helper that bumps `version.json`, signs it, and pushes the new manifest to the repo |
| `gelotech_icon.ico` | App icon (also embedded in the built exe) |

Build-time resources (ADB/fastboot tools, scrcpy zip, drivers, icon cache)
live in the local working folder and are excluded from the repo via
`.gitignore`; they are bundled into the exe at build time.

## Running from source

```bash
pip install customtkinter pillow requests pyinstaller
python techtool.py
```

Login is email-based. The login page opens on the **LOGIN** form: enter your
email and the password you were sent, then log in — passwords stay valid
until you request a new one. New users (or anyone who lost their password)
click "Forgot password? Get a new one by email", and the app emails them a
generated password (also check the spam folder); requesting a new password
replaces the old one. The maintainer unlocks the admin login by typing the
secret phrase into the email field (maintainer-only, not shown to users).
Non-admin users get all tabs and tools (Cleaner, Monitor, DNS, all sidebar
actions); only the VirusTotal tab is reserved for the admin account.

## Building the exe

Obfuscated build (requires PyArmor — re-runs `pyarmor gen` into
`build/pyarmor_out` before running `GeloTechTool_obf.spec`). **This is the
only supported release build** — obfuscation applies to all modules and all
release exes:

```bash
pyarmor gen -O build/pyarmor_out techtool.py tech_common.py tech_ui.py tech_settings.py tech_admin.py tech_reg.py tech_secscan.py tech_secops.py tech_secops2.py tech_vtop.py tech_misc.py
python -m PyInstaller GeloTechTool_obf.spec --noconfirm
```

Standard (non-obfuscated) build — debugging only, never distribute:

```bash
python -m PyInstaller GeloTechTool.spec --noconfirm
```

## Updating the app on other PCs

The update URL and GitHub token are embedded in the app (`tech_common.py`),
so users need no configuration — the update source is **pinned** to those
embedded constants and can never be redirected by settings or by the repo's
`secret.json`. Every login does three verified things in one go:

1. Fetches `secret.json` (live accounts: email + PBKDF2 hash) from GitHub —
   credentials are never written to the user's PC. Entering your email in
   the first step self-registers / resets your password: the app generates a
   password, writes the PBKDF2 hash to the repo's `secret.json` (via the
   embedded write token), and emails it to you.
2. Pulls the latest `gelotech_database_v3.json`, verifies it, caches it for
   the session in the temp folder, and deletes it on app close / logout / the
   next login — so users always get the newest database with no manual
   intervention.
3. Checks `version.json` for a newer `banking_apps.json` and downloads it
   into the user's settings folder (version-based, same verification).

Every update is cryptographically verified before it is applied:

1. `version.json` must be signed — the app verifies `version.json.sig`
   against the embedded Ed25519 public key (`tech_common.py`), otherwise the
   update is rejected.
2. Each downloaded data file must match the signed SHA-256 hash listed inside
   `version.json`, otherwise that file is rejected. The signed hashes cover
   the exact bytes GitHub serves (`.gitattributes` enforces LF line endings).
   `secret.json` is exempt: it is the live accounts file maintained by the
   app itself.

To publish a data update:

1. Replace `gelotech_database_v3.json` (and/or `banking_apps.json`) and/or
   edit user hashes in `secret.json` at the repo root.
2. Run `python bump_version.py` (add `db` or `banking` to bump only one;
   `sign` to re-hash/re-sign without bumping). This computes the file
   hashes, writes `version.json`, signs it into `version.json.sig`, and
   commits + pushes both.
3. Users' apps fetch it automatically on their next login — and only if the
   signature and hashes verify.

To change a user's password, update the PBKDF2 hash in `secret.json`
(format `iters$salt$digest`, 100000 iterations) and run
`python bump_version.py sign`. Never use the legacy plain-SHA-256 format.

To ship a code change, edit the Python files, rebuild the exe (above), and
redistribute the new exe — code only changes when a new exe is built.

## Security notes

- Accounts are email-based, self-managed: the app generates PBKDF2 hashed
  passwords, persists them to the repo's `secret.json`, and emails them via a
  dedicated SMTP sender. Credentials are never stored on users' PCs. The
  Admin Panel shows the server-verified account list and can **Block /
  Unblock** any account — blocked accounts can't log in and can't request a
  new password (the `blocked` flag lives on the account in `secret.json`).
- Updates are signed (Ed25519): the manifest signature and per-file SHA-256
  hashes are verified before anything is applied, and the update source is
  pinned to the embedded constants in `tech_common.py`.
- The embedded GitHub tokens give this app access to this repo only: a
  read-only token for fetching and a write token (Contents read+write, this
  repo only) used solely to persist self-registered accounts. The SMTP sender
  is a dedicated low-privilege account. Rotate all three regularly — anything
  embedded in the exe can be extracted.
- The package database is only ever pulled fresh from the server per login
  (no bundled copy in the exe), so stale data is impossible.

## The package database

`gelotech_database_v3.json` is the single live database. The loader
(`tech_common.py::load_package_database`) maps its schema into internal
records: removal levels (`Recommended` / `Advanced` / `Expert` / `Unsafe`),
UAD warnings, GeloTech notes, and the `debloated` / exclusion flags. If the
file is missing it falls back to `gelotech_database_v2.json`.
