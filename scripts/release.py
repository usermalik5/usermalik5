import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    "tech_common.py", "tech_reg.py", "tech_database.py", "tech_task_manager.py",
    "tech_phone_mirror.py", "tech_phone_mirror_embedded.py",
    "tech_phone_mirror_host.py", "tech_phone_mirror_fix.py", "tech_phone_mirror_restore_patch.py",
    "tech_navigation.py", "tech_task_manager.py", "tech_database.py",
    "tech_themes.py", "tech_phone_mirror/__init__.py", "runtime_hook_gelotech.py", "sitecustomize.py",
    "tech_qt_app.py", "tech_qt_auto_refresh.py", "tech_qt_bezel.py", "tech_qt_bootstrap.py", "tech_qt_backup.py", "tech_qt_cleaner.py",
    "tech_qt_drivers.py", "tech_qt_final_fixes.py", "tech_qt_icons.py", "tech_qt_iconsync.py",
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