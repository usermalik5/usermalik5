# GeloTech Tool — Migrate UI from customtkinter (Tkinter) to Qt6 / PySide6

You are working inside the repository `C:\Users\poijlojo\Documents\GitHub\GeloTech-Tool` on the existing branch **`qt6-migration`** (already created). Do NOT switch to `main`, do NOT merge this branch into `main`, and do NOT push without being asked. Work only on `qt6-migration`.

Read the existing code thoroughly before changing anything. This is a *migration*, not a rewrite from scratch: the goal is a feature-identical Qt6 app that reuses as much existing non-UI logic as possible.

---

## 1. The app today (customtkinter / Tkinter)

GeloTech Tool is a Windows desktop tool for managing an Android phone over ADB. UI is customtkinter + `tkinter.ttk`. Key modules (all in repo root):

- `techtool.py` (677 lines) — main window, sidebar navigation, top-level wiring.
- `tech_common.py` (487 lines) — NON-UI core: UTF-8 subprocess wrappers, `get_bundle_dir()`, `get_app_dir()`, `get_settings_dir()`, `get_live_database_path()`, `Tooltip`, `load_package_database()`, `APP_VERSION`, `THEME`, `THEMES`, `COLOR_SWAP`, `CANONICAL_DARK`, icon-cache helpers, Ed25519 update verification, `AUTH_WORKER_URL`. **This must be preserved as-is** (it only imports `customtkinter` at the top for two module-level lines — see §4).
- `techtool_core.py` (309 lines) — application logic that must be preserved.
- `tech_themes.py` (488 lines) — theme engine: `THEME_DIR`, `DEFAULT_THEME`, ~18 palettes, 22 UI fonts, `apply_ctk_theme()`, `recolor_existing_widgets()`. Port the palette/font data to Qt QSS.
- `tech_ui.py` (412 lines), `tech_settings.py`, `tech_settings_login.py`, `tech_admin.py`, `tech_reg.py` (login/registration/admin).
- `tech_secscan.py`, `tech_secops.py`, `tech_secops2.py`, `tech_secops3.py`, `tech_secops4.py` — security scan, app list (ttk.Treeview with per-row app icons), bloatware filtering.
- `tech_bloatware.py` (118 lines) — bloatware filter mixin.
- `tech_dash.py` — Dashboard (uses phone PNG images from `assets/`).
- `tech_vtop.py` — "Monitor Running Apps" live view.
- `tech_misc.py` — misc + log viewer.
- `tech_hardening.py`, `tech_hardening_ops.py` — hardening, patches `action_sec_show_icons`.
- `tech_phone_mirror.py` (+ `_host.py`, `_embedded.py`, `_fix.py`, `_restore_patch.py`) — scrcpy mirroring; embeds scrcpy's window.
- `tech_navigation.py` (196 lines) — `NavigationController` for page switching.
- `tech_task_manager.py` (62 lines), `tech_database.py` (55 lines).

Non-UI modules that need NO migration (import unchanged): `tech_common.py` (after §4 fix), `techtool_core.py`, `tech_database.py`, `tech_bloatware.py`, `tech_secops4.py` logic parts, ADB/worker/scrcpy logic in every module.

### Build system
- Obfuscation: PyArmor (`pyarmor gen`). PyInstaller spec: `GeloTechTool_obf.spec` — bundles `assets`, `themes`, `scrcpy-win64-v3.3.4.zip`, `ApkIconHelper.apk`, `banking_apps.json`, `gelotech_icon.ico`, `tech_phone_mirror.py`. The `assets` datas entry already bundles `assets/icons/tabler/` — do not remove it.
- Release flow: `scripts/release.py` (has gates; the doc-sync gate and preflight must keep passing — see §8).

---

## 2. Required outcome

A PySide6 (Qt 6, installed as `PySide6 6.11.1`, Python 3.14) version of the app that:
1. Boots and shows the same features: login/registration, Dashboard, Monitor Running Apps, Block Ads DNS, VirusTotal, Screen Mirror (scrcpy), reboot to recovery/fastboot, re-authorize ADB, fix/downlaod ADB drivers, Accounts (admin panel), Logout, security scan / app list / bloatware, task manager, settings, log viewer.
2. Uses **Qt-native SVG icons** loaded from `assets/icons/tabler/` (see §3) everywhere the old UI used emoji glyphs in the sidebar/buttons.
3. Preserves the dark theme + theme-picker behavior (18 palettes, 22 fonts) via Qt QSS.
4. Loads Tabler SVGs as icons with Qt's native SVG support (QIcon/SvgIconEngine). Do NOT use cairosvg/svglib (broken/unavailable on this machine).

---

## 3. Tabler icons — MANDATORY

The repo now contains a curated Tabler icon subset (MIT licensed) at:

- `assets/icons/tabler/outline/*.svg` (184 icons)
- `assets/icons/tabler/filled/*.svg` (26 icons)

These are bundled into the EXE automatically. **The Qt UI must use these icons.** Implementation requirements:

- Build a small Qt icon helper (e.g. `tech_qt_icons.py`) that resolves `assets/icons/tabler/` correctly in both source mode (`os.path.dirname(os.path.abspath(__file__)) + "/assets/icons/tabler"`) and frozen EXE mode (`sys._MEIPASS + "/assets/icons/tabler"`) — mirror the pattern already used by `tech_themes.THEME_DIR`.
- Provide `load_icon(name, size=20, weight="outline") -> QIcon` with a cached renderer; support tinting to the current theme accent color if straightforward (QPainter recoloring), but a working uncolored icon is acceptable first.
- Replace the sidebar emoji icons in the Qt main window with the matching Tabler icons. Suggested mapping (all verified to exist in `outline/`): Dashboard→`dashboard`, Monitor Apps→`search` (or `activity`), Block Ads DNS→`globe`, VirusTotal→`virus`, Screen Mirror→`device-mobile`, Reboot→`refresh`, Re-authorize ADB→`plug-connected`, Fix/Download Drivers→`tool`, Accounts→`key`, Logout→`logout`, plus `shield-check`, `scan`, `eye`, `settings`, `user`, `battery`, `wifi`, `bluetooth`, `trash`, `folder`, `database`, `server`, `cpu`, `terminal`, `alert-triangle`, `info-circle`, `check`, `x`, `lock`, `power`, `login`.
- The `filled/` weight is available for emphasis states (active tab, warnings).

---

## 4. tech_common.py compatibility (read this before touching it)

`tech_common.py` has exactly TWO module-level customtkinter calls that will crash without Tkinter:
- `ctk.set_appearance_mode("Dark")`
- `ctk.set_default_color_theme(os.path.join(_tthemes.THEME_DIR, f"{_tthemes.DEFAULT_THEME}.json"))`

Do NOT delete or refactor the rest of `tech_common.py`. Minimal change allowed: guard those two lines so they are a no-op when Qt is being used, or move them behind a `if not QT_MODE:` check. Everything else (`get_bundle_dir`, `subprocess` wrappers, `THEME`, `THEMES`, icon-cache, update verification, `AUTH_WORKER_URL`) stays exactly as-is. If you must import `customtkinter` lazily for anything, keep it optional so the Qt build does not require customtkinter.

`tech_themes.py` similarly imports customtkinter — port its palette/font data into a Qt QSS theme module rather than importing the CTk one.

---

## 5. Suggested architecture for the Qt app

- `tech_qt_app.py` — `QApplication` entry point, sets Qt dark style + QSS, loads fonts, starts `MainWindow`.
- `tech_qt_mainwindow.py` — `QMainWindow` with left sidebar (`QListWidget` or buttons with `QIcon` from §3) + `QStackedWidget` for pages, replicating the sidebar layout/grouping (PAGES / DISPLAY / POWER / CONNECTION / SESSION) and the USB debugging + how-to hint labels.
- `tech_qt_icons.py` — icon loader (§3).
- `tech_qt_themes.py` — port of the 18 palettes + 22 fonts from `tech_themes.py` to QSS.
- One Qt page widget per screen, reusing the existing non-UI logic classes (e.g. `BloatwareFilterMixin`, `DatabaseService`, hardening patch mixins). Where the old code reached into `self` (the CTk app object) for shared state, introduce a small shared context object passed to each page.
- Threading: use Qt signals/`QThread`/`QTimer` for the polling screens (Monitor Apps, task manager, icon sync) instead of `threading` + `root.after`.
- Mirror: keep `tech_phone_mirror*.py` scrcpy spawning logic; embed the scrcpy window via `QWindow::fromWinId` (`QWidget.createWindowContainer` + foreign window) or fall back to launching scrcpy in its own window exactly like today if embedding is too risky. Preserve the existing behavior of auto-open ~5s after connect and never auto-stopping the mirror.

---

## 6. Feature-parity checklist (verify each against the old app)

- [ ] Login + registration + password reset (uses `AUTH_WORKER_URL` worker) works.
- [ ] Admin "Accounts" panel (permission-gated buttons).
- [ ] Dashboard renders phone PNG (`assets/tech_dash_images/iPhone17_P_PM_CosmicOrange@2x.png` + overlay) — reuse existing paths.
- [ ] Security scan app list: ttk.Treeview-equivalent (`QTableWidget`/`QTreeView`) with per-row app icons from the device icon cache; refresh, filter All/User/System/Disabled, Advanced Filter, Scan Bloatware, right-click row actions.
- [ ] Monitor Running Apps live view (QTimer refresh).
- [ ] Block Ads DNS, VirusTotal, task manager.
- [ ] Screen mirror (scrcpy) + mirror log restore behavior.
- [ ] Reboot recovery/fastboot, re-authorize ADB, fix/download ADB drivers.
- [ ] Theme picker (palette + UI font) via a Qt settings dialog.
- [ ] App Cleaner with four-column table + horizontally scrollable descriptions (matches current README behavior).
- [ ] Auto per-device icon cache (`icon_cache/<sha256(serial)[:32]>`) restore on re-connect.

---

## 7. Dependencies & environment

- Python 3.14 at `C:\Users\poijlojo\AppData\Local\Programs\Python\Python314\python.exe`.
- PySide6 6.11.1 already installed. Do not pin/install cairosvg or svglib.
- `requirements-dev.txt` has pytest/ruff/basedpyright — keep using them.
- Add PySide6 to a new `requirements-qt.txt` (e.g. `PySide6>=6.11,<7`).

---

## 8. Verification required before you call the task done

1. `python -m compileall -q .` passes.
2. App boots from source: `python techtool_qt.py` (or your entry point) opens the Qt window with the Tabler icons visible in the sidebar, from a clean working directory (e.g. the temp dir) with NO `themes/` in CWD — this guards against the CWD-relative-path class of bug.
3. `python -m pytest -q` still passes (non-UI tests must not break).
4. Run `ruff check` and `basedpyright` on any new/modified files.
5. Run `scripts/release.py`'s preflight/verify gates if feasible; if a gate fails for a reason directly caused by the migration, report it explicitly rather than silently editing the gate.
6. Report a written migration summary: what was ported, what was left for later (if anything), and exact commands to boot the Qt app.

Do not commit unless I explicitly ask. If you need to commit to checkpoint progress, ask first and commit ONLY on `qt6-migration` with a message prefixed `qt6: `. Never touch `main`.