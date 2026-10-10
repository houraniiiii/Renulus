# SPDX-License-Identifier: MIT
"""Bounded selected-route batches with private checkpoints and atomic publication."""
from __future__ import annotations

import asyncio
from contextlib import aclosing, suppress
import json
import re
from types import SimpleNamespace
import unicodedata

from pydantic import ValidationError

from renulus.contracts import ApiError, ContextScope, Scope, durable_id
from renulus.design_c_contracts import (
    ContentReference, Job, QuestionSnapshot, SavedTestVersion, canonical_digest,
)
from renulus.storage import utc_now
from renulus.storage.assessment_policy import policy_snapshot, require_assistance
from renulus.storage.invalidation import context_epoch_in
from renulus.storage.relations import TOMBSTONES
from .generated_contracts import GeneratedBatch
from .generated_streaming import SYSTEM, citation, retrieve
from .generation_models import CreateGenerationRequest, NightlySchedule

MAX_CALLS = 12
MAX_RECEIPTS = 40
MAX_OUTPUT = 65536
MAX_INPUT = 96000
MAX_CHECKPOINT = 1048576
MAX_ACTIVE = 3


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stem_key(stem):
    return re.sub(r"[\W_]+", " ", unicodedata.normalize("NFKC", stem).casefold()).strip()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class SavedGenerationService:
    def __init__(self, services, *, timeout=180):
        self.services, self.db, self.timeout = services, services.db, timeout
        self.tasks = {}
        self.run_ids = {}
        services.on_startup.append(self.recover)
        services.on_shutdown.append(self.close)

    def recover(self):
        # Never repeat model work on startup, restore or a progress GET.
        self.db.execute("UPDATE assessment_test_jobs SET state='failed',error_code='interrupted',updated_at=? "
            "WHERE operation IN ('generate_test','nightly_test') AND state IN ('queued','running')", (utc_now(),))

    def reconcile_nightly(self, conn) -> int:
        """Neutral owner hook for status/tick; never start or inspect provider work.

        Imported epoch numbers are not execution ownership. Preserve live local
        tasks, and fail orphaned work even if a foreign epoch happens to match.
        The caller owns the transaction; checkpoints and counts remain intact.
        """
        epoch, changed = context_epoch_in(conn), 0
        rows = conn.execute("SELECT id,context_epoch FROM assessment_test_jobs "
            "WHERE operation='nightly_test' AND state IN ('queued','running')").fetchall()
        for row in rows:
            task = self.tasks.get(row["id"])
            if row["context_epoch"] == epoch and task is not None and not task.done():
                continue
            changed += conn.execute("UPDATE assessment_test_jobs SET state='failed',error_code='interrupted',updated_at=? "
                "WHERE id=? AND operation='nightly_test' AND state IN ('queued','running')", (utc_now(), row["id"])).rowcount
        return changed

    def _route(self):
        status = self.services.get("provider").status()
        provider = status.get("selected_provider")
        model = status.get("selected_models", {}).get(provider)
        connection = next((entry for entry in status.get("connections", []) if entry.get("provider") == provider), {})
        if not provider or not model:
            raise ApiError("connection_required", "Select a subscription and model in Connections before generating a set", 409, True)
        if connection.get("learning_use", {}).get("generation_allowed") is not True:
            raise ApiError("learning_use_unverified", "The selected subscription is not approved for learning requests", 403)
        if not any(entry.get("id") == model and entry.get("availability") == "available" for entry in connection.get("models", [])):
            raise ApiError("model_unavailable", "The selected model is unavailable. Your validated work is retained", 409, True)
        return {"provider": provider, "model": model}

    def _context(self, conn, request):
        policy = require_assistance(conn)
        route = self._route()
        content = self.services.get("content")
        topics = content.list_topics()
        topic = next((entry for entry in topics if entry["id"] == request.topic_id), None)
        if request.topic_id and topic is None:
            raise ApiError("topic_unavailable", "Choose a topic from the installed learning catalogue", 409)
        material = []
        if request.inputs:
            # Home's canonical eligibility resolver excludes raw cases, unclassified
            # records, suppression, unavailable owners and uncommitted evidence.
            context = self.services.get("home")._context(conn)
            approved = {entry.dependency.target.key: entry for entry in context.inputs}
            if any(approved.get(entry.dependency.target.key) != entry for entry in request.inputs):
                raise ApiError("generation_inputs_changed", "Saved learning inputs are unavailable or changed. Start a new set", 409)
            for entry in request.inputs:
                target = entry.dependency.target
                if target.type == "memory_revision":
                    identifier, revision = target.id.rsplit(":", 1)
                    row = conn.execute("SELECT text FROM memory_history WHERE record_id=? AND revision=?", (identifier, int(revision))).fetchone()
                    material.append({"kind": entry.kind, "text": row[0]})
                elif target.type == "learning_evidence":
                    row = conn.execute("SELECT topic_id,payload_json FROM learning_evidence WHERE id=?", (target.id,)).fetchone()
                    value = json.loads(row["payload_json"])
                    # Evidence contributes topic/results, never arbitrary payload text or keys.
                    material.append({"kind": entry.kind, "topic_id": row["topic_id"],
                        **{key: value[key] for key in ("correct", "score_bucket", "activity") if key in value}})
                elif target.type == "goal":
                    row = conn.execute("SELECT title,topic_id,target_date FROM study_project_goals WHERE id=?", (target.id,)).fetchone()
                    material.append(dict(row))
                elif target.type == "preferences":
                    row = conn.execute("SELECT value FROM preferences WHERE key=?", (target.id,)).fetchone()
                    material.append(json.loads(row[0]))
        topic_value = {"id": topic["id"], "label": topic.get("label") or topic.get("title") or topic["id"]} if topic else None
        if len(encode(material).encode("utf-8")) > MAX_INPUT // 2:
            raise ApiError("generation_input_limit", "Choose fewer saved learning inputs", 413)
        selected_sources = []
        if request.source_refs:
            knowledge = self.services.get("knowledge")
            revisions = knowledge._retrievable_revisions(ContextScope(kind=Scope.GENERATED_PRACTICE), request.topic_id, False, conn=conn)
            for reference in request.source_refs:
                revision = revisions.get(reference.target.id)
                if revision is None:
                    raise ApiError("generation_sources_changed", "A selected source is unavailable. Choose eligible Library sources", 409)
                self._source_revision(conn, revision)
                selected_sources.append({"id": revision["id"], "hash": canonical_digest(revision)})
        settings = int(canonical_digest({"route": route, "topic": topic_value, "inputs": material, "sources": selected_sources})[:15], 16) + 1
        return {"route": route, "settings": settings, "policy": policy, "epoch": context_epoch_in(conn),
                "material": material, "topic": topic_value}

    @staticmethod
    def _row(conn, identifier):
        row = conn.execute("SELECT * FROM assessment_test_jobs WHERE id=? AND operation IN ('generate_test','nightly_test')", (identifier,)).fetchone()
        if row is None:
            raise ApiError("not_found", "This generation job is unavailable", 404)
        if conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type='job' AND entity_id=?", (identifier,)).fetchone():
            raise ApiError("not_found", "This generation job was deleted", 404)
        return dict(row)

    @staticmethod
    def _checkpoint(row):
        value = json.loads(row["checkpoint_json"])
        if value.get("schema") != "saved-generation/1":
            raise ApiError("generation_checkpoint_unavailable", "This generation checkpoint needs a compatible app version", 409)
        return value

    @staticmethod
    def _encode_checkpoint(checkpoint):
        value = encode(checkpoint)
        if len(value.encode("utf-8")) > MAX_CHECKPOINT:
            raise ApiError("generation_checkpoint_limit", "This draft reached its storage bound. Prior batches are retained", 409)
        return value

    def _nightly_guard(self, conn, row):
        if row["operation"] != "nightly_test":
            return
        checkpoint = self._checkpoint(row)
        try:
            schedule = NightlySchedule.model_validate(checkpoint.get("nightly"))
            request = CreateGenerationRequest.model_validate(checkpoint["request"])
        except (KeyError, ValidationError):
            raise ApiError("nightly_checkpoint_unavailable", "This nightly checkpoint needs a compatible app version", 409) from None
        if (request.topic_id is not None or request.source_refs or request.idempotency_key != "nightly:" + schedule.day or
                request.idempotency_key != row["idempotency_key"] or request.count != row["requested_count"] or
                [entry.model_dump(mode="json") for entry in request.inputs] != json.loads(row["inputs_json"])):
            raise ApiError("nightly_checkpoint_unavailable", "This nightly checkpoint is not a trusted saved-input request", 409)
        # Immutable result replay starts no work. Current assistance and deletion
        # policy still apply at its caller; a later scheduler token cannot erase it.
        if row["state"] == "published":
            return
        owner = self.services.registry.get("nightly")
        guard = getattr(owner, "require_publication", None)
        if not callable(guard):
            raise ApiError("nightly_unavailable", "Nightly scheduling is unavailable. Retained work has not been published", 503, True)
        guard(conn, row)

    @staticmethod
    def _capacity(conn):
        if conn.execute("SELECT COUNT(*) FROM assessment_test_jobs WHERE operation IN ('generate_test','nightly_test') AND state IN ('queued','running')").fetchone()[0] >= MAX_ACTIVE:
            raise ApiError("generation_capacity", "Finish or cancel an active generation job before starting another", 409, True)

    def _view(self, conn, row):
        # A restored running checkpoint has no right to resume model work. Its
        # local epoch is deliberately not portable. Reconcile stale progress
        # even when this process did not own the pre-restore execution.
        if row["state"] in ("queued", "running") and row["context_epoch"] != context_epoch_in(conn):
            error_code = "interrupted" if row["operation"] == "nightly_test" else "generation_context_changed"
            conn.execute("UPDATE assessment_test_jobs SET state='failed',error_code=?,updated_at=? WHERE id=?", (error_code, utc_now(), row["id"]))
            row = {**row, "state": "failed", "error_code": error_code}
        checkpoint = self._checkpoint(row)
        # The frozen contract also guards restored progress/count invariants.
        Job(id=row["id"], operation=row["operation"], idempotency_key=row["idempotency_key"],
            request_hash=row["request_hash"], state=row["state"], inputs=json.loads(row["inputs_json"]),
            settings_revision=row["settings_revision"], policy_revision=row["policy_revision"], context_epoch=row["context_epoch"],
            requested_count=row["requested_count"], validated_count=row["validated_count"], accepted_count=row["accepted_count"],
            published_version={"type": "saved_test_version", "id": row["published_version_id"]} if row["published_version_id"] else None)
        result = None
        if row["published_version_id"]:
            live = conn.execute("SELECT v.test_id,v.ordinal FROM assessment_test_versions v JOIN assessment_tests t ON t.id=v.test_id "
                "WHERE v.id=? AND t.lifecycle!='deleted' AND NOT EXISTS(SELECT 1 FROM deletion_ledger WHERE "
                "(entity_type='saved_test_version' AND entity_id=v.id) OR (entity_type='saved_test' AND entity_id=t.id))", (row["published_version_id"],)).fetchone()
            result = {"version_id": row["published_version_id"], "test_id": checkpoint["test_id"],
                "item_count": row["accepted_count"] or row["requested_count"], "available": live is not None}
        recoverable = row["state"] in ("failed", "needs_review", "cancelled")
        if recoverable:
            try:
                self._check(conn, row, states=(row["state"],))
            except ApiError:
                recoverable = False
        return {"id": row["id"], "state": row["state"], "requested_count": row["requested_count"],
            "validated_count": row["validated_count"], "accepted_count": row["accepted_count"],
            "effective_count": row["accepted_count"] or row["requested_count"], "error_code": row["error_code"],
            "calls_used": checkpoint["calls"], "calls_remaining": MAX_CALLS - checkpoint["calls"],
            "title": checkpoint["request"]["title"], "route": checkpoint["route"], "result": result,
            "can_retry": recoverable and checkpoint["calls"] < MAX_CALLS,
            "can_accept_shorter": recoverable and 0 < row["validated_count"] < row["requested_count"]}

    def read(self, identifier):
        with self.db.transaction() as conn:
            require_assistance(conn)
            self.reconcile_nightly(conn)
            return self._view(conn, self._row(conn, identifier))

    def list_jobs(self):
        with self.db.transaction() as conn:
            require_assistance(conn)
            self.reconcile_nightly(conn)
            rows = conn.execute("SELECT * FROM assessment_test_jobs j WHERE operation IN ('generate_test','nightly_test') AND NOT EXISTS "
                "(SELECT 1 FROM deletion_ledger WHERE entity_type='job' AND entity_id=j.id) ORDER BY created_at DESC,id DESC LIMIT 50")
            return {"items": [self._view(conn, dict(row)) for row in rows]}

    async def create(self, request: CreateGenerationRequest):
        if request.idempotency_key.startswith("nightly:"):
            raise ApiError("invalid_request", "Nightly day keys belong to the trusted scheduler", 422)
        return await self._create(request)

    async def create_nightly(self, request: CreateGenerationRequest, *, schedule: dict) -> dict:
        try:
            nightly = NightlySchedule.model_validate(schedule).model_dump(mode="json")
        except ValidationError:
            raise ApiError("invalid_request", "Nightly requires the exact trusted schedule checkpoint", 422) from None
        if request.topic_id is not None or request.source_refs or request.idempotency_key != "nightly:" + nightly["day"]:
            raise ApiError("invalid_request", "Nightly requires saved learning inputs and its exact day key", 422)
        return await self._create(request, nightly=nightly)

    async def _create(self, request, *, nightly=None):
        operation = "nightly_test" if nightly is not None else "generate_test"
        intent = request.model_dump(mode="json", exclude={"idempotency_key"})
        digest = canonical_digest({"request": intent, "nightly": nightly}) if nightly is not None else canonical_digest(intent)
        with self.db.transaction() as conn:
            require_assistance(conn)  # Current policy precedes every outcome replay.
            self.reconcile_nightly(conn)
            previous = conn.execute("SELECT * FROM assessment_test_jobs WHERE idempotency_key=?", (request.idempotency_key,)).fetchone()
            if previous:
                if previous["operation"] != operation or previous["request_hash"] != digest:
                    raise ApiError("idempotency_conflict", "This request key was already used for different work", 409)
                row = self._row(conn, previous["id"])
                self._nightly_guard(conn, row)
                return self._view(conn, row)
            self._capacity(conn)
            context = self._context(conn, request)
            identifier, now = durable_id("test_job"), utc_now()
            checkpoint = {"schema": "saved-generation/1", "request": request.model_dump(mode="json"),
                "route": context["route"], "calls": 0, "items": [], "sources": [], "receipts": [], "execution": durable_id("execution"),
                "test_id": durable_id("test"), "version_id": durable_id("test_version")}
            if nightly is not None:
                checkpoint["nightly"] = nightly
            conn.execute("INSERT INTO assessment_test_jobs "
                "(id,operation,state,idempotency_key,request_hash,inputs_json,checkpoint_json,settings_revision,policy_revision,context_epoch,"
                "requested_count,validated_count,created_at,updated_at) VALUES(?,?,'running',?,?,?,?,?,?,?, ?,0,?,?)",
                (identifier, operation, request.idempotency_key, digest, encode([entry.model_dump(mode="json") for entry in request.inputs]),
                 self._encode_checkpoint(checkpoint), context["settings"], context["policy"], context["epoch"], request.count, now, now))
            row = self._row(conn, identifier)
            self._nightly_guard(conn, row)
            result = self._view(conn, row)
        self._schedule(identifier, checkpoint["execution"])
        return result

    async def quick_practice(self, request: CreateGenerationRequest):
        if request.count != 5:
            raise ApiError("invalid_request", "Quick practice creates exactly five saved questions", 422)
        return await self.create(request)

    def _schedule(self, identifier, execution):
        task = asyncio.create_task(self._produce(identifier, execution))
        self.tasks[identifier] = task
        def completed(done):
            if self.tasks.get(identifier) is done:
                self.tasks.pop(identifier, None)
            with suppress(BaseException):
                done.result()
        task.add_done_callback(completed)

    def _check(self, conn, row, *, states=("running",), execution=None):
        require_assistance(conn, expected_revision=row["policy_revision"])
        if row["state"] not in states:
            raise ApiError("generation_stopped", "Generation is no longer active", 409)
        checkpoint = self._checkpoint(row)
        if execution is not None and execution != checkpoint["execution"]:
            raise ApiError("generation_stopped", "This execution was superseded", 409)
        self._nightly_guard(conn, row)
        request = CreateGenerationRequest.model_validate(checkpoint["request"])
        context = self._context(conn, request)
        if context["route"] != checkpoint["route"]:
            raise ApiError("connection_changed", "The selected route changed. Retained questions have not been republished", 409)
        if context["epoch"] != row["context_epoch"] or context["settings"] != row["settings_revision"]:
            raise ApiError("generation_context_changed", "Learning context changed. Start a new set; this checkpoint is retained", 409)
        for source in checkpoint["sources"]:
            self._source(conn, source)
        return checkpoint, request, context

    def _source(self, conn, source):
        knowledge = self.services.get("knowledge")
        # Use the existing canonical eligibility policy against the write snapshot.
        eligible = knowledge._retrievable_revisions(ContextScope(kind=Scope.GENERATED_PRACTICE), None, False, conn=conn)
        revision = eligible.get(source["revision_id"])
        passage = conn.execute("SELECT * FROM knowledge_passages WHERE id=? AND revision_id=?", (source["passage_id"], source["revision_id"])).fetchone()
        if not revision or not passage:
            raise ApiError("generation_sources_changed", "A pinned source is unavailable. Retained draft questions are not Ready", 409)
        self._source_revision(conn, revision)
        metadata = json.loads(revision["metadata_json"])
        locators = json.loads(passage["locators_json"])
        if (any(item.get("page") in metadata.get("excluded_pages", []) for item in locators) or
                metadata.get("repository_removed") or canonical_digest({"revision": revision, "passage": dict(passage)}) != source["hash"]):
            raise ApiError("generation_sources_changed", "A pinned source changed. Start a new set with the current sources", 409)
        return revision, dict(passage)

    def _source_revision(self, conn, revision):
        for entity_type, table in TOMBSTONES.items():
            identifier = revision["id"] if table == "knowledge_revisions" else revision["document_id"] if table == "knowledge_documents" else None
            if identifier and conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?", (entity_type, identifier)).fetchone():
                raise ApiError("generation_sources_changed", "A selected source was deleted", 409)
        rights = json.loads(revision["rights_json"])
        knowledge = self.services.get("knowledge")
        metadata = knowledge.source_status.effective(json.loads(revision["metadata_json"]), knowledge.source_status.events(revision["source_id"], conn)).model_dump()
        if (not all(rights.get(key) is True for key in ("model_input", "cache", "display", "derivation")) or
                any(metadata.get(key) for key in ("retracted", "superseded", "repository_removed", "access_changed", "replaced_topics")) or
                metadata.get("correction") and not metadata.get("content_reviewed")):
            raise ApiError("generation_sources_changed", "A selected source no longer permits generation", 409)

    async def _batch(self, identifier, execution, checkpoint, request, context, amount):
        provider = self.services.get("provider")
        run_id = durable_id("generation")
        self.run_ids[execution] = run_id
        prompt = "Generate original nephrology learning practice" + (" about " + context["topic"]["label"] if context["topic"] else " across varied nephrology domains")
        passages, verification = await retrieve(self, SimpleNamespace(scope=ContextScope(kind=Scope.GENERATED_PRACTICE), prompt=prompt, topic_id=request.topic_id))
        if request.source_refs:
            selected = {reference.target.id for reference in request.source_refs}
            passages = [entry for entry in passages if entry.get("document_revision") in selected]
            if not passages:
                raise ApiError("generation_sources_unavailable", "No eligible passages were retrieved from the selected sources. The draft is retained", 409, True)
        sources = []
        with self.db.transaction() as conn:
            current = self._row(conn, identifier)
            checkpoint, _, _ = self._check(conn, current, execution=execution)
            if checkpoint["calls"] >= MAX_CALLS:
                raise ApiError("generation_budget_exhausted", "This set reached its bounded call budget", 409)
            for entry in passages:
                knowledge = self.services.get("knowledge")
                revisions = knowledge._retrievable_revisions(ContextScope(kind=Scope.GENERATED_PRACTICE), request.topic_id, False, conn=conn)
                revision = revisions.get(entry.get("document_revision"))
                passage = conn.execute("SELECT * FROM knowledge_passages WHERE id=? AND revision_id=?", (entry["id"], entry.get("document_revision"))).fetchone()
                if not revision or not passage or passage["text"] != entry["text"]:
                    raise ApiError("generation_sources_changed", "Retrieved evidence changed before generation", 409)
                source = {"revision_id": revision["id"], "passage_id": passage["id"],
                    "hash": canonical_digest({"revision": revision, "passage": dict(passage)}), "citation": citation(entry)}
                self._source(conn, source)
                sources.append(source)
            checkpoint["calls"] += 1
            conn.execute("UPDATE assessment_test_jobs SET checkpoint_json=?,updated_at=? WHERE id=?", (self._encode_checkpoint(checkpoint), utc_now(), identifier))
        messages = [{"role": "user", "content": encode({"task": prompt, "saved_learning_inputs": context["material"],
            "previous_stems": [entry["question"]["stem"] for entry in checkpoint["items"]],
            "evidence": [{"index": index, "text": entry["text"][:8000]} for index, entry in enumerate(passages)]})}]
        if len(encode(messages).encode("utf-8")) > MAX_INPUT:
            raise ApiError("generation_input_limit", "This learning context exceeds the generation budget", 413)
        raw, completed = [], False
        async with aclosing(provider.events(messages, scope=ContextScope(kind=Scope.GENERATED_PRACTICE, entity_id=identifier),
                run_id=run_id, model=context["route"]["model"], system=SYSTEM + f"Produce exactly {amount} questions. Avoid every previous stem.",
                purpose="generated-practice")) as events:
            iterator = events.__aiter__()
            while True:
                pending = asyncio.create_task(anext(iterator))
                try:
                    while not pending.done():
                        await asyncio.wait((pending,), timeout=.1)
                        with self.db.transaction() as conn:
                            self._check(conn, self._row(conn, identifier), execution=execution)
                    try:
                        event = pending.result()
                    except StopAsyncIteration:
                        break
                    with self.db.transaction() as conn:
                        self._check(conn, self._row(conn, identifier), execution=execution)
                    if event.type == "started" and any(event.payload.get(key) != value for key, value in context["route"].items()):
                        raise ApiError("connection_changed", "The selected route changed before model work", 409)
                    if event.type == "error":
                        raise ApiError(event.payload["code"], "The selected subscription could not finish the batch. Validated work is retained", 503, True)
                    if event.type == "cancelled":
                        raise ApiError("generation_stopped", "Generation was cancelled", 409)
                    if event.type == "delta":
                        raw.append(event.payload["text"])
                        if sum(map(len, raw)) > MAX_OUTPUT:
                            raise ApiError("generation_invalid_output", "The batch exceeded its output bound", 502, True)
                    if event.type == "completed":
                        completed = True
                finally:
                    if not pending.done():
                        pending.cancel()
                        with suppress(BaseException):
                            await pending
        if not completed:
            raise ApiError("generation_incomplete_stream", "The subscription ended before confirming completion", 502, True)
        try:
            batch = GeneratedBatch.model_validate(json.loads("".join(raw), object_pairs_hook=unique_keys))
        except (TypeError, ValueError):
            raise ApiError("generation_invalid_output", "The model returned an invalid batch. Retry explicitly", 502, True) from None
        if len(batch.items) > amount or any(index >= len(sources) for item in batch.items for index in item.source_indices):
            raise ApiError("generation_invalid_output", "The model returned an unexpected count or source reference", 502, True)
        keys = [stem_key(item.stem) for item in batch.items]
        previous = {stem_key(entry["question"]["stem"]) for entry in checkpoint["items"]}
        if len(set(keys)) != len(keys) or previous.intersection(keys):
            raise ApiError("generation_duplicate_batch", "The batch repeats a question. Validated prior batches are retained", 502, True)
        if any(not key for key in keys) or any(len({stem_key(option.text) for option in item.options}) != len(item.options) for item in batch.items):
            raise ApiError("generation_invalid_output", "Each question needs distinct meaningful options and a meaningful stem", 502, True)
        return batch, sources, verification

    async def _produce(self, identifier, execution):
        try:
            while True:
                with self.db.transaction() as conn:
                    row = self._row(conn, identifier)
                    checkpoint, request, context = self._check(conn, row, execution=execution)
                    remaining = request.count - row["validated_count"]
                    if remaining == 0:
                        self._publish(conn, row, checkpoint)
                        return
                amount = min(5, remaining)
                batch, sources, verification = await asyncio.wait_for(self._batch(identifier, execution, checkpoint, request, context, amount), self.timeout)
                with self.db.transaction() as conn:
                    row = self._row(conn, identifier)
                    checkpoint, _, _ = self._check(conn, row, execution=execution)
                    for source in sources:
                        self._source(conn, source)
                    for question in batch.items:
                        checkpoint["items"].append({"question": question.model_dump(),
                            "sources": [sources[index]["citation"] for index in question.source_indices], "verification": verification})
                    known = {(source["revision_id"], source["passage_id"]) for source in checkpoint["sources"]}
                    checkpoint["sources"].extend(source for source in sources if (source["revision_id"], source["passage_id"]) not in known)
                    short = len(batch.items) != amount
                    conn.execute("UPDATE assessment_test_jobs SET checkpoint_json=?,validated_count=?,state=?,error_code=?,updated_at=? WHERE id=?",
                        (self._encode_checkpoint(checkpoint), len(checkpoint["items"]), "needs_review" if short else "running", "generation_short_batch" if short else None, utc_now(), identifier))
                    if short:
                        return
        except asyncio.CancelledError:
            self._fail(identifier, execution, "interrupted")
            raise
        except Exception as failure:
            code = failure.code if isinstance(failure, ApiError) else "generation_timeout" if isinstance(failure, TimeoutError) else "generation_failed"
            self._fail(identifier, execution, code)
        finally:
            run_id = self.run_ids.pop(execution, None)
            if run_id:
                with suppress(Exception):
                    await asyncio.wait_for(self.services.get("provider").cancel(run_id), timeout=2)

    def _fail(self, identifier, execution, code):
        with self.db.transaction() as conn:
            row = conn.execute("SELECT * FROM assessment_test_jobs WHERE id=?", (identifier,)).fetchone()
            if row and row["state"] in ("queued", "running") and self._checkpoint(row)["execution"] == execution:
                conn.execute("UPDATE assessment_test_jobs SET state='failed',error_code=?,updated_at=? WHERE id=?", (code, utc_now(), identifier))

    def _publish(self, conn, row, checkpoint, *, accepted_count=None):
        self._check(conn, row, states=("running", "failed", "needs_review", "cancelled"))
        count = accepted_count or row["requested_count"]
        if count != len(checkpoint["items"]):
            raise ApiError("generation_incomplete", "Only the displayed validated count can be published", 409)
        items, provenance = [], []
        for index, entry in enumerate(checkpoint["items"], 1):
            question = entry["question"]
            item_id = "generated_item_" + canonical_digest([row["id"], index])
            identity = "generated_question_" + canonical_digest([row["id"], index])
            items.append(QuestionSnapshot(item_id=item_id, question_id=identity, question_version="1", key_version="1",
                family_id=identity, family_version="1", topic_id=checkpoint["request"]["topic_id"] or "general",
                stem=question["stem"], options=[{"id": option["id"], "text": option["text"]} for option in question["options"]],
                correct_option_ids=(question["correct_option_id"],), explanation=question["explanation"]))
            provenance.append({"item_id": item_id, "ordinal": index, "original_snapshot": entry})
        refs = tuple(ContentReference(target={"type": "library_revision", "id": source["revision_id"]}) for source in checkpoint["sources"])
        # Deduplicate revision references while retaining each precise native citation in provenance.
        refs = tuple({reference.target.id: reference for reference in refs}.values())
        nightly = row["operation"] == "nightly_test"
        method = "nightly" if nightly else "generation"
        version = SavedTestVersion(id=checkpoint["version_id"], test_id=checkpoint["test_id"], ordinal=1,
            origin="nightly" if nightly else "generated", review_quality="personal", status="ready", items=items, source_refs=refs,
            provenance={"method": method, "job_id": row["id"]},
            terms="Generated personal learning practice; referenced sources retain their original terms. No reviewed-bank claim.", created_at=utc_now())
        self.services.get("saved_tests").publish_version(conn, version, title=checkpoint["request"]["title"],
            provenance={"schema": "saved-test-provenance/1", "items": provenance, "job_id": row["id"],
                "route": checkpoint["route"], "requested_count": row["requested_count"], "accepted_count": accepted_count},
            idempotency_key="generation-publish:" + row["id"])
        conn.execute("UPDATE assessment_test_jobs SET state='published',accepted_count=?,published_version_id=?,live_published_version_id=?,"
            "error_code=NULL,updated_at=? WHERE id=?", (accepted_count, version.id, version.id, utc_now(), row["id"]))

    async def _cancel(self, identifier, request):
        # Always return the same neutral shape. A Test may start while awaiting
        # provider shutdown, so no earlier assistance snapshot authorises content.
        old_task = self.tasks.get(identifier)
        with self.db.transaction() as conn:
            policy_snapshot(conn)  # Observe current policy before receipt replay.
            row = self._row(conn, identifier)
            checkpoint = self._checkpoint(row)
            digest = canonical_digest({"operation": "cancel", "request": {}})
            previous = next((receipt for receipt in checkpoint["receipts"] if receipt["key"] == request.idempotency_key), None)
            if previous:
                if previous["hash"] != digest:
                    raise ApiError("idempotency_conflict", "This action key was used for different work", 409)
                return {"id": identifier, "state": row["state"]}
            if row["state"] != "published":
                conn.execute("UPDATE assessment_test_jobs SET state='cancelled',error_code='generation_cancelled',updated_at=? WHERE id=?", (utc_now(), identifier))
            # Even an exhausted receipt journal must permit neutral Stop.
            if len(checkpoint["receipts"]) < MAX_RECEIPTS:
                checkpoint["receipts"].append({"key": request.idempotency_key, "hash": digest})
                conn.execute("UPDATE assessment_test_jobs SET checkpoint_json=? WHERE id=?", (self._encode_checkpoint(checkpoint), identifier))
        if old_task:
            old_task.cancel()
            with suppress(asyncio.CancelledError):
                await old_task
        with self.db.transaction() as conn:
            policy_snapshot(conn)
            return {"id": identifier, "state": self._row(conn, identifier)["state"]}

    async def action(self, identifier, operation, request):
        if operation == "cancel":
            return await self._cancel(identifier, request)
        with self.db.transaction() as conn:
            require_assistance(conn)
            self.reconcile_nightly(conn)
            row = self._row(conn, identifier)
            checkpoint = self._checkpoint(row)
            self._nightly_guard(conn, row)
            digest = canonical_digest({"operation": operation, "request": request.model_dump(mode="json", exclude={"idempotency_key"})})
            previous = next((receipt for receipt in checkpoint["receipts"] if receipt["key"] == request.idempotency_key), None)
            if previous:
                if previous["hash"] != digest:
                    raise ApiError("idempotency_conflict", "This action key was used for different work", 409)
                return self._view(conn, row)
            if len(checkpoint["receipts"]) >= MAX_RECEIPTS:
                raise ApiError("generation_action_limit", "This job reached its action receipt bound", 409)
            if row["state"] == "published":
                checkpoint["receipts"].append({"key": request.idempotency_key, "hash": digest})
                conn.execute("UPDATE assessment_test_jobs SET checkpoint_json=? WHERE id=?", (self._encode_checkpoint(checkpoint), identifier))
                return self._view(conn, row)  # Publication won cancellation; return the durable winner.
            if operation == "retry":
                if row["state"] not in ("failed", "needs_review", "cancelled") or checkpoint["calls"] >= MAX_CALLS:
                    raise ApiError("generation_retry_unavailable", "The job cannot start another provider call", 409)
                self._check(conn, row, states=("failed", "needs_review", "cancelled"))
                self._capacity(conn)
                checkpoint["execution"] = durable_id("execution")
                conn.execute("UPDATE assessment_test_jobs SET state='running',error_code=NULL,updated_at=? WHERE id=?", (utc_now(), identifier))
            elif operation == "accept_shorter":
                if row["state"] not in ("failed", "needs_review", "cancelled") or request.accepted_count >= row["requested_count"]:
                    raise ApiError("generation_accept_unavailable", "Accept only a shorter recovered set after generation stops", 409)
                self._publish(conn, row, checkpoint, accepted_count=request.accepted_count)
            else:
                raise ValueError("Unknown generation action")
            checkpoint["receipts"].append({"key": request.idempotency_key, "hash": digest})
            conn.execute("UPDATE assessment_test_jobs SET checkpoint_json=?,updated_at=? WHERE id=?", (self._encode_checkpoint(checkpoint), utc_now(), identifier))
            result = self._view(conn, self._row(conn, identifier))
        if operation == "retry":
            self._schedule(identifier, checkpoint["execution"])
        return result

    async def close(self):
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task

