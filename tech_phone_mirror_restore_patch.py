"""Source-tree compatibility patch for Dashboard log restoration.

The native mirror can terminate from a worker thread. Tk widgets must only be
remapped from the Tk main thread, and a transient geometry race can otherwise
leave the existing Dashboard log unmapped. This patch keeps the existing
widget and retries until Tk reports that it is mapped.
"""


def install():
    try:
        import tech_phone_mirror as mirror
    except Exception:
        return

    cls = getattr(mirror, "PhoneMirrorManager", None)
    if cls is None or getattr(cls, "_gelotech_log_restore_patch", False):
        return

    def restore_console_safe(self):
        dashboard = getattr(self, "_dashboard", None)
        if dashboard is not None:
            try:
                dashboard.after_idle(self._restore_dashboard_console)
                return
            except Exception:
                pass
        self._restore_dashboard_console()

    def restore_dashboard_console(self, attempt=0):
        console = getattr(self, "_hidden_console", None)
        dashboard = getattr(self, "_dashboard", None)
        if console is None or dashboard is None:
            return

        try:
            if not console.winfo_exists():
                self._hidden_console = None
                self._console_place = None
                return

            rect = getattr(dashboard, "_dash_log_rect", None)
            if not rect:
                rect = getattr(self, "_console_place", None)
            if not rect:
                if attempt < 10:
                    dashboard.after(50, lambda: restore_dashboard_console(self, attempt + 1))
                return

            x, y, width, height = map(int, rect)
            console.place_configure(x=x, y=y, width=width, height=height)
            console.lift()
            dashboard.update_idletasks()

            if not console.winfo_ismapped():
                if attempt < 10:
                    dashboard.after(50, lambda: restore_dashboard_console(self, attempt + 1))
                    return
                self._log("[PHONE] Dashboard log could not be remapped after retries")
                return

            clip = getattr(dashboard, "_clip_dash_console", None)
            if callable(clip):
                try:
                    clip(width, height, 24, attempts=3)
                except Exception:
                    pass

            self._hidden_console = None
            self._console_place = None
        except Exception as exc:
            if attempt < 10:
                try:
                    dashboard.after(50, lambda: restore_dashboard_console(self, attempt + 1))
                    return
                except Exception:
                    pass
            try:
                self._log(f"[PHONE] Dashboard log restore failed: {exc}")
            except Exception:
                pass

    cls._restore_console_safe = restore_console_safe
    cls._restore_dashboard_console = restore_dashboard_console
    cls._gelotech_log_restore_patch = True


install()
