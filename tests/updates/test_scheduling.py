"""Real SQLite/lifecycle tests; only the anonymous transport is controlled."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from renulus.contracts import ApiError
from renulus.server import create_app


class Clock:
    def __init__(self):
        self.value = datetime(2026, 10, 5, 6, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, **duration):
        self.value += timedelta(**duration)


class Checker:
    def __init__(self, values=None, hold=False):
        self.values = iter(values or [b'<a href="/synthetic.pdf">Guideline</a>'] * 100)
        self.calls = []
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.hold, self.cancelled = hold, False

    async def fetch(self, url, hosts, limit=2_000_000):
        self.calls.append((url, hosts, limit))
        self.entered.set()
        if self.hold:
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        value = next(self.values)
        if isinstance(value, Exception):
            raise value
        return value, {"content-type": "text/html"}, url


def setup(tmp_path, checker=None):
    app = create_app(tmp_path)
    updates = app.state.services.registry["updates"]
    updates.fetcher = checker or Checker()
    clock = Clock()
    updates.scheduling.clock = clock
    return app, updates, updates.scheduling, clock


def select(*identifiers):
    return [{"kind": "source", "id": identifier} for identifier in identifiers]


async def finished(schedule):
    for _ in range(500):
        state = schedule.status()
        if not state["running"]:
            return state
        await asyncio.sleep(0)
    pytest.fail("Controlled batch did not finish")


@pytest.mark.asyncio
async def test_opt_in_and_registered_routes_are_enforced_at_local_api(tmp_path):
    app, updates, schedule, _ = setup(tmp_path)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        state = (await client.get("/api/v1/updates/schedule")).json()
        assert state["enabled"] is False and state["cadence_hours"] == 24
        assert state["next_due_at"] is None and state["selection"] == []
        offered = {(item["kind"], item["id"]) for item in state["options"]}
        assert ("source", "K01") in offered
        assert not any(("source", identifier) in offered for identifier in ("E01", "E02", "L07", "G07"))
        assert (await client.put("/api/v1/updates/schedule", json={"enabled": True})).status_code == 400
        for identifier in ("E01", "T01", "https://127.0.0.1/private"):
            response = await client.put("/api/v1/updates/schedule", json={"enabled": True, "selection": select(identifier)})
            assert response.status_code == 400
        extra = await client.put("/api/v1/updates/schedule", json={"enabled": False, "api_key": "synthetic-forbidden-field"})
        assert extra.status_code == 422
    await schedule.start()
    await asyncio.sleep(0)
    await schedule.close()
    assert updates.fetcher.calls == []


@pytest.mark.asyncio
async def test_daily_timestamps_survive_restart_and_no_early_check(tmp_path):
    _, updates, schedule, clock = setup(tmp_path)
    schedule.configure(True, selection=select("K01"))
    schedule.begin(due_only=True)
    state = await finished(schedule)
    assert state["last_run"]["state"] == "checked"
    assert state["last_run"]["started_at"] == "2026-10-05T06:00:00.000+00:00"
    assert state["jobs"][0]["last_success_at"] == "2026-10-05T06:00:00.000+00:00"
    assert state["next_due_at"] == "2026-10-06T06:00:00.000+00:00"
    await schedule.close()
    _, restarted, schedule, clock = setup(tmp_path)
    clock.advance(hours=23)
    await schedule.start()
    await asyncio.sleep(0)
    assert restarted.fetcher.calls == []
    assert schedule.status()["last_run"] == state["last_run"]
    clock.advance(hours=1)
    schedule.begin(due_only=True)
    assert (await finished(schedule))["next_due_at"] == "2026-10-07T06:00:00.000+00:00"
    await schedule.close()
    assert len(restarted.fetcher.calls) == 1


@pytest.mark.asyncio
async def test_five_route_cap_preserves_backlog_and_never_overlaps_manual_checks(tmp_path):
    checker = Checker(hold=True)
    _, updates, schedule, clock = setup(tmp_path, checker)
    schedule.configure(True, selection=select(*(f"K{i:02d}" for i in range(1, 9))))
    schedule.begin(due_only=True)
    await checker.entered.wait()
    with pytest.raises(ApiError, match="already running"):
        schedule.begin()
    with pytest.raises(ApiError) as busy:
        await schedule.manual(updates.check_source, "K10", True)
    assert busy.value.code == "source_checks_busy"
    checker.release.set()
    state = await finished(schedule)
    assert len(checker.calls) == 5 and state["last_run"]["checked"] == 5
    assert sum(job["last_success_at"] is not None for job in state["jobs"]) == 5
    assert state["next_due_at"] == "2026-10-05T06:01:00.000+00:00"
    assert schedule.begin(due_only=True) is None
    clock.advance(minutes=1)
    schedule.begin(due_only=True)
    assert (await finished(schedule))["last_run"]["checked"] == 3
    assert len(checker.calls) == 8
    await schedule.close()


@pytest.mark.asyncio
async def test_offline_retries_are_capped_and_success_evidence_is_retained(tmp_path):
    checker = Checker([b'<a href="/synthetic.pdf">Guideline</a>', RuntimeError("offline"),
                       RuntimeError("offline"), RuntimeError("offline"), b'<a href="/corrected.pdf">Correction</a>'])
    _, updates, schedule, clock = setup(tmp_path, checker)
    schedule.configure(True, selection=select("K01"))
    schedule.begin(due_only=True)
    initial = await finished(schedule)
    successful = initial["jobs"][0]["last_success_at"]
    clock.advance(days=1)
    for minutes, retry, due in ((0, 1, "2026-10-06T06:05:00.000+00:00"),
                                (5, 2, "2026-10-06T06:35:00.000+00:00"),
                                (30, 0, "2026-10-07T06:35:00.000+00:00")):
        clock.advance(minutes=minutes)
        schedule.begin(due_only=True)
        state = await finished(schedule)
        assert state["next_due_at"] == due
        assert state["jobs"][0]["retry_count"] == retry
        assert state["jobs"][0]["last_success_at"] == successful
        assert state["last_run"]["state"] == "failed"
    assert state["jobs"][0]["failure_count"] == 3
    clock.advance(hours=23)
    assert schedule.begin(due_only=True) is None
    assert len(checker.calls) == 4
    clock.advance(hours=1)
    schedule.begin(due_only=True)
    recovered = await finished(schedule)
    assert recovered["jobs"][0]["error_code"] is None
    assert recovered["jobs"][0]["failure_count"] == 0
    assert len(updates.list_entries()) == 1
    assert updates.list_entries()[0]["review_state"] == "pending"
    assert updates.list_entries(reviewed_only=True) == []
    await schedule.close()


@pytest.mark.asyncio
async def test_cancel_and_shutdown_abort_transport_and_remain_inspectable(tmp_path):
    checker = Checker(hold=True)
    app, updates, schedule, _ = setup(tmp_path, checker)
    schedule.configure(True, selection=select("K01"))
    assert schedule.start in app.state.services.on_startup
    assert schedule.close in app.state.services.on_shutdown
    schedule.begin()
    await checker.entered.wait()
    stopped = await schedule.cancel()
    assert checker.cancelled
    assert stopped["last_run"]["state"] == "cancelled"
    assert stopped["jobs"][0]["last_success_at"] is None
    updates.fetcher = Checker(hold=True)
    schedule.begin()
    await updates.fetcher.entered.wait()
    await schedule.close()
    assert updates.fetcher.cancelled
    state = schedule.status()
    assert state["running"] is False
    assert state["last_run"]["state"] == "interrupted"
    assert state["last_run"]["error_code"] == "app_shutdown"
    assert state["jobs"][0]["last_success_at"] is None


@pytest.mark.asyncio
async def test_cancel_before_first_task_step_does_not_leave_running_record(tmp_path):
    _, updates, schedule, _ = setup(tmp_path)
    schedule.configure(False, selection=select("K01"))
    schedule.begin()
    state = await schedule.cancel()
    assert state["last_run"]["state"] == "cancelled" and not state["running"]
    assert updates.fetcher.calls == []


@pytest.mark.asyncio
async def test_scheduled_publication_digest_uses_explicit_tracking_and_leaves_review_pending(tmp_path):
    checker = Checker([b"%PDF-1.7 synthetic first", b"%PDF-1.7 synthetic correction"])
    _, updates, schedule, clock = setup(tmp_path, checker)
    candidate = next(item for item in updates.publications.candidates("K01") if "/wp-content/uploads/" in item["url"])
    publication = updates.publications.track("K01", candidate["url"], "Synthetic test permission: anonymous bounded public check")
    selection = [{"kind": "publication", "id": publication["id"]}]
    schedule.configure(True, selection=selection)
    schedule.begin(due_only=True)
    assert (await finished(schedule))["last_run"]["state"] == "checked"
    clock.advance(days=1)
    schedule.begin(due_only=True)
    assert (await finished(schedule))["last_run"]["checked"] == 1
    item = updates.list_entries()[0]
    assert item["kind"] == "publication-change" and item["review_state"] == "pending"
    assert updates.publications.get(publication["id"])["state"] == "changed"
    assert all(limit == 16_000_000 for _, _, limit in checker.calls)
    updates.publications.stop(publication["id"])
    clock.advance(days=1)
    schedule.begin(due_only=True)
    unavailable = await finished(schedule)
    assert unavailable["jobs"][0]["available"] is False
    assert unavailable["jobs"][0]["error_code"] == "schedule_route_unavailable"
    assert len(checker.calls) == 2
    await schedule.close()


@pytest.mark.asyncio
async def test_scheduled_literature_only_queries_installed_topic_metadata(tmp_path):
    body = json.dumps({"hitCount": 1, "resultList": {"result": [{"id": "999991", "source": "MED",
        "title": "Synthetic scheduler metadata", "firstPublicationDate": "2026-10-04"}]}}).encode()
    checker = Checker([body])
    _, updates, schedule, _ = setup(tmp_path, checker)
    class Content:
        def list_topics(self):
            return [{"id": "transplantation", "title": "Kidney transplantation"}]
    updates.services.registry["content"] = Content()
    schedule.configure(True, selection=[{"kind": "literature", "id": "transplantation"}])
    schedule.begin(due_only=True)
    state = await finished(schedule)
    assert state["last_run"]["state"] == "checked"
    from urllib.parse import parse_qs, urlparse
    url, hosts, limit = checker.calls[0]
    query = parse_qs(urlparse(url).query)
    assert hosts == {"www.ebi.ac.uk"} and limit == 2_000_000
    assert query["pageSize"] == ["25"] and "Kidney transplantation" in query["query"][0]
    assert len(updates.list_entries()) == 1 and updates.list_entries()[0]["review_state"] == "pending"
    with pytest.raises(ApiError):
        schedule.configure(True, selection=[{"kind": "literature", "id": "private-case-query"}])
    await schedule.close()


@pytest.mark.asyncio
async def test_app_lifespan_runs_overdue_opt_in_and_aborts_it_on_shutdown(tmp_path):
    checker = Checker(hold=True)
    app, updates, schedule, _ = setup(tmp_path, checker)
    schedule.configure(True, selection=select("K01"))
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(checker.entered.wait(), 2)
        assert schedule.status()["running"] is True
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            blocked = await client.post("/api/v1/updates/sources/K02/check?force=true")
            assert blocked.status_code == 409
            assert blocked.json()["error"]["code"] == "source_checks_busy"
    assert checker.cancelled
    assert schedule.status()["last_run"]["state"] == "interrupted"
    assert len(checker.calls) == 1 and updates.list_entries() == []


@pytest.mark.asyncio
async def test_manual_check_guard_prevents_automatic_overlap_and_closes_cleanly(tmp_path):
    checker = Checker(hold=True)
    _, updates, schedule, _ = setup(tmp_path, checker)
    schedule.configure(True, selection=select("K01"))
    manual = asyncio.create_task(schedule.manual(updates.check_source, "K02", True))
    await checker.entered.wait()
    with pytest.raises(ApiError) as blocked:
        schedule.begin(due_only=True)
    assert blocked.value.code == "source_checks_busy"
    await schedule.close()
    assert manual.cancelled() and checker.cancelled
    assert len(checker.calls) == 1


@pytest.mark.asyncio
async def test_abrupt_restart_marks_unfinished_evidence_and_preserves_retry_delay(tmp_path):
    _, updates, schedule, _ = setup(tmp_path)
    schedule.configure(True, selection=select("K01"))
    # Simulate a process exit, which cannot run graceful close callbacks.
    updates.db.execute("INSERT INTO update_schedule_runs(id,trigger,started_at,state) VALUES('synthetic-crash','automatic','2026-10-05T05:59:00.000+00:00','running')")
    updates.db.execute("UPDATE update_schedule_jobs SET state='running',last_attempt_at='2026-10-05T05:59:00.000+00:00',retry_count=1,failure_count=1 WHERE kind='source' AND target_id='K01'")
    _, restarted, schedule, _ = setup(tmp_path)
    await schedule.start()
    state = schedule.status()
    assert state["last_run"]["state"] == "interrupted"
    assert state["last_run"]["error_code"] == "app_interrupted"
    assert state["jobs"][0]["last_success_at"] is None
    assert state["jobs"][0]["retry_count"] == 1
    assert state["next_due_at"] == "2026-10-05T06:05:00.000+00:00"
    await asyncio.sleep(0)
    assert restarted.fetcher.calls == []
    await schedule.close()


@pytest.mark.asyncio
async def test_outer_deadline_cancels_slow_checker_without_success(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.updates.scheduling.CHECK_TIMEOUT", 0.01)
    checker = Checker(hold=True)
    _, _, schedule, _ = setup(tmp_path, checker)
    schedule.configure(True, selection=select("K01"))
    schedule.begin(due_only=True)
    await checker.entered.wait()
    await asyncio.sleep(0.02)
    state = await finished(schedule)
    assert checker.cancelled
    assert state["jobs"][0]["last_success_at"] is None
    assert state["jobs"][0]["error_code"] == "source_check_timeout"
    assert state["jobs"][0]["retry_count"] == 1
    await schedule.close()
