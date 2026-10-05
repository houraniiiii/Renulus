"""Real Library routes/SQLite/worker, synthetic CPU adapters only."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
from threading import Event
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError, durable_id
from renulus.knowledge import api as library_api
from renulus.knowledge.collection import CollectionCatalogue, MANIFEST
from renulus.knowledge.engines import Extracted
from renulus.knowledge.models import own_text_rights
from renulus.knowledge.priority_queue import INTERACTIVE_BURST, MAX_HINTS, PREFERENCE, LibraryPriorityQueue
from renulus.knowledge.repository import KnowledgeRepository
from renulus.knowledge.worker import IngestionWorker
from renulus.services import Services
from renulus.storage import AppPaths, Database


class SyntheticExtractor:
    def __init__(self):
        self.titles = []
        self.hold_title = None
        self.entered, self.release = Event(), Event()

    def extract_file(self, path, title):
        self.titles.append(title)
        if title == self.hold_title:
            self.entered.set()
            assert self.release.wait(15), "Synthetic conversion was not released"
        text = path.read_text(encoding="utf-8")
        if text == "FAIL":
            raise ApiError("synthetic_failure", "Synthetic extraction failure", 422)
        return Extracted([{"text": text, "context_text": text, "headings": [],
            "locators": [{"page": None, "char_span": [0, len(text)], "item_ref": "#/texts/0"}]}],
            {"synthetic": True})


class SyntheticEmbedder:
    model_id, max_tokens = "synthetic", 512

    def embed(self, texts):
        return [[1.0] for _ in texts]


class SyntheticIndex:
    def __init__(self, path):
        self.path, self.rows = path, []

    def stage(self, rows, **kwargs):
        self.rows.extend(rows)

    def build_fts(self):
        pass

    def remove(self, revision_id):
        self.rows = [row for row in self.rows if row["revision_id"] != revision_id]


@pytest.fixture(autouse=True)
def no_native_engines():
    before = set(sys.modules)
    yield
    heavy = ("docling", "docling_core", "fastembed", "lancedb", "onnxruntime", "torch", "mem0")
    assert not any(name == root or name.startswith(root + ".")
                   for name in set(sys.modules) - before for root in heavy)


@pytest.fixture
def repository(tmp_path):
    paths = AppPaths.create(tmp_path / "synthetic-library")
    db = Database(paths.database)
    module = Path(__file__).parents[2] / "runtime/renulus/knowledge"
    db.apply_migration("knowledge-001", (module / "schema.sql").read_text(encoding="utf-8"))
    for migration in sorted((module / "migrations").glob("*.sql")):
        db.apply_migration("knowledge-" + migration.stem, migration.read_text(encoding="utf-8"))
    services = Services(paths, db)
    return KnowledgeRepository(services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder(),
        index=SyntheticIndex(paths.indexes / "knowledge"))


@pytest.fixture
def client(repository, tmp_path, monkeypatch):
    # Only the actual Library router is installed. No helper bootstrap, other
    # module pollers, default collection access or private/native profile.
    monkeypatch.setattr(library_api, "KnowledgeRepository", lambda services: repository)
    monkeypatch.setattr(library_api, "CollectionCatalogue",
        lambda repo: CollectionCatalogue(repo, tmp_path / "synthetic-collection"))
    app = FastAPI()

    @app.exception_handler(ApiError)
    async def error(request, exception):
        return JSONResponse({"error": {"code": exception.code}}, status_code=exception.status)

    app.include_router(library_api.create_router(repository.services), prefix="/api/v1")
    api = TestClient(app)  # Tests control worker lifecycle to establish the queue first.
    worker = repository.services.registry["knowledge_worker"]
    try:
        yield api, worker
    finally:
        repository.extractor.release.set()
        worker.stop()
        api.close()


def note(api, key, **kwargs):
    return api.post("/api/v1/library/import/text", json={"text": "Synthetic kidney learning " + key,
        "title": key, "scope": {"kind": "personal-library"}, "idempotency_key": key, **kwargs})


def file(api, key):
    return api.post("/api/v1/library/import/file", content=b"Synthetic dialysis file",
        headers={"x-renulus-filename": "synthetic.txt", "x-renulus-import-options": json.dumps({
            "title": key, "scope": {"kind": "personal-library"}, "idempotency_key": key,
            "rights": own_text_rights().model_dump()})})


def hints(repository):
    row = repository.db.fetch_one("SELECT value FROM preferences WHERE key=?", (PREFERENCE,))
    return json.loads(row["value"]) if row else []


def seed_bulk(repository, count):
    # Thousands of canonical synthetic jobs sharing one synthetic stored input:
    # no acquisition inspection and no thousands of file copies/conversions.
    first = repository.import_text("Synthetic bulk source", title="bulk-0", process=False)
    revision = repository.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (first["revision_id"],))
    jobs = [first["job"]["id"]]
    with repository.db.transaction() as conn:
        conn.execute("UPDATE knowledge_jobs SET created_at='2000-01-01T00:00:00' WHERE id=?", (jobs[0],))
        for ordinal in range(1, count):
            document_id, revision_id, job_id = durable_id("doc"), durable_id("rev"), durable_id("ingest")
            created = f"2000-01-01T00:00:00.{ordinal:06d}"
            conn.execute("INSERT INTO knowledge_documents(id,title,source_id,scope_kind,latest_revision,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (document_id, f"bulk-{ordinal}", "R01", "personal-library", revision_id, created, created))
            conn.execute("INSERT INTO knowledge_revisions(id,document_id,ordinal,status,sha256,media_type,bytes,original_path,metadata_json,rights_json,created_at) VALUES(?,?,1,'queued',?,?,?,?,?,?,?)",
                (revision_id, document_id, revision["sha256"], revision["media_type"], revision["bytes"],
                 revision["original_path"], revision["metadata_json"], revision["rights_json"], created))
            conn.execute("INSERT INTO knowledge_jobs(id,revision_id,idempotency_key,request_hash,state,phase,created_at) VALUES(?,?,?,?,'queued','queued',?)",
                (job_id, revision_id, f"bulk-key-{ordinal}", "synthetic-request", created))
            jobs.append(job_id)
    return jobs


def wait_ready(repository, jobs):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        states = [repository.get_job(job)["state"] for job in jobs]
        if all(state == "ready" for state in states):
            return
        assert "failed" not in states, states
        time.sleep(0.01)
    raise AssertionError(states)


def test_direct_note_and_file_pass_two_thousand_bulk_jobs_with_original_times(client, repository):
    api, worker = client
    bulk = seed_bulk(repository, 2000)
    created = repository.db.fetch_all("SELECT id,created_at FROM knowledge_jobs ORDER BY id")
    text, raw = note(api, "new-note"), file(api, "new-file")
    assert text.status_code == raw.status_code == 202
    direct = [text.json()["job"]["id"], raw.json()["job"]["id"]]
    assert hints(repository) == direct
    for job_id in direct:
        assert worker._queue.next_job() == {"id": job_id}
        repository.run_job(job_id)
    assert worker._queue.next_job() == {"id": bulk[0]}
    assert repository.db.fetch_all("SELECT id,created_at FROM knowledge_jobs WHERE id NOT IN (?,?) ORDER BY id", direct) == created
    assert worker.status()["cpu_workers"] == 1


def test_current_conversion_finishes_then_direct_imports_begin(client, repository):
    api, worker = client
    bulk = seed_bulk(repository, 5)
    extractor = repository.extractor
    extractor.hold_title = "bulk-0"
    worker.start()
    assert extractor.entered.wait(5)
    direct = [note(api, "deliberate-note").json(), file(api, "deliberate-file").json()]
    assert worker.active_job == bulk[0]
    assert extractor.titles == ["bulk-0"]
    assert all(repository.get_job(item["job"]["id"])["state"] == "queued" for item in direct)
    extractor.release.set()
    wait_ready(repository, bulk + [item["job"]["id"] for item in direct])
    worker.stop()
    assert extractor.titles == ["bulk-0", "deliberate-note", "deliberate-file",
                                "bulk-1", "bulk-2", "bulk-3", "bulk-4"]
    assert worker.status()["queued"] == 0


def test_finite_burst_makes_bulk_progress_and_drains_when_only_interactive_remains(client, repository):
    api, worker = client
    bulk = seed_bulk(repository, 3)
    direct = [note(api, f"direct-{index}").json()["job"]["id"]
              for index in range(INTERACTIVE_BURST * 2 + 1)]
    worker.start()
    wait_ready(repository, bulk + direct)
    worker.stop()
    expected = ([f"direct-{i}" for i in range(INTERACTIVE_BURST)] + ["bulk-0"] +
        [f"direct-{i}" for i in range(INTERACTIVE_BURST, INTERACTIVE_BURST * 2)] +
        ["bulk-1", f"direct-{INTERACTIVE_BURST * 2}", "bulk-2"])
    assert repository.extractor.titles == expected
    assert hints(repository) == []


def test_conversion_finishing_between_import_commit_and_hint_cannot_start_bulk(client, repository, monkeypatch):
    api, worker = client
    bulk = seed_bulk(repository, 2)
    extractor = repository.extractor
    extractor.hold_title = "bulk-0"
    committed, permit_hint = Event(), Event()
    original_import = repository.import_text

    def delayed_import(*args, **kwargs):
        result = original_import(*args, **kwargs)
        committed.set()
        assert permit_hint.wait(15)
        return result

    monkeypatch.setattr(repository, "import_text", delayed_import)
    worker.start()
    assert extractor.entered.wait(5)
    with ThreadPoolExecutor(max_workers=1) as requests:
        response = requests.submit(note, api, "admission-race")
        try:
            assert committed.wait(5)
            extractor.release.set()
            wait_ready(repository, [bulk[0]])
            deadline = time.monotonic() + 5
            while worker.active_job is not None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert worker.active_job is None
            assert extractor.titles == ["bulk-0"]
            assert repository.get_job(bulk[1])["state"] == "queued"
        finally:
            permit_hint.set()
            extractor.release.set()
        accepted = response.result(timeout=5)
    assert accepted.status_code == 202
    wait_ready(repository, [accepted.json()["job"]["id"], *bulk])
    worker.stop()
    assert extractor.titles == ["bulk-0", "admission-race", "bulk-1"]


def test_interrupted_selected_hint_survives_new_worker_recovery(client, repository):
    api, old = client
    bulk = seed_bulk(repository, 2)
    direct = note(api, "restart-priority").json()
    job_id = direct["job"]["id"]
    assert old._queue.next_job() == {"id": job_id}
    assert hints(repository) == [job_id]
    repository.db.execute("UPDATE knowledge_jobs SET state='processing',phase='extraction' WHERE id=?", (job_id,))
    repository.db.execute("UPDATE knowledge_revisions SET status='processing' WHERE id=?", (direct["revision_id"],))
    fresh = KnowledgeRepository(repository.services, extractor=SyntheticExtractor(),
        embedder=SyntheticEmbedder(), index=repository.index)
    restarted = IngestionWorker(fresh)
    try:
        restarted.start()
        wait_ready(fresh, [job_id, *bulk])
    finally:
        restarted.stop()
    assert fresh.extractor.titles == ["restart-priority", "bulk-0", "bulk-1"]
    assert fresh.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_passages WHERE revision_id=?",
                            (direct["revision_id"],))["n"] == 1


def test_graceful_stop_leaves_new_direct_hint_for_next_start(client, repository):
    api, worker = client
    bulk = seed_bulk(repository, 2)
    extractor = repository.extractor
    extractor.hold_title = "bulk-0"
    worker.start()
    assert extractor.entered.wait(5)
    direct = note(api, "saved-during-conversion").json()["job"]["id"]
    worker.stop(timeout=0.01)
    assert worker._thread.is_alive()
    extractor.release.set()
    worker.stop()
    assert not worker._thread.is_alive()
    assert repository.get_job(direct)["state"] == "queued"
    assert hints(repository) == [direct]
    restarted = IngestionWorker(repository)
    try:
        restarted.start()
        wait_ready(repository, [direct, *bulk])
    finally:
        restarted.stop()
    assert extractor.titles == ["bulk-0", "saved-during-conversion", "bulk-1"]


def test_cancel_replace_delete_missing_and_terminal_hints_are_pruned(client, repository):
    api, worker = client
    bulk = seed_bulk(repository, 1)
    cancelled = note(api, "cancelled").json()
    deleted = note(api, "deleted").json()
    replaced = note(api, "replaced").json()
    ready = note(api, "ready").json()
    failed = note(api, "failed", text="FAIL").json()
    assert api.post("/api/v1/library/jobs/" + cancelled["job"]["id"] + "/cancel").status_code == 200
    assert api.delete("/api/v1/library/documents/" + deleted["document_id"]).status_code == 200
    latest = note(api, "replacement", document_id=replaced["document_id"]).json()
    repository.run_job(ready["job"]["id"])
    repository.run_job(failed["job"]["id"])
    stale = [durable_id("ingest"), *[item["job"]["id"] for item in
             [cancelled, deleted, replaced, ready, failed]], latest["job"]["id"]]
    repository.db.execute("UPDATE preferences SET value=? WHERE key=?", (json.dumps(stale), PREFERENCE))
    assert worker._queue.next_job() == {"id": latest["job"]["id"]}
    assert hints(repository) == [latest["job"]["id"]]
    repository.run_job(latest["job"]["id"])
    assert worker._queue.next_job() == {"id": bulk[0]}
    assert hints(repository) == []
    replay = note(api, "ready").json()
    assert replay["job"]["id"] == ready["job"]["id"] and replay["status"] == "ready"
    assert hints(repository) == []


@pytest.mark.parametrize("submit", [note, file], ids=["note", "file"])
def test_advisory_write_failure_keeps_success_and_replay_identity(client, repository, monkeypatch, submit):
    api, worker = client
    seed_bulk(repository, 2)
    count = repository.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_jobs")["n"]

    def unavailable(conn, ids):
        raise OSError("SYNTHETIC_PRIVATE_FAILURE_TEXT")

    with monkeypatch.context() as patch:
        patch.setattr(worker._queue, "_save", unavailable)
        first, replay = submit(api, "retry-safe"), submit(api, "retry-safe")
        assert first.status_code == replay.status_code == 202
        assert first.json() == replay.json()
        job_id = first.json()["job"]["id"]
        assert repository.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_jobs")["n"] == count + 1
        assert worker._queue.next_job() == {"id": job_id}
        assert "SYNTHETIC_PRIVATE_FAILURE_TEXT" not in first.text + json.dumps(worker.status())
    # Retrying the hint write never reimports or changes the original timestamps.
    before = repository.get_job(job_id)["created_at"]
    assert submit(api, "retry-safe").json()["job"]["id"] == job_id
    assert hints(repository) == [job_id]
    assert repository.get_job(job_id)["created_at"] == before


def test_replay_does_not_reorder_hints_and_changed_request_still_conflicts(client, repository):
    api, worker = client
    first, second = note(api, "first").json(), note(api, "second").json()
    assert note(api, "first").json() == first
    assert hints(repository) == [first["job"]["id"], second["job"]["id"]]
    assert note(api, "first", text="Changed source").status_code == 409
    assert repository.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_jobs")["n"] == 2


def test_hint_capacity_overflow_stays_in_fifo_and_contains_only_job_ids(repository):
    jobs = seed_bulk(repository, MAX_HINTS + 2)
    queue = LibraryPriorityQueue(repository)
    repository.db.execute("INSERT INTO preferences VALUES('synthetic.other','untouched','2000-01-01')")
    for job_id in jobs:
        assert queue.mark(job_id)
    assert hints(repository) == jobs[-MAX_HINTS:]
    assert len(hints(repository)) == MAX_HINTS
    assert queue.next_job() == {"id": jobs[-MAX_HINTS]}
    queue._burst = INTERACTIVE_BURST
    assert queue.next_job() == {"id": jobs[0]}
    row = repository.db.fetch_one("SELECT value FROM preferences WHERE key=?", (PREFERENCE,))["value"]
    assert all(item.startswith("ingest_") and len(item) == 39 for item in json.loads(row))
    assert "Synthetic" not in row and str(repository.paths.root) not in row
    assert repository.db.fetch_one("SELECT value FROM preferences WHERE key='synthetic.other'")["value"] == "untouched"
    assert repository.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_jobs WHERE state='queued'")["n"] == len(jobs)


def test_independent_hint_writers_merge_without_lost_ids(repository):
    jobs = seed_bulk(repository, 8)
    queues = [LibraryPriorityQueue(repository), LibraryPriorityQueue(repository)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: queues[item[0] % 2].mark(item[1]), enumerate(jobs)))
    assert all(results)
    assert set(hints(repository)) == set(jobs)


@pytest.mark.parametrize("value", ["{bad-json", '"source-content"', '["not-a-job-id"]', "x" * 5000],
                         ids=["invalid-json", "non-list", "invalid-id", "oversized"])
def test_damaged_hint_is_advisory_and_next_mark_repairs_it(repository, value):
    bulk = seed_bulk(repository, 2)
    repository.db.execute("INSERT INTO preferences VALUES(?,?,?)", (PREFERENCE, value, "2000-01-01"))
    queue = LibraryPriorityQueue(repository)
    assert queue.next_job() == {"id": bulk[0]}
    assert queue.mark(bulk[1])
    assert hints(repository) == [bulk[1]]


def test_non_library_and_obsolete_revisions_cannot_be_priority_hints(repository):
    bulk = seed_bulk(repository, 3)
    second = repository.db.fetch_one("SELECT r.document_id FROM knowledge_revisions r JOIN knowledge_jobs j ON j.revision_id=r.id WHERE j.id=?", (bulk[1],))
    third = repository.db.fetch_one("SELECT r.document_id FROM knowledge_revisions r JOIN knowledge_jobs j ON j.revision_id=r.id WHERE j.id=?", (bulk[2],))
    repository.db.execute("UPDATE knowledge_documents SET scope_kind='temporary-case' WHERE id=?", (second["document_id"],))
    repository.db.execute("UPDATE knowledge_documents SET latest_revision=NULL WHERE id=?", (third["document_id"],))
    queue = LibraryPriorityQueue(repository)
    queue.mark(bulk[1])
    queue.mark(bulk[2])
    assert hints(repository) == []
    assert queue.next_job() == {"id": bulk[0]}


def test_collection_route_prioritizes_synthetic_selected_file_ahead_of_bulk(client, repository):
    api, worker = client
    background = seed_bulk(repository, 2)
    collection = repository.services.registry["knowledge_catalogue"]
    source = collection.root / "raw/R01/synthetic.txt"
    source.parent.mkdir(parents=True)
    source.write_text("Synthetic teaching file", encoding="utf-8")
    manifest = collection.root / MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"source_id": "R01", "title": "Synthetic bulk file",
        "local_path": "raw/R01/synthetic.txt",
        "processing_scope": {name: True for name in ["display", "cache", "index", "embedding", "model_input"]},
        "licence": {"identifier": "CC-BY-4.0"}}) + "\n", encoding="utf-8")
    assert api.post("/api/v1/library/collection/catalogue", params={"source_id": "R01"}).status_code == 200
    entry = api.get("/api/v1/library/collection/catalogue").json()["entries"][0]
    bulk = api.post("/api/v1/library/collection/import", json={"entry_ids": [entry["id"]],
        "scope": {"kind": "personal-library"}}).json()
    assert bulk["queued"] == 1
    selected = bulk["results"][0]["job"]["id"]
    assert hints(repository) == [selected]
    direct = note(api, "after-collection").json()
    assert worker._queue.next_job() == {"id": selected}
    repository.run_job(selected)
    assert worker._queue.next_job() == {"id": direct["job"]["id"]}
    repository.run_job(direct["job"]["id"])
    assert worker._queue.next_job() == {"id": background[0]}


def test_unsafe_note_and_file_scope_never_creates_hint(client, repository):
    api, worker = client
    assert note(api, "temporary", scope={"kind": "temporary-case"}).status_code == 409
    response = api.post("/api/v1/library/import/file", content=b"SYNTHETIC_TEMPORARY_CASE",
        headers={"x-renulus-filename": "synthetic.txt", "x-renulus-import-options": json.dumps({
            "scope": {"kind": "temporary-case"}, "idempotency_key": "temporary-file"})})
    assert response.status_code == 409
    assert hints(repository) == []
    assert worker.status()["queued"] == 0
    assert not list(repository.paths.library.rglob("original.*"))
