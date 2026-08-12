"""GeloTech compatibility hooks.

Only compatibility behavior that genuinely belongs outside normal application
control flow lives here. Ordinary login/navigation is implemented directly by
the application and must not depend on import-time patches.
"""

# ---------------------------------------------------------------------------
# Mirror: ensure the Dashboard uses the embedded child-window manager.
# ---------------------------------------------------------------------------
try:
    import tech_phone_mirror as _mirror
    from tech_phone_mirror_embedded import PhoneMirrorManager as _DashboardMirror
    _mirror.PhoneMirrorManager = _DashboardMirror
    import tech_phone_mirror_restore_patch
except Exception:
    pass


# ---------------------------------------------------------------------------
# Website links: keep them clickable, but don't show a hover tooltip for URLs.
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
