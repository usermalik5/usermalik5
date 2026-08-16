# GeloTechTool Documentation Index

This directory contains the subsystem guides for the current **PySide6 / Qt6** application. The official entry point is `tech_qt_app.py`.

## Documentation authority

```text
README.md
   ↓
user-facing behavior and supported workflows

PROCESS_GUIDE.md
   ↓
architecture, execution flow, testing and release process

AGENTS.md
   ↓
mandatory agent rules and documentation/release gates

QT6_MIGRATION_STATUS.md
   ↓
completed Qt6 migration record

QT6_MIGRATION_TASK.md
   ↓
historical migration specification / acceptance criteria

SECURITY.md
   ↓
security and authentication model

worker/README.md
   ↓
auth proxy routes, secrets and deployment
```

## Subsystem guides

| Guide | Covers |
|---|---|
| [`DASHBOARD_LAYOUT.md`](DASHBOARD_LAYOUT.md) | Qt Dashboard, phone mockup, App Cleaner table, description scrollbar and sidebar geometry |
| [`ICON_SYNC.md`](ICON_SYNC.md) | Automatic ADB icon export, per-device cache, fingerprints and Cleaner refresh |
| [`SCRCPY_GUIDE.md`](SCRCPY_GUIDE.md) | Native scrcpy embedding, phone-frame geometry, clipping and shutdown cleanup |

## Update rule

When a Qt subsystem changes its user-visible behavior, execution flow, ownership, packaging, or testing requirements:

1. Update the subsystem guide here under `docs/`.
2. Update `README.md` when the behavior is user-facing.
3. Update `PROCESS_GUIDE.md` when the architecture or workflow changes.
4. Update `AGENTS.md` when agent ownership or mandatory process changes.
5. Update `QT6_MIGRATION_STATUS.md` only when migration status/validation changes.
6. Keep `SECURITY.md` and `worker/README.md` synchronized for authentication or security changes.

## Verification

Before release, use the repository release workflow and make sure the documentation-sync gate passes. Do not claim documentation is synchronized when it still describes the old Tk UI or dead migration branch.
