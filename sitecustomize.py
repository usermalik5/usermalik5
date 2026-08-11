"""GeloTech source-tree compatibility hooks.

This module is intentionally defensive: optional hooks must never prevent the
application from starting if an implementation changes.
"""

# ---------------------------------------------------------------------------
# Mirror: ensure the Dashboard uses the embedded child-window manager.
# ---------------------------------------------------------------------------
try:
    import tech_phone_mirror as _mirror
    from tech_phone_mirror_embedded import PhoneMirrorManager as _DashboardMirror
    _mirror.PhoneMirrorManager = _DashboardMirror
except Exception:
    pass


# ---------------------------------------------------------------------------
# Website links: keep them clickable, but don't show a hover tooltip for URLs.
# Other application tooltips remain unchanged.
# ---------------------------------------------------------------------------
try:
    import re
    import tech_common as _common
    _Tooltip = _common.Tooltip
    _tooltip_init = _Tooltip.__init__

    def _tooltip_init_no_url_hint(self, widget, text):
        if isinstance(text, str) and re.match(r"^https?://", text.strip(), re.I):
            self.widget = widget
            self.text = text
            return
        _tooltip_init(self, widget, text)

    _Tooltip.__init__ = _tooltip_init_no_url_hint
except Exception:
    pass


# ---------------------------------------------------------------------------
# Login: always land on Dashboard after permissions are applied.
# ---------------------------------------------------------------------------
try:
    import tech_settings as _settings

    _original_apply_permissions = getattr(_settings.SettingsMixin,
                                           "_apply_permissions", None)
    if _original_apply_permissions is not None and not getattr(
            _original_apply_permissions, "_gelotech_dashboard_hook", False):

        def _apply_permissions_then_dashboard(self, *args, **kwargs):
            result = _original_apply_permissions(self, *args, **kwargs)

            def _open_dashboard():
                # _show_page is the application's actual page-stack navigation
                # method. Prefer it so the selected sidebar state and
                # _current_page stay synchronized.
                for method_name in (
                    "_show_page", "show_page", "select_page", "switch_page",
                    "navigate_to", "set_page",
                ):
                    method = getattr(self, method_name, None)
                    if callable(method):
                        try:
                            method("Dashboard")
                            return
                        except Exception:
                            pass

                # Last-resort fallback: raise the existing Dashboard frame
                # without rebuilding the page.
                try:
                    page = self.page("Dashboard")
                    if page is not None:
                        page.tkraise()
                    if hasattr(self, "_current_page"):
                        self._current_page = "Dashboard"
                except Exception:
                    pass

            try:
                self.after_idle(_open_dashboard)
            except Exception:
                try:
                    _open_dashboard()
                except Exception:
                    pass
            return result

        _apply_permissions_then_dashboard._gelotech_dashboard_hook = True
        _settings.SettingsMixin._apply_permissions = _apply_permissions_then_dashboard
except Exception:
    pass
