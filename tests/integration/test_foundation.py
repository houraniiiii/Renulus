from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ContextScope, Scope
from renulus.server import create_app
from renulus.storage import AppPaths, Database


def test_profiles_are_independent_and_paths_cannot_escape(tmp_path):
    a, b = (AppPaths.create(tmp_path / n) for n in ("a", "b"))
    da, db = Database(a.database), Database(b.database)
    da.execute("INSERT INTO preferences VALUES(?,?,?)", ("goal", "study", "now"))
    assert db.fetch_all("SELECT * FROM preferences") == []
    with pytest.raises(ValueError):
        a.owned("../outside")


def test_migration_is_atomic_resumable_and_cannot_drift(tmp_path):
    db = Database(tmp_path / "state.db")
    ddl = "CREATE TABLE example(id TEXT PRIMARY KEY);\n"
    db.apply_migration("example-001", ddl)
    db.apply_migration("example-001", ddl)
    assert len(db.fetch_all("SELECT * FROM migration_ledger")) == 1
    with pytest.raises(RuntimeError, match="Applied migration changed"):
        db.apply_migration("example-001", ddl + "CREATE TABLE changed(id TEXT);\n")
    with pytest.raises(sqlite3.OperationalError):
        db.apply_migration("broken-001", "CREATE TABLE partial(id TEXT);\nNOT SQL;\n")
    assert db.fetch_one("SELECT name FROM sqlite_master WHERE name='partial'") is None
    assert db.fetch_one("SELECT 1 FROM migration_ledger WHERE name='broken-001'") is None


def test_downgrade_refuses_to_open_newer_schema(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version=99")
    with pytest.raises(RuntimeError, match="downgrade refused"):
        Database(path)


def test_local_session_boundary_and_safe_health(tmp_path):
    with TestClient(create_app(tmp_path / "api", token="app-session")) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/meta").status_code == 401
        assert client.get("/api/v1/meta", headers={"X-Renulus-Token": "app-session"}).status_code == 200
        assert client.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 403
        assert client.get("/api/v1/health", headers={"Origin": "https://evil.example"}).status_code == 403


def test_temporary_and_unclassified_scopes_never_become_persistent():
    for kind in (Scope.TEMPORARY_CASE, Scope.UNCLASSIFIED):
        assert not ContextScope(kind=kind).persistent
    assert ContextScope(kind=Scope.STUDY).persistent
