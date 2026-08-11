# -*- coding: utf-8 -*-
"""GeloTech startup compatibility hook.

Python imports sitecustomize before the application's main module when running
from the source tree. Replace the mirror manager with the true Dashboard-
embedded implementation. Both native mirror windows become CHILD windows of
Dashboard.dash_phone instead of independent desktop windows.
"""
try:
    import tech_phone_mirror as _mirror
    from tech_phone_mirror_embedded import PhoneMirrorManager as _DashboardMirror
    _mirror.PhoneMirrorManager = _DashboardMirror
except Exception:
    # Never make the whole application fail because the optional mirror host
    # could not initialize. The original mirror manager remains available.
    pass
