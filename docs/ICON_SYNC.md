# Automatic Device Icon Synchronization

The Qt6 icon pipeline is owned by `tech_qt_iconsync.py` and is triggered by the existing ADB device monitor.

## Automatic flow

```text
authorized device detected
        ↓
package list/device fingerprint
        ↓
valid per-device cache?
   ├─ yes → restore cached PNGs → refresh App Cleaner
   └─ no  → verify/install ApkIconHelper.apk
              ↓
           launch automatic export
              ↓
           wait for export completion
              ↓
           adb pull export
              ↓
           locate packages.jsonl / icon files
              ↓
           store package PNGs in cache
              ↓
           refresh App Cleaner
```

The importer accepts both the legacy flat `icon_cache` layout and nested ADB-pulled export layouts. `adb pull` failures are treated as failures; a successful helper launch alone is not reported as a successful icon sync.

## Cache

Per-device data is stored under the user settings area using a hash of the device serial. The cache records the package fingerprint, icon count, manifest and PNG files. If the same device reconnects and its fingerprint still matches, GeloTech restores the cache instead of exporting again.

A disconnect clears the in-session seen-device state so a reconnect can trigger synchronization. Automatic icon synchronization waits when multiple authorized devices make the target ambiguous.

## Important UI rule

Icon synchronization is not complete until the visible App Cleaner rows are refreshed. A populated cache without a table refresh is considered an integration bug.

## Related

- [`DASHBOARD_LAYOUT.md`](DASHBOARD_LAYOUT.md)
- [`SCRCPY_GUIDE.md`](SCRCPY_GUIDE.md)
- [`../PROCESS_GUIDE.md`](../PROCESS_GUIDE.md)
