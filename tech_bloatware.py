# -*- coding: utf-8 -*-
"""Bloatware filter behavior.

Scan Bloatware is intentionally independent of whichever package-list mode is
currently visible. A UAD level scan always refreshes the complete installed
package set from the connected device, then filters that set by the requested
UAD removal level.
"""

import subprocess
import threading


class BloatwareFilterMixin:
    def _sec_build_complete_package_entries(self, installed):
        labels = self._load_app_labels()
        uad = self._build_uad_lookup()
        clean_excluded = self._load_excluded_clean()
        uninstall_excluded = self._load_excluded_uninstall()

        # A package returned by pm list packages -3 is a user/third-party app;
        # everything else in the complete list is treated as system/OEM.
        user_packages = set()
        try:
            result = subprocess.run(
                [self.scrcpy_adb, "shell", "pm", "list", "packages", "-3"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
            )
            user_packages = {
                line[len("package:"):].strip()
                for line in result.stdout.splitlines()
                if line.startswith("package:")
            }
        except Exception:
            pass

        existing = {entry.get("id"): entry for entry in getattr(self, "sec_packages", []) or []}
        entries = []
        for package_id in sorted(set(installed)):
            record = uad.get(package_id, {})
            old = existing.get(package_id, {})
            entries.append({
                "id": package_id,
                "label": labels.get(package_id, old.get("label") or self._resolve_label(package_id)),
                "system": package_id not in user_packages,
                "excluded_clean": package_id in clean_excluded,
                "excluded_uninstall": package_id in uninstall_excluded,
                "threat_level": old.get("threat_level", 0),
                "threat_labels": list(old.get("threat_labels", [])),
                "removal": record.get("removal", old.get("removal", "")),
                "description": record.get("description", old.get("description", "")),
                "risk": record.get("risk", old.get("risk", "unknown")),
                "category": record.get("category", old.get("category", "Other")),
                "manufacturer": record.get("manufacturer", old.get("manufacturer", "Unknown")),
                "source": record.get("source", old.get("source", "Unknown")),
            })
        return entries

    def _sec_action_recommendation(self, level):
        if not self._can("cleaner"):
            self._sec_status("Permission denied: Adware Remover is disabled for this account.", "#e74c3c")
            return

        if getattr(self, "sec_removal_filter", None) == level:
            self.sec_removal_filter = None
            self.after(0, self._sec_render_rows)
            self._sec_status("\U0001f4e6 Level filter cleared — showing all loaded apps.", "#58a6ff")
            self._sec_log(f"[GeloTech] List filter removed (UAD '{level}' level).", "#8b949e")
            return

        def worker():
            try:
                installed = self._sec_get_packages(force=True)
                if not installed:
                    self.after(0, lambda: self._sec_status(
                        "⚠ No installed packages found. Connect/authorize the device and try again.",
                        "#f39c12",
                    ))
                    return
                entries = self._sec_build_complete_package_entries(installed)
                matches = [entry for entry in entries if entry.get("removal") == level]

                def apply_results():
                    if not matches:
                        self._sec_status(f"No apps at the '{level}' removal level on the connected device.", "#f39c12")
                        return
                    self.sec_packages = entries
                    self.sec_list_mode = "all"
                    self.sec_removal_filter = level
                    self.sec_legend_filter = None
                    for _mode, (_dot, lbl) in getattr(self, "sec_legend_widgets", {}).items():
                        lbl.configure(text_color="#8b949e", font=self._font(size=9))
                    self._sec_render_rows()
                    count = self._sec_check_level(level)
                    self._sec_show_level_actions(level, len(matches))
                    self._sec_status(
                        f"\U0001f50e Scanned complete device package list: {count} '{level}' app(s) found and checked.",
                        "#58a6ff",
                    )
                    self._sec_log(
                        f"[GeloTech] Scan Bloatware: complete device scan found {count} app(s) at UAD '{level}' level.",
                        "#58a6ff",
                    )

                self.after(0, apply_results)
            except Exception as exc:
                self.after(0, lambda: self._sec_status(f"⚠ Bloatware scan failed: {exc}", "#e74c3c"))
                self.after(0, lambda: self._sec_log(f"[GeloTech ERROR] Bloatware scan: {exc}", "#e74c3c"))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _font(size=9):
        try:
            import customtkinter as ctk
            return ctk.CTkFont(size=size)
        except Exception:
            return None
