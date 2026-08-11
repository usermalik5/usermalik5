# -*- coding: utf-8 -*-
"""GeloTech startup compatibility hook.

Python imports sitecustomize before the application's main module when running
from the source tree. We use that hook only to replace the mirror manager with
the Dashboard-owned implementation. The original scrcpy implementation is
left untouched so its working video/rendering code remains the source of truth.
"""
try:
    import tech_phone_mirror as _mirror
    from tech_phone_mirror_host import PhoneMirrorManager as _DashboardMirror
    _mirror.PhoneMirrorManager = _DashboardMirror
except Exception:
    # Never make the whole application fail because the optional mirror host
    # could not initialize. The original mirror manager remains available.
    pass
