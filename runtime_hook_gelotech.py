"""PyInstaller runtime hook for GeloTech compatibility patches.

PyInstaller does not automatically execute source-tree ``sitecustomize.py``
like a normal CPython installation. The release build therefore imports the
same defensive compatibility hooks explicitly at startup.
"""
try:
    import sitecustomize  # noqa: F401
except Exception:
    # Compatibility hooks are optional; never prevent the application from
    # starting if an environment-specific hook cannot be applied.
    pass
