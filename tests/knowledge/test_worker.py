from pathlib import Path
import time

from renulus.knowledge.repository import KnowledgeRepository
from renulus.knowledge.worker import IngestionWorker
from test_repository import repository, import_note, SyntheticEmbedder, SyntheticExtractor


def wait_ready(repository, jobs):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if all(repository.get_job(job)["state"] == "ready" for job in jobs):
            return
        time.sleep(0.02)
    raise AssertionError([repository.get_job(job) for job in jobs])


def test_startup_worker_drains_persisted_queue_without_request_and_skips_cancelled(repository):
    first = import_note(repository, "Dialysis persisted queued job", process=False)
    interrupted = import_note(repository, "Transplant persisted interrupted job", process=False)
    cancelled = import_note(repository, "Cancelled sentinel", process=False)
    repository.cancel_job(cancelled["job"]["id"])
    repository.db.execute("UPDATE knowledge_jobs SET state='processing' WHERE id=?", (interrupted["job"]["id"],))
    fresh = KnowledgeRepository(repository.services, extractor=SyntheticExtractor(), embedder=SyntheticEmbedder())
    worker = IngestionWorker(fresh)
    worker.start()
    try:
        wait_ready(fresh, [first["job"]["id"], interrupted["job"]["id"]])
        assert fresh.get_job(cancelled["job"]["id"])["state"] == "cancelled"
        assert worker.status()["cpu_workers"] == 1
        assert worker.status()["queued"] == 0
        assert fresh.index._open().count_rows() == 2
    finally:
        worker.stop()
    assert not worker.status()["running"]
