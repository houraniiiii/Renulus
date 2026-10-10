# SPDX-License-Identifier: MIT
"""Actual production migrations, private drafts and ProviderManager transport tests."""
import asyncio
from copy import deepcopy
import hashlib
import json

from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
import pytest

from renulus.assessment.contracts import Command
from renulus.assessment.attempt_models import StartAttempt, SubmitAttempt
from renulus.assessment.import_api import create_router
from renulus.assessment.import_models import (CandidateVisibilityRequest, CreateImportRequest,
    EditImportCandidateRequest, ImportRevisionCommand, ResolveImportCandidateRequest)
from renulus.assessment.import_service import MAX_CALLS, SavedImportService, parse_original
from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage import utc_now
from renulus.storage.backup import export_records, restore_records
from renulus.storage.invalidation import bump_context_epoch

TEXT = "  1. Which synthetic CKD learning interpretation is supplied?\nA. First interpretation\nB. Second interpretation\nAnswer: A\n\n2. Which dialysis learning option is supported?\nA. First dialysis option\nB. Second dialysis option\n  "


def request(key="synthetic-import-create", text=TEXT):
    return CreateImportRequest(idempotency_key=key, title="Private CKD and dialysis practice",
        original={"kind": "paste", "text": text, "terms": "Synthetic private fixture, retained user terms", "permission_confirmed": True})


def command(row, key):
    return ImportRevisionCommand(idempotency_key=key, expected_revision=row["revision"])


def normalized(text=TEXT):
    return {"candidates": [{"span": item["original"]["span"], "stem_span": item["original"]["stem_span"],
        "stem": item["stem"].upper(),
        "options": [{**option, "span": item["original"]["options"][index]["span"]} for index, option in enumerate(item["options"])],
        "explanation": "", "explanation_span": None} for item in parse_original(text)]}


class SyntheticTransport:
    """The provider manager/selected route is real; only its remote endpoint is synthetic."""
    def __init__(self):
        self.calls, self.responses = [], []
        self.started = asyncio.Event()
        self.release = None
        self.error = None

    async def stream(self, provider, model, token, messages):
        assert token == "synthetic-import-token"
        index = len(self.calls)
        self.calls.append((provider, model, deepcopy(messages)))
        self.started.set()
        if self.release:
            await self.release.wait()
        if self.error:
            raise self.error
        value = self.responses[index] if index < len(self.responses) else normalized()
        yield {"type": "delta", "text": value if isinstance(value, str) else json.dumps(value)}
        yield {"type": "completed", "response_model": model}


@pytest.fixture
def imports(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "learn", "cases", "assessment", "memory", "study"))
    app = create_app(tmp_path / "synthetic-import")
    services = app.state.services
    if "saved_imports" not in services.registry:
        app.include_router(create_router(services), prefix="/api/v1")
    service = services.get("saved_imports")
    owners = {id(getattr(callback, "__self__", None)) for callback in services.on_startup
              if isinstance(getattr(callback, "__self__", None), SavedImportService)}
    assert owners == {id(service)}
    provider = services.get("provider")
    provider._settings["connections"]["codex"] = {"access_token": "synthetic-import-token", "expires_at": 9999999999}
    provider._settings["selected_provider"] = "codex"
    provider._settings.setdefault("selected_models", {})["codex"] = "gpt-6.1-sol"
    transport = SyntheticTransport()
    provider._transport = transport
    services.on_startup = [services.get("saved_tests").backfill_legacy, service.recover]
    services.on_shutdown = [provider.close, service.close]
    return app, service, transport


async def finish(service, identifier):
    task = service.tasks.get(identifier)
    if task:
        await task
    return service.read(identifier)


def resolve_all(service, row):
    for index, item in enumerate(row["candidates"]):
        if not item["removed"]:
            row = service.mutate_candidate(row["id"], item["id"], "resolve", ResolveImportCandidateRequest(
                idempotency_key=f'{row["id"]}:resolve-{index}', expected_revision=row["revision"],
                correct_option_ids=("a",), review_confirmed=True))
    return row


def test_parser_preserves_missing_ambiguous_and_explicit_original_keys():
    values = parse_original(TEXT)
    assert len(values) == 2
    assert values[0]["key_state"] == "supplied" and values[0]["correct_option_ids"] == ["a"]
    assert values[1]["key_state"] == "missing" and values[1]["correct_option_ids"] == []
    assert not any(item["review_confirmed"] for item in values)
    for item in values:
        for option, original in zip(item["options"], item["original"]["options"]):
            span = original["span"]
            assert TEXT[span["start"]:span["end"]] == option["text"]
    conflict = parse_original(TEXT.replace("Answer: A", "Answer: A\nKey: B"))
    assert conflict[0]["key_state"] == "ambiguous" and conflict[0]["correct_option_ids"] == []


def test_parser_request_keeps_exact_private_whitespace_and_requires_permission():
    assert request().original.text == TEXT
    invalid = request().model_dump()
    invalid["original"]["permission_confirmed"] = False
    with pytest.raises(ValidationError):
        CreateImportRequest.model_validate(invalid)


def test_actual_create_edit_resolve_explicit_save_and_lost_ack(imports):
    app, service, transport = imports
    row = service.create(request())
    assert row["state"] == "draft" and row["candidate_count"] == 2
    assert service.original(row["id"])["text"] == TEXT
    assert service.original(row["id"])["sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert service.create(request()) == row
    with pytest.raises(ApiError) as error:
        service.save(row["id"], command(row, "synthetic-unresolved-save"))
    assert error.value.code == "import_needs_review"
    item = row["candidates"][0]
    edit = EditImportCandidateRequest(idempotency_key="synthetic-edit-first", expected_revision=row["revision"],
        stem="Personal edit for transplantation learning", options=item["options"], explanation="A personal explanation")
    row = service.mutate_candidate(row["id"], item["id"], "edit", edit)
    assert service.mutate_candidate(row["id"], item["id"], "edit", edit) == row
    assert row["candidates"][0]["original"] == item["original"]
    row = resolve_all(service, row)
    save = command(row, "synthetic-import-save")
    result = service.save(row["id"], save)
    assert result["state"] == "published" and service.save(row["id"], save) == result
    assert len(service.db.fetch_all("SELECT id FROM assessment_test_versions")) == 1
    assert len(transport.calls) == 0
    with service.db.transaction() as conn:
        version = app.state.services.get("saved_tests").pinned_version(conn, result["result"]["version_id"])
    assert version.origin == "imported" and version.review_quality == "personal" and version.status == "ready"
    assert not version.bank_cohort_eligible and version.item_count == 2
    assert version.items[0].stem == edit.stem
    assert app.state.services.get("saved_tests").setup_version(version.id)["version"]["item_count"] == 2


@pytest.mark.asyncio
async def test_actual_selected_provider_normalization_is_explicit_and_never_resolves(imports):
    _, service, transport = imports
    row = service.create(request())
    intent = command(row, "synthetic-normalize")
    start = await service.normalize(row["id"], intent)
    assert start["state"] == "running"
    await service.normalize(row["id"], intent)
    result = await finish(service, row["id"])
    assert result["state"] == "draft" and result["call_count"] == 1
    assert all(not candidate["review_confirmed"] for candidate in result["candidates"])
    assert result["candidates"][1]["correct_option_ids"] == []
    assert transport.calls[0][:2] == ("codex", "gpt-6.1-sol")
    assert len(transport.calls) == 1
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []
    assert service.original(row["id"])["text"] == TEXT


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["invented_key", "invented_review", "invented_option", "bad_span", "duplicate", "duplicate_json", "json"])
async def test_invalid_normalization_retains_original_edits_and_bounded_retry(imports, failure):
    _, service, transport = imports
    row = service.create(request())
    item = row["candidates"][0]
    row = service.mutate_candidate(row["id"], item["id"], "edit", EditImportCandidateRequest(
        idempotency_key="synthetic-preserved-edit", expected_revision=row["revision"], stem="Retained private personal edit", options=item["options"]))
    original_candidates = deepcopy(row["candidates"])
    value = normalized()
    if failure == "invented_key":
        value["candidates"][1]["correct_option_ids"] = ["a"]
    elif failure == "invented_review":
        value["candidates"][0]["review_quality"] = "reviewed"
    elif failure == "invented_option":
        value["candidates"][0]["options"][0]["text"] = "Unsupported invented answer"
    elif failure == "bad_span":
        value["candidates"][0]["options"][0]["span"]["end"] = 999999
    elif failure == "duplicate":
        value["candidates"].append(deepcopy(value["candidates"][0]))
    elif failure == "duplicate_json":
        value = '{"candidates":[],"candidates":[]}'
    elif failure == "json":
        value = "not JSON"
    transport.responses = [value] * MAX_CALLS
    for index in range(MAX_CALLS):
        await service.normalize(row["id"], command(row, f"synthetic-failure-{index}"), retry=index > 0)
        row = await finish(service, row["id"])
        assert row["state"] == "failed" and row["error_code"] == "import_invalid_output"
        assert row["candidates"] == original_candidates
        assert service.original(row["id"])["text"] == TEXT
    with pytest.raises(ApiError) as error:
        await service.normalize(row["id"], command(row, "synthetic-budget-final"), retry=True)
    assert error.value.code == "import_budget_exhausted" and len(transport.calls) == MAX_CALLS


@pytest.mark.asyncio
async def test_late_normalization_cannot_overwrite_actual_edit(imports):
    _, service, transport = imports
    transport.release = asyncio.Event()
    row = service.create(request())
    await service.normalize(row["id"], command(row, "synthetic-running-edit"))
    await transport.started.wait()
    row = service.read(row["id"])
    item = row["candidates"][0]
    edited = service.mutate_candidate(row["id"], item["id"], "edit", EditImportCandidateRequest(
        idempotency_key="synthetic-midrun-edit", expected_revision=row["revision"], stem="Newest glomerular learning edit", options=item["options"]))
    transport.release.set()
    result = await finish(service, row["id"])
    assert result["state"] == "failed" and result["error_code"] == "import_edits_changed"
    assert result["candidates"] == edited["candidates"]


@pytest.mark.asyncio
async def test_remove_and_resolve_survive_explicit_normalization(imports):
    _, service, _ = imports
    row = service.create(request())
    item = row["candidates"][1]
    row = service.mutate_candidate(row["id"], item["id"], "visibility", CandidateVisibilityRequest(
        idempotency_key="synthetic-remove", expected_revision=row["revision"], removed=True))
    row = resolve_all(service, row)
    before = deepcopy(row["candidates"])
    await service.normalize(row["id"], command(row, "synthetic-protected-normalize"))
    result = await finish(service, row["id"])
    assert result["candidates"] == before
    saved = service.save(row["id"], command(result, "synthetic-removed-save"))
    assert service.db.fetch_one("SELECT items_json FROM assessment_test_versions WHERE id=?", (saved["result"]["version_id"],))["items_json"].count('"item_id"') == 1


@pytest.mark.asyncio
async def test_neutral_cancel_during_denied_policy_stops_real_transport(imports):
    app, service, transport = imports
    reviewed = resolve_all(service, service.create(request("synthetic-policy-published")))
    version = service.save(reviewed["id"], command(reviewed, "synthetic-policy-publish"))["result"]
    transport.release = asyncio.Event()
    row = service.create(request())
    await service.normalize(row["id"], command(row, "synthetic-cancel-run"))
    await transport.started.wait()
    attempts = app.state.services.get("whole_attempts")
    attempt = attempts.start(StartAttempt(version={"type": "saved_test_version", "id": version["version_id"]}, mode="test"), "synthetic-import-active-test")
    cancel = Command(idempotency_key="synthetic-neutral-cancel")
    result = await service.cancel(row["id"], cancel)
    assert result == {"id": row["id"], "state": "cancelled"}
    assert await service.cancel(row["id"], cancel) == result
    assert len(transport.calls) == 1
    with pytest.raises(ApiError) as error:
        service.read(row["id"])
    assert error.value.code == "assistance_restricted"
    with pytest.raises(ApiError) as error:
        service.create(request())
    assert error.value.code == "assistance_restricted"
    attempts.submit(attempt["id"], SubmitAttempt(expected_draft_revision=attempt["draft_revision"]), "synthetic-policy-submit")
    assert service.original(row["id"])["text"] == TEXT


def test_restart_recovery_preserves_original_and_candidates_without_provider(imports):
    _, service, transport = imports
    row = service.create(request())
    service.db.execute("UPDATE assessment_test_imports SET state='running',call_count=1 WHERE id=?", (row["id"],))
    service.recover()
    result = service.read(row["id"])
    assert result["state"] == "failed" and result["error_code"] == "interrupted"
    assert result["candidates"] == row["candidates"] and result["call_count"] == 1
    assert service.original(row["id"])["text"] == TEXT and transport.calls == []


def test_context_change_prevents_save_until_explicit_review(imports):
    _, service, _ = imports
    row = resolve_all(service, service.create(request()))
    with service.db.transaction() as conn:
        bump_context_epoch(conn)
    with pytest.raises(ApiError) as error:
        service.save(row["id"], command(row, "synthetic-context-save"))
    assert error.value.code == "import_context_changed"
    assert service.db.fetch_all("SELECT id FROM assessment_test_versions") == []


@pytest.mark.asyncio
async def test_actual_mounted_router_create_private_original_and_save(imports):
    app, service, _ = imports
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.post("/api/v1/assessment/imports", json=request().model_dump(mode="json"))
        assert response.status_code == 201, response.text
        row = response.json()
        assert response.headers["Cache-Control"] == "no-store"
        original = await client.get(f'/api/v1/assessment/imports/{row["id"]}/original')
        assert original.json()["text"] == TEXT
        row = resolve_all(service, row)
        body = command(row, "synthetic-http-save").model_dump(mode="json")
        result = await client.post(f'/api/v1/assessment/imports/{row["id"]}/save', json=body)
        assert result.status_code == 200 and result.json()["state"] == "published", result.text
        replay = await client.post(f'/api/v1/assessment/imports/{row["id"]}/save', json=body)
        assert replay.json() == result.json()


def test_actual_json_restore_interrupts_foreign_epoch_collision_and_keeps_edits(imports, tmp_path):
    app, service, transport = imports
    row = service.create(request())
    service.db.execute("UPDATE assessment_test_imports SET state='running',context_epoch=5,call_count=1 WHERE id=?", (row["id"],))
    bundle = export_records(app.state.services)
    destination = create_app(tmp_path / "synthetic-import-restore")
    services = destination.state.services
    if "saved_imports" not in services.registry:
        destination.include_router(create_router(services), prefix="/api/v1")
    services.db.execute("INSERT INTO preferences VALUES('design_c.context_epoch','4',?)", (utc_now(),))
    services.get("data_recovery").restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    stored = services.db.fetch_one("SELECT * FROM assessment_test_imports WHERE id=?", (row["id"],))
    assert stored["state"] == "failed" and stored["error_code"] == "interrupted"
    assert stored["original_text"] == TEXT and json.loads(stored["candidates_json"]) == row["candidates"]
    assert stored["call_count"] == 1
    assert services.db.fetch_one("SELECT value FROM preferences WHERE key='design_c.context_epoch'")["value"] == "5"
    assert services.get("saved_imports").read(row["id"])["state"] == "failed"
    assert transport.calls == []


@pytest.mark.asyncio
async def test_private_import_deletion_tombstone_blocks_restore_and_preserves_saved_version(imports, tmp_path):
    app, service, _ = imports
    row = resolve_all(service, service.create(request()))
    row = service.save(row["id"], command(row, "synthetic-delete-saved"))
    bundle = export_records(app.state.services)
    result = await service.delete(row["id"], command(row, "synthetic-import-delete"))
    assert result == {"id": row["id"], "state": "deleted"}
    assert len(service.db.fetch_all("SELECT id FROM assessment_test_versions")) == 1
    restore_records(app.state.services, bundle, confirm_older=True)
    assert service.db.fetch_all("SELECT id FROM assessment_test_imports") == []
    with pytest.raises(ApiError) as error:
        service.create(request())
    assert error.value.code == "not_found"
    assert app.state.services.get("saved_tests").setup_version(row["result"]["version_id"])["version"]["item_count"] == 2
