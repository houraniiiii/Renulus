# SPDX-License-Identifier: MIT
"""App-running nightly eligibility; saved_generation alone produces saved tests."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import date, datetime, time, timedelta
import json

from pydantic import ValidationError

from renulus.assessment.generation_models import CreateGenerationRequest, GenerationAction
from renulus.contracts import ApiError, durable_id
from renulus.design_c_contracts import EligibleInput, canonical_digest
from renulus.storage import utc_now
from renulus.storage.assessment_policy import policy_snapshot, require_assistance
from renulus.storage.invalidation import context_epoch_in
from .nightly_models import (
    NightlyCommands, NightlyPreferences, NightlySchedule, NightlyState,
    PreferenceReceipt, PreferencesUpdate,
)

PREFERENCES = "nightly.preferences"
COMMANDS = "nightly.commands"
STATE = "nightly.state"
MAX_INPUTS = 20


def _load(conn, key, model):
    row = conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
    try:
        return model.model_validate_json(row[0]) if row else None
    except ValidationError:
        return None


def _save(conn, key, value):
    conn.execute("INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET "
        "value=excluded.value,updated_at=excluded.updated_at", (key, value.model_dump_json(), utc_now()))


class NightlyService:
    def __init__(self, services, *, local_now=None, poll_interval=30):
        self.services, self.db = services, services.db
        self.local_now = local_now or (lambda: datetime.now().astimezone())
        self.poll_interval = poll_interval
        self._scheduler = None
        self._closing = False
        services.on_startup.append(self.start)
        services.on_shutdown.append(self.close)

    def _now(self):
        now = self.local_now()
        if now.utcoffset() is None:
            raise ValueError("Nightly scheduling needs an aware local clock")
        return now

    @staticmethod
    def _preferences(conn):
        # Invalid/restored settings fail closed to Off, never an inferred opt-in.
        return _load(conn, PREFERENCES, NightlyPreferences) or NightlyPreferences()

    @staticmethod
    def _due(now, preferences, *, future=False):
        preferred = time.fromisoformat(preferences.local_time)
        due = datetime.combine(now.date(), preferred, tzinfo=now.tzinfo)
        if future and due <= now:
            due += timedelta(days=1)
        elif not future and due > now:
            due -= timedelta(days=1)
        return due

    def _reset(self, conn, now, preferences):
        old = _load(conn, STATE, NightlyState)
        # Jobs retain the day even when local-only scheduler state was not restored.
        row = conn.execute("SELECT MAX(json_extract(checkpoint_json,'$.nightly.day')) AS day "
            "FROM assessment_test_jobs WHERE operation='nightly_test'").fetchone()
        days = [old.last_claimed_day] if old and old.last_claimed_day else []
        with suppress(TypeError, ValueError):
            days.append(date.fromisoformat(row["day"]))
        state = NightlyState(context_epoch=context_epoch_in(conn), preferences_revision=preferences.revision,
            eligibility_token=durable_id("nightly"), timezone=str(now.tzinfo),
            not_before=self._due(now, preferences, future=True),
            last_claimed_day=max(days) if days else None,
            last_key=old.last_key if old else None, latest_job_id=old.latest_job_id if old else None)
        _save(conn, STATE, state)
        return state

    def recover(self):
        """Invalidate old eligibility; no inference or missed-work replay on recovery."""
        now = self._now()
        with self.db.transaction() as conn:
            self._reset(conn, now, self._preferences(conn))
            conn.execute("UPDATE assessment_test_jobs SET state='failed',error_code='interrupted',updated_at=? "
                "WHERE operation='nightly_test' AND state IN ('queued','running')", (utc_now(),))

    async def start(self):
        self._closing = False
        self.recover()
        if self._scheduler is None or self._scheduler.done():
            self._scheduler = asyncio.create_task(self._loop())

    async def _loop(self):
        while True:
            await asyncio.sleep(self.poll_interval)
            # A transient storage error must not kill scheduling or disclose payloads.
            # A claimed day stays consumed; failures never spin provider retries.
            with suppress(Exception):
                await self.tick()

    def preferences(self):
        with self.db.transaction() as conn:
            return self._preferences(conn).model_dump()

    async def update_preferences(self, body: PreferencesUpdate, key: str):
        digest = canonical_digest(body.model_dump())
        with self.db.transaction() as conn:
            journal = _load(conn, COMMANDS, NightlyCommands) or NightlyCommands()
            previous = next((receipt for receipt in journal.receipts if receipt.key == key), None)
            if previous:
                if previous.request_hash != digest:
                    raise ApiError("idempotency_conflict", "This nightly settings key was used for different work.", 409)
                return previous.result.model_dump()
            current = self._preferences(conn)
            if body.expected_revision != current.revision:
                raise ApiError("revision_conflict", "Nightly preferences changed. Reload before saving.", 409)
            result = NightlyPreferences(**body.model_dump(exclude={"expected_revision"}), revision=current.revision + 1)
            _save(conn, PREFERENCES, result)
            self._reset(conn, self._now(), result)
            receipt = PreferenceReceipt(key=key, request_hash=digest, result=result)
            _save(conn, COMMANDS, NightlyCommands(receipts=(*journal.receipts[-127:], receipt)))
        # The preference/token change already prevents publication in its transaction.
        # Stop only this owner's nightly work; never cancel manual generation.
        await self._stop_active("nightly-settings")
        return result.model_dump()

    async def _stop_active(self, reason):
        owner = self.services.registry.get("saved_generation")
        if owner is None:
            return
        rows = self.db.fetch_all("SELECT id FROM assessment_test_jobs WHERE operation='nightly_test' "
                                "AND state IN ('queued','running')")
        for row in rows:
            await owner.action(row["id"], "cancel", GenerationAction(idempotency_key=reason + ":" + row["id"]))

    def require_publication(self, conn, row):
        """Generation calls this before work/chunks and in its publication transaction."""
        if row["operation"] != "nightly_test":
            raise ApiError("nightly_invalid_job", "This job is not nightly work.", 409)
        try:
            value = conn.execute("SELECT json_extract(checkpoint_json,'$.nightly') FROM assessment_test_jobs "
                                 "WHERE id=? AND operation='nightly_test'", (row["id"],)).fetchone()
            schedule = NightlySchedule.model_validate_json(value[0])
            inputs = tuple(EligibleInput.model_validate(item) for item in json.loads(row["inputs_json"]))
        except (ValidationError, TypeError, ValueError, IndexError):
            raise ApiError("nightly_checkpoint_unavailable", "Nightly scheduling metadata is unavailable.", 409) from None
        preferences = self._preferences(conn)
        state = _load(conn, STATE, NightlyState)
        if (self._closing or not preferences.enabled or preferences.revision != schedule.preferences_revision or
                state is None or state.eligibility_token != schedule.eligibility_token or
                state.preferences_revision != preferences.revision or state.context_epoch != context_epoch_in(conn) or
                state.timezone != schedule.timezone or str(self._now().tzinfo) != schedule.timezone or
                row["idempotency_key"] != "nightly:" + schedule.day.isoformat() or state.last_key != row["idempotency_key"] or
                row["requested_count"] != preferences.question_count):
            raise ApiError("nightly_invalidated", "Nightly eligibility changed. This work cannot publish.", 409)
        require_assistance(conn, expected_revision=row["policy_revision"])
        context = self.services.get("home")._context(conn)
        if (context.epoch != row["context_epoch"] or context.policy_revision != row["policy_revision"] or
                context.settings_revision != schedule.home_settings_revision or inputs != context.inputs[:MAX_INPUTS]):
            raise ApiError("nightly_context_changed", "Saved learning context changed before nightly publication.", 409)

    async def tick(self):
        """One due-day claim; concurrent callers and long sleep cannot build a backlog."""
        if self._closing:
            return self.read()
        now = self._now()
        request, schedule = None, None
        with self.db.transaction() as conn:
            preferences = self._preferences(conn)
            state = _load(conn, STATE, NightlyState)
            owner = self.services.registry.get("saved_generation")
            if owner is not None:
                owner.reconcile_nightly(conn)
            if state is None or (state.context_epoch != context_epoch_in(conn) or
                    state.preferences_revision != preferences.revision or state.timezone != str(now.tzinfo)):
                self._reset(conn, now, preferences)
            elif preferences.enabled and now >= state.not_before:
                due = self._due(now, preferences)
                active = conn.execute("SELECT 1 FROM assessment_test_jobs WHERE operation='nightly_test' "
                                      "AND state IN ('queued','running') LIMIT 1").fetchone()
                if not active and (state.last_claimed_day is None or due.date() > state.last_claimed_day):
                    key = "nightly:" + due.date().isoformat()
                    state = state.model_copy(update={"last_claimed_day": due.date(), "last_key": key,
                        "not_before": due + timedelta(days=1), "latest_job_id": None, "error_code": None})
                    try:
                        context = self.services.get("home")._context(conn)
                        owner = self.services.get("saved_generation")
                        if not callable(getattr(owner, "create_nightly", None)):
                            raise ApiError("nightly_generation_unavailable", "Nightly saved generation is not available yet.", 503)
                        schedule = NightlySchedule(day=due.date(), timezone=str(now.tzinfo),
                            preferences_revision=preferences.revision, home_settings_revision=context.settings_revision,
                            eligibility_token=state.eligibility_token)
                        request = CreateGenerationRequest(idempotency_key=key, title="Nightly practice · " + due.date().isoformat(),
                            count=preferences.question_count, inputs=context.inputs[:MAX_INPUTS])
                    except ApiError as error:
                        state = state.model_copy(update={"error_code": error.code})
                    _save(conn, STATE, state)
        if request is not None:
            try:
                result = await self.services.get("saved_generation").create_nightly(request, schedule=schedule.model_dump(mode="json"))
                with self.db.transaction() as conn:
                    state = _load(conn, STATE, NightlyState)
                    if state and state.last_key == request.idempotency_key and state.eligibility_token == schedule.eligibility_token:
                        _save(conn, STATE, state.model_copy(update={"latest_job_id": result["id"], "error_code": None}))
            except ApiError as error:
                with self.db.transaction() as conn:
                    state = _load(conn, STATE, NightlyState)
                    if state and state.last_key == request.idempotency_key and state.eligibility_token == schedule.eligibility_token:
                        _save(conn, STATE, state.model_copy(update={"error_code": error.code}))
        return self.read()

    def read(self):
        """Neutral status remains usable to turn Off/Stop during a Test; no keys."""
        with self.db.transaction() as conn:
            preferences = self._preferences(conn)
            state = _load(conn, STATE, NightlyState)
            owner = self.services.registry.get("saved_generation")
            if owner is not None:
                owner.reconcile_nightly(conn)
            row = conn.execute("SELECT id,state,requested_count,validated_count,error_code,published_version_id "
                "FROM assessment_test_jobs j WHERE operation='nightly_test' AND NOT EXISTS "
                "(SELECT 1 FROM deletion_ledger WHERE entity_type='job' AND entity_id=j.id) "
                "ORDER BY created_at DESC,id DESC LIMIT 1").fetchone()
            job = None
            if row:
                job = {key: row[key] for key in ("id", "state", "requested_count", "validated_count", "error_code")}
                job["result"] = None
                if row["published_version_id"]:
                    live = conn.execute("SELECT v.test_id FROM assessment_test_versions v JOIN assessment_tests t ON t.id=v.test_id "
                        "WHERE v.id=? AND t.lifecycle!='deleted' AND NOT EXISTS (SELECT 1 FROM deletion_ledger WHERE "
                        "(entity_type='saved_test' AND entity_id=t.id) OR (entity_type='saved_test_version' AND entity_id=v.id))",
                        (row["published_version_id"],)).fetchone()
                    job["result"] = {"version": {"type": "saved_test_version", "id": row["published_version_id"]},
                        "test": {"type": "saved_test", "id": live["test_id"]} if live else None,
                        "available": live is not None}
            current = (state is not None and state.context_epoch == context_epoch_in(conn) and
                       state.preferences_revision == preferences.revision and state.timezone == str(self._now().tzinfo))
            return {"preferences": preferences.model_dump(), "app_running_only": True,
                "next_eligible_at": state.not_before.isoformat() if preferences.enabled and current else None,
                "last_job": job, "error_code": state.error_code if state else None,
                "assistance_allowed": policy_snapshot(conn)["assistance_allowed"]}

    async def cancel(self, identifier, key):
        with self.db.transaction() as conn:
            row = conn.execute("SELECT 1 FROM assessment_test_jobs WHERE id=? AND operation='nightly_test'",
                               (identifier,)).fetchone()
            if row is None:
                raise ApiError("not_found", "This nightly job is unavailable.", 404)
        return await self.services.get("saved_generation").action(identifier, "cancel", GenerationAction(idempotency_key=key))

    async def close(self):
        self._closing = True
        if self._scheduler and not self._scheduler.done():
            self._scheduler.cancel()
            with suppress(asyncio.CancelledError):
                await self._scheduler
        await self._stop_active("nightly-close")
