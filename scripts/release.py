# -*- coding: utf-8 -*-
"""Repeatable GeloTech release build helper.

This script intentionally does not commit, tag, push, or publish releases.
It validates the source tree, runs tests, regenerates PyArmor output, and
builds the supported obfuscated PyInstaller executable.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    "tech_common.py", "tech_reg.py", "tech_database.py", "tech_task_manager.py",
    "tech_phone_mirror.py", "tech_phone_mirror_embedded.py",
    "tech_phone_mirror_host.py", "tech_phone_mirror_fix.py", "tech_phone_mirror_restore_patch.py",
    "tech_navigation.py", "tech_themes.py", "tech_phone_mirror/__init__.py", "runtime_hook_gelotech.py", "sitecustomize.py",
    "tech_qt_app.py", "tech_qt_auto_refresh.py", "tech_qt_backup.py", "tech_qt_bezel.py",
    "tech_qt_bootstrap.py", "tech_qt_cleaner.py", "tech_qt_compat.py", "tech_qt_drivers.py",
    "tech_qt_final_fixes.py", "tech_qt_iconfix.py", "tech_qt_icons.py", "tech_qt_iconsync.py",
    "tech_qt_mainwindow.py", "tech_qt_mirror.py", "tech_qt_phone.py", "tech_qt_themes.py",
    "tech_qt_ui.py", "tech_qt_virustotal.py",
]


def run(*args):
    print("+", " ".join(map(str, args)))
    subprocess.run(args, cwd=ROOT, check=True)


def preflight():
    run(sys.executable, str(ROOT / "scripts" / "agent_preflight.py"))
    run(sys.executable, "-m", "compileall", "-q", ".")
    run(sys.executable, "-m", "pytest", "-q")
    _verify_security_doc()
    _verify_documentation_sync()


def _verify_pyarmor_module(name):
    path = ROOT / "build" / "pyarmor_out" / name
    if not path.is_file():
        raise SystemExit(f"PyArmor did not generate {name} in build/pyarmor_out")
    if path.stat().st_size < 50:
        raise SystemExit(f"PyArmor output {path} is suspiciously small ({path.stat().st_size} bytes)")
    return path


def _verify_exe_contains(exe, module):
    if not exe.is_file():
        raise SystemExit(f"Release EXE was not produced: {exe}")
    data = exe.read_bytes()
    if module.encode() not in data:
        raise SystemExit(
            f"Release EXE does not contain module '{module}' in its archive: {exe}\n"
            "The obfuscated build is missing the fix module. Refusing to publish."
        )
    print(f"[verify] EXE contains '{module}': OK")


def _verify_source_imports():
    """Verify that every Qt module in MODULES is imported by tech_qt_app.py."""
    text = (ROOT / "tech_qt_app.py").read_text(encoding="utf-8", errors="replace")
    imported = set(re.findall(r"(?:from|import)\s+(tech_qt_[A-Za-z0-9_]+)", text))
    required = {
        Path(name).stem for name in MODULES
        if Path(name).stem.startswith("tech_qt_")
    }
    missing = sorted(required - imported)
    if missing:
        raise SystemExit(
            "Missing Qt module imports in tech_qt_app.py: " + ", ".join(missing)
        )
    print("[verify] tech_qt_app.py imports all required Qt modules: OK")


def _verify_security_doc():
    """SECURITY.md must describe the current auth proxy security model (the Cloudflare auth
    proxy Worker) or it silently drifts back to the obsolete embedded-token
    wording. Block the release if the markers are missing or stale wording
    reappears."""
    path = ROOT / "SECURITY.md"
    text = path.read_text(encoding="utf-8", errors="replace")
    required = ["auth proxy Worker", "wrangler secret put", "AUTH_WORKER_URL"]
    missing = [m for m in required if m not in text]
    stale = ["embedded GitHub update credentials", "embedded SMTP sender credential"]
    found_stale = [s for s in stale if s in text]
    if missing or found_stale:
        raise SystemExit(
            "SECURITY.md does not match the current security model (auth proxy Worker, "
            "Cloudflare secrets). Update its 'Current Security Model' section before releasing."
        )
    print("[verify] SECURITY.md matches the current auth proxy security model: OK")


def _read_version():
    """Read APP_VERSION from tech_common.py without importing application code."""
    text = (ROOT / "tech_common.py").read_text(encoding="utf-8", errors="replace")
    match = re.search(r"^\s*APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
    if not match:
        raise SystemExit("Could not determine APP_VERSION from tech_common.py; refusing to release.")
    return match.group(1)


def _verify_documentation_sync():
    """Block the release when user-facing/agent documentation has drifted."""
    version = _read_version()
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="replace")
    process = (ROOT / "PROCESS_GUIDE.md").read_text(encoding="utf-8", errors="replace")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8", errors="replace")

    checks = {
        "README.md": {
            f"(v{version})": readme,
            "CTkThemesPack": readme,
            "UI Font": readme,
            "horizontal scrollbar": readme.lower(),
            "app icon": readme.lower(),
            "automatic": readme.lower(),
        },
        "PROCESS_GUIDE.md": {
            "CTkThemesPack": process,
            "UI Font": process,
            "horizontal scrollbar": process.lower(),
            "icon cache": process.lower(),
            "automatic": process.lower(),
        },
        "AGENTS.md": {
            "Documentation sync gate": agents,
            "scripts/release.py": agents,
        },
    }

    failures = []
    for filename, markers in checks.items():
        for marker, text in markers.items():
            if marker not in text:
                failures.append(f"{filename}: missing required marker {marker!r}")

    readme_versions = re.findall(r"\(v(\d+\.\d+\.\d+)\)", readme)
    if not readme_versions or version not in readme_versions:
        failures.append(f"README.md: Latest release label does not match APP_VERSION v{version}")

    if failures:
        details = "\n".join(f"  - {item}" for item in failures)
        raise SystemExit(
            "Documentation is out of sync; release is blocked.\n"
            "Update AGENTS.md, README.md, and PROCESS_GUIDE.md to describe the current source behavior, "
            "then rerun scripts/release.py.\n"
            f"{details}"
        )

    print(f"[verify] Documentation sync gate passed for v{version}: OK")


def build(obfuscated=True, qt_mode=False):
    if qt_mode:
        run(sys.executable, "-m", "PyInstaller", "GeloTechTool_qt.spec", "--noconfirm", "--clean")
    else:
        if not obfuscated:
            run(sys.executable, "-m", "PyInstaller", "GeloTechTool.spec", "--noconfirm", "--clean")
            return
        missing = [name for name in MODULES if not (ROOT / name).is_file()]
        if missing:
            raise SystemExit("Missing release module(s): " + ", ".join(missing))
        pyarmor = shutil.which("pyarmor")
        if not pyarmor:
            raise SystemExit("PyArmor is required for the supported release build.")
        _verify_source_imports()
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        shutil.rmtree(ROOT / "dist", ignore_errors=True)
        run(pyarmor, "gen", "-O", "build/pyarmor_out", *MODULES)
        _verify_pyarmor_module("tech_bloatware.py")
        run(sys.executable, "-m", "PyInstaller", "GeloTechTool_obf.spec", "--noconfirm", "--clean")
        _verify_exe_contains(ROOT / "dist" / "GeloTechTool.exe", "tech_bloatware")


def main():
    parser = argparse.ArgumentParser(description="Build GeloTech Tool consistently.")
    parser.add_argument("--standard", action="store_true", help="Build the non-obfuscated debug EXE.")
    parser.add_argument("--qt", action="store_true", help="Build the Qt6 version EXE.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip preflight/tests (not recommended).")
    args = parser.parse_args()

    if not args.skip_tests:
        preflight()
    if args.qt:
        build(obfuscated=False, qt_mode=True)
    elif not args.standard:
        build(obfuscated=True)
    else:
        build(obfuscated=False)
    print("Release build completed. No Git commit, tag, push, or release was performed.")


if __name__ == "__main__":
    main()
