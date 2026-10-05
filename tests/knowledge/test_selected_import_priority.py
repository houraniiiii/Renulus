"""Large synthetic SQLite queue and race checks; no selected engines loaded."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from threading import Event

import pytest

from renulus.knowledge.priority_queue import INTERACTIVE_BURST, MAX_HINTS, LibraryPriorityQueue
from renulus.knowledge.worker import IngestionWorker
from renulus.knowledge.collection import MANIFEST
from test_interactive_queue import client, hints, no_native_engines, repository, seed_bulk, wait_ready


def selected(repository, count=29):
    results = [repository.import_text("Synthetic selected renal teaching",
        title=f"selected-{number}", idempotency_key=f"selected-{number}", process=False)
        for number in range(count)]
    return {"results": results, "queued": len({item["job"]["id"] for item in results
            if item["status"] == "queued"})}


def test_twenty_nine_selected_jobs_pass_a_6175_backlog_with_bounded_fairness(repository, monkeypatch, record_property):
    bulk = seed_bulk(repository, 6175)
    before = repository.db.fetch_all("SELECT id,created_at FROM knowledge_jobs ORDER BY id")
    worker = IngestionWorker(repository)
    saves = []
    save = worker._queue._save
    monkeypatch.setattr(worker._queue, "_save", lambda conn, ids: (saves.append(len(ids)), save(conn, ids)))
    result = worker.import_selected(lambda: selected(repository))
    jobs = [item["job"]["id"] for item in result["results"]]
    assert saves == [29]  # One hint write, rather than 29 preference transactions.
    assert hints(repository) == jobs
    assert repository.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_jobs WHERE state='ready'")["n"] == 0
    order, remaining = [], set(jobs)
    while remaining:
        job = worker._queue.next_job()["id"]
        order.append(job)
        repository.run_job(job)
        remaining.discard(job)
        assert len(order) <= 38
    assert order[:3] == jobs[:3] and order[3] == bulk[0]
    assert [job for job in order if job in jobs] == jobs
    assert [job for job in order if job in bulk] == bulk[:9]
    assert repository.db.fetch_all("SELECT id,created_at FROM knowledge_jobs WHERE id NOT IN (" +
        ",".join("?" for _ in jobs) + ") ORDER BY id", jobs) == before
    assert worker.status()["cpu_workers"] == 1
    record_property("backlog_jobs", len(bulk))
    record_property("selections_until_all_29_ready", len(order))


def test_priority_survives_interrupted_job_recovery_and_new_worker(repository):
    seed_bulk(repository, 5)
    worker = IngestionWorker(repository)
    result = worker.import_selected(lambda: selected(repository, 2))
    first = result["results"][0]["job"]["id"]
    revision = repository.get_job(first)["revision_id"]
    repository.db.execute("UPDATE knowledge_jobs SET state='processing' WHERE id=?", (first,))
    repository.db.execute("UPDATE knowledge_revisions SET status='processing' WHERE id=?", (revision,))
    repository.recover()
    restarted = IngestionWorker(repository)
    assert restarted._queue.next_job() == {"id": first}
    assert repository.get_job(first)["phase"] == "resuming"
    assert hints(repository) == [item["job"]["id"] for item in result["results"]]


def test_selected_jobs_begin_after_the_current_conversion_on_the_only_worker(repository):
    bulk = seed_bulk(repository, 2)
    worker = IngestionWorker(repository)
    extractor = repository.extractor
    extractor.hold_title = "bulk-0"
    worker.start()
    try:
        assert extractor.entered.wait(10)
        result = worker.import_selected(lambda: selected(repository, 2))
        assert worker.active_job == bulk[0]
        assert all(item["status"] == "queued" for item in result["results"])
        extractor.release.set()
        wait_ready(repository, [item["job"]["id"] for item in result["results"]])
        assert extractor.titles[:3] == ["bulk-0", "selected-0", "selected-1"]
        assert worker.status()["cpu_workers"] == 1
    finally:
        extractor.release.set()
        worker.stop()


def test_ready_replay_and_failed_selected_entries_do_not_create_hints(repository):
    first = selected(repository, 1)["results"][0]
    repository.run_job(first["job"]["id"])
    ready = selected(repository, 1)["results"][0]
    result = {"results": [ready, {"status": "failed", "code": "synthetic_rejected_source"}],
              "queued": 0}
    worker = IngestionWorker(repository)
    assert worker.import_selected(lambda: result) is result
    assert hints(repository) == [] and not worker._wake.is_set()


def test_selected_commit_and_priority_admission_cannot_be_split_by_background_selection(repository):
    seed_bulk(repository, 2)
    worker = IngestionWorker(repository)
    committed, release = Event(), Event()

    def operation():
        result = selected(repository, 1)
        committed.set()
        assert release.wait(10)
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        admission = pool.submit(worker.import_selected, operation)
        try:
            assert committed.wait(10)
            selection = pool.submit(worker._queue.next_job)
            release.set()
            result = admission.result(timeout=10)
            assert selection.result(timeout=10) == {"id": result["results"][0]["job"]["id"]}
        finally:
            release.set()


@pytest.mark.parametrize("change", ["cancel", "delete", "replace"])
def test_terminal_or_obsolete_selection_cannot_get_a_hint(repository, change):
    bulk = seed_bulk(repository, 2)
    worker = IngestionWorker(repository)

    def operation():
        result = selected(repository, 1)
        item = result["results"][0]
        if change == "cancel":
            repository.cancel_job(item["job"]["id"])
        elif change == "delete":
            repository.delete_document(item["document_id"])
        else:
            repository.import_text("Synthetic replacement", document_id=item["document_id"], process=False)
        return result

    result = worker.import_selected(operation)
    assert repository.get_job(result["results"][0]["job"]["id"])["state"] == "cancelled"
    assert hints(repository) == []
    assert worker._queue.next_job() == {"id": bulk[0]}


def test_advisory_batch_write_failure_retains_success_and_bounded_retry(repository, monkeypatch):
    seed_bulk(repository, 2)
    worker = IngestionWorker(repository)

    def unavailable(conn, ids):
        raise OSError("SYNTHETIC_PRIVATE_ERROR")

    with monkeypatch.context() as patch:
        patch.setattr(worker._queue, "_save", unavailable)
        result = worker.import_selected(lambda: selected(repository))
        jobs = [item["job"]["id"] for item in result["results"]]
        assert result["queued"] == 29 and all(item["status"] == "queued" for item in result["results"])
        assert worker._queue._pending == jobs
        assert worker._queue.next_job() == {"id": jobs[0]}
        assert hints(repository) == []
    assert worker._queue.next_job() == {"id": jobs[0]}
    assert hints(repository) == jobs
    replay = worker.import_selected(lambda: selected(repository))
    assert replay == result and hints(repository) == jobs


def test_selected_batch_overflow_is_bounded_and_keeps_background_fifo(repository):
    jobs = seed_bulk(repository, 250)
    worker = IngestionWorker(repository)
    worker.import_selected(lambda: {"results": [repository._result(job) for job in jobs], "queued": len(jobs)})
    assert hints(repository) == jobs[-MAX_HINTS:]
    worker._queue._burst = INTERACTIVE_BURST
    assert worker._queue.next_job() == {"id": jobs[0]}


def test_selected_batch_hint_writers_preserve_other_pending_imports(repository):
    jobs = seed_bulk(repository, 29)
    queues = [LibraryPriorityQueue(repository), LibraryPriorityQueue(repository)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: queues[item[0]].mark_many(item[1]),
                                [(0, jobs[:15]), (1, jobs[15:])]))
    assert all(results) and set(hints(repository)) == set(jobs)


def catalogue_entries(api, repository, count):
    """Only tiny original synthetic text files in the existing isolated fixture."""
    root = repository.services.registry["knowledge_catalogue"].root
    records = []
    for number in range(count):
        relative = f"raw/R01/selected-{number}.txt"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"Synthetic renal learning source {number}".encode("utf-8")
        path.write_bytes(payload)
        records.append({"source_id": "R01", "title": f"Synthetic selected source {number}",
            "local_path": relative, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
            "processing_scope": {name: True for name in ("display", "cache", "index", "embedding", "model_input")},
            "licence": {"identifier": "CC-BY-4.0"}})
    manifest = root / MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    assert api.post("/api/v1/library/collection/catalogue", params={"source_id": "R01"}).status_code == 200
    return api.get("/api/v1/library/collection/catalogue").json()["entries"]


def test_collection_api_selects_29_ahead_of_6175_and_replay_preserves_order(client, repository, monkeypatch, record_property):
    api, worker = client
    bulk = seed_bulk(repository, 6175)
    entries = catalogue_entries(api, repository, 29)
    save, writes = worker._queue._save, []
    monkeypatch.setattr(worker._queue, "_save", lambda conn, ids: (writes.append(len(ids)), save(conn, ids)))
    request = {"entry_ids": [item["id"] for item in entries], "scope": {"kind": "personal-library"}}
    response = api.post("/api/v1/library/collection/import", json=request)
    assert response.status_code == 202
    result = response.json()
    jobs = [item["job"]["id"] for item in result["results"]]
    assert result["queued"] == 29 and writes == [29]
    assert all(item["status"] == "queued" for item in result["results"])
    assert hints(repository) == jobs
    times = repository.db.fetch_all("SELECT id,created_at FROM knowledge_jobs ORDER BY id")
    assert api.post("/api/v1/library/collection/import", json=request).json() == result
    assert hints(repository) == jobs and writes == [29, 29]
    assert repository.db.fetch_all("SELECT id,created_at FROM knowledge_jobs ORDER BY id") == times
    assert worker._queue.next_job() == {"id": jobs[0]}
    assert api.get("/api/v1/library/queue").json()["queued"] == len(bulk) + 29
    record_property("route_selected_hints", len(jobs))
    record_property("initial_batch_hint_writes", 1)


def test_collection_api_partial_failure_and_ready_replay_only_hint_live_queued_jobs(client, repository):
    api, worker = client
    entries = catalogue_entries(api, repository, 2)
    request = {"entry_ids": [entries[0]["id"]], "scope": {"kind": "personal-library"}}
    first = api.post("/api/v1/library/collection/import", json=request).json()["results"][0]
    repository.run_job(first["job"]["id"])
    request["entry_ids"] = [entries[0]["id"], "synthetic-missing-entry", entries[1]["id"]]
    response = api.post("/api/v1/library/collection/import", json=request)
    assert response.status_code == 202
    result = response.json()
    assert [item["status"] for item in result["results"]] == ["ready", "failed", "queued"]
    queued = result["results"][2]["job"]["id"]
    assert result["queued"] == 1 and hints(repository) == [queued]
    assert worker._queue.next_job() == {"id": queued}


def test_collection_api_import_next_remains_background_fifo(client, repository, monkeypatch):
    api, worker = client
    collection = repository.services.registry["knowledge_catalogue"]
    admitted = []

    def synthetic_bulk(**kwargs):
        assert kwargs["source_id"] == "L02" and kwargs["limit"] == 2
        result = selected(repository, 2)
        admitted.extend(item["job"]["id"] for item in result["results"])
        return result

    # Isolate routing policy from the separate acquired-literature inspector.
    # These are genuine canonical synthetic imports, with no ready records.
    monkeypatch.setattr(collection, "import_next", synthetic_bulk)
    response = api.post("/api/v1/library/collection/import-next",
        json={"scope": {"kind": "personal-library"}, "limit": 2})
    assert response.status_code == 202 and response.json()["queued"] == 2
    assert hints(repository) == []
    assert worker._queue.next_job() == {"id": admitted[0]}


def test_collection_api_rejects_temporary_scope_before_admission(client, repository, monkeypatch):
    api, worker = client

    def forbidden(entries):
        pytest.fail("Unsafe scope reached collection admission")

    monkeypatch.setattr(repository.services.registry["knowledge_catalogue"], "import_selected", forbidden)
    response = api.post("/api/v1/library/collection/import",
        json={"entry_ids": ["synthetic-entry"], "scope": {"kind": "temporary-case"}})
    assert response.status_code == 409
    assert hints(repository) == [] and worker.status()["queued"] == 0
