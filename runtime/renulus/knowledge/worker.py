"""One bounded local CPU worker over the existing canonical SQLite queue."""
from threading import Event, Thread

from .priority_queue import LibraryPriorityQueue


class IngestionWorker:
    def __init__(self, repository):
        self.repository = repository
        self._wake = Event()
        self._stop = Event()
        self._thread = None
        self.active_job = None
        self.error_code = None
        self._queue = LibraryPriorityQueue(repository)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self.repository.recover()
        self._stop.clear()
        self._thread = Thread(target=self._run, name="renulus-knowledge-cpu", daemon=True)
        self._thread.start()
        self.wake()

    def wake(self):
        self._wake.set()

    def prioritize(self, job_id):
        self._queue.mark(job_id)
        self.wake()

    def import_interactive(self, operation):
        with self._queue.admission():
            result = operation()
            if result["status"] == "queued":
                self.prioritize(result["job"]["id"])
            return result

    def import_selected(self, operation):
        # Explicit collection selections share the direct-import priority.
        # Bulk import-next keeps its existing FIFO admission. No extraction
        # starts here, and failed/ready entries cannot acquire a queue hint.
        with self._queue.admission():
            result = operation()
            jobs = [item["job"]["id"] for item in result["results"]
                    if item["status"] == "queued"]
            if jobs:
                self._queue.mark_many(jobs)
                self.wake()
            return result

    def stop(self, timeout=5):
        self._stop.set()
        self.wake()
        if self._thread:
            self._thread.join(timeout)
        # A process interrupted during a native conversion leaves a processing
        # row and stored original. The next app startup safely requeues it.

    def status(self):
        return {"running": bool(self._thread and self._thread.is_alive() and not self._stop.is_set()),
                "cpu_workers": 1, "active_job": self.active_job, "error_code": self.error_code,
                "queued": self.repository.db.fetch_one("SELECT COUNT(*) AS n FROM knowledge_jobs WHERE state='queued'")["n"]}

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self._queue.next_job()
                if job:
                    self.active_job = job["id"]
                    self.repository.run_job(job["id"])
                    self.error_code = None
                    continue
            except Exception:
                # No source contents or paths enter worker status/logging.
                self.error_code = "ingestion_worker_unavailable"
            finally:
                self.active_job = None
            self._wake.wait(1)
            self._wake.clear()
