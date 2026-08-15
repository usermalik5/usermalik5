# Dashboard App Cleaner layout

The package list keeps app label and package ID in separate responsive columns. The existing debounced tree resize handler recalculates name, package, badge, and description widths from the actual Treeview width. The Description column is fixed wide (min 500 px) and the table gets a **horizontal scrollbar**, so the full description text is readable in place without a separate description panel.

Long instruction banners wrap to their parent panel width. The root resize handler re-anchors the Dashboard phone log console and requests package-list relayout after maximize, resize, or monitor changes. The sidebar USB-debugging / how-to banners wrap to the sidebar width.

The layout fix does not change the native scrcpy mirror architecture.
