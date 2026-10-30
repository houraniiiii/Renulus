"""BF08: a published backend selector fences every Python canonical writer, including one opened before it."""
import pytest

from renulus.storage.database import BACKEND_SELECTOR, Database


def test_selector_refuses_new_and_existing_python_writers(tmp_path):
    profile = tmp_path / "profile"
    db = Database(profile / "state" / "renulus.sqlite3")
    db.execute("INSERT INTO preferences VALUES('synthetic','1','2026-10-30T00:00:00Z')")
    (profile / BACKEND_SELECTOR).write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="backend_canonical_authority_ts"):
        db.execute("INSERT INTO preferences VALUES('late','1','2026-10-30T00:00:00Z')")
    with pytest.raises(RuntimeError, match="backend_canonical_authority_ts"):
        Database(profile / "state" / "renulus.sqlite3")
    generation = profile / "generations" / "g1" / "state" / "renulus.sqlite3"
    with pytest.raises(RuntimeError, match="backend_canonical_authority_ts"):
        Database(generation)


def test_retired_selector_keeps_python_authority(tmp_path):
    profile = tmp_path / "profile"
    db = Database(profile / "state" / "renulus.sqlite3")
    (profile / ".renulus-backend-selector.retired.json").write_text("{}", encoding="utf-8")
    db.execute("INSERT INTO preferences VALUES('after-rollback','1','2026-10-30T00:00:00Z')")
    assert db.fetch_one("SELECT value FROM preferences WHERE key='after-rollback'") == {"value": "1"}
