"""Bootstrapping helpers for the PySide6 entry point.

The legacy shared modules import CustomTkinter for their Tk application. The
Qt application must not require it, so when it is unavailable we install a
minimal module-level stub containing only the legacy style calls.
"""
from __future__ import annotations

import os
import sys
import types


def enable_qt_mode() -> None:
    os.environ["GELOTECH_QT_MODE"] = "1"
    if "customtkinter" in sys.modules:
        return
    try:
        __import__("customtkinter")
        return
    except ImportError:
        pass

    stub = types.ModuleType("customtkinter")

    def _noop(*_args, **_kwargs):
        return None

    stub.set_appearance_mode = _noop
    stub.set_default_color_theme = _noop
    stub.set_widget_scaling = _noop
    sys.modules["customtkinter"] = stub
