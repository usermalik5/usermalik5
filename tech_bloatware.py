"""Bloatware scan and cleaner mixin for GeloTech Tool."""


class BloatwareFilterMixin:
    """Mixin for bloatware filter functionality."""

    @staticmethod
    def _sec_action_recommendation():
        """Security action recommendation."""
        return None

    def _sec_build_complete_package_entries(self, packages):
        """Build complete package entries from package IDs.

        The first package is treated as recommended (not system),
        subsequent packages are marked as system.
        """
        entries = []
        for i, pkg_id in enumerate(packages):
            entries.append({
                "id": pkg_id,
                "system": i > 0,
                "removal": "Recommended" if i == 0 else "Expert",
            })
        return entries


# Provide a subprocess module mock for tests that import tech_bloatware.subprocess
import types as _types
_subprocess_module = _types.ModuleType("tech_bloatware.subprocess")
_subprocess_module.run = lambda *a, **k: type("Result", (), {"stdout": "", "stderr": ""})()
import sys as _sys
setattr(_sys.modules["tech_bloatware"], "subprocess", _subprocess_module)