"""Advisory, bounded Library job IDs over the existing canonical queue."""
from contextlib import contextmanager
import json
import re
from threading import RLock

from ..storage.database import utc_now

PREFERENCE = "knowledge.interactive_imports"
# Tunable queue policy, not permanent product limits. Overflow stays in FIFO.
MAX_HINTS = 64
INTERACTIVE_BURST = 3
JOB_ID = re.compile(r"ingest_[0-9a-f]{32}")


class LibraryPriorityQueue:
    def __init__(self, repository):
        self.repository = repository
        self.db = repository.db
        self._lock = RLock()
        self._pending = []
        self._burst = 0

    @contextmanager
    def admission(self):
        # Let the active conversion finish, but select nothing else between a
        # deliberate import's canonical commit and its advisory priority mark.
        with self._lock:
            yield

    @staticmethod
    def _bounded(values):
        ids = []
        for value in values:
            if isinstance(value, str) and JOB_ID.fullmatch(value) and value not in ids:
                ids.append(value)
        return ids[-MAX_HINTS:]

    def _load(self, conn):
        row = conn.execute("SELECT value FROM preferences WHERE key=?", (PREFERENCE,)).fetchone()
        if not row:
            return []
        try:
            # Reject damaged/oversized hints without treating them as job data.
            values = json.loads(row["value"]) if len(row["value"]) <= MAX_HINTS * 64 else None
        except (TypeError, ValueError):
            values = None
        return self._bounded(values) if isinstance(values, list) else []

    def _save(self, conn, ids):
        conn.execute("INSERT INTO preferences(key,value,updated_at) VALUES(?,?,?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
                     (PREFERENCE, json.dumps(ids, separators=(",", ":")), utc_now()))

    @staticmethod
    def _live(conn, ids):
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            "SELECT j.id,j.state FROM knowledge_jobs j "
            "JOIN knowledge_revisions r ON r.id=j.revision_id "
            "JOIN knowledge_documents d ON d.id=r.document_id "
            "WHERE d.scope_kind='personal-library' AND d.deleted_at IS NULL "
            "AND d.latest_revision=r.id AND j.state IN ('queued','processing') "
            f"AND j.id IN ({placeholders})", ids).fetchall()
        return {row["id"]: row["state"] for row in rows}

    def mark(self, job_id):
        """Best effort: import success must survive an advisory write failure."""
        if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
            return False
        return self.mark_many([job_id])

    def mark_many(self, job_ids):
        """Persist a bounded deliberate selection in one advisory transaction."""
        selected = self._bounded(job_ids)
        if not selected:
            return False
        with self._lock:
            self._pending = self._bounded([*self._pending, *selected])
            try:
                with self.db.transaction() as conn:
                    ids = self._bounded([*self._load(conn), *self._pending])
                    live = self._live(conn, ids)
                    self._save(conn, [item for item in ids if item in live])
            except Exception:
                # IDs only in this bounded retry buffer; no contents or paths.
                return False
            self._pending = []
            return True

    def next_job(self):
        with self._lock:
            job, interactive = None, False
            try:
                with self.db.transaction() as conn:
                    stored = self._load(conn)
                    ids = self._bounded([*stored, *self._pending])
                    live = self._live(conn, ids)
                    ids = [item for item in ids if item in live]
                    queued = [item for item in ids if live[item] == "queued"]
                    if queued and self._burst < INTERACTIVE_BURST:
                        job, interactive = {"id": queued[0]}, True
                    else:
                        exclusion = " AND id NOT IN (" + ",".join("?" for _ in ids) + ")" if ids else ""
                        row = conn.execute("SELECT id FROM knowledge_jobs WHERE state='queued'" +
                            exclusion + " ORDER BY created_at,id LIMIT 1", ids).fetchone()
                        if row:
                            job = dict(row)
                        elif queued:
                            job, interactive = {"id": queued[0]}, True
                    if ids != stored or self._pending:
                        self._save(conn, ids)
                self._pending = []
            except Exception:
                # A failed hint write does not discard a selection already read
                # from canonical state. A failed read falls back to normal FIFO.
                if job is None:
                    job = self.repository.next_queued_job()
            self._burst = min(self._burst + 1, INTERACTIVE_BURST) if interactive else 0
            # Keep selected hints until terminal state: an interrupted conversion
            # can be requeued by repository.recover() without losing its priority.
            return job
