# SPDX-License-Identifier: MIT
from pathlib import Path
import sqlite3

from jsonschema import Draft202012Validator
import pytest

from renulus.content.repository import ContentRepository
from renulus.content.schema import BUNDLE_SCHEMA
from renulus.storage import Database


SCHEMA = Path(__file__).parents[2] / "runtime/renulus/content/schema.sql"


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "state/renulus.sqlite3")
    database.apply_migration("content-001", SCHEMA.read_text(encoding="utf-8"))
    return database


def test_schema_is_valid_2020_12_contract():
    Draft202012Validator.check_schema(BUNDLE_SCHEMA)


def test_empty_repository_uses_shared_database_and_teaches_no_questions(db, tmp_path):
    repo = ContentRepository(db, tmp_path)
    assert repo.active_manifest() is None
    assert repo.list_topics() == repo.list_cases() == repo.list_questions() == []
    assert repo.teaching_material() == []


def test_sql_rejects_mutation_and_deletion_of_published_question(db):
    with db.transaction() as conn:
        conn.execute("INSERT INTO content_question_versions VALUES(?,?,?,?,?)",
                     ("synthetic-key", 1, "synthetic-family", "{}", "a" * 64))
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.execute("UPDATE content_question_versions SET body_json='changed'")
    with pytest.raises(sqlite3.IntegrityError, match="historical"):
        db.execute("DELETE FROM content_question_versions")
    assert db.fetch_one("SELECT body_json FROM content_question_versions")["body_json"] == "{}"
