from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Event

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.engines import Extracted, LanceIndex
from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.knowledge.repository import KnowledgeRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database

STUDY = ContextScope(kind=Scope.STUDY)
LIBRARY = ContextScope(kind=Scope.LIBRARY)


class SyntheticExtractor:
    """Deterministic application-rule adapter, never labelled an engine proof."""
    def extract_file(self, path, title):
        text = path.read_text(encoding="utf-8")
        if text == "FAIL":
            raise ApiError("synthetic_failure", "Synthetic extraction failure", 422)
        return Extracted([{"text": text, "context_text": text, "headings": [],
            "locators": [{"page": None, "char_span": [0, len(text)], "item_ref": "#/texts/0"}]}], {"synthetic": True})


class SyntheticEmbedder:
    model_id, dimensions, max_tokens = "synthetic-384", 384, 512
    def embed(self, texts, *, query=False):
        return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.fixture
def repository(tmp_path):
    paths = AppPaths.create(tmp_path / "profile")
    db = Database(paths.database)
    schema = Path(__file__).parents[2] / "runtime/renulus/knowledge/schema.sql"
    db.apply_migration("knowledge-001", schema.read_text())
    for migration in sorted((schema.parent / "migrations").glob("*.sql")):
        db.apply_migration("knowledge-" + migration.stem, migration.read_text())
    services = Services(paths, db)
    return KnowledgeRepository(services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder())


def import_note(repository, text, **kwargs):
    return repository.import_text(text, scope=LIBRARY, **kwargs)


def test_real_lancedb_hybrid_uses_canonical_revisions_and_topic_filters(repository):
    renal = import_note(repository, "Glomerulonephritis causes hematuria and proteinuria.",
                        metadata=SourceMetadata(topic_ids=["glomerular"]))
    import_note(repository, "Dialysis access surveillance includes fistula assessment.",
                metadata=SourceMetadata(topic_ids=["dialysis"]))
    import_note(repository, "Reserved glomerular examination item sentinel", reserved=True)
    result = repository.retrieve("hematuria", topic_id="glomerular", scope=STUDY)
    assert renal["status"] == "ready"
    assert [p["document_id"] for p in result["passages"]] == [renal["document_id"]]
    assert result["passages"][0]["locators"][0]["page"] is None
    assert repository.retrieve("hematuria", scope=STUDY, current_only=True)["passages"] == []


def test_failed_and_cancelled_replacement_keep_previous_active_and_idempotency(repository):
    initial = import_note(repository, "Transplant rejection study note", idempotency_key="first")
    assert import_note(repository, "Transplant rejection study note", idempotency_key="first")["job"]["id"] == initial["job"]["id"]
    with pytest.raises(ApiError, match="different request"):
        import_note(repository, "Changed payload", idempotency_key="first")
    failed = import_note(repository, "FAIL", document_id=initial["document_id"])
    assert failed["status"] == "failed"
    queued = import_note(repository, "Replacement", document_id=initial["document_id"], process=False)
    assert repository.cancel_job(queued["job"]["id"])["state"] == "cancelled"
    repository.run_job(queued["job"]["id"])
    assert repository.get_document(initial["document_id"])["active_revision"] == initial["revision_id"]
    assert repository.retrieve("rejection", scope=STUDY)["passages"][0]["document_revision"] == initial["revision_id"]


@pytest.mark.parametrize("operation", ["cancel", "delete", "replace"])
def test_races_cannot_publish_stale_extraction(repository, operation):
    started, release = Event(), Event()
    base = repository.extractor
    class Blocked:
        def extract_file(self, path, title):
            output = base.extract_file(path, title)
            started.set()
            assert release.wait(10)
            return output
    repository.extractor = Blocked()
    queued = import_note(repository, "Race sentinel kidney injury", process=False)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(repository.run_job, queued["job"]["id"])
        assert started.wait(10)
        if operation == "delete":
            repository.delete_document(queued["document_id"])
        elif operation == "replace":
            import_note(repository, "New source revision", document_id=queued["document_id"], process=False)
        else:
            repository.cancel_job(queued["job"]["id"])
        release.set()
        assert future.result(timeout=10)["state"] == "cancelled"
    assert repository.retrieve("sentinel", scope=STUDY)["passages"] == []
    assert not repository.db.fetch_all("SELECT * FROM knowledge_passages")


def test_replacement_and_deletion_physically_prune_old_lance_versions(repository):
    initial = import_note(repository, "OLD_RENAL_SENTINEL sodium review")
    replaced = import_note(repository, "New transplant review", document_id=initial["document_id"])
    table = repository.index._open()
    assert table.count_rows() == 1
    assert len(table.list_versions()) == 1
    assert repository.citation(initial["revision_id"])["document_revision"] == initial["revision_id"]
    result = repository.delete_document(initial["document_id"])
    assert result["cleanup_pending"] is False
    assert table.count_rows() == 0
    assert len(table.list_versions()) == 1
    assert not repository.db.fetch_all("SELECT * FROM knowledge_passages")
    assert not list((repository.paths.library / "knowledge").rglob("original.*"))
    assert repository.retrieve("transplant", scope=STUDY)["passages"] == []
    with pytest.raises(ApiError):
        repository.original(replaced["revision_id"])


def test_rebuild_uses_eligible_canonical_passages_and_survives_restart(repository):
    active = import_note(repository, "Dialysis access stenosis learning note")
    import_note(repository, "Reserved examination sentinel", reserved=True)
    import_note(repository, "Retracted teaching sentinel", metadata=SourceMetadata(retracted=True))
    deleted = import_note(repository, "Deleted kidney sentinel")
    repository.db.mark_deleted("knowledge-document", deleted["document_id"])
    old_path = repository.index.path
    repository.index.stage([{"passage_id": "orphan", "revision_id": "orphan", "document_id": "orphan",
                             "text": "Stale index sentinel", "vector": [1.0] + [0.0] * 383}])
    result = repository.rebuild_index()
    assert result["status"] == "ready" and result["passages"] == 1
    assert not result["cleanup_pending"]
    assert not old_path.exists()
    assert repository.get_document(deleted["document_id"], include_deleted=True)["deleted_at"]
    restored = KnowledgeRepository(repository.services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder())
    assert restored.index.path == repository.index.path
    assert restored.index._open().count_rows() == 1
    assert restored.retrieve("stenosis", scope=STUDY)["passages"][0]["document_revision"] == active["revision_id"]
    restored.index.close()


def test_failed_rebuild_keeps_active_index_and_retries_cleanly(repository, monkeypatch):
    note = import_note(repository, "Transplant immunology learning note")
    previous = repository.index
    selector = repository.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'")
    def reject(self, identities):
        raise ApiError("index_validation_failed", "Synthetic rejected index", 503, True)
    with monkeypatch.context() as patch:
        patch.setattr(LanceIndex, "validate_passages", reject)
        with pytest.raises(ApiError) as caught:
            repository.rebuild_index()
        assert caught.value.code == "index_validation_failed"
    assert repository.index is previous
    assert repository.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'") == selector
    assert repository.retrieve("immunology", scope=STUDY)["passages"][0]["document_revision"] == note["revision_id"]
    assert not list((repository.paths.indexes / "k").glob("*"))
    assert repository.rebuild_index()["passages"] == 1


def test_empty_rebuild_and_abandoned_generation_cleanup(repository):
    first = repository.rebuild_index()
    assert first["passages"] == 0
    abandoned = repository.paths.indexes / "knowledge-generations" / ("index_" + "f" * 32)
    abandoned.mkdir(parents=True)
    (abandoned / "partial.txt").write_text("Synthetic abandoned index")
    assert repository.cleanup() == []
    assert not abandoned.exists()
    assert repository.index.path.exists()
    assert repository.rebuild_index()["passages"] == 0


def test_delete_during_rebuild_cannot_leave_a_retrievable_or_retained_passage(repository):
    note = import_note(repository, "SYNTHETIC_REBUILD_DELETE_SENTINEL anemia learning")
    started, release, deleting = Event(), Event(), Event()
    base = repository.embedder
    class BlockedEmbedder(SyntheticEmbedder):
        def embed(self, texts, **kwargs):
            started.set()
            assert release.wait(10)
            return base.embed(texts, **kwargs)
    repository.embedder = BlockedEmbedder()
    def remove():
        deleting.set()
        return repository.delete_document(note["document_id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        rebuild = pool.submit(repository.rebuild_index)
        assert started.wait(10)
        deletion = pool.submit(remove)
        assert deleting.wait(10)
        release.set()
        assert rebuild.result(timeout=10)["status"] == "ready"
        assert not deletion.result(timeout=10)["cleanup_pending"]
    repository.embedder = base
    assert repository.retrieve("anemia", scope=STUDY)["passages"] == []
    assert repository.index._open().count_rows() == 0
    assert len(repository.index._open().list_versions()) == 1
    assert len(list((repository.paths.indexes / "k").glob("*"))) == 1


def test_legacy_selected_generation_reopens_and_promotes_without_removing_unknown_folders(repository):
    note = import_note(repository, "Legacy renal anemia study note")
    first = repository.rebuild_index()
    previous = repository.index.path
    repository.index.close()
    legacy = repository.paths.indexes / "knowledge-generations" / first["generation"]
    legacy.parent.mkdir(parents=True, exist_ok=True)
    previous.rename(legacy)
    unrelated = legacy.parent / "other-session"
    unrelated.mkdir()
    (unrelated / "sentinel.txt").write_text("Retained unrelated state")
    reopened = KnowledgeRepository(repository.services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder())
    assert reopened.index.path == legacy
    assert reopened.retrieve("anemia", scope=STUDY)["passages"][0]["document_revision"] == note["revision_id"]
    assert reopened.rebuild_index()["passages"] == 1
    assert reopened.index.path.parent == repository.paths.indexes / "k"
    assert not legacy.exists()
    assert (unrelated / "sentinel.txt").read_text() == "Retained unrelated state"
    reopened.index.close()


def test_real_lance_rebuild_at_118_character_profile_path(tmp_path_factory):
    base = tmp_path_factory.mktemp("lance-long")
    assert len(str(base)) < 116
    paths = AppPaths.create(base / ("p" * (118 - len(str(base)) - 1)))
    assert len(str(paths.root)) == 118
    db = Database(paths.database)
    schema = Path(__file__).parents[2] / "runtime/renulus/knowledge/schema.sql"
    db.apply_migration("knowledge-001", schema.read_text())
    for migration in sorted((schema.parent / "migrations").glob("*.sql")):
        db.apply_migration("knowledge-" + migration.stem, migration.read_text())
    repository = KnowledgeRepository(Services(paths, db), extractor=SyntheticExtractor(), embedder=SyntheticEmbedder())
    note = import_note(repository, "Long-path nephrology learning and recovery")
    outcome = repository.rebuild_index()
    assert outcome["status"] == "ready" and outcome["passages"] == 1 and not outcome["cleanup_pending"]
    selected = db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'")
    assert json.loads(selected["value"]) == outcome["generation"]
    reopened = KnowledgeRepository(repository.services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder())
    assert reopened.retrieve("recovery", scope=STUDY)["passages"][0]["document_revision"] == note["revision_id"]
    reopened.index.close()
    repository.index.close()


def test_temporary_and_unclassified_imports_do_not_write(repository, tmp_path):
    before = {str(p): p.read_bytes() for p in repository.paths.root.rglob("*") if p.is_file()}
    for kind in (Scope.TEMPORARY_CASE, Scope.UNCLASSIFIED, Scope.SAVED_CASE):
        with pytest.raises(ApiError) as caught:
            repository.import_text("PRIVATE_SYNTHETIC_CASE_SENTINEL", scope=ContextScope(kind=kind))
        assert caught.value.code == "unsafe_import_scope"
        with pytest.raises(ApiError):
            repository.import_file(tmp_path / "does-not-exist.pdf", scope=ContextScope(kind=kind))
    after = {str(p): p.read_bytes() for p in repository.paths.root.rglob("*") if p.is_file()}
    assert before == after
    assert repository.list_documents()["documents"] == []


def test_replacement_topic_scope_and_overdue_currency(repository):
    import_note(repository, "Original glomerular summaries and lupus table", metadata=SourceMetadata(
        publication_status="final", latest_final_verified=True, content_reviewed=True,
        topic_ids=["glomerular", "lupus"], replaced_topics=["lupus"]))
    assert repository.retrieve("lupus", scope=STUDY)["passages"] == []
    assert repository.retrieve("lupus", topic_id="lupus", scope=STUDY)["passages"] == []
    assert repository.retrieve("glomerular", topic_id="glomerular", scope=STUDY)["passages"] == []
    import_note(repository, "Current anemia guideline", metadata=SourceMetadata(
        topic_ids=["anemia"], publication_status="final", latest_final_verified=True,
        content_reviewed=True, review_due="2020-01-01"))
    assert repository.retrieve("anemia", topic_id="anemia", scope=STUDY, current_only=True)["passages"] == []


def test_restart_requeues_interrupted_job_and_retains_original_and_previous_revision(repository):
    initial = import_note(repository, "Chronic kidney disease note")
    queued = import_note(repository, "Replacement CKD note", document_id=initial["document_id"], process=False)
    repository.db.execute("UPDATE knowledge_jobs SET state='processing' WHERE id=?", (queued["job"]["id"],))
    original = repository.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (queued["revision_id"],))["original_path"]
    repository.index.stage([{
        "passage_id": "partial", "revision_id": queued["revision_id"], "document_id": initial["document_id"],
        "text": "Unactivated partial extraction", "vector": [1.0] + [0.0] * 383,
    }])
    repository.recover()
    assert repository.get_job(queued["job"]["id"])["state"] == "queued"
    assert Path(original).read_text() == "Replacement CKD note"
    assert repository.index._open().count_rows() == 1
    assert repository.get_document(initial["document_id"])["active_revision"] == initial["revision_id"]
    assert repository.run_job(queued["job"]["id"])["state"] == "ready"
    assert repository.get_document(initial["document_id"])["active_revision"] == queued["revision_id"]


def test_cpu_jobs_are_serial_and_waiting_job_can_be_cancelled(repository):
    started, release = Event(), Event()
    base = repository.extractor
    calls = []
    class Blocked:
        def extract_file(self, path, title):
            calls.append(title)
            output = base.extract_file(path, title)
            started.set()
            assert release.wait(10)
            return output
    repository.extractor = Blocked()
    first = import_note(repository, "Serial dialysis note", title="First", process=False)
    second = import_note(repository, "Serial transplant note", title="Second", process=False)
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(repository.run_job, first["job"]["id"])
        assert started.wait(10)
        waiting = pool.submit(repository.run_job, second["job"]["id"])
        assert repository.get_job(second["job"]["id"])["state"] == "queued"
        assert repository.cancel_job(second["job"]["id"])["state"] == "cancelled"
        release.set()
        assert active.result(timeout=10)["state"] == "ready"
        assert waiting.result(timeout=10)["state"] == "cancelled"
    assert calls == ["First"]
