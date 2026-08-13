# Dashboard App Cleaner layout

The package list keeps app label and package ID in separate responsive columns. The existing debounced tree resize handler recalculates name, package, badge, and description widths from the actual Treeview width.

Long instruction banners wrap to their parent panel width. The root resize handler re-anchors the Dashboard phone log console and requests package-list relayout after maximize, resize, or monitor changes.

The layout fix does not change the native scrcpy mirror architecture.
