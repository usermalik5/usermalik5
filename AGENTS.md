# Project Instructions

- Whenever a major change is made to the source code, update `README.md` accordingly before committing.
- When a major change is made to the source code, also update `PROCESS_GUIDE.md` (the process tree visual guide) when necessary — e.g. new modules, changed architecture, changed update/release flow, or new data locations.

## Security & Release Rules (DO NOT VIOLATE)

1. **OBFUSCATION APPLIES TO ALL CODE AND ALL BUILDS.** Every release exe MUST be built from the PyArmor-obfuscated spec (`GeloTechTool_obf.spec`), never the plain `GeloTechTool.spec`. Before building, ALWAYS re-run `pyarmor gen` over **every** Python module in the project (techtool.py + ALL `tech_*.py` files) so new/changed code is always obfuscated. Never ship an un-obfuscated exe. Because obfuscation hides imports from PyInstaller's static analysis, ANY new import (stdlib or 3rd-party) in a `tech_*.py` module MUST also be added to `hiddenimports` in `GeloTechTool_obf.spec` — otherwise the exe crashes at startup with `ModuleNotFoundError`.
2. **UPDATE MANIFESTS ARE SIGNED.** Every data release MUST be published with `python bump_version.py` (or `--no-commit` first to stage files). It computes SHA-256 of the data files, writes them into `version.json`, and writes the Ed25519 signature into `version.json.sig`. The app refuses unsigned/tampered updates (verifies against `tech_common.py::UPDATE_SIGN_PUBLIC_KEY`). Never edit `version.json` or data files without re-signing, and never commit `version.json.sig` without a matching `version.json`. Signed hashes MUST cover the exact bytes GitHub serves — `.gitattributes` forces `eol=lf` for `*.json` and `version.json.sig`; if you renormalize or touch line endings, re-sign.
2b. **DATABASE EDIT => RE-SIGN IMMEDIATELY, IN THE SAME COMMIT SESSION.** Whenever `gelotech_database_v3.json` (or `banking_apps.json`) is modified in ANY way — adding/removing/editing packages, enrichment, reordering, reformatting (e.g. changing `indent`), line-ending renormalization — the sha256 in `version.json` goes stale and EVERY user login fails hard (the app verifies the DB hash on login and refuses to proceed on mismatch). NEVER commit/push a modified data file alone. ALWAYS run `python bump_version.py sign` (re-hash + re-sign + push) in the SAME work session, BEFORE telling the user anything is done, and verify the new hash landed on GitHub (commit includes both `version.json` and `version.json.sig`). This includes local-only edits: the manifest on GitHub MUST match the file GitHub serves, so after any local data edit, `sign` must be run and pushed. If you ever see "MISMATCH" between the local DB sha256 and `version.json`, stop and fix it before anything else.
3. **UPDATE SOURCE IS PINNED.** The app only ever fetches from `EMBEDDED_UPDATE_URL` / `EMBEDDED_UPDATE_TOKEN` in `tech_common.py`. Never re-introduce `update_url`/`update_token` overrides from settings or from the repo's `secret.json`.
4. **GITHUB-ONLY DATA, NO LOCAL CREDENTIALS.** User accounts (`secret.json`) and the package database (`gelotech_database_v3.json`) are NEVER stored locally or bundled into the exe. Both are fetched from the pinned update server on every login (manifest signature + DB sha256 verified); the DB is cached for the session and deleted on app close/logout/next login. `secret.json` is the LIVE accounts file: users self-register by entering their email, the app generates a PBKDF2 password, writes it back to the repo via the embedded write token, and emails it via the embedded SMTP sender. Accounts carry an optional `blocked: true` flag (set from the Admin Panel) that denies login AND password requests. `secret.json` is therefore NOT covered by the signed manifest (database + banking list are). Passwords must stay PBKDF2 (`iters$salt$digest`) — never legacy plain SHA-256.
5. **SECRETS.** The signing private key (`%USERPROFILE%\.gelotech_signing\update_ed25519.pem`) must NEVER be committed or copied into the repo. The embedded write token (`EMBEDDED_UPDATE_WRITE_TOKEN`) and SMTP app password are extractable from the exe by a determined attacker — they MUST be scoped/rotated: write token = fine-grained, Contents Read+Write, THIS repo only; SMTP = dedicated low-privilege sender account with an app password. Never embed your personal account credentials. Admin access in the app is gated by the `ADMIN_SECRET_PHRASE` (login screen) + the PBKDF2 admin password — never change the admin password to a weak/default value.
6. **VERSION BUMP EVERY RELEASE — KEEP EVERY UI VERSION IN SYNC.** Bump `APP_VERSION` in `tech_common.py` before every build and make the release tag match `v<APP_VERSION>` exactly. It MUST drive EVERY user-facing version label: the login window title (`GeloTech Tool v{APP_VERSION} - Login`), the login header (`TECH TOOL v{APP_VERSION}`), the main window title, and the sidebar tool name. Never hardcode a version string (e.g. `v1.0`) in any UI element — all of them must read from `APP_VERSION` so they stay in sync automatically. Also update the README download link to the new version and delete older releases so only the latest remains.
6b. **PYARMOR FILE-SIZE LIMIT — SPLIT OVERSIZED MODULES.** The PyArmor license (org/trial) fails with `ERROR out of license` when a single script exceeds roughly 34-36KB of source. Safe rule: keep EVERY Python module under ~30KB (measure with `len(open(f, encoding='utf-8').read().encode('utf-8'))`). When a module grows too big, split it: move a batch of methods into a new `tech_*X.py` module with a new mixin class (e.g. `SecOps3Mixin`), add the import + mixin to `techtool.py`, and add the new module to `hiddenimports` in `GeloTechTool_obf.spec` and to the `pyarmor gen` command in `README.md`. This has been done before: `tech_secops.py`→`tech_secops3.py`, `tech_secops2.py`→`tech_secops4.py`. Do NOT switch obfuscators (pyobfuscate.com has no API — browser only — and uploading source with the embedded GitHub tokens to a third party is a security risk).
7. **TEST THE APP BEFORE BUILDING AND PUSHING.** Before building the exe and pushing to GitHub, run the app (`python techtool.py` or the built exe) and verify at minimum: (a) it starts with no traceback/exception output, (b) the login window appears, (c) the app list renders all rows without exceptions (load the package list and confirm the count label matches the number of visible rows), and (d) the sidebar renders fully with no clipped widgets. Fix any exception first, then re-test, then build + release. Never push a version you have not tested.
8. **LOCAL RUNTIME SETTINGS ARE `exclusions.json`, NEVER `secret.json`.** The local runtime state (clean/uninstall exclusions, debloated history, update_state) lives in `%APPDATA%\GeloTechTool\exclusions.json` and is dropped next to the exe on login as `exclusions.json` (`_drop_settings_copy`). The name `secret.json` is RESERVED for the live accounts file on GitHub — never use it for local settings, never write it into the app/exe folder, and never let local settings overwrite the repo's `secret.json`. `_migrate_settings` converts any legacy local `secret.json`/`gelotech_settings.json` that contains runtime state (and NO `users` key) into `exclusions.json`, and must never delete a file containing the `users` key.

## Build Exe Agent

---
description: Execute a task with strict boundary enforcement and concise output
agent: build exe
---
### Operating Constraints
1. DO NOT write or edit files if any ambiguities exist—ask clarifying questions FIRST.
2. Suppress step-by-step internal reasoning and verbose thought logs in your final answer.
3. Keep response output focused strictly on the final summary format.

---
### Task
$ARGUMENTS

### Project Rules
- Follow existing project style guidelines and architectural patterns.
- Do not introduce external dependencies without explicit review.

### Strict Guardrails (DO NOT ALTER)
- Do not modify files outside the immediate scope unless strictly necessary.

---
### Required Output Format
Provide output strictly matching this layout:
1. **Status / Questions**: (Clarifying questions if stuck, or confirmation if clear)
2. **Planned / Changed Files**:
3. **Verification Command Executed**:
4. **Open Items for Human Review**:

# CRITICAL DEVELOPMENT RULES — ROOT CAUSE FIRST

## 1. STOP GUESSING — INSPECT FIRST

Before modifying code for a bug or feature:

1. Inspect the existing implementation and execution path.
2. Identify the actual external component involved.
3. Reproduce or inspect the failure.
4. Determine the root cause.
5. Only then implement a fix.

Do NOT repeatedly change coordinates, delays, window positions, colors, sizes, or retry counts when the underlying component is not functioning.

If the same approach fails twice, STOP and reconsider the architecture.

Never claim a feature is working because a unit/fake test passes if the real external application has not been successfully tested.

## 2. REAL IMPLEMENTATION > MOCK TEST

Tests using fake processes, fake HWNDs, mocked subprocesses, or simulated windows are useful for regression testing, but they do NOT prove that a Windows GUI integration works.

For features involving scrcpy, ADB, Win32 windows, SDL windows, native processes, device connections, or external executables, distinguish explicitly between:

- Automated/unit/integration tests using mocks or simulated components.
- Real-process tests using the actual executable.
- Real-device tests using the actual connected Android device.

A feature must NOT be declared complete until the real implementation has been tested whenever the required hardware/software is available.

## 3. SCRCPY MUST REMAIN THE VIDEO RENDERER

GeloTech screen mirroring MUST use the actual native scrcpy video stream.

DO NOT implement mirroring using screenshots, PIL frame capture, ImageGrab, OpenCV screen capture, repeated screenshots, JPEG/PNG frame loops, converting screenshots to Tk images, video re-encoding, or fake/mock video in production.

The intended flow is:

    Android device
         |
        ADB
         |
       scrcpy
         |
    native video window
         |
    GeloTech native host/container
         |
    iPhone frame presentation

## 4. DO NOT USE A TWO-WINDOW Z-ORDER HACK AS THE PRIMARY ARCHITECTURE

Do not solve the mirror by creating unrelated top-level windows and repeatedly forcing their Z-order every few milliseconds.

Avoid an architecture where a top-level scrcpy window and a separate topmost transparent overlay are kept synchronized by repeated `SetWindowPos(... TOPMOST ...)` calls and sleeps.

Prefer a native Windows host/container relationship where practical. If a separate-window architecture is required, document why and prove it is stable with the real scrcpy executable.

## 5. DO NOT ASSUME SCRCPY'S HWND

Never assume the scrcpy title alone, the `Popen()` PID alone, or the first visible window belonging to a PID identifies the renderer window.

Account for process startup delay, SDL window creation, child processes, actual window title, executable/process ownership, visibility, process exit, and multiple windows.

If the window cannot be found, STOP and inspect the actual scrcpy log. Do not merely increase the timeout repeatedly.

## 6. SCRCPY FAILURE MUST SHOW THE REAL ERROR

Whenever scrcpy fails to create/show its window, collect and report:

- exact command line used
- executable path
- ADB executable path
- device detection state
- scrcpy exit code
- stdout/stderr where available
- scrcpy log file path
- relevant final log lines

Never reduce a real failure to `scrcpy window not found`; that is a symptom, not a root cause.

## 7. VERIFY SCRCPY INDEPENDENTLY BEFORE DEBUGGING EMBEDDING

Before debugging HWND embedding, verify that the exact bundled scrcpy executable and ADB path used by GeloTech can independently start a live mirror against the connected device.

Debug in this order:

    ADB/device detection
          -> scrcpy startup
          -> scrcpy video window
          -> native embedding/hosting
          -> geometry/DPI
          -> iPhone frame/clipping
          -> input
          -> resize/lifecycle

Do not debug a later layer while an earlier layer is broken.

## 8. NEVER HARD-CODE DYNAMIC DISPLAY COORDINATES

Do not assume fixed values such as `x=280`, `y=12`, `width=368`, `height=800` when the phone is inside a DPI-scaled CustomTkinter UI.

Derive geometry from the actual phone widget/window and account for CustomTkinter scaling, Windows DPI scaling, window resizing, screen resolution, and dashboard layout changes.

Log the calculated phone position/size, image scale, display cutout position/size, scrcpy HWND position/size, overlay HWND position/size, and DPI scale when debugging alignment.

## 9. DO NOT BLOCK TKINTER

scrcpy process management and Win32 monitoring may run on worker threads, but Tk/CustomTkinter widget operations MUST run on the Tk main thread. Use `self.after(...)` to marshal UI changes back to Tk. Do not directly modify Tk widgets from background threads.

## 10. DO NOT HIDE FAILURE WITH RETRIES

Retries are acceptable for known transient conditions. They are NOT a substitute for diagnosis.

Bad approach: repeatedly retrying, moving windows, sleeping, and forcing TOPMOST without collecting new evidence.

Good approach: detect failure, collect diagnostics, identify root cause, then retry only if the failure is known to be transient.

## 11. AFTER TWO FAILED ATTEMPTS, STOP AND RECONSIDER

If two materially different attempts fail, STOP making another variation of the same approach.

Review what the attempts had in common, identify the shared assumption that may be wrong, inspect logs/processes/windows, and consider an architectural change.

For example, if repeated attempts to position a separate scrcpy top-level window fail, do not keep changing x/y, delays, TOPMOST, window size, or retry intervals. Investigate actual window creation and consider native embedding/hosting.

## 12. NEVER DECLARE SUCCESS FROM APPEARANCE OR TEST COUNT ALONE

For screen mirroring, success requires all of the following where applicable:

- real scrcpy process running
- real device connected
- real live video visible
- video inside the correct phone screen
- no rectangular/sharp edges
- correct rounded clipping
- mouse input reaches the device
- keyboard input reaches the device where applicable
- resize remains aligned
- Dashboard remains responsive
- stopping mirror cleans up scrcpy
- restarting mirror works
- disconnect/reconnect does not leave orphan processes
- no screenshot/frame-copy implementation

Always report separately:

    Automated tests: PASS/FAIL
    Real scrcpy test: PASS/FAIL
    Real device test: PASS/FAIL

Do not collapse mocked tests into a single feature `PASS`.

## 13. PRESERVE WORKING CODE

Before changing a working subsystem, inspect its current behavior and minimize unrelated changes. Do not rewrite unrelated Dashboard functionality or remove working features just to simplify the implementation.

For experimental architectural changes, use a separate branch or clearly isolated commit when practical.

## 14. WHEN STUCK, REPORT FACTS

If the implementation cannot be completed, report:

- what works
- what fails
- exact error
- relevant logs
- what was tested
- what assumptions were disproven
- what remains unknown

Do NOT keep making speculative changes just to produce a successful-looking result.

## 15. NO-LOOP RULE

After every failed implementation attempt, identify what NEW evidence was obtained. If no new evidence was obtained, do not make another speculative change.

The goal is to solve the root cause, not accumulate patches.

For external GUI integrations, always verify the external application independently before debugging the integration layer.
