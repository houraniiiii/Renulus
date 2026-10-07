"""Fresh installed-profile regression: correction ancestry is atomic, not setup."""
import shutil

import pytest

from renulus.content.repository import ContentConflict, ContentRepository
from .conftest import ROOT
from .helpers import read, write
from .test_bootstrap import boot

PACKS = ROOT / "content/packs"
TARGET = "RN11-T11-001"


def bundled(tmp_path, *versions):
    root = tmp_path / "bundled"
    for version in versions:
        shutil.copytree(PACKS / "renulus-foundations" / version,
                        root / "renulus-foundations" / version)
    return root


def test_fresh_current_release_installs_correction_ancestry_and_reopens(database, tmp_path):
    repository, outcome = boot(database, tmp_path, PACKS)
    assert outcome["status"] == "activated" and outcome["reason"] == "fresh_profile"
    assert repository.active_manifest()["version"] == "1.3.0"
    assert len(repository.list_question_summaries()) == 230
    assert len(repository.list_cases()) == 52
    assert repository.get_source("K01-2024")["register_id"] == "K01"
    prior = repository.get_question_version(TARGET, 1)
    current = repository.get_question_version(TARGET, 2)
    assert prior["answer"] == current["answer"] == "A"
    assert prior["withdrawn"] and prior["withdrawal"]["replacement_version"] == 2
    assert "Review medications and acquired/inherited causes" in prior["rationale"]
    assert "Review medications and acquired/inherited causes" not in current["rationale"]
    assert {row["version"] for row in database.fetch_all("SELECT version FROM content_packs")} == {"1.2.0", "1.3.0"}
    before = database.fetch_all("SELECT * FROM content_packs ORDER BY version")
    repository, reopened = boot(database, tmp_path, PACKS)
    assert reopened["reason"] == "active_version_not_older"
    assert repository.get_question_version(TARGET, 1) == prior
    assert database.fetch_all("SELECT * FROM content_packs ORDER BY version") == before


def test_missing_ancestry_leaves_fresh_profile_empty(database, tmp_path):
    root = bundled(tmp_path, "1.3.0")
    repository, outcome = boot(database, tmp_path, root)
    assert outcome["error"]["code"] == "content_conflict"
    assert repository.active_manifest() is None
    assert database.fetch_one("SELECT count(*) n FROM content_packs")["n"] == 0
    assert database.fetch_one("SELECT count(*) n FROM content_question_versions")["n"] == 0


def test_corrupt_ancestry_preserves_existing_profile(database, tmp_path):
    root = bundled(tmp_path, "1.0.0", "1.2.0", "1.3.0")
    repository = ContentRepository(database, root)
    repository.install_pack(root / "renulus-foundations/1.0.0")
    before = database.fetch_all("SELECT * FROM content_question_versions ORDER BY question_id,version")
    questions = root / "renulus-foundations/1.2.0/questions.json"
    questions.write_bytes(questions.read_bytes() + b" ")  # Deliberately break its pinned digest.
    repository, outcome = boot(database, tmp_path, root)
    assert outcome["error"]["code"] == "invalid_content_pack"
    assert repository.active_manifest()["version"] == "1.0.0"
    assert database.fetch_one("SELECT count(*) n FROM content_packs")["n"] == 1
    assert database.fetch_all("SELECT * FROM content_question_versions ORDER BY question_id,version") == before


def test_failed_final_activation_rolls_back_staged_ancestry(database, tmp_path):
    # A failure after the predecessor's selection must not publish a partial older release.
    database.execute("CREATE TRIGGER synthetic_activation_failure BEFORE UPDATE ON content_active_pack "
                     "BEGIN SELECT RAISE(ABORT, 'synthetic interrupted activation'); END")
    repository = ContentRepository(database, PACKS)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError, match="synthetic interrupted"):
        repository.install_bundled_release(PACKS / "renulus-foundations/1.3.0")
    assert repository.active_manifest() is None
    assert database.fetch_one("SELECT count(*) n FROM content_packs")["n"] == 0
    assert database.fetch_one("SELECT count(*) n FROM content_question_versions")["n"] == 0


def test_existing_ancestry_needs_no_bundled_old_copy(database, tmp_path):
    root = bundled(tmp_path, "1.3.0")
    repository = ContentRepository(database, root)
    repository.install_pack(PACKS / "renulus-foundations/1.2.0")
    before = repository.get_question_version(TARGET, 1)
    repository, outcome = boot(database, tmp_path, root)
    assert outcome["status"] == "activated"
    current = repository.get_question_version(TARGET, 1)
    assert current["rationale"] == before["rationale"]
    assert current["source_records"] == before["source_records"]
    assert repository.active_manifest()["version"] == "1.3.0"


def test_draft_predecessor_is_not_installed(database, tmp_path):
    root = bundled(tmp_path, "1.2.0", "1.3.0")
    draft = root / "renulus-foundations/1.2.1"
    shutil.copytree(root / "renulus-foundations/1.2.0", draft)
    manifest = read(draft, "manifest.json")
    manifest.update(version="1.2.1", state="draft")
    write(draft, "manifest.json", manifest)
    repository, outcome = boot(database, tmp_path, root)
    assert outcome["status"] == "activated"
    assert repository.active_manifest()["version"] == "1.3.0"
    assert {row["version"] for row in database.fetch_all("SELECT version FROM content_packs")} == {"1.2.0", "1.3.0"}


def test_explicit_import_still_requires_predecessor(database):
    repository = ContentRepository(database, PACKS)
    with pytest.raises(ContentConflict, match="predecessor"):
        repository.install_pack(PACKS / "renulus-foundations/1.3.0")
    assert repository.active_manifest() is None
