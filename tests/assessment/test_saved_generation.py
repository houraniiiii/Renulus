# SPDX-License-Identifier: MIT
"""Real migrations, repositories and ProviderManager with an installed synthetic transport."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
import pytest

from renulus.assessment.generation_api import create_router
from renulus.assessment.generation_models import AcceptShorterRequest, CreateGenerationRequest, GenerationAction
from renulus.assessment.generation_service import MAX_CALLS, SavedGenerationService
from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.engines import Extracted
from renulus.knowledge.models import SourceMetadata
from renulus.server import create_app
from renulus.storage import utc_now
from renulus.storage.assessment_policy import advance_policy
from renulus.storage.invalidation import bump_context_epoch
from renulus.storage.backup import export_records
from renulus.study.nightly_api import create_router as create_nightly_router
from renulus.study.nightly_models import PreferencesUpdate


def batch(start=0, count=5):
    return {"items": [{"stem": f"Original synthetic renal learning question {index}",
        "options": [{"id": "a", "text": "First interpretation", "rationale": "PRIVATE_RATIONALE"},
                    {"id": "b", "text": "Second interpretation", "rationale": "Other rationale"}],
        "correct_option_id": "a", "explanation": "PRIVATE_GENERATED_EXPLANATION", "hint": None,
        "source_indices": []} for index in range(start, start + count)]}


class SyntheticTransport:
    """Only the transport is synthetic: routing, token/stream handling and storage are real."""
    def __init__(self):
        self.calls = []
        self.responses = []
        self.release = None
        self.started = asyncio.Event()
        self.error = None

    async def stream(self, provider, model, token, messages):
        assert token == "synthetic-generation-token"
        number = len(self.calls)
        self.calls.append((provider, model, deepcopy(messages)))
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.error:
            raise self.error
        output = self.responses[number] if number < len(self.responses) else batch(number * 5)
        yield {"type": "delta", "text": output if isinstance(output, str) else json.dumps(output)}
        yield {"type": "completed", "response_model": model}


@pytest.fixture
def generation(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "learn", "cases", "assessment", "memory", "study"))
    app = create_app(tmp_path / "synthetic-generation")
    if "saved_generation" not in app.state.services.registry:
        app.include_router(create_router(app.state.services), prefix="/api/v1")
    services = app.state.services
    service = services.get("saved_generation")
    owners = {id(getattr(callback, "__self__", None)) for callback in services.on_startup
              if isinstance(getattr(callback, "__self__", None), SavedGenerationService)}
    assert owners == {id(service)}, "One assembled generation service owns the router and startup recovery"
    provider = services.get("provider")
    transport = SyntheticTransport()
    provider._settings["connections"]["codex"] = {"access_token": "synthetic-generation-token", "expires_at": 9999999999}
    provider._settings["selected_provider"] = "codex"
    provider._settings.setdefault("selected_models", {})["codex"] = "gpt-6.1-sol"
    provider._transport = transport
    # Avoid unrelated helper acquisition; no migration or repository is replaced.
    services.on_startup = [services.get("saved_tests").backfill_legacy, service.recover]
    services.on_shutdown = [provider.close, service.close]
    return app, service, transport


def request(**values):
    return CreateGenerationRequest(idempotency_key="synthetic-generation-create", **values)


async def finish(service, identifier):
    task = service.tasks.get(identifier)
    if task:
        await task
    return service.read(identifier)


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [5, 10, 20])
async def test_real_selected_route_batches_publish_once_and_keep_keys_private(generation, count):
    app, service, transport = generation
    results = await asyncio.gather(*(service.create(request(count=count)) for _ in range(6)))
    identifier = results[0]["id"]
    assert len({result["id"] for result in results}) == 1
    result = await finish(service, identifier)
    assert result["state"] == "published", service.db.fetch_all("SELECT error_code,checkpoint_json FROM assessment_test_jobs")
    assert result["validated_count"] == result["effective_count"] == result["result"]["item_count"] == count
    assert len(transport.calls) == count // 5
    assert all(call[:2] == ("codex", "gpt-6.1-sol") for call in transport.calls)
    assert len(service.db.fetch_all("SELECT id FROM assessment_test_versions")) == 1
    assert await service.create(request(count=count)) == result
    assert service.read(identifier) == result
    assert len(transport.calls) == count // 5
    repository = app.state.services.get("saved_tests")
    with service.db.transaction() as conn:
        version = repository.pinned_version(conn, result["result"]["version_id"])
    assert version.item_count == count and not version.bank_cohort_eligible
    assert version.items[0].correct_option_ids == ("a",)
    assert repository.setup_version(version.id)["version"]["item_count"] == count
    assert "PRIVATE_GENERATED_EXPLANATION" not in json.dumps(result)
    assert service.db.fetch_all("SELECT id FROM learning_evidence") == []


@pytest.mark.asyncio
async def test_short_second_batch_is_explicitly_accepted_once_with_every_count(generation):
    app, service, transport = generation
    transport.responses = [batch(), batch(5, 2)]
    row = await service.create(request(count=10))
    result = await finish(service, row["id"])
    assert result["state"] == "needs_review" and result["validated_count"] == 7
    assert service.db.fetch_all("SELECT id FROM assessment_tests") == []
    bad = AcceptShorterRequest(idempotency_key="synthetic-bad-accept", accepted_count=6)
    with pytest.raises(ApiError, match="displayed validated count"):
        await service.action(row["id"], "accept_shorter", bad)
    accept = AcceptShorterRequest(idempotency_key="synthetic-short-accept", accepted_count=7)
    accepted = await service.action(row["id"], "accept_shorter", accept)
    assert accepted["state"] == "published"
    assert accepted["accepted_count"] == accepted["effective_count"] == accepted["result"]["item_count"] == 7
    assert accepted["requested_count"] == 10 and accepted["validated_count"] == 7
    assert await service.action(row["id"], "accept_shorter", accept) == accepted
    assert app.state.services.get("saved_tests").setup_version(accepted["result"]["version_id"])["version"]["item_count"] == 7
    assert len(transport.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["json", "duplicate_json", "key", "option_id", "option_text", "source", "within_duplicate", "cross_duplicate", "oversized"])
async def test_invalid_second_batch_retains_prior_work_and_explicit_retry_only_deficit(generation, invalid):
    _, service, transport = generation
    value = batch(5)
    if invalid == "json":
        value = "invalid"
    elif invalid == "duplicate_json":
        value = json.dumps(value)[:-1] + ',"items":' + json.dumps(value["items"]) + "}"
    elif invalid == "key":
        value["items"][0]["correct_option_id"] = "missing"
    elif invalid == "option_id":
        value["items"][0]["options"][1]["id"] = "a"
    elif invalid == "option_text":
        value["items"][0]["options"][1]["text"] = "FIRST interpretation!"
    elif invalid == "source":
        value["items"][0]["source_indices"] = [0]
    elif invalid == "within_duplicate":
        value["items"][1]["stem"] = value["items"][0]["stem"].upper() + "!"
    elif invalid == "cross_duplicate":
        value["items"][0]["stem"] = batch()["items"][0]["stem"].upper() + "!"
    else:
        value = "x" * 65537
    transport.responses = [batch(), value, batch(5)]
    row = await service.create(request(count=10))
    result = await finish(service, row["id"])
    assert result["state"] == "failed" and result["validated_count"] == 5
    assert result["error_code"] in ("generation_invalid_output", "generation_duplicate_batch")
    assert service.db.fetch_all("SELECT id FROM assessment_tests") == []
    assert service.read(row["id"])["validated_count"] == 5 and len(transport.calls) == 2
    retry = GenerationAction(idempotency_key="synthetic-retry-deficit")
    await service.action(row["id"], "retry", retry)
    result = await finish(service, row["id"])
    assert result["state"] == "published" and result["validated_count"] == 10
    assert len(transport.calls) == 3
    assert await service.action(row["id"], "retry", retry) == result
    assert len(transport.calls) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["epoch", "policy", "route", "model"])
async def test_changes_during_provider_wait_prevent_stale_publication(generation, change):
    app, service, transport = generation
    transport.release = asyncio.Event()
    row = await service.create(request())
    await asyncio.wait_for(transport.started.wait(), timeout=5)
    with service.db.transaction() as conn:
        if change == "epoch":
            bump_context_epoch(conn)
        elif change == "policy":
            advance_policy(conn)
        elif change == "route":
            app.state.services.get("provider")._settings["selected_provider"] = None
        else:
            app.state.services.get("provider")._settings["selected_models"]["codex"] = "gpt-6-luna"
    transport.release.set()
    result = await finish(service, row["id"])
    assert result["state"] == "failed" and result["result"] is None
    assert not result["can_retry"] and not result["can_accept_shorter"]
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
    assert app.state.services.get("provider").status()["active_runs"] == []


@pytest.mark.asyncio
async def test_cancel_retry_race_old_execution_cannot_fail_or_cancel_new_work(generation):
    _, service, transport = generation
    transport.release = asyncio.Event()
    row = await service.create(request())
    await transport.started.wait()
    cancel = GenerationAction(idempotency_key="synthetic-cancel-race")
    retry = GenerationAction(idempotency_key="synthetic-retry-race")
    first = asyncio.create_task(service.action(row["id"], "cancel", cancel))
    await asyncio.sleep(0)  # cancel transaction commits before the retry transaction
    await service.action(row["id"], "retry", retry)
    await first
    transport.release.set()
    result = await finish(service, row["id"])
    assert result["state"] == "published"
    assert len(service.db.fetch_all("SELECT id FROM assessment_test_versions")) == 1


@pytest.mark.asyncio
async def test_restart_retains_validated_checkpoint_and_never_starts_provider(generation):
    app, service, transport = generation
    transport.responses = [batch(), "invalid"]
    row = await service.create(request(count=10))
    await finish(service, row["id"])
    service.db.execute("UPDATE assessment_test_jobs SET state='running' WHERE id=?", (row["id"],))
    restarted = SavedGenerationService(app.state.services)
    restarted.recover()
    result = restarted.read(row["id"])
    assert result["state"] == "failed" and result["error_code"] == "interrupted"
    assert result["validated_count"] == 5 and len(transport.calls) == 2
    assert restarted.tasks == {}
    await restarted.action(row["id"], "retry", GenerationAction(idempotency_key="synthetic-restart-retry"))
    assert (await finish(restarted, row["id"]))["state"] == "published"
    assert len(transport.calls) == 3


@pytest.mark.asyncio
async def test_bounded_explicit_retries_and_no_automatic_retry_on_quota(generation):
    _, service, transport = generation
    transport.error = ApiError("subscription_limit", "Synthetic limit", 429, True)
    row = await service.create(request())
    await finish(service, row["id"])
    for index in range(MAX_CALLS - 1):
        await service.action(row["id"], "retry", GenerationAction(idempotency_key=f"synthetic-bounded-retry-{index}"))
        await finish(service, row["id"])
    assert len(transport.calls) == MAX_CALLS
    assert service.read(row["id"])["calls_remaining"] == 0
    with pytest.raises(ApiError) as error:
        await service.action(row["id"], "retry", GenerationAction(idempotency_key="synthetic-budget-final"))
    assert error.value.code == "generation_retry_unavailable"


@pytest.mark.parametrize("field", ["prompt", "context", "fictional_artifact", "review_quality"])
def test_renderer_cannot_attest_or_store_raw_temporary_input(field):
    with pytest.raises(ValidationError):
        CreateGenerationRequest.model_validate({"idempotency_key": "synthetic-input-refused", field: "RAW_TEMPORARY_SENTINEL"})


def test_router_real_publication_polling_replay_and_neutral_key_free_progress(generation):
    app, service, transport = generation
    with TestClient(app) as client:
        started = client.post("/api/v1/assessment/generation/quick-practice", json=request().model_dump(mode="json"))
        assert started.status_code == 202, started.text
        for _ in range(80):
            response = client.get("/api/v1/assessment/generation/jobs/" + started.json()["id"])
            result = response.json()
            if result["state"] == "published":
                break
        assert result["state"] == "published", result
        assert response.headers["cache-control"] == "no-store"
        assert all(value not in response.text for value in ("correct_option", "PRIVATE_RATIONALE", "PRIVATE_GENERATED_EXPLANATION"))
        assert client.get("/api/v1/assessment/generation/jobs").json()["items"][0] == result
        assert client.post("/api/v1/assessment/generation/jobs", json=request().model_dump(mode="json")).json() == result
        cancel = client.post("/api/v1/assessment/generation/jobs/" + result["id"] + "/cancel", json={"idempotency_key": "synthetic-after-publish"})
        assert cancel.json()["state"] == "published"
        assert client.post("/api/v1/assessment/generation/quick-practice", json=request(count=10).model_dump(mode="json")).status_code == 422
    assert len(transport.calls) == 1


class SyntheticExtractor:
    def extract_file(self, path, title):
        text = path.read_text(encoding="utf-8")
        return Extracted([{"text": text, "context_text": text, "headings": [],
            "locators": [{"page": 1, "char_span": [0, len(text)], "item_ref": "#/texts/0"}]}], {"synthetic": True})


class SyntheticEmbedder:
    model_id, dimensions, max_tokens = "synthetic-384", 384, 512

    def embed(self, texts, *, query=False):
        return [[1.0] + [0.0] * 383 for _ in texts]


def source(app):
    knowledge = app.state.services.get("knowledge")
    knowledge.extractor, knowledge.embedder = SyntheticExtractor(), SyntheticEmbedder()
    note = knowledge.import_text("Original synthetic renal learning about dialysis access surveillance.",
        title="Synthetic learning source", scope=ContextScope(kind=Scope.LIBRARY),
        metadata=SourceMetadata(topic_ids=["T01"]), idempotency_key="synthetic-generation-source")
    assert note["status"] == "ready"
    return knowledge, note


@pytest.mark.asyncio
async def test_actual_library_retrieval_and_pinned_source_provenance(generation):
    app, service, transport = generation
    knowledge, note = source(app)
    try:
        value = batch()
        value["items"][0]["source_indices"] = [0]
        transport.responses = [value]
        row = await service.create(request(source_refs=[{"target": {"type": "library_revision", "id": note["revision_id"]}}]))
        result = await finish(service, row["id"])
        assert result["state"] == "published", result
        assert "dialysis access surveillance" in json.dumps(transport.calls)
        with service.db.transaction() as conn:
            version = app.state.services.get("saved_tests").pinned_version(conn, result["result"]["version_id"])
        assert [ref.target.id for ref in version.source_refs] == [note["revision_id"]]
        provenance = json.loads(service.db.fetch_one("SELECT provenance_json FROM assessment_test_versions")["provenance_json"])
        assert provenance["items"][0]["original_snapshot"]["sources"][0]["document_revision"] == note["revision_id"]
    finally:
        knowledge.index.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["delete", "tombstone", "rights", "retracted", "page", "passage"])
async def test_actual_source_changes_midstream_block_ready_and_preserve_draft(generation, change):
    app, service, transport = generation
    knowledge, note = source(app)
    try:
        transport.release = asyncio.Event()
        row = await service.create(request(source_refs=[{"target": {"type": "library_revision", "id": note["revision_id"]}}]))
        await asyncio.wait_for(transport.started.wait(), timeout=5)
        with service.db.transaction() as conn:
            if change == "delete":
                conn.execute("UPDATE knowledge_documents SET deleted_at=? WHERE id=?", (utc_now(), note["document_id"]))
            elif change == "tombstone":
                service.db.mark_deleted("knowledge-revision", note["revision_id"], conn=conn)
            elif change == "rights":
                conn.execute("UPDATE knowledge_revisions SET rights_json=json_set(rights_json,'$.derivation',json('false')) WHERE id=?", (note["revision_id"],))
            elif change == "retracted":
                conn.execute("UPDATE knowledge_revisions SET metadata_json=json_set(metadata_json,'$.retracted',json('true')) WHERE id=?", (note["revision_id"],))
            elif change == "page":
                conn.execute("UPDATE knowledge_revisions SET metadata_json=json_set(metadata_json,'$.excluded_pages',json('[1]')) WHERE id=?", (note["revision_id"],))
            else:
                conn.execute("UPDATE knowledge_passages SET text='Changed synthetic passage' WHERE revision_id=?", (note["revision_id"],))
        transport.release.set()
        result = await finish(service, row["id"])
        assert result["state"] == "failed" and result["result"] is None
        assert result["error_code"] in ("generation_sources_changed", "generation_context_changed")
        assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
    finally:
        knowledge.index.close()


@pytest.mark.asyncio
async def test_saved_memory_resolution_and_revised_input_refusal(generation):
    app, service, transport = generation
    stamp = utc_now()
    service.db.execute("INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("memory_synthetic", "Synthetic general renal learning", "synthetic-hash", "learning-point", "T01", "study", 1, "manual", None, stamp, stamp))
    service.db.execute("INSERT INTO memory_history VALUES(?,?,?,?,?)", ("memory_synthetic", 1, "Synthetic general renal learning", "added", stamp))
    with service.db.transaction() as conn:
        inputs = app.state.services.get("home")._context(conn).inputs
    assert inputs
    transport.release = asyncio.Event()
    row = await service.create(request(inputs=inputs))
    await transport.started.wait()
    assert "Synthetic general renal learning" in json.dumps(transport.calls)
    service.db.execute("UPDATE memory_facts SET revision=2,text='Corrected learning' WHERE id='memory_synthetic'")
    transport.release.set()
    result = await finish(service, row["id"])
    assert result["error_code"] == "generation_inputs_changed" and result["result"] is None
    with pytest.raises(ApiError) as error:
        await service.action(row["id"], "retry", GenerationAction(idempotency_key="synthetic-memory-retry"))
    assert error.value.code == "generation_inputs_changed" and len(transport.calls) == 1


@pytest.mark.asyncio
async def test_active_test_policy_precedes_create_replay_retry_and_publication(generation):
    _, service, transport = generation
    transport.responses = ["invalid"]
    row = await service.create(request())
    await finish(service, row["id"])
    stamp = utc_now()
    # An actual frozen table row models the other writer's active attempt; no fixture DDL.
    service.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
        "VALUES('synthetic-active-test','synthetic-version','{}','test',?,?,?)", (stamp, stamp, stamp))
    for operation in (service.create(request()), service.action(row["id"], "retry", GenerationAction(idempotency_key="synthetic-policy-retry"))):
        with pytest.raises(ApiError) as error:
            await operation
        assert error.value.code == "assistance_restricted"
    assert len(transport.calls) == 1
    service.db.execute("DELETE FROM assessment_test_attempts WHERE id='synthetic-active-test'")
    transport.release = asyncio.Event()
    transport.started.clear()
    transport.responses.append(batch())
    await service.action(row["id"], "retry", GenerationAction(idempotency_key="synthetic-policy-before-wait"))
    await transport.started.wait()
    service.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
        "VALUES('synthetic-active-test','synthetic-version','{}','test',?,?,?)", (stamp, stamp, stamp))
    transport.release.set()
    await service.tasks[row["id"]]
    stored = service.db.fetch_one("SELECT state,error_code FROM assessment_test_jobs WHERE id=?", (row["id"],))
    assert stored == {"state": "failed", "error_code": "assistance_restricted"}
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []


@pytest.mark.asyncio
async def test_active_test_neutral_cancel_stops_real_provider_and_replay_never_discloses(generation):
    app, service, transport = generation
    transport.release = asyncio.Event()
    row = await service.create(request(title="PRIVATE_GENERATION_TITLE"))
    await transport.started.wait()
    stamp = utc_now()
    service.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
        "VALUES('synthetic-active-test','synthetic-version','{}','test',?,?,?)", (stamp, stamp, stamp))
    action = GenerationAction(idempotency_key="synthetic-test-cancel")
    result = await service.action(row["id"], "cancel", action)
    assert result == {"id": row["id"], "state": "cancelled"}
    assert await service.action(row["id"], "cancel", action) == result
    assert app.state.services.get("provider").status()["active_runs"] == []
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
    for operation in (service.create(request()), service.action(row["id"], "retry", GenerationAction(idempotency_key="synthetic-blocked-retry")),
                      service.action(row["id"], "accept_shorter", AcceptShorterRequest(idempotency_key="synthetic-blocked-accept", accepted_count=1))):
        with pytest.raises(ApiError) as error:
            await operation
        assert error.value.code == "assistance_restricted"
    with pytest.raises(ApiError) as error:
        service.read(row["id"])
    assert error.value.code == "assistance_restricted"


@pytest.mark.asyncio
async def test_actual_json_restore_invalidates_active_and_orphaned_jobs_without_provider_replay(generation):
    app, service, transport = generation
    transport.release = asyncio.Event()
    row = await service.create(request())
    await transport.started.wait()
    bundle = export_records(app.state.services)
    recovery = app.state.services.get("data_recovery")
    recovery.restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    result = service.read(row["id"])
    assert result["state"] == "failed" and result["error_code"] == "generation_context_changed"
    assert not result["can_retry"] and result["result"] is None
    await service.tasks[row["id"]]
    assert len(transport.calls) == 1 and service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
    # Import the actual prior running checkpoint into the live process: there
    # is no owner task, and no automatic startup/retry callback may run it.
    service.db.execute("DELETE FROM assessment_test_jobs WHERE id=?", (row["id"],))
    recovery.restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    result = service.read(row["id"])
    assert result["state"] == "failed" and result["error_code"] == "generation_context_changed"
    assert service.db.fetch_one("SELECT state FROM assessment_test_jobs WHERE id=?", (row["id"],))["state"] == "failed"
    assert service.tasks == {} and len(transport.calls) == 1


class BoundaryNightlyGuard:
    """External owner boundary only; scheduler eligibility needs its connected suite."""
    def __init__(self):
        self.calls = []
        self.denied = False
        self.stop_after = None

    def require_publication(self, conn, row):
        assert conn.in_transaction and row["operation"] == "nightly_test"
        self.calls.append((row["state"], row["validated_count"]))
        if self.denied or self.stop_after is not None and row["validated_count"] >= self.stop_after:
            raise ApiError("nightly_ineligible", "Synthetic owner revoked publication", 409)


def nightly_request(**values):
    return CreateGenerationRequest(idempotency_key="nightly:2026-10-10", title="Synthetic nightly practice", **values)


def nightly_schedule():
    return {"day": "2026-10-10", "timezone": "Europe/Warsaw", "preferences_revision": 1,
            "home_settings_revision": 1, "eligibility_token": "synthetic-nightly-eligibility"}


@pytest.fixture
def nightly_boundary(generation):
    app, service, transport = generation
    guard = BoundaryNightlyGuard()
    app.state.services.registry["nightly"] = guard
    return app, service, transport, guard


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [5, 10, 20])
async def test_trusted_nightly_boundary_batches_publish_actual_personal_versions(nightly_boundary, count):
    app, service, transport, guard = nightly_boundary
    rows = await asyncio.gather(*(service.create_nightly(nightly_request(count=count), schedule=nightly_schedule()) for _ in range(4)))
    identifier = rows[0]["id"]
    assert len({row["id"] for row in rows}) == 1
    result = await finish(service, identifier)
    assert result["state"] == "published", result
    stored = service.db.fetch_one("SELECT * FROM assessment_test_jobs WHERE id=?", (identifier,))
    assert stored["operation"] == "nightly_test"
    assert json.loads(stored["checkpoint_json"])["nightly"] == nightly_schedule()
    assert len(transport.calls) == count // 5
    assert guard.calls.count(("running", count)) >= 2, "Final publication rechecks the guard inside its transaction"
    with service.db.transaction() as conn:
        version = app.state.services.get("saved_tests").pinned_version(conn, result["result"]["version_id"])
    assert version.item_count == count and version.origin == "nightly"
    assert version.provenance.method == "nightly" and version.provenance.job_id == identifier
    assert version.review_quality == "personal" and not version.bank_cohort_eligible
    assert service.list_jobs()["items"] == [result]
    assert await service.create_nightly(nightly_request(count=count), schedule=nightly_schedule()) == result
    assert len(transport.calls) == count // 5
    assert not any(key in json.dumps(result) for key in ("PRIVATE_", "eligibility_token", "checkpoint_json", "correct_option_ids"))


@pytest.mark.asyncio
async def test_nightly_missing_or_denied_owner_rolls_back_and_published_replay_remains_safe(generation):
    app, service, transport = generation
    with pytest.raises(ApiError) as error:
        await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    assert error.value.code == "nightly_unavailable"
    assert service.db.fetch_all("SELECT id FROM assessment_test_jobs") == [] and transport.calls == []
    guard = BoundaryNightlyGuard()
    app.state.services.registry["nightly"] = guard
    guard.denied = True
    with pytest.raises(ApiError) as error:
        await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    assert error.value.code == "nightly_ineligible"
    assert service.db.fetch_all("SELECT id FROM assessment_test_jobs") == [] and transport.calls == []
    guard.denied = False
    row = await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    published = await finish(service, row["id"])
    guard.denied = True
    assert await service.create_nightly(nightly_request(), schedule=nightly_schedule()) == published
    assert len(transport.calls) == 1
    assert service.read(row["id"])["state"] == "published", "Safe existing progress remains readable after disable"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["extra", "missing", "date", "revision", "key", "topic", "source"])
async def test_nightly_trusted_checkpoint_exact_shape_and_reserved_renderer_keys(nightly_boundary, change):
    _, service, transport, _ = nightly_boundary
    schedule, values = nightly_schedule(), {}
    if change == "extra":
        schedule["prompt"] = "RAW_TEMPORARY_SENTINEL"
    elif change == "missing":
        del schedule["eligibility_token"]
    elif change == "date":
        schedule["day"] = "2026-02-30"
    elif change == "revision":
        schedule["preferences_revision"] = True
    elif change == "key":
        schedule["day"] = "2026-10-11"
    elif change == "topic":
        values["topic_id"] = "T01"
    else:
        values["source_refs"] = [{"target": {"type": "library_revision", "id": "synthetic-source"}}]
    with pytest.raises(ApiError) as error:
        await service.create_nightly(nightly_request(**values), schedule=schedule)
    assert error.value.code == "invalid_request"
    with pytest.raises(ApiError) as error:
        await service.create(nightly_request())
    assert error.value.code == "invalid_request"
    assert service.db.fetch_all("SELECT id FROM assessment_test_jobs") == [] and transport.calls == []


@pytest.mark.asyncio
async def test_nightly_guard_revocation_stops_waiting_stream_without_next_chunk(nightly_boundary):
    _, service, transport, guard = nightly_boundary
    transport.release = asyncio.Event()
    row = await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    await asyncio.wait_for(transport.started.wait(), timeout=5)
    guard.denied = True
    await asyncio.wait_for(service.tasks[row["id"]], timeout=3)
    result = service.read(row["id"])
    assert result["state"] == "failed" and result["error_code"] == "nightly_ineligible"
    assert not result["can_retry"] and result["validated_count"] == 0
    assert len(transport.calls) == 1 and service.db.fetch_all("SELECT id FROM assessment_test_versions") == []


@pytest.mark.asyncio
async def test_nightly_guard_before_second_batch_retains_validated_work(nightly_boundary):
    _, service, transport, guard = nightly_boundary
    guard.stop_after = 5
    row = await service.create_nightly(nightly_request(count=10), schedule=nightly_schedule())
    result = await finish(service, row["id"])
    assert result["state"] == "failed" and result["validated_count"] == 5
    assert len(transport.calls) == 1 and service.db.fetch_all("SELECT id FROM assessment_test_versions") == []


@pytest.mark.asyncio
async def test_nightly_guard_in_final_publication_transaction_refuses_late_revocation(nightly_boundary, monkeypatch):
    _, service, transport, guard = nightly_boundary
    publish = service._publish
    def revoked(conn, row, checkpoint, **kwargs):
        guard.denied = True
        return publish(conn, row, checkpoint, **kwargs)
    monkeypatch.setattr(service, "_publish", revoked)
    row = await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    result = await finish(service, row["id"])
    assert result["state"] == "failed" and result["validated_count"] == 5
    assert result["error_code"] == "nightly_ineligible"
    assert service.db.fetch_all("SELECT id FROM assessment_tests") == []
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == [] and len(transport.calls) == 1


@pytest.mark.asyncio
async def test_nightly_explicit_shorter_and_action_replay_recheck_owner(nightly_boundary):
    _, service, transport, guard = nightly_boundary
    transport.responses = [batch(count=2)]
    row = await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    result = await finish(service, row["id"])
    assert result["state"] == "needs_review" and result["validated_count"] == 2
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
    guard.denied = True
    for operation, action in (("retry", GenerationAction(idempotency_key="synthetic-nightly-retry")),
                              ("accept_shorter", AcceptShorterRequest(idempotency_key="synthetic-nightly-short", accepted_count=2))):
        with pytest.raises(ApiError) as error:
            await service.action(row["id"], operation, action)
        assert error.value.code == "nightly_ineligible"
    guard.denied = False
    action = AcceptShorterRequest(idempotency_key="synthetic-nightly-short", accepted_count=2)
    accepted = await service.action(row["id"], "accept_shorter", action)
    assert accepted["state"] == "published" and accepted["effective_count"] == 2
    guard.denied = True
    assert await service.action(row["id"], "accept_shorter", action) == accepted
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_nightly_cancel_remains_neutral_during_test_and_owner_disable(nightly_boundary):
    _, service, transport, guard = nightly_boundary
    transport.release = asyncio.Event()
    row = await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    await asyncio.wait_for(transport.started.wait(), timeout=5)
    guard.denied = True
    stamp = utc_now()
    service.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
        "VALUES('synthetic-active-test','synthetic-version','{}','test',?,?,?)", (stamp, stamp, stamp))
    action = GenerationAction(idempotency_key="synthetic-nightly-neutral-cancel")
    assert await service.action(row["id"], "cancel", action) == {"id": row["id"], "state": "cancelled"}
    assert await service.action(row["id"], "cancel", action) == {"id": row["id"], "state": "cancelled"}
    with pytest.raises(ApiError) as error:
        service.read(row["id"])
    assert error.value.code == "assistance_restricted"
    assert service.services.get("provider").status()["active_runs"] == []
    assert len(transport.calls) == 1 and service.db.fetch_all("SELECT id FROM assessment_test_versions") == []


@pytest.mark.asyncio
async def test_nightly_restart_and_actual_restore_never_replay_provider(nightly_boundary):
    app, service, transport, _ = nightly_boundary
    transport.release = asyncio.Event()
    row = await service.create_nightly(nightly_request(), schedule=nightly_schedule())
    await asyncio.wait_for(transport.started.wait(), timeout=5)
    bundle = export_records(app.state.services)
    recovery = app.state.services.get("data_recovery")
    recovery.restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    result = service.read(row["id"])
    assert result["state"] == "failed" and result["error_code"] == "interrupted"
    assert not result["can_retry"]
    await asyncio.wait_for(service.tasks[row["id"]], timeout=3)
    service.db.execute("DELETE FROM assessment_test_jobs WHERE id=?", (row["id"],))
    recovery.restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    assert service.list_jobs()["items"][0]["error_code"] == "interrupted"
    assert service.tasks == {} and len(transport.calls) == 1
    for state in ("queued", "running"):
        service.db.execute("UPDATE assessment_test_jobs SET state=? WHERE id=?", (state, row["id"]))
        restarted = SavedGenerationService(app.state.services)
        restarted.recover()
        result = restarted.read(row["id"])
        assert result["state"] == "failed" and result["error_code"] == "interrupted"
        assert restarted.tasks == {} and len(transport.calls) == 1
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []


@pytest.fixture
def connected_nightly(generation):
    """Actual scheduler/guard, migrations, eligibility and generation; transport only is synthetic."""
    app, service, transport = generation
    if "nightly" not in app.state.services.registry:
        app.include_router(create_nightly_router(app.state.services), prefix="/api/v1")
    nightly = app.state.services.get("nightly")
    clock = [datetime(2026, 10, 10, 20, tzinfo=timezone.utc)]
    nightly.local_now = lambda: clock[0]
    return app, service, transport, nightly, clock


async def scheduled(nightly, clock, *, count=5):
    await nightly.update_preferences(PreferencesUpdate(enabled=True, question_count=count, expected_revision=1),
                                     "synthetic-connected-nightly-enable")
    clock[0] = clock[0].replace(hour=23)
    result = await nightly.tick()
    assert result["last_job"] is not None, result
    return result["last_job"]["id"]


async def provider_started(service, transport, identifier):
    observed = asyncio.create_task(transport.started.wait())
    try:
        await asyncio.wait((observed, service.tasks[identifier]), timeout=20, return_when=asyncio.FIRST_COMPLETED)
        assert transport.started.is_set(), service.db.fetch_one("SELECT state,error_code FROM assessment_test_jobs WHERE id=?", (identifier,))
    finally:
        if not observed.done():
            observed.cancel()


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [5, 10, 20])
async def test_actual_nightly_scheduler_provider_publication_and_generation_routes(connected_nightly, count):
    app, service, transport, nightly, clock = connected_nightly
    identifier = await scheduled(nightly, clock, count=count)
    result = await finish(service, identifier)
    assert result["state"] == "published", result
    assert len(transport.calls) == count // 5
    assert nightly.read()["last_job"]["result"]["version"]["id"] == result["result"]["version_id"]
    with service.db.transaction() as conn:
        version = app.state.services.get("saved_tests").pinned_version(conn, result["result"]["version_id"])
    assert version.origin == version.provenance.method == "nightly"
    assert version.item_count == count and version.review_quality == "personal"
    async with AsyncClient(transport=ASGITransport(app), base_url="http://testserver") as client:
        progress = await client.get("/api/v1/assessment/generation/jobs/" + identifier)
        assert progress.status_code == 200 and progress.json() == result, progress.text
        assert progress.headers["cache-control"] == "no-store"
        assert (await client.get("/api/v1/assessment/generation/jobs")).json()["items"] == [result]
        forbidden = await client.post("/api/v1/assessment/generation/jobs", json=nightly_request().model_dump(mode="json"))
        assert forbidden.status_code == 422
        assert not any(value in progress.text for value in ("correct_option", "PRIVATE_", "eligibility_token"))
    for _ in range(3):
        await nightly.tick()
    assert len(transport.calls) == count // 5
    assert service.db.fetch_all("SELECT id FROM assessment_test_attempts") == [], "Publication does not start an attempt or timer"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["off", "memory", "epoch", "policy"])
async def test_actual_nightly_owner_and_context_revocation_stop_provider_wait(connected_nightly, change):
    app, service, transport, nightly, clock = connected_nightly
    stamp = utc_now()
    service.db.execute("INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        ("nightly_connected_memory", "Synthetic general dialysis learning", "synthetic-hash", "learning-point", "T01", "study", 1, "manual", None, stamp, stamp))
    service.db.execute("INSERT INTO memory_history VALUES(?,?,?,?,?)",
        ("nightly_connected_memory", 1, "Synthetic general dialysis learning", "added", stamp))
    transport.release = asyncio.Event()
    identifier = await scheduled(nightly, clock, count=10)
    await provider_started(service, transport, identifier)
    stored = service.db.fetch_one("SELECT inputs_json FROM assessment_test_jobs WHERE id=?", (identifier,))
    assert json.loads(stored["inputs_json"])[0]["kind"] == "memory"
    if change == "off":
        await nightly.update_preferences(PreferencesUpdate(enabled=False, expected_revision=2), "synthetic-connected-nightly-disable")
    else:
        with service.db.transaction() as conn:
            if change == "memory":
                conn.execute("DELETE FROM memory_history WHERE record_id='nightly_connected_memory'")
            elif change == "epoch":
                bump_context_epoch(conn)
            else:
                advance_policy(conn)
        await asyncio.wait_for(service.tasks[identifier], timeout=3)
    result = service.read(identifier)
    assert result["state"] in ("failed", "cancelled") and result["result"] is None
    assert not result["can_retry"] and len(transport.calls) == 1
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
    assert app.state.services.get("provider").status()["active_runs"] == []


@pytest.mark.asyncio
async def test_actual_nightly_guard_rechecks_final_write_and_retains_complete_draft(connected_nightly, monkeypatch):
    _, service, transport, nightly, clock = connected_nightly
    publish = service._publish
    def changed(conn, row, checkpoint, **kwargs):
        # A real write-snapshot mutation at the seam, not a replacement guard.
        conn.execute("UPDATE preferences SET value=json_set(value,'$.enabled',json('false')) WHERE key='nightly.preferences'")
        return publish(conn, row, checkpoint, **kwargs)
    monkeypatch.setattr(service, "_publish", changed)
    identifier = await scheduled(nightly, clock)
    result = await finish(service, identifier)
    assert result["state"] == "failed" and result["validated_count"] == 5
    assert result["error_code"] == "nightly_invalidated"
    assert service.db.fetch_all("SELECT id FROM assessment_tests") == []
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == [] and len(transport.calls) == 1


@pytest.mark.asyncio
async def test_actual_nightly_published_replay_old_token_and_neutral_stop_winner(connected_nightly):
    _, service, transport, nightly, clock = connected_nightly
    identifier = await scheduled(nightly, clock)
    result = await finish(service, identifier)
    checkpoint = json.loads(service.db.fetch_one("SELECT checkpoint_json FROM assessment_test_jobs WHERE id=?", (identifier,))["checkpoint_json"])
    intent = CreateGenerationRequest.model_validate(checkpoint["request"])
    await nightly.update_preferences(PreferencesUpdate(enabled=False, expected_revision=2), "synthetic-published-nightly-off")
    assert await service.create_nightly(intent, schedule=checkpoint["nightly"]) == result
    assert await nightly.cancel(identifier, "synthetic-published-nightly-stop") == {"id": identifier, "state": "published"}
    stamp = utc_now()
    service.db.execute("INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
        "VALUES('synthetic-active-test','synthetic-version','{}','test',?,?,?)", (stamp, stamp, stamp))
    with pytest.raises(ApiError) as error:
        await service.create_nightly(intent, schedule=checkpoint["nightly"])
    assert error.value.code == "assistance_restricted"
    assert await nightly.cancel(identifier, "synthetic-published-test-stop") == {"id": identifier, "state": "published"}
    assert len(transport.calls) == 1
    service.db.execute("DELETE FROM assessment_test_attempts WHERE id='synthetic-active-test'")
    service.db.mark_deleted("job", identifier)
    with pytest.raises(ApiError) as error:
        await service.create_nightly(intent, schedule=checkpoint["nightly"])
    assert error.value.code == "not_found" and len(transport.calls) == 1


@pytest.mark.asyncio
async def test_actual_nightly_reconciliation_preserves_unfinished_local_execution(connected_nightly):
    _, service, transport, nightly, clock = connected_nightly
    transport.release = asyncio.Event()
    identifier = await scheduled(nightly, clock)
    await provider_started(service, transport, identifier)
    with service.db.transaction() as conn:
        assert service.reconcile_nightly(conn) == 0
    assert service.read(identifier)["state"] == "running"
    transport.release.set()
    assert (await finish(service, identifier))["state"] == "published"
    assert len(transport.calls) == 1


@pytest.mark.asyncio
async def test_nightly_orphan_restore_epoch_collision_fails_without_provider_replay(connected_nightly):
    app, service, transport, nightly, clock = connected_nightly
    stamp = utc_now()
    # Source and destination profiles can have different local epoch histories.
    service.db.execute("INSERT INTO preferences VALUES('design_c.context_epoch','5',?)", (stamp,))
    transport.release = asyncio.Event()
    identifier = await scheduled(nightly, clock)
    await provider_started(service, transport, identifier)
    bundle = export_records(app.state.services)
    await service.close()
    service.db.execute("DELETE FROM assessment_test_jobs WHERE id=?", (identifier,))
    service.db.execute("UPDATE preferences SET value='4' WHERE key='design_c.context_epoch'")
    nightly.recover()  # Destination eligibility belongs to its own epoch history.
    app.state.services.get("data_recovery").restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    restored = service.db.fetch_one("SELECT context_epoch FROM assessment_test_jobs WHERE id=?", (identifier,))
    assert restored["context_epoch"] == 5
    assert service.db.fetch_one("SELECT value FROM preferences WHERE key='design_c.context_epoch'")["value"] == "5"
    result = service.read(identifier)
    assert result["state"] == "failed" and result["error_code"] == "interrupted"
    assert len(transport.calls) == 1 and service.tasks == {}
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
