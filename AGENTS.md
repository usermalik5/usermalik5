# GeloTech Agent Rules — Qt6

## Before coding

1. Run `python scripts/agent_preflight.py`.
2. Read `README.md` and this file completely.
3. Read the relevant guide under `docs/` before touching a specialized subsystem.
4. Inspect the current Qt6 execution path and identify the root cause before editing.
5. Make the smallest correct change; do not add speculative retries or timing hacks.
6. Run compile/tests and review the full diff before committing.

## Current application architecture

- **Official UI:** PySide6 / Qt6, entry point `tech_qt_app.py`.
- `tech_qt_mainwindow.py` owns the Qt shell and login window.
- `tech_qt_themes.py` owns the Qt palette/font system.
- `tech_qt_icons.py` owns Tabler icon loading.
- `tech_qt_cleaner.py` owns Qt App Cleaner presentation.
- `tech_qt_iconsync.py` owns automatic device icon export/cache.
- `tech_qt_mirror.py` + `tech_qt_phone.py` + `tech_qt_bezel.py` own scrcpy embedding.
- Feature-specific Qt installers own Monitor, DNS, VirusTotal, Backup/Restore and ADB driver workflows.
- `tech_reg.py`, `tech_common.py`, `tech_database.py` and other shared modules retain non-UI responsibilities.

The legacy Tk files are historical/compatibility code. Do not use them as the current launch target unless the task explicitly concerns the legacy implementation.

## UI invariants

- Dashboard is the post-login landing page.
- The App Cleaner table remains `APP NAME | PACKAGE ID | UAD LEVEL | DESCRIPTION`.
- Long Description text remains readable with a **horizontal scrollbar**. Do not add a permanent description editor panel.
- The sidebar is compact and non-scrolling under the intended window geometry.
- The current visual reference uses restrained gray dark surfaces; themes may change accents but must keep the Qt surfaces consistent.
- `gelotech_icon.ico` is the app/login icon and the Qt PyInstaller icon.
- Use bundled Tabler SVG icons rather than emoji-only control icons.

## Device automation invariants

- ADB polling must drive the full transition: detection → package list refresh → icon sync/cache → App Cleaner refresh.
- The same connected serial must not trigger a full reload on every poll.
- Disconnect/reconnect must allow synchronization again.
- Icon sync is not successful until the visible Cleaner rows are refreshed.
- scrcpy must use the **existing single phone mockup**. Never create a second floating phone frame.
- scrcpy remains a native video surface; embedding/positioning belongs in the mirror subsystem.

See `docs/ICON_SYNC.md` and `docs/SCRCPY_GUIDE.md`.

## Security

Do not move account secrets into the client. Authentication and privileged account operations use the Cloudflare Worker at `AUTH_WORKER_URL`. Worker secrets stay server-side. Update integrity continues to use the signed manifest and SHA-256 verification.

See `SECURITY.md` and `worker/README.md`.

## Testing

Minimum:

```bash
python -m compileall -q .
python -m pytest -q
python tech_qt_app.py
```

Real-device checks are separate from mocked/no-device checks. Never claim real-device parity from a mocked test.

## Release and documentation gate

Production releases require the repository documentation to describe the current source. Before a release:

- Update `README.md` for user-visible behavior.
- Update `PROCESS_GUIDE.md` for architecture/process changes.
- Update `AGENTS.md` when rules/ownership/release requirements change.
- Update specialized `docs/*.md` when a subsystem changes.
- Keep `QT6_MIGRATION_STATUS.md` current when migration status or validation changes.
- Run the supported release workflow; do not bypass the documentation gate.

The gate checks current markers including **CTkThemesPack**, **UI Font**, **horizontal scrollbar**, **app icon**, and **automatic** behavior.

Production packaging must respect the configured PyArmor Trial source-size limit. If a source module is too large, split it into cohesive modules and update the release module lists; do not use an un-obfuscated production workaround.

## Documentation authority

1. `README.md` — user-facing truth.
2. `PROCESS_GUIDE.md` — architecture/process truth.
3. `AGENTS.md` — agent/release rules.
4. `docs/README.md` — subsystem documentation map.
5. `QT6_MIGRATION_STATUS.md` — migration history/status.

When these conflict with the source, stop and resolve the conflict instead of guessing.
