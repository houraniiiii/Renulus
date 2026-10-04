from concurrent.futures import ThreadPoolExecutor
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


def test_restart_marks_interrupted_job_failed_and_retains_previous_revision(repository):
    initial = import_note(repository, "Chronic kidney disease note")
    queued = import_note(repository, "Replacement CKD note", document_id=initial["document_id"], process=False)
    repository.db.execute("UPDATE knowledge_jobs SET state='processing' WHERE id=?", (queued["job"]["id"],))
    repository.recover()
    assert repository.get_job(queued["job"]["id"])["error_code"] == "ingestion_interrupted"
    assert repository.get_document(initial["document_id"])["active_revision"] == initial["revision_id"]
