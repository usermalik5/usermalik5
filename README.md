# GeloTechTool

Android debloating / security tool for Windows. Scans connected ADB devices,
classifies packages against the merged GeloTech + UAD database, and supports
debloating (disable / uninstall for user / restore), exclusion lists, APK
backup & restore, screen mirroring via scrcpy, VirusTotal scanning, popup
virus cleanup, and DNS-based ad blocking.

Access is protected by a login system with per-user permissions and tabs
(admin always has everything). Logs stream to a Matrix-style console, and
non-URL application hints appear in a red attention banner at the bottom of
the window. Website links remain clickable without a hover tooltip. The
package-list context menu (right-click) offers per-app actions plus batch
actions for all checked apps (disable / uninstall / APK backup / exclude).
Destructive batch actions ask you to type YES to confirm, and clicking a
color in the list legend filters the list to that group (click again to
reset). The toolbar keeps a single **Scan Bloatware** button (its menu
covers uninstalling by UAD recommendation level — Recommended / Advanced /
Expert / Unsafe), plus **Restore/Backup**, **Load Apps**, and **Advanced Filter**. A permanent legend in the sidebar explains the app
removal levels (Recommended = safe to remove, Advanced = mostly safe,
Expert = may break features, Unsafe = dangerous) and the list row colors
(green = removable, orange = clean excluded, red = uninstall excluded,
purple = both excluded) — rows in the app list follow the same color scheme,
and removal-level badges use the same colors. The sidebar header shows
`© 2026 GeloTech` with clickable links to Gsmcodeph.com and
facebook.com/gelotechxyz, and the title/tool name always shows the current
version (e.g. v1.0.9). The Dashboard tab shows a device mockup (phone image with the live log console
rendered inside its screen) on the left, with the App Cleaner UI on the right (a
scrollable list of installed apps with uninstall/disable/clear-data/exclude
actions, plus a small live device strip with model, Android version, storage,
and battery). **Refresh** and **Screen Mirror** sit under the phone.

After a successful login, the application always returns to the **Dashboard**
page regardless of the page that was previously selected. The Dashboard
phone mirror uses the native scrcpy stream embedded into the Dashboard phone
widget; the existing log console is temporarily hidden during mirroring and
restored when mirroring stops. The mirror compatibility layer retries log
restoration if Tk has not completed its geometry update yet.

Loading the app list is fast even without the phone plugged in: the first
successful scan caches the package list locally on the PC, later loads render
that cached list instantly and then refresh from the device in the background
(stale-while-revalidate), and any load falls back to the cache whenever the
phone is unreachable. List rows are rendered lazily in small batches so the UI
stays responsive with hundreds of apps loaded.

## Development workflow

Repository coding agents MUST run the preflight before every coding task:

```bash
python scripts/agent_preflight.py
```

The preflight verifies that `AGENTS.md` and `README.md` are present and
non-empty. **Passing the script does not replace reading them.** Agents must
read `AGENTS.md` completely and then read the relevant `README.md` sections
before modifying any code. They must inspect the current execution path,
identify the root cause before fixing bugs, run source-level verification, and
review the diff before committing.

For login/navigation changes, test `python techtool.py` directly as well as the
packaged EXE when an EXE is being built. A working EXE does not prove the source
execution path is correct, and a working source run does not prove the packaged
build is correct. Do not solve source navigation problems by relying only on
PyInstaller runtime hooks or startup timing when the underlying navigation code
can be fixed directly.

## Download

**Latest release:** [GeloTechTool.exe
(v1.7.0)](https://github.com/usermalik5/GeloTech-Tool/releases/latest)

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
| `scripts/agent_preflight.py` | Mandatory coding-agent preflight; verifies repository instructions are present before work begins |
| `scripts/release.py` | Repeatable source/test/PyArmor/PyInstaller release build; never commits or pushes |
| `requirements-dev.txt` | Lightweight development test dependency (`pytest`) |

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
After successful authentication, Dashboard is selected automatically.
Non-admin users get all tabs and tools (Cleaner, Monitor, DNS, all sidebar
actions); only the VirusTotal tab is reserved for the admin account.

## Building the exe

The supported release procedure is the release helper. It runs repository
preflight, Python compile checks, tests, PyArmor generation, and the
obfuscated PyInstaller build with verification gates:

```bash
python scripts/release.py
```

### PyArmor Trial size constraint

GeloTech uses the **PyArmor Trial** edition in the current build environment.
Treat the approximate **35 KB per-source-file limit as a hard production-build
constraint**.

- **32 KB or more:** review the module before adding more code; extract a
  cohesive responsibility when practical.
- **35 KB or more:** stop the production build and split the module into
  focused files before running PyArmor.
- Keep the size rule enforced in release tooling; documentation alone is not
  sufficient.
- If PyArmor reports a size/license error, the correct fix is modularization,
  not a non-obfuscated fallback.
- Update `scripts/release.py`'s `MODULES` list and
  `GeloTechTool_obf.spec` hidden imports whenever a module is split.

Expected release behavior:

```text
oversized source module
    ↓
release blocked
    ↓
exact file + byte size reported
    ↓
split cohesive functionality
    ↓
PyArmor obfuscation succeeds
    ↓
PyInstaller obfuscated EXE
```

A PyInstaller build that succeeds without successful PyArmor obfuscation is a
debug build only and must not be treated as a production artifact.

Manual build / debugging only — the release helper runs the same PyArmor +
PyInstaller sequence below; run these by hand only when debugging the build
itself (obfuscation applies to all modules and all release exes):

```bash
pyarmor gen -O build/pyarmor_out techtool.py techtool_core.py tech_common.py tech_ui.py tech_settings.py tech_settings_login.py tech_admin.py tech_reg.py tech_secscan.py tech_secops.py tech_secops3.py tech_secops2.py tech_secops4.py tech_bloatware.py tech_dash.py tech_vtop.py tech_misc.py tech_hardening.py tech_hardening_ops.py tech_dashboard_redesign.py tech_phone_mirror.py tech_phone_mirror_embedded.py tech_phone_mirror_host.py tech_phone_mirror_fix.py tech_phone_mirror_restore_patch.py tech_navigation.py tech_task_manager.py tech_database.py tech_phone_mirror/__init__.py runtime_hook_gelotech.py sitecustomize.py
python -m PyInstaller GeloTechTool_obf.spec --noconfirm
```

Standard (non-obfuscated) build — debugging only, **never distribute, never commit/push**:
(agents: only build this when the user explicitly asks for a debug build; the
supported production build is the obfuscated one from `python scripts/release.py`.
If PyArmor reports a size/license limit, split oversized source modules into
~35 KB files instead of falling back to this build.)

```bash
python -m PyInstaller GeloTechTool.spec --noconfirm
```

## Updating the app on other PCs

The update URL and GitHub token are embedded in the app (`tech_common.py`),
so users need no configuration — the update source is **pinned** to those
embedded constants and can never be redirected by settings or by the repo's
`secret.json`. Every login does three verified things in one go:

1. Fetches `secret.json` (live accounts: email + PBKDF2 hash) from GitHub —
   credentials are never written to the user's PC. Entering your email in the
   first step self-registers / resets your password: the app generates a
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
(format `iters$salt$digest`, 100000 iterations) and run `python bump_version.py sign`.
Never use the legacy plain-SHA-256 format.

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

## Fast development/release commands

Source smoke check:

```bash
python scripts/agent_preflight.py
python -m compileall -q .
python -m pytest -q
```

Agent environment check (Python, pytest, Ruff, BasedPyright, required files,
test discovery, syntax compilation — fast, no network, no app imports):

```bash
python scripts/agent_check.py
```

Lint / format check (Ruff is configured in `pyproject.toml`; do not reformat
the whole repo — fix findings incrementally):

```bash
python -m ruff check .
python -m ruff format --check .
```

Python language server: BasedPyright is configured in `pyproject.toml`
(`typeCheckingMode = "basic"`, excludes `build/`/`dist/`). Editors and OpenCode
with LSP enabled use it for go-to-definition, find-references, and diagnostics.

Release build:

```bash
python scripts/release.py
```

### Coding-agent tooling

`opencode.json` enables LSP for the project. Semantic code navigation
(go-to-definition / find-references / find-implementations over the code graph)
is provided by the `codebase-memory-mcp` server, which is already configured
globally. Filesystem and terminal access use OpenCode's built-in tools, GitHub
work uses the `gh` CLI plus `git`, and documentation lookup uses the built-in
web search/fetch tools. No extra MCP servers are required.

See the **Code intelligence** section in `AGENTS.md` for the preferred
navigation order before editing code.

The release helper performs repository preflight, Python compile checks, tests, PyArmor generation, and the supported obfuscated PyInstaller build. It does not commit, tag, or push anything automatically.
