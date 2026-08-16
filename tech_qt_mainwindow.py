        rows.sort(key=lambda x: x[0].lower()); self.table.setRowCount(len(rows))
        for r, (label, pkg, level, desc) in enumerate(rows):
            icon = self._cached_icon(pkg)
            for c, value in enumerate((label, pkg, level, desc)):
                item = QTableWidgetItem(str(value));
                if c == 0 and not icon.isNull(): item.setIcon(icon)
                self.table.setItem(r, c, item)
        self.cleaner_status.setText(f"{len(rows)} packages loaded. Horizontal scrollbar reads full descriptions.")

    def _cached_icon(self, package):
        from PySide6.QtGui import QIcon

        # Search both the per-device cache and shared cache. Cache restoration
        # mirrors icons into the shared directory, while fresh exports retain
        # them in the hashed per-device directory.
        roots = []
        if self.serial:
            roots.append(self._cache_dir_for(self.serial))
        roots.append(Path(get_cache_dir()))

        candidates = []
        for root in roots:
            candidates.extend((
                root / f"{package}.png",
                root / f"{package}.ico",
                root / "apk_icon_export" / f"{package}.png",
                root / "apk_icon_export" / f"{package}.ico",
            ))
            export_root = root / "apk_icon_export"
            if export_root.is_dir():
                candidates.extend(export_root.rglob(f"{package}.png"))
                candidates.extend(export_root.rglob(f"{package}.ico"))

        seen = set()
        for path in candidates:
            try:
                key = path.resolve()
            except OSError:
                continue
            if key in seen:
                continue
            seen.add(key)
            if path.is_file():
                icon = QIcon(str(path))
                if not icon.isNull():
                    return icon

        return load_icon("device-mobile")
