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

## What's in this folder

| Item | Purpose |
|---|---|
| `techtool.py` + `tech_*.py` | Application source (entry point: `techtool.py`) |
| `GeloTechTool.spec` | PyInstaller build spec (onefile, windowed) |
| `GeloTechTool_obf.spec` | PyInstaller spec for the PyArmor-obfuscated build (needs `build/pyarmor_out` from `pyarmor gen`) |
| `gelotech_database_v3.json` | **The package database the tool loads at runtime** (merged UAD + GeloTech data; user-app exclusions live here as per-package flags) |
| `banking_apps.json` | Banking apps exclusion list — banking apps are auto-protected (never cleaned/uninstalled, shown with a 🏦 badge, can be filter-excluded) |
| `secret.json` | Hashed login credentials only (users). Runtime state like excluded lists / debloated history lives in the user's local copy, which is merged on update, never replaced |
| `version.json` | Update manifest: bump `database` / `settings` / `banking` to publish a new release |
| `bump_version.py` | Helper that bumps `version.json` and pushes the new manifest to the repo |
| `gelotech_icon.ico` | App icon (also embedded in the built exe) |

Build-time resources (ADB/fastboot tools, scrcpy zip, drivers, icon cache)
live in the local working folder and are excluded from the repo via
`.gitignore`; they are bundled into the exe at build time.

## Running from source

```bash
pip install customtkinter pillow requests pyinstaller
python techtool.py
```

Default login: `admin` / `admin123` (change it in the Admin Panel after
logging in).

## Building the exe

Obfuscated build (requires PyArmor — re-runs `pyarmor gen` into
`build/pyarmor_out` before running `GeloTechTool_obf.spec`):

```bash
pyarmor gen -O build/pyarmor_out techtool.py tech_common.py tech_ui.py tech_settings.py tech_admin.py tech_secscan.py tech_secops.py tech_secops2.py tech_vtop.py tech_misc.py
python -m PyInstaller GeloTechTool_obf.spec --noconfirm
```

Standard (non-obfuscated) build:

```bash
python -m PyInstaller GeloTechTool.spec --noconfirm
```

## Updating the app on other PCs

The update URL and GitHub token are embedded in the app (`tech_common.py`),
so users need no configuration. On every login the app checks
`version.json` in this repo and pulls a newer `gelotech_database_v3.json` /
`secret.json` / `banking_apps.json` into the user's settings folder,
overriding the bundled copies until the exe is rebuilt. The repo `secret.json`
only carries hashed user credentials — on download it is merged into the
user's local file, so local state (excluded lists, debloated history, update
tracking) is never wiped by an update.

To publish a data update:

1. Replace `gelotech_database_v3.json` (and/or `secret.json` and/or
   `banking_apps.json`) at the repo root.
2. Bump the matching `database` / `settings` / `banking` number in
   `version.json` — or just run `python bump_version.py` (add `db`,
   `settings`, or `banking` to bump only one).
3. Commit and push. Users' apps download it automatically on their next login.

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
- The embedded GitHub token gives read access to this repo from the app.
  Keep the repo private; if you ever share the exe publicly, replace the
  token in `tech_common.py` with a fine-grained read-only token scoped to
  this repository.

## The package database

`gelotech_database_v3.json` is the single live database. The loader
(`tech_common.py::load_package_database`) maps its schema into internal
records: removal levels (`Recommended` / `Advanced` / `Expert` / `Unsafe`),
UAD warnings, GeloTech notes, and the `debloated` / exclusion flags. If the
file is missing it falls back to `gelotech_database_v2.json`.
