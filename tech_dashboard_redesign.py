# -*- coding: utf-8 -*-
"""Legacy placeholder for the optional dashboard redesign.

The redesigned dashboard is intentionally disabled. GeloTech uses the original
DashboardMixin layout from tech_dash.py. The hardening layer may still import
and call install_dashboard_redesign(), so this no-op keeps that integration
backwards-compatible without replacing the original dashboard.
"""


def install_dashboard_redesign(cls):
    """Keep the original dashboard layout unchanged."""
    return None
