"""Synthetic, event-driven Library concurrency and publication regressions.

Engine barriers prove responses happen while work is blocked; deadlines only
bound a failing test. No models, downloads, provider calls or native profiles.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event, Lock, get_ident
from types import ModuleType
import sys

import pytest
from fastapi.testclient import TestClient

from renulus.contracts import ApiError
from renulus.knowledge.engines import Extracted, FastEmbedEngine
from renulus.knowledge.models import SourceMetadata
from test_repository import (
    STUDY, SyntheticEmbedder, SyntheticExtractor, import_note, repository,
)

RESPONSE_TIMEOUT = 3
WORK_TIMEOUT = 12


class Barrier:
    def __init__(self):
        self.entered, self.release = Event(), Event()

    def block(self):
        self.entered.set()
        assert self.release.wait(WORK_TIMEOUT), "engine barrier was not released"

    def wait(self):
        assert self.entered.wait(WORK_TIMEOUT), "engine never reached the barrier"


@contextmanager
def blocked_work(barrier, operation, *, workers=6):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        work = pool.submit(operation)
        try:
            barrier.wait()
            yield pool, work
        finally:
            # Always release before executor shutdown, including failed assertions.
            barrier.release.set()


class MemoryIndex:
    """Small derived-index double; canonical eligibility remains repository work."""
    def __init__(self, path):
        self.path = path
        self.rows, self.stage_calls = [], []
        self.fts_calls = 0
        self.search_barrier = self.stage_barrier = self.fts_barrier = self.remove_barrier = None
        self.block_stage_call = 1
        self.fail_fts = False
        self.fail_remove = set()
        self.on_stage = None

    def stage(self, rows, *, create_fts=True):
        rows = [dict(row) for row in rows]
        self.rows.extend(rows)
        self.stage_calls.append((len(rows), create_fts))
        if self.on_stage:
            self.on_stage()
        if self.stage_barrier and len(self.stage_calls) == self.block_stage_call:
            self.stage_barrier.block()
        if create_fts:
            self.build_fts()

    def build_fts(self):
        self.fts_calls += 1
        if self.fts_barrier:
            self.fts_barrier.block()
        if self.fail_fts:
            raise ApiError("synthetic_fts_failure", "Synthetic FTS failure", 503)

    def search(self, query, vector, revision_ids, limit):
        # Capture hits before the barrier to emulate a stale native search.
        hits = [dict(row) for row in self.rows if row["revision_id"] in revision_ids]
        if self.search_barrier:
            self.search_barrier.block()
        return hits[:limit]

    def remove(self, revision_id):
        if self.remove_barrier:
            self.remove_barrier.block()
        if revision_id in self.fail_remove:
            raise ApiError("synthetic_cleanup_failure", "Synthetic cleanup failure", 503)
        self.rows[:] = [row for row in self.rows if row["revision_id"] != revision_id]


class RecordingEmbedder(SyntheticEmbedder):
    def __init__(self):
        self.batches = []
        self.query_barrier = self.ingest_barrier = None

    def embed(self, texts, *, query=False):
        texts = list(texts)
        if query and self.query_barrier:
            self.query_barrier.block()
        if not query:
            self.batches.append(len(texts))
            if self.ingest_barrier:
                self.ingest_barrier.block()
        return super().embed(texts, query=query)


class PassageExtractor(SyntheticExtractor):
    def __init__(self, count=1):
        self.count = count

    def extract_file(self, path, title):
        base = super().extract_file(path, title)
        passages = []
        for number in range(self.count):
            text = base.passages[0]["text"] + f" passage {number}"
            passages.append({"text": text, "context_text": text,
                "headings": [title], "locators": [{"page": 3,
                    "char_span": [0, len(text)], "item_ref": f"#/texts/{number}"}]})
        return Extracted(passages, {"synthetic": True})


@pytest.fixture
def library(repository):
    repository.index = MemoryIndex(repository.index.path)
    repository.embedder = RecordingEmbedder()
    repository.extractor = PassageExtractor()
    return repository


def current_metadata():
    return SourceMetadata(doi="10.9999/renulus-synthetic-concurrency",
        topic_ids=["dialysis"], publication_status="final",
        content_reviewed=True, latest_final_verified=True)


def assert_metadata_responsive(pool, library, note, *, processing=None):
    calls = {
        "page": lambda: library.list_documents(limit=100),
        "document": lambda: library.get_document(note["document_id"]),
        "citation": lambda: library.citation(note["revision_id"]),
        "job": lambda: library.get_job((processing or note)["job"]["id"]),
    }
    pending = {name: pool.submit(call) for name, call in calls.items()}
    result = {name: future.result(timeout=RESPONSE_TIMEOUT)
              for name, future in pending.items()}
    assert result["page"]["total"] >= 1
    assert result["document"]["active_revision"] == note["revision_id"]
    assert result["citation"]["document_revision"] == note["revision_id"]
    assert result["job"]["state"] == ("processing" if processing else "ready")
    return result


@pytest.mark.parametrize("phase", ["embedding", "search"])
def test_query_does_not_block_library_metadata(library, phase):
    note = import_note(library, "Synthetic dialysis source")
    barrier = Barrier()
    if phase == "embedding":
        library.embedder.query_barrier = barrier
    else:
        library.index.search_barrier = barrier
    with blocked_work(barrier, lambda: library.retrieve("dialysis", scope=STUDY)) as (pool, query):
        assert_metadata_responsive(pool, library, note)
        assert not barrier.release.is_set()
        barrier.release.set()
        assert query.result(timeout=WORK_TIMEOUT)["passages"][0]["document_revision"] == note["revision_id"]


@pytest.mark.parametrize("phase", ["embedding", "search"])
@pytest.mark.parametrize("change", ["delete", "replace", "retract", "access", "pages", "review"])
def test_query_rechecks_canonical_eligibility_after_blocked_engine(library, phase, change):
    metadata = current_metadata()
    note = import_note(library, "Synthetic dialysis eligibility sentinel", metadata=metadata)
    barrier = Barrier()
    if phase == "embedding":
        library.embedder.query_barrier = barrier
    else:
        library.index.search_barrier = barrier

    def mutate():
        if change == "delete":
            return library.delete_document(note["document_id"])
        if change == "replace":
            # Queuing a reserved replacement revokes personal-study eligibility
            # immediately; publication itself must wait for the index lock.
            return import_note(library, "Synthetic reserved replacement",
                document_id=note["document_id"], metadata=metadata, reserved=True,
                process=phase != "search")
        changes = {"retract": {"retracted": True},
            "access": {"access_changed": True}, "pages": {"excluded_pages": [3]},
            "review": {"content_reviewed": False}}[change]
        return library.update_source_status({"contract_version": 1,
            "event_id": f"synthetic-{phase}-{change}", "source_id": metadata.source_id,
            "identity": {"doi": metadata.doi}, "changes": changes,
            "evidence": [{"inspected": True, "note": "Synthetic test evidence"}]})

    with blocked_work(barrier, lambda: library.retrieve("dialysis", scope=STUDY,
            topic_id="dialysis", current_only=True)) as (pool, query):
        mutation = pool.submit(mutate).result(timeout=RESPONSE_TIMEOUT)
        if change == "replace":
            document = library.get_document(note["document_id"])
            assert document["reserved"] is True
            assert mutation["status"] == ("queued" if phase == "search" else "ready")
            assert document["active_revision"] == (note["revision_id"] if phase == "search" else mutation["revision_id"])
        elif change == "delete":
            assert library.get_document(note["document_id"], include_deleted=True)["active_revision"] is None
        else:
            assert mutation["state"] == "applied" and mutation["revisions"] == 1
        assert not barrier.release.is_set()
        barrier.release.set()
        assert query.result(timeout=WORK_TIMEOUT)["passages"] == []
    if change == "replace" and phase == "search":
        assert library.run_job(mutation["job"]["id"])["state"] == "ready"
        assert library.get_document(note["document_id"])["active_revision"] == mutation["revision_id"]
    library.cleanup()
    if change == "delete":
        assert not any(row["document_id"] == note["document_id"] for row in library.index.rows)
        assert library.get_document(note["document_id"], include_deleted=True)["cleanup_pending"] is False


def test_completed_replacement_during_query_embedding_never_returns_old_revision(library):
    note = import_note(library, "Old synthetic transplant revision")
    barrier = library.embedder.query_barrier = Barrier()
    with blocked_work(barrier, lambda: library.retrieve("transplant", scope=STUDY)) as (pool, query):
        replacement = pool.submit(lambda: import_note(library,
            "New synthetic transplant revision", document_id=note["document_id"])).result(timeout=RESPONSE_TIMEOUT)
        assert replacement["status"] == "ready"
        barrier.release.set()
        result = query.result(timeout=WORK_TIMEOUT)
        assert all(p["document_revision"] == replacement["revision_id"] for p in result["passages"])
    assert library.retrieve("transplant", scope=STUDY)["passages"][0]["document_revision"] == replacement["revision_id"]


@pytest.mark.parametrize("phase", ["stage", "fts"])
@pytest.mark.parametrize("outcome", ["ready", "cancelled", "failed"])
def test_staging_keeps_metadata_and_previous_revision_until_atomic_publication(library, phase, outcome):
    note = import_note(library, "Previous synthetic glomerular revision")
    replacement = import_note(library, "Replacement synthetic glomerular revision",
        document_id=note["document_id"], process=False)
    barrier = Barrier()
    library.index.stage_calls.clear()
    if phase == "stage":
        library.index.stage_barrier = barrier
    else:
        library.index.fts_barrier = barrier
    library.index.fail_fts = outcome == "failed"
    with blocked_work(barrier, lambda: library.run_job(replacement["job"]["id"])) as (pool, job):
        response = assert_metadata_responsive(pool, library, note, processing=replacement)
        newest = response["document"]["revisions"][0]
        assert newest["id"] == replacement["revision_id"]
        assert newest["status"] == "processing" and newest["passage_count"] == 0
        assert any(row["revision_id"] == replacement["revision_id"] for row in library.index.rows)
        if outcome == "cancelled":
            assert pool.submit(library.cancel_job, replacement["job"]["id"]).result(timeout=RESPONSE_TIMEOUT)["state"] == "cancelled"
            assert library.get_document(note["document_id"])["active_revision"] == note["revision_id"]
        assert not barrier.release.is_set()
        barrier.release.set()
        assert job.result(timeout=WORK_TIMEOUT)["state"] == outcome
    library.cleanup()
    document = library.get_document(note["document_id"])
    assert document["active_revision"] == (replacement["revision_id"] if outcome == "ready" else note["revision_id"])
    if outcome != "ready":
        assert not library.db.fetch_all("SELECT * FROM knowledge_passages WHERE revision_id=?", (replacement["revision_id"],))
        assert not any(row["revision_id"] == replacement["revision_id"] for row in library.index.rows)
        assert not library._folder(note["document_id"], replacement["revision_id"]).exists()
    assert document["cleanup_pending"] is False


@pytest.mark.parametrize("count", [65, 129, 193])
def test_ingestion_batches_are_bounded_and_never_publish_partial_ready(library, count):
    library.extractor = PassageExtractor(count)
    note = import_note(library, "Synthetic CKD batch source", process=False)
    observations = []

    def observe():
        document = library.get_document(note["document_id"])
        observations.append((document["active_revision"], document["status"],
            document["revisions"][0]["passage_count"], library.get_job(note["job"]["id"])["state"]))

    library.index.on_stage = observe
    assert library.run_job(note["job"]["id"])["state"] == "ready"
    expected_batches = [64] * (count // 64) + ([count % 64] if count % 64 else [])
    assert library.embedder.batches == expected_batches
    assert library.index.stage_calls == [(size, False) for size in expected_batches]
    assert library.index.fts_calls == 1
    assert observations == [(None, "processing", 0, "processing")] * len(expected_batches)
    document = library.get_document(note["document_id"])
    assert document["active_revision"] == note["revision_id"]
    assert document["revisions"][0]["passage_count"] == count
    assert len(library.index.rows) == count


def test_cancellation_between_batches_removes_all_partial_index_rows(library):
    library.extractor = PassageExtractor(193)
    note = import_note(library, "Synthetic anemia cancelled batch source", process=False)
    barrier = library.index.stage_barrier = Barrier()
    library.index.block_stage_call = 2
    with blocked_work(barrier, lambda: library.run_job(note["job"]["id"])) as (pool, job):
        assert len(library.index.rows) == 128
        assert pool.submit(library.cancel_job, note["job"]["id"]).result(timeout=RESPONSE_TIMEOUT)["state"] == "cancelled"
        assert library.get_document(note["document_id"])["active_revision"] is None
        barrier.release.set()
        assert job.result(timeout=WORK_TIMEOUT)["state"] == "cancelled"
    assert library.index.rows == []
    assert library.embedder.batches == [64, 64]
    assert library.index.stage_calls == [(64, False), (64, False)]
    assert library.index.fts_calls == 0
    assert library.db.fetch_all("SELECT * FROM knowledge_passages") == []
    assert library.db.fetch_all("SELECT * FROM knowledge_cleanup") == []
    assert not library._folder(note["document_id"], note["revision_id"]).exists()


def test_blocked_physical_cleanup_keeps_other_library_metadata_responsive(library):
    kept = import_note(library, "Synthetic dialysis retained source")
    removed = import_note(library, "Synthetic transplant removed source")
    barrier = library.index.remove_barrier = Barrier()
    with blocked_work(barrier, lambda: library.delete_document(removed["document_id"])) as (pool, deletion):
        assert_metadata_responsive(pool, library, kept)
        deleted = pool.submit(lambda: library.get_document(removed["document_id"],
            include_deleted=True)).result(timeout=RESPONSE_TIMEOUT)
        assert deleted["status"] == "deleted"
        assert deleted["active_revision"] is None and deleted["cleanup_pending"] is True
        assert not barrier.release.is_set()
        barrier.release.set()
        assert deletion.result(timeout=WORK_TIMEOUT)["cleanup_pending"] is False
    assert all(row["document_id"] != removed["document_id"] for row in library.index.rows)


def test_page100_uses_constant_connections_and_preserves_full_revision_details(library, monkeypatch):
    notes = [import_note(library, "FAIL" if n == 3 else f"Synthetic source {n}",
        title=f"Synthetic nephrology {n:03}", process=False, reserved=n == 6) for n in range(100)]
    for note in notes[:2]:
        assert library.run_job(note["job"]["id"])["state"] == "ready"
    replacement = import_note(library, "Synthetic failed replacement",
        document_id=notes[0]["document_id"], process=False)
    library.cancel_job(replacement["job"]["id"])
    assert library.run_job(notes[3]["job"]["id"])["state"] == "failed"
    library.index.fail_remove.add(notes[4]["revision_id"])
    assert library.delete_document(notes[4]["document_id"])["cleanup_pending"]
    library.db.execute("UPDATE knowledge_documents SET updated_at=?", ("2026-10-05T00:00:00+00:00",))
    expected = {note["document_id"]: library.get_document(note["document_id"], include_deleted=True) for note in notes}
    assert expected[notes[0]["document_id"]]["active_revision"] == notes[0]["revision_id"]
    assert len(expected[notes[0]["document_id"]]["revisions"]) == 2
    assert expected[notes[4]["document_id"]]["cleanup_pending"] is True
    actual_connect, connections = library.db.connect, []

    def connect():
        connections.append(1)
        return actual_connect()

    monkeypatch.setattr(library.db, "connect", connect)
    small = library.list_documents(include_deleted=True, limit=1)
    small_connections = len(connections)
    connections.clear()
    page = library.list_documents(include_deleted=True, limit=100)
    page_connections = len(connections)
    assert 1 <= small_connections <= 8
    assert page_connections <= 8, f"list100 opened {page_connections} SQLite connections"
    assert page_connections <= small_connections + 2
    assert page["total"] == small["total"] == 100
    assert page["counts"] == {"queued": 96, "ready": 1, "cancelled": 1, "failed": 1, "deleted": 1}
    assert [document["id"] for document in page["documents"]] == sorted(expected)
    assert {document["id"]: document for document in page["documents"]} == expected
    replaced_document = next(document for document in page["documents"]
                             if document["id"] == notes[0]["document_id"])
    assert [revision["ordinal"] for revision in replaced_document["revisions"]] == [2, 1]
    assert [revision["status"] for revision in replaced_document["revisions"]] == ["cancelled", "ready"]
    assert [revision["passage_count"] for revision in replaced_document["revisions"]] == [0, 1]
    revision_keys = {"id", "document_id", "ordinal", "status", "sha256",
        "media_type", "bytes", "metadata", "rights", "embedding_model",
        "chunk_tokens", "created_at", "activated_at", "passage_count"}
    for document in page["documents"]:
        for revision in document["revisions"]:
            assert set(revision) == revision_keys
            assert "original_path" not in revision and "extraction_json" not in revision


@pytest.mark.parametrize("phase", ["embedding", "stage", "fts"])
def test_asgi_lifespan_worker_drains_queue_while_library_routes_respond(tmp_path, monkeypatch, phase):
    from renulus import server

    # Exercise the real application boundary and Library router lifespan only;
    # omit unrelated helper and memory startup from this focused route proof.
    monkeypatch.setattr(server, "MODULE_ORDER", ("knowledge",))
    app = server.create_app(tmp_path / "asgi-profile")
    library = app.state.services.registry["knowledge"]
    library.index = MemoryIndex(library.index.path)
    library.extractor, library.embedder = PassageExtractor(), RecordingEmbedder()
    note = import_note(library, "Previous synthetic electrolyte source")
    queued = import_note(library, "Queued synthetic electrolyte replacement",
        document_id=note["document_id"], process=False)
    barrier = Barrier()
    if phase == "embedding":
        library.embedder.ingest_barrier = barrier
    elif phase == "stage":
        library.index.stage_calls.clear()
        library.index.stage_barrier = barrier
    else:
        library.index.fts_barrier = barrier
    completed, run_job = Event(), library.run_job

    def observed_job(job_id):
        try:
            return run_job(job_id)
        finally:
            completed.set()

    monkeypatch.setattr(library, "run_job", observed_job)
    worker = app.state.services.registry["knowledge_worker"]
    with TestClient(app) as api:
        try:
            barrier.wait()
            routes = ["/documents?limit=100", f"/documents/{note['document_id']}",
                f"/revisions/{note['revision_id']}/citation", f"/jobs/{queued['job']['id']}", "/queue"]
            with ThreadPoolExecutor(max_workers=len(routes)) as pool:
                responses = [pool.submit(api.get, "/api/v1/library" + route) for route in routes]
                try:
                    responses = [future.result(timeout=RESPONSE_TIMEOUT) for future in responses]
                finally:
                    # Release before executor teardown even if a route deadlocks.
                    barrier.release.set()
            assert all(response.status_code == 200 for response in responses)
            assert responses[1].json()["active_revision"] == note["revision_id"]
            assert responses[3].json()["state"] == "processing"
            assert responses[4].json()["running"] is True
            assert responses[4].json()["cpu_workers"] == 1
            assert completed.wait(WORK_TIMEOUT)
            assert api.get(f"/api/v1/library/jobs/{queued['job']['id']}").json()["state"] == "ready"
            hit = api.post("/api/v1/library/retrieve", json={"query": "electrolyte",
                "scope": {"kind": STUDY.kind.value}}).json()["passages"][0]
            assert hit["document_revision"] == queued["revision_id"]
        finally:
            barrier.release.set()
    assert not worker.status()["running"]
    assert not worker._thread.is_alive()


def test_fastembed_serializes_lazy_model_creation_and_iterator_consumption(tmp_path, monkeypatch):
    construction, consumption = Barrier(), Barrier()
    second_attempted, second_finished = Event(), Event()
    instances, calls, asset_calls = [], [], []
    overlap, state_lock = [], Lock()
    active = 0

    class Assets:
        def validate(self, kind):
            assert kind == "fastembed"
            asset_calls.append("validate")
            return tmp_path

        def config(self, kind):
            assert kind == "fastembed"
            asset_calls.append("config")
            return {"cache_dir": tmp_path, "cpu_threads": 1}

    class TextEmbedding:
        def __init__(self, **options):
            instances.append(options)
            assert options["local_files_only"] is True
            assert options["providers"] == ["CPUExecutionProvider"]
            assert options["cuda"] is False
            construction.block()

        def passage_embed(self, texts):
            return self.values(texts, "passage")

        def query_embed(self, texts):
            return self.values(texts, "query")

        def values(self, texts, kind):
            nonlocal active
            with state_lock:
                active += 1
                overlap.append(active)
                calls.append(kind)
            try:
                if kind == "passage":
                    consumption.block()
                for _ in texts:
                    yield [1.0] + [0.0] * 383
            finally:
                with state_lock:
                    active -= 1

    module = ModuleType("fastembed")
    module.TextEmbedding = TextEmbedding
    monkeypatch.setitem(sys.modules, "fastembed", module)
    engine = FastEmbedEngine(Assets())
    model_lock = engine._model_lock

    class ObservedLock:
        """Signal actual lock entry, before acquisition; no scheduler sleeps."""
        owner = None

        def __enter__(self):
            if self.owner is None:
                self.owner = get_ident()
            elif self.owner != get_ident():
                second_attempted.set()
            model_lock.acquire()
            return self

        def __exit__(self, *error):
            model_lock.release()

    engine._model_lock = ObservedLock()

    def query():
        try:
            return engine.embed(["Synthetic query"], query=True)
        finally:
            second_finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        passage = pool.submit(engine.embed, ["Synthetic passage"])
        try:
            construction.wait()
            retrieval = pool.submit(query)
            assert second_attempted.wait(WORK_TIMEOUT)
            assert len(instances) == 1
            construction.release.set()
            consumption.wait()
            assert not second_finished.is_set()
            assert calls == ["passage"]
            consumption.release.set()
            assert passage.result(timeout=WORK_TIMEOUT) == retrieval.result(timeout=WORK_TIMEOUT)
        finally:
            construction.release.set()
            consumption.release.set()
    assert len(instances) == 1
    assert asset_calls == ["validate", "config"]
    assert calls == ["passage", "query"]
    assert overlap == [1, 1]
