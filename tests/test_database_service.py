from pathlib import Path

from tech_database import DatabaseService


def test_database_service_caches_and_refreshes(tmp_path: Path):
    db_path = tmp_path / "database.json"
    db_path.write_text("one", encoding="utf-8")
    calls = []

    def loader(path):
        calls.append(path)
        return {"value": Path(path).read_text(encoding="utf-8")}

    service = DatabaseService(db_path, loader=loader)
    assert service.get("value") == "one"
    assert service.get("value") == "one"
    assert len(calls) == 1

    db_path.write_text("two", encoding="utf-8")
    service.clear()
    assert service.get("value") == "two"
    assert len(calls) == 2
