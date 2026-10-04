# SPDX-License-Identifier: MIT
import json
import sqlite3

import pytest

from renulus.content.exports import EXPORT_TABLES
from renulus.content.repository import ContentConflict, ContentRepository, ContentUnavailable
from renulus.content.validation import PackValidationError
from .helpers import PACK, copy_pack, correction_pack, read, refresh, write


def test_real_pack_activation_idempotency_and_restart(repository, database):
    first = repository.install_pack(PACK)
    assert first["installed"] and first["active"]
    second = repository.install_pack(PACK)
    assert not second["installed"]
    restarted = ContentRepository(database, PACK.parent.parent)
    assert len(restarted.list_topics()) == 27
    assert all(t["title"] == t["name"] == t["label"] for t in restarted.list_topics())
    assert len(restarted.list_cases()) == 14
    assert len(restarted.list_questions()) == 52
    assert len(restarted.list_questions("T21")) == 4
    assert restarted.list_question_summaries(track="esen_eph") == []
    assert len(restarted.list_question_summaries(domain="T21", track="general_nephrology")) == 4
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1


def test_pinned_sources_and_teaching_exclude_every_question(installed):
    q = installed.get_question_version("RN-AKI-002", 1)
    assert q["question_id"] == "RN-AKI-002"
    assert q["family_id"] == "RN-AKI-002.family"
    assert q["key_version"] == q["family_version"] == 1
    assert q["correct_option_ids"] == [q["answer"]]
    assert q["explanation"] == q["rationale"]
    assert q["current_version"] == 1 and not q["withdrawn"]
    assert q["source_records"][0]["register_id"] == "K10"
    assert q["source_records"][0]["edition"] == "2012 final"
    source = installed.get_source("K10-2012")
    assert source["id"] == q["source_records"][0]["id"]
    material = json.dumps(installed.teaching_material())
    assert all(question["id"] not in material for question in installed.list_questions())
    assert "correct_option_ids" not in material
    assert len(installed.teaching_material()) == 41
    with pytest.raises(ContentUnavailable):
        installed.get_case("user-case-synthetic-sentinel")


def test_pack_tamper_never_changes_active_snapshot(installed, tmp_path):
    path = copy_pack(tmp_path)
    q = read(path, "questions.json")
    q[0]["stem"] += " Synthetic changed question."
    write(path, "questions.json", q)
    refresh(path)
    before = installed.get_question_version(q[0]["id"], 1)
    with pytest.raises(ContentConflict, match="Immutable pack"):
        installed.install_pack(path)
    assert installed.get_question_version(q[0]["id"], 1) == before
    manifest = read(path, "manifest.json")
    manifest["version"] = "1.0.1"
    write(path, "manifest.json", manifest)
    with pytest.raises(ContentConflict, match="Immutable version"):
        installed.install_pack(path)
    assert installed.active_manifest()["version"] == "1.0.0"


def test_correction_is_atomic_and_keeps_old_private_key(installed, tmp_path):
    path, revised = correction_pack(tmp_path)
    prior = installed.get_question_version(revised["id"], 1)
    installed.install_pack(path)
    historic = installed.get_question_version(revised["id"], 1)
    current = installed.get_question_version(revised["id"], 2)
    assert historic["answer"] == prior["answer"]
    assert historic["rationale"] == prior["rationale"]
    assert historic["withdrawn"] and historic["withdrawal"]["replacement_version"] == 2
    assert historic["current_version"] == 2
    assert current["family_id"] == prior["family_id"]
    assert not current["withdrawn"] and current["key_version"] == 2
    assert next(q for q in installed.list_questions() if q["id"] == revised["id"])["version"] == 2
    with pytest.raises(ContentConflict, match="withdrawn"):
        installed.install_pack(PACK)
    assert installed.active_manifest()["version"] == "1.0.1"


def test_key_or_choice_change_requires_declared_correction(installed, tmp_path):
    path = copy_pack(tmp_path)
    manifest = read(path, "manifest.json")
    manifest["version"] = "1.0.1"
    questions = read(path, "questions.json")
    q = questions[0]
    q["version"] = q["key_version"] = 2
    q["options"][0]["rationale"] += " Synthetic modified choice explanation."
    write(path, "questions.json", questions)
    write(path, "manifest.json", manifest)
    refresh(path)
    with pytest.raises(ContentConflict, match="requires a correction|requires|requires a|correction"):
        installed.install_pack(path)
    assert installed.active_manifest()["version"] == "1.0.0"


def test_missing_predecessor_rolls_back_every_insert(repository, database, tmp_path):
    path, _ = correction_pack(tmp_path)
    with pytest.raises(ContentConflict, match="predecessor"):
        repository.install_pack(path)
    assert repository.active_manifest() is None
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 0
    assert database.fetch_one("SELECT COUNT(*) n FROM content_question_versions")["n"] == 0
    assert database.fetch_one("SELECT COUNT(*) n FROM content_case_versions")["n"] == 0


def test_activation_failure_keeps_old_pack_and_removes_staged_rows(installed, database, tmp_path):
    path = copy_pack(tmp_path)
    manifest = read(path, "manifest.json")
    manifest["version"] = "1.0.1"
    write(path, "manifest.json", manifest)
    with database.transaction() as conn:
        conn.execute("CREATE TRIGGER synthetic_activation_failure BEFORE UPDATE ON content_active_pack "
                     "BEGIN SELECT RAISE(ABORT, 'synthetic interrupted activation'); END")
    with pytest.raises(sqlite3.IntegrityError, match="interrupted"):
        installed.install_pack(path)
    assert installed.active_manifest()["version"] == "1.0.0"
    assert len(installed.list_questions()) == 52
    assert database.fetch_one("SELECT COUNT(*) n FROM content_packs")["n"] == 1
    assert database.fetch_one("SELECT COUNT(*) n FROM content_pack_questions WHERE pack_version='1.0.1'")["n"] == 0


def test_withdrawal_prevents_new_use_but_not_historical_resolution(installed, database):
    id = "RN-CKD-001"
    before = installed.get_question_version(id, 1)
    installed.withdraw_question(id, 1, "Synthetic review hold")
    installed.withdraw_question(id, 1, "Synthetic review hold")
    assert len(installed.list_questions()) == 51
    assert all(q["id"] != id for q in installed.list_question_summaries())
    after = installed.get_question_version(id, 1)
    assert after["answer"] == before["answer"] and after["withdrawn"]
    with pytest.raises(ContentConflict):
        installed.install_pack(PACK)
    with pytest.raises(sqlite3.IntegrityError, match="permanent"):
        database.execute("DELETE FROM content_question_withdrawals")
    with pytest.raises(ContentUnavailable):
        installed.withdraw_question("missing-synthetic-id", 1, "Review hold")


def test_source_impact_and_export_allowlist_exclude_private_state(installed, database):
    references = installed.references_for_source("K10")
    assert any(r["id"] == "RN-AKI-002" for r in references)
    assert any(r["id"] == "RN-CASE-AKI" for r in references)
    assert all(not ({"stem", "answer", "options", "rationale", "body_json"} & r.keys()) for r in references)
    tables = {r["name"] for r in database.fetch_all("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'content_%'")}
    assert tables == set(EXPORT_TABLES)
    assert all("case" not in name or name in {"content_case_versions", "content_pack_cases"} for name in EXPORT_TABLES)


def test_drafts_and_non_synthetic_cases_cannot_be_installed(repository, database, tmp_path):
    path = copy_pack(tmp_path)
    cases = read(path, "cases.json")
    cases[0]["synthetic"] = False
    cases[0]["summary"] = "SYNTHETIC_TEST_TEMP_CASE_SENTINEL"
    write(path, "cases.json", cases)
    refresh(path)
    with pytest.raises(PackValidationError):
        repository.install_pack(path)
    assert database.fetch_one("SELECT COUNT(*) n FROM content_case_versions")["n"] == 0
    assert repository.active_manifest() is None


def test_runtime_rejects_unknown_source_register_id(repository, tmp_path):
    path = copy_pack(tmp_path)
    sources = read(path, "sources.json")
    sources[0]["register_id"] = "G99"
    write(path, "sources.json", sources)
    refresh(path)
    with pytest.raises(PackValidationError, match="Unknown SOURCES"):
        repository.install_pack(path)
    assert repository.active_manifest() is None


def test_reserved_evaluation_never_inflates_coverage_or_enters_selection(repository, tmp_path):
    path = copy_pack(tmp_path)
    questions = read(path, "questions.json")
    questions[-1]["usage"] = "evaluation_reserved"
    heldout_id = questions[-1]["id"]
    write(path, "questions.json", questions)
    refresh(path)
    repository.install_pack(path)
    assert len(repository.list_questions()) == 51
    assert all(q["id"] != heldout_id for q in repository.list_question_summaries())
    assert heldout_id not in json.dumps(repository.teaching_material())
    coverage = read(path, "coverage.json")
    assert all(heldout_id not in row["question_ids"] for row in coverage["topics"])
