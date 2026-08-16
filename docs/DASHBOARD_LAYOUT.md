# Dashboard and App Cleaner Layout

The current Dashboard is a **Qt6/PySide6** workspace. The official entry point is `tech_qt_app.py` and the main UI composition is owned by the Qt modules.

## Layout

- Fixed compact sidebar on the left.
- Large iPhone-style phone mockup on the Dashboard's left side.
- Native scrcpy is placed inside the existing phone display opening; no second phone mockup is created.
- Live logs belong to the Dashboard and remain visually associated with the phone area.
- Refresh and Screen Mirror controls sit with the phone workspace.
- App Cleaner occupies the main work area beside the phone.

## App Cleaner table

The table remains exactly four columns:

```text
APP NAME | PACKAGE ID | UAD LEVEL | DESCRIPTION
```

The **Description** column remains part of each table row. Long descriptions are readable using the table's **horizontal scrollbar**. Do not add a large always-visible description editor beneath the table.

The App Cleaner also keeps Search, Select All, filtering/legend controls, Refresh, Scan Bloatware, Restore/Backup, Load Apps and Advanced Filter, plus per-row and batch actions.

## Responsive behavior

The Qt layout should preserve compact spacing while resizing the main content. The sidebar should remain dense and non-scrolling for normal window sizes. Guide text wraps within its available panel.

The layout must not change the native scrcpy ownership model. See [`SCRCPY_GUIDE.md`](SCRCPY_GUIDE.md).
