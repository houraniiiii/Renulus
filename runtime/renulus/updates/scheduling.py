"""Durable opt-in checks while the local app is running, using existing producers."""
import asyncio
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import uuid4

from renulus.contracts import ApiError
from .fetch import validate_url


MAX_SELECTION = 20
MAX_BATCH = 5
RETRY_SECONDS = (300, 1800)
CHECK_TIMEOUT = 50
BATCH_PAUSE = 60


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def public_catalogue(source):
    """Supported public index pages, not all URLs/rights in the source register."""
    url = urlparse(source["url"])
    host = (url.hostname or "").removeprefix("www.")
    if source["id"] in {f"K{i:02d}" for i in range(19)}:
        eligible = host == "kdigo.org" and url.path.startswith("/guidelines/")
    else:
        eligible = (source["id"], host, url.path.rstrip("/")) in {
            ("G01", "era-online.org", "/era-guidance"),
            ("G02", "ukkidney.org", "/health-professionals/guidelines/guidelines-commentaries"),
        }
    if not eligible or url.query or url.fragment:
        return False
    try:
        validate_url(source["url"], {url.hostname})
        return True
    except ApiError:
        return False


class Scheduling:
    def __init__(self, updates, clock=None):
        self.updates, self.db = updates, updates.db
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._worker = self._batch = None
        self._active = set()
        self._closing = False

    def options(self):
        sources = {source["id"]: source for source in self.updates.sources if public_catalogue(source)}
        options = [{"kind": "source", "id": key, "source_id": key, "title": source["title"],
                    "route": "public publication links"} for key, source in sources.items()]
        for publication in self.updates.publications.list():
            # Digest checks retain the explicit tracking/permission prerequisite.
            # ERA membership bodies are never automatic-check candidates.
            url = urlparse(publication["url"])
            if publication["source_id"] not in sources or publication["source_id"] == "G01":
                continue
            host = (url.hostname or "").removeprefix("www.")
            if host not in ("kdigo.org", "ukkidney.org") or not publication["permission_reference"]:
                continue
            if not url.path.lower().endswith(".pdf") or not url.path.startswith(
                ("/wp-content/uploads/", "/sites/", "/health-professionals/")
            ):
                continue
            try:
                validate_url(publication["url"], {url.hostname})
            except ApiError:
                continue
            options.append({"kind": "publication", "id": publication["id"],
                            "source_id": publication["source_id"], "title": publication["title"],
                            "route": "tracked public publication digest"})
        # L03 is the existing anonymous Europe PMC metadata producer.
        registered = next((source for source in self.updates.sources if source["id"] == "L03"), None)
        content = self.updates.services.registry.get("content")
        if registered and urlparse(registered["url"]).hostname in ("europepmc.org", "www.ebi.ac.uk") and content:
            options.extend({"kind": "literature", "id": topic["id"], "source_id": "L03",
                            "title": topic["title"], "route": "Europe PMC topic metadata (25 records)"}
                           for topic in content.list_topics())
        return options

    def status(self):
        config = self.db.fetch_one("SELECT * FROM update_schedule WHERE id=1")
        jobs = self.db.fetch_all("SELECT * FROM update_schedule_jobs ORDER BY kind,target_id")
        last_run = self.db.fetch_one("SELECT * FROM update_schedule_runs ORDER BY started_at DESC,rowid DESC LIMIT 1")
        next_due = min((job["next_due_at"] for job in jobs), default=None) if config["enabled"] else None
        available = {(option["kind"], option["id"]): option for option in self.options()}
        for job in jobs:
            option = available.get((job["kind"], job["target_id"]))
            job["title"] = option["title"] if option else job["target_id"]
            job["available"] = bool(option)
        return {"enabled": bool(config["enabled"]), "cadence_hours": config["cadence_hours"],
                "selection": [{"kind": job["kind"], "id": job["target_id"]} for job in jobs],
                "jobs": jobs, "options": list(available.values()), "last_run": last_run,
                "next_due_at": next_due, "running": bool(self._batch and not self._batch.done()),
                "max_batch": MAX_BATCH, "max_selection": MAX_SELECTION, "max_retries": len(RETRY_SECONDS),
                "app_running_only": True}

    def configure(self, enabled, cadence_hours=24, selection=()):
        if self._batch and not self._batch.done():
            raise ApiError("schedule_busy", "Stop the running batch before changing automatic checks", 409)
        if not 24 <= cadence_hours <= 720:
            raise ApiError("schedule_cadence_invalid", "Choose an interval from 24 to 720 hours")
        keys = {(item["kind"], item["id"]) for item in selection}
        available = {(item["kind"], item["id"]) for item in self.options()}
        if len(selection) > MAX_SELECTION or not keys <= available:
            raise ApiError("schedule_selection_invalid", "Choose at most 20 supported public routes shown in Updates")
        if enabled and not keys:
            raise ApiError("schedule_selection_required", "Select a public source before enabling automatic checks")
        now = self.clock()
        with self.db.transaction() as conn:
            old = conn.execute("SELECT * FROM update_schedule WHERE id=1").fetchone()
            conn.execute("UPDATE update_schedule SET enabled=?,cadence_hours=?,updated_at=? WHERE id=1",
                         (int(enabled), cadence_hours, stamp(now)))
            for row in conn.execute("SELECT kind,target_id FROM update_schedule_jobs").fetchall():
                if (row["kind"], row["target_id"]) not in keys:
                    conn.execute("DELETE FROM update_schedule_jobs WHERE kind=? AND target_id=?", (row["kind"], row["target_id"]))
            for kind, target in keys:
                conn.execute("INSERT OR IGNORE INTO update_schedule_jobs(kind,target_id,next_due_at) VALUES(?,?,?)",
                             (kind, target, stamp(now)))
            if old["cadence_hours"] != cadence_hours:
                # A cadence edit does not clear failures or reclassify previous evidence.
                for job in conn.execute("SELECT * FROM update_schedule_jobs WHERE retry_count=0 AND last_attempt_at IS NOT NULL").fetchall():
                    due = datetime.fromisoformat(job["last_attempt_at"]) + timedelta(hours=cadence_hours)
                    conn.execute("UPDATE update_schedule_jobs SET next_due_at=? WHERE kind=? AND target_id=?",
                                 (stamp(max(now, due)), job["kind"], job["target_id"]))
        self._wake.set()
        return self.status()

    async def start(self):
        if self._worker and not self._worker.done():
            return
        self._closing = False
        now = stamp(self.clock())
        # A process exit can leave a run in flight. Do not claim it completed.
        with self.db.transaction() as conn:
            conn.execute("UPDATE update_schedule_runs SET state='interrupted',finished_at=?,error_code='app_interrupted' WHERE state='running'", (now,))
            conn.execute("UPDATE update_schedule_jobs SET state='interrupted',error_code='app_interrupted',next_due_at=? WHERE state='running'",
                         (stamp(self.clock() + timedelta(seconds=RETRY_SECONDS[0])),))
        self._worker = asyncio.create_task(self._loop(), name="updates-schedule")

    async def close(self):
        self._closing = True
        tasks = {task for task in (self._worker, self._batch, *self._active) if task and task is not asyncio.current_task()}
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._finish_unstarted("interrupted", "app_shutdown")
        self._worker = self._batch = None

    def _finish_unstarted(self, state, code):
        self.db.execute("UPDATE update_schedule_runs SET state=?,finished_at=?,error_code=? WHERE state='running'",
                        (state, stamp(self.clock()), code))

    async def manual(self, producer, *args):
        """The manual API and background batch share one non-queued check guard."""
        if self._closing:
            raise ApiError("updates_stopping", "Source checking is stopping with the app", 503)
        if self._lock.locked() or (self._batch and not self._batch.done()):
            raise ApiError("source_checks_busy", "A source check is running. Wait or stop the automatic batch", 409, True)
        async with self._lock:
            task = asyncio.current_task()
            self._active.add(task)
            try:
                return await producer(*args)
            finally:
                self._active.discard(task)
                self._wake.set()

    def begin(self, *, due_only=False):
        if self._closing:
            raise ApiError("updates_stopping", "Source checking is stopping with the app", 503)
        if self._lock.locked() or (self._batch and not self._batch.done()):
            raise ApiError("source_checks_busy", "A source check is already running", 409, True)
        config = self.status()
        if due_only and not config["enabled"]:
            return None
        jobs = sorted(config["jobs"], key=lambda job: (job["next_due_at"], job["kind"], job["target_id"]))
        if due_only:
            jobs = [job for job in jobs if datetime.fromisoformat(job["next_due_at"]) <= self.clock()]
        if not jobs:
            if due_only:
                return None
            raise ApiError("schedule_selection_required", "Select public sources before checking the selection")
        identifier = "check_" + uuid4().hex
        self.db.execute("INSERT INTO update_schedule_runs(id,trigger,started_at,state) VALUES(?,?,?,'running')",
                        (identifier, "automatic" if due_only else "manual", stamp(self.clock())))
        self._batch = asyncio.create_task(self._run(identifier, jobs[:MAX_BATCH], config["cadence_hours"]), name="updates-batch")
        return identifier

    async def cancel(self):
        if self._batch and not self._batch.done():
            self._batch.cancel()
            with suppress(asyncio.CancelledError):
                await self._batch
            self._finish_unstarted("cancelled", "check_cancelled")
            config = self.db.fetch_one("SELECT cadence_hours FROM update_schedule WHERE id=1")
            next_interval = stamp(self.clock() + timedelta(hours=config["cadence_hours"]))
            # Stop is an explicit interruption, not a request to resume overdue
            # siblings a minute later. Keep opt-in but defer the selection.
            self.db.execute("UPDATE update_schedule_jobs SET next_due_at=? WHERE next_due_at<?",
                            (next_interval, next_interval))
        self._wake.set()
        return self.status()

    async def _check(self, job, cadence):
        key = (job["kind"], job["target_id"])
        if key not in {(option["kind"], option["id"]) for option in self.options()}:
            raise ApiError("schedule_route_unavailable", "The selected route is no longer supported or tracked")
        if job["kind"] == "source":
            registered = next(source for source in self.updates.sources if source["id"] == job["target_id"])
            current = self.db.fetch_one("SELECT url FROM update_source_checks WHERE source_id=?", (job["target_id"],))
            if not current or current["url"] != registered["url"]:
                raise ApiError("schedule_route_unavailable", "The source check URL no longer matches its registered public route")
            return await self.updates.check_source(job["target_id"], force=True)
        if job["kind"] == "publication":
            return await self.updates.publications.check(job["target_id"], force=True)
        # One installed topic per job; cover at least the configured interval
        # without unbounded catch-up queries or additional result pages.
        return await self.updates.check_literature([job["target_id"]], days=max(7, (cadence + 23) // 24))

    async def _run(self, identifier, jobs, cadence):
        checked = failed = 0
        current = None
        state, error_code = "checked", None
        try:
            async with self._lock:
                for current in jobs:
                    attempted = stamp(self.clock())
                    self.db.execute("UPDATE update_schedule_jobs SET state='running',last_attempt_at=? WHERE kind=? AND target_id=?",
                                    (attempted, current["kind"], current["target_id"]))
                    try:
                        async with asyncio.timeout(CHECK_TIMEOUT):
                            result = await self._check(current, cadence)
                        failure = result.get("state") in ("failed", "partial", "tracking-stopped")
                        codes = [item.get("error_code") for item in result.get("checks", []) if item.get("error_code")]
                        code = (result.get("error") or {}).get("code") or (codes[0] if codes else "source_check_failed") if failure else None
                    except Exception as error:
                        failure = True
                        code = error.code if isinstance(error, ApiError) else "source_check_timeout" if isinstance(error, TimeoutError) else "source_check_failed"
                    checked += 1
                    failed += int(failure)
                    retry = current["retry_count"]
                    next_retry = retry + 1 if failure and retry < len(RETRY_SECONDS) else 0
                    next_due = self.clock() + (timedelta(seconds=RETRY_SECONDS[retry]) if next_retry else timedelta(hours=cadence))
                    job_state = "retry-wait" if next_retry else "failed" if failure else "checked"
                    self.db.execute("UPDATE update_schedule_jobs SET state=?,next_due_at=?,retry_count=?,failure_count=?,error_code=?,last_success_at=CASE WHEN ? THEN last_success_at ELSE ? END WHERE kind=? AND target_id=?",
                        (job_state, stamp(next_due), next_retry, current["failure_count"] + 1 if failure else 0, code,
                         int(failure), stamp(self.clock()), current["kind"], current["target_id"]))
                    if failure:
                        error_code = code
                    current = None
                state = "failed" if failed == checked else "partial" if failed else "checked"
        except asyncio.CancelledError:
            state, error_code = ("interrupted", "app_shutdown") if self._closing else ("cancelled", "check_cancelled")
            if current:
                self.db.execute("UPDATE update_schedule_jobs SET state=?,error_code=?,next_due_at=? WHERE kind=? AND target_id=?",
                                (state, error_code, stamp(self.clock() + timedelta(hours=cadence)), current["kind"], current["target_id"]))
            raise
        except Exception:
            state, error_code = "failed", "schedule_run_failed"
            if current:
                self.db.execute("UPDATE update_schedule_jobs SET state='failed',error_code=?,next_due_at=? WHERE kind=? AND target_id=?",
                                (error_code, stamp(self.clock() + timedelta(hours=cadence)), current["kind"], current["target_id"]))
        finally:
            now = self.clock()
            with self.db.transaction() as conn:
                conn.execute("UPDATE update_schedule_runs SET finished_at=?,state=?,checked=?,failed=?,error_code=? WHERE id=?",
                             (stamp(now), state, checked, failed, error_code, identifier))
                # Bound backlog and prevent an overdue selection becoming a tight loop.
                conn.execute("UPDATE update_schedule_jobs SET next_due_at=? WHERE next_due_at<=?",
                             (stamp(now + timedelta(seconds=BATCH_PAUSE)), stamp(now)))
                conn.execute("DELETE FROM update_schedule_runs WHERE id NOT IN (SELECT id FROM update_schedule_runs ORDER BY started_at DESC,rowid DESC LIMIT 100)")
            self._wake.set()

    async def _loop(self):
        while not self._closing:
            self._wake.clear()
            status = self.status()
            delay = BATCH_PAUSE
            if status["enabled"] and not status["running"] and not self._lock.locked() and status["next_due_at"]:
                delay = max(0, (datetime.fromisoformat(status["next_due_at"]) - self.clock()).total_seconds())
                if delay == 0:
                    self.begin(due_only=True)
                    delay = BATCH_PAUSE
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=min(BATCH_PAUSE, max(1, delay)))
            except TimeoutError:
                pass
