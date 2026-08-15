# PyInstaller spec for the PySide6 migration build.
# This is a migration/debug spec for qt6-migration; the production release
# helper is intentionally unchanged until the Qt branch reaches parity.

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)

hiddenimports = [
    "tech_qt_app",
    "tech_qt_mainwindow",
    "tech_qt_icons",
    "tech_qt_themes",
    "tech_qt_bootstrap",
    "tech_qt_cleaner",
    "tech_qt_virustotal",
    "tech_qt_drivers",
    "tech_qt_mirror",
    "tech_qt_iconsync",
    "shiboken6",
]
hiddenimports += collect_submodules("PySide6")

datas = [
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "themes"), "themes"),
    (str(ROOT / "scrcpy-win64-v3.3.4.zip"), "."),
    (str(ROOT / "ApkIconHelper.apk"), "."),
    (str(ROOT / "banking_apps.json"), "."),
    (str(ROOT / "gelotech_icon.ico"), "."),
]


a = Analysis(
    [str(ROOT / "tech_qt_app.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["customtkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GeloTechTool_Qt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "gelotech_icon.ico"),
)
