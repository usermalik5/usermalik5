# -*- coding: utf-8 -*-
from pathlib import Path
p=Path('tech_hardening.py')
s=p.read_text(encoding='utf-8')
imports='from tech_dashboard_redesign import install_dashboard_redesign\n'
if 'from tech_dashboard_redesign import install_dashboard_redesign' not in s:
    marker='from tech_common import get_settings_dir, load_banking_apps\n'
    if marker not in s: raise SystemExit('hardening import marker not found')
    s=s.replace(marker, marker+imports,1)
block='''\n\ndef _patch_dashboard_navigation(cls):\n    if getattr(cls, "_dashboard_navigation_patched", False):\n        return\n    original_show = getattr(cls, "_show_page", None)\n    if original_show is None:\n        return\n    def _remove_mirror_button(self):\n        if getattr(self, "_mirror_sidebar_removed", False):\n            return\n        try:\n            for child in list(self.sidebar_frame.winfo_children()):\n                try:\n                    if isinstance(child, ctk.CTkButton) and "Screen Mirror" in str(child.cget("text")):\n                        child.destroy()\n                except Exception:\n                    pass\n            self._mirror_sidebar_removed = True\n        except Exception:\n            pass\n    def show_page(self, name, *args, **kwargs):\n        result = original_show(self, name, *args, **kwargs)\n        try:\n            _remove_mirror_button(self)\n            mgr = getattr(self, "_phone_mirror", None)\n            if mgr is not None:\n                mgr.set_visible(name == "Dashboard")\n        except Exception:\n            pass\n        return result\n    cls._show_page = show_page\n    cls._dashboard_navigation_patched = True\n\n\ndef _patch_phone_mirror_visibility(manager_cls):\n    if getattr(manager_cls, "_mirror_visibility_patched", False):\n        return\n    original_align = getattr(manager_cls, "_align_all", None)\n    if original_align is None:\n        return\n    def set_visible(self, visible):\n        self._mirror_visible = bool(visible)\n        try:\n            import ctypes\n            u=ctypes.windll.user32\n            if self.hwnd:\n                u.ShowWindow(self.hwnd, 5 if visible else 0)\n            if self.overlay is not None and self.overlay.hwnd:\n                u.ShowWindow(self.overlay.hwnd, 5 if visible else 0)\n            if visible and self.hwnd and self.overlay is not None and self.overlay.alive():\n                original_align(self)\n        except Exception:\n            pass\n    def guarded_align(self):\n        if getattr(self, "_mirror_visible", True):\n            return original_align(self)\n    manager_cls.set_visible=set_visible\n    manager_cls._align_all=guarded_align\n    manager_cls._mirror_visibility_patched=True\n\n'''
marker='\ndef apply_hardening(cls):'
if '_patch_dashboard_navigation' not in s:
    if marker not in s: raise SystemExit('apply marker not found')
    s=s.replace(marker,block+marker,1)
needle='    _patch_icon_helper(cls)\n    _patch_init(cls)'
replacement='    _patch_icon_helper(cls)\n    _patch_dashboard_navigation(cls)\n    _patch_phone_mirror_visibility(__import__("tech_phone_mirror").PhoneMirrorManager)\n    install_dashboard_redesign(cls)\n    _patch_init(cls)'
if needle not in s: raise SystemExit('apply calls not found')
s=s.replace(needle,replacement,1)
p.write_text(s,encoding='utf-8')
