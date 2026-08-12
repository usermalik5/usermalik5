from tech_bloatware import BloatwareFilterMixin

class FakeMixin(BloatwareFilterMixin):
    def _load_app_labels(self):
        return {"com.example.rec": "Recommended App"}

    def _build_uad_lookup(self):
        return {
            "com.example.rec": {"removal": "Recommended", "description": "recommended"},
            "com.example.exp": {"removal": "Expert", "description": "expert"},
        }

    def _load_excluded_clean(self):
        return set()

    def _load_excluded_uninstall(self):
        return set()

    def _resolve_label(self, package_id):
        return package_id

def test_complete_package_entries_include_system_and_user_packages(monkeypatch):
    fake = FakeMixin()
    fake.scrcpy_adb = "adb"
    fake.sec_packages = []

    class Result:
        stdout = "package:com.example.rec\n"
        stderr = ""

    monkeypatch.setattr("tech_bloatware.subprocess.run", lambda *a, **k: Result())
    entries = fake._sec_build_complete_package_entries([
        "com.example.rec", "com.example.exp", "com.example.unknown"
    ])
    by_id = {item["id"]: item for item in entries}
    assert by_id["com.example.rec"]["system"] is False
    assert by_id["com.example.exp"]["system"] is True
    assert by_id["com.example.rec"]["removal"] == "Recommended"

def test_recommendation_method_is_owned_by_new_mixin():
    assert BloatwareFilterMixin._sec_action_recommendation.__qualname__.startswith("BloatwareFilterMixin.")
