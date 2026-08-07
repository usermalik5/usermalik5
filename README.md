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
All, Disabled, and Filter.

## Download

**Latest release:** [GeloTechTool.exe (v1.0.0)](https://github.com/usermalik5/GeloTech-Tool/releases/latest)

Windows only. Download the exe and run it — no installation needed. The
built-in updater pulls database / banking-list / credentials updates
automatically from this repo on each login.

## What's in this folder

| Item | Purpose |
|---|---|
| `techtool.py` + `tech_*.py` | Application source (entry point: `techtool.py`) |
| `GeloTechTool.spec` | PyInstaller build spec (onefile, windowed) |
| `GeloTechTool_obf.spec` | PyInstaller spec for the PyArmor-obfuscated build (needs `build/pyarmor_out` from `pyarmor gen`) |
| `gelotech_database_v3.json` | **The package database the tool loads at runtime** (merged UAD + GeloTech data; user-app exclusions live here as per-package flags) |
| `banking_apps.json` | Banking apps exclusion list — banking apps are auto-protected (never cleaned/uninstalled, shown with a 🏦 badge, can be filter-excluded) |
| `secret.json` | Hashed login credentials only (users). Runtime state like excluded lists / debloated history lives in the user's local copy, which is merged on update, never replaced |
| `version.json` | Update manifest: bump `database` / `settings` / `banking` to publish a new release; carries the signed SHA-256 hashes of the data files |
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

Default login: `admin` / `admin123` (the default account is forced to change
its password on first login).

## Building the exe

Obfuscated build (requires PyArmor — re-runs `pyarmor gen` into
`build/pyarmor_out` before running `GeloTechTool_obf.spec`). **This is the
only supported release build** — obfuscation applies to all modules and all
release exes:

```bash
pyarmor gen -O build/pyarmor_out techtool.py tech_common.py tech_ui.py tech_settings.py tech_admin.py tech_secscan.py tech_secops.py tech_secops2.py tech_vtop.py tech_misc.py
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
`secret.json`. On every login the app checks
`version.json` in this repo and pulls a newer `gelotech_database_v3.json` /
`secret.json` / `banking_apps.json` into the user's settings folder,
overriding the bundled copies until the exe is rebuilt. The repo `secret.json`
only carries hashed user credentials — on download it is merged into the
user's local file, so local state (excluded lists, debloated history, update
tracking) is never wiped by an update.

Every update is cryptographically verified before it is applied:

1. `version.json` must be signed — the app verifies `version.json.sig`
   against the embedded Ed25519 public key (`tech_common.py`), otherwise the
   update is rejected.
2. Each downloaded data file must match the signed SHA-256 hash listed inside
   `version.json`, otherwise that file is rejected.

To publish a data update:

1. Replace `gelotech_database_v3.json` (and/or `secret.json` and/or
   `banking_apps.json`) at the repo root.
2. Run `python bump_version.py` (add `db`, `settings`, or `banking` to bump
   only one; `sign` to re-hash/re-sign without bumping). This computes the
   file hashes, writes `version.json`, signs it into `version.json.sig`, and
   commits + pushes both.
3. Users' apps download it automatically on their next login — and only if
   the signature and hashes verify.

Each downloaded file keeps a `.bak` of the previous copy in the settings
folder, so a bad update can be rolled back manually. A file that fails to
download is skipped and only the files that actually succeeded are recorded
in the update state, so failures are retried on the next check instead of
being skipped silently.

To ship a code change, edit the Python files, rebuild the exe (above), and
redistribute the new exe — code only changes when a new exe is built.

## Security notes

- Settings store salted PBKDF2 password hashes; the exe-side settings copy is
  marked as a hidden Windows file.
- Updates are signed (Ed25519): the manifest signature and per-file SHA-256
  hashes are verified before anything is applied, and the update source is
  pinned to the embedded constants in `tech_common.py`.
- The embedded GitHub token gives read-only access to this repo from the app
  (fine-grained, scoped to this repository). Write-capable tokens are never
  embedded.
- The default `admin` account is forced to change its password on first
  login; the password hint is not shown anywhere in the app.

## The package database

`gelotech_database_v3.json` is the single live database. The loader
(`tech_common.py::load_package_database`) maps its schema into internal
records: removal levels (`Recommended` / `Advanced` / `Expert` / `Unsafe`),
UAD warnings, GeloTech notes, and the `debloated` / exclusion flags. If the
file is missing it falls back to `gelotech_database_v2.json`.
