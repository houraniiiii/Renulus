# SPDX-License-Identifier: MIT
"""Real migrations, repositories and ProviderManager with an installed synthetic transport."""
import asyncio
from copy import deepcopy
import json

from fastapi.testclient import TestClient
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
    app.include_router(create_router(app.state.services), prefix="/api/v1")
    services = app.state.services
    service = services.get("saved_generation")
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
