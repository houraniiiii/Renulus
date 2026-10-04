"""Synthetic application-rule checks; extractor fixtures never establish engine safety."""

import asyncio
import json
from threading import Event

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from renulus.cases.api import create_router
from renulus.cases.attachments import AttachmentPreviews, MAX_ATTACHMENT_BYTES, UPLOAD_TIMEOUT_SECONDS
from renulus.cases.models import DiscussCase, EditCase, HandoffCase, StartCase
from renulus.cases.repository import CaseRepository
from renulus.cases.streaming import discuss
from renulus.contracts import ApiError, ContextScope, Scope
from renulus.server import create_app

from .conftest import SENTINEL, ProviderFixture, assert_absent_from_profile, assert_terminals

ATTACHMENT_SENTINEL = "RENULUS_SYNTHETIC_ATTACHMENT_F54A71_NEVER_AUTOSAVE"
RAW = b"%PDF-1.7\n" + ATTACHMENT_SENTINEL.encode()


class ExtractorFixture:
    def __init__(self, *, safe=True, blocked=False, error=None, status="extracted"):
        self.safe, self.blocked, self.error = safe, blocked, error
        self.status = status
        self.calls = []
        self.started, self.release = Event(), Event()

    def capabilities(self):
        return {"temporary_extraction": self.safe, "pdf_image_import": True,
                "temporary_limits": {"max_bytes": MAX_ATTACHMENT_BYTES, "max_pages": 20,
                                     "image_pixels": 12000000}}

    def extract_bytes(self, data, filename, title):
        self.calls.append((data, filename, title))
        self.started.set()
        if self.blocked:
            assert self.release.wait(5)
        if self.error:
            raise self.error
        return {"passages": [{"text": ATTACHMENT_SENTINEL}], "document": {}, "status": self.status,
                "ocr": {"confidence": 0.65, "used": True}}


def scope(case):
    return ContextScope(kind=Scope.TEMPORARY_CASE, entity_id=case["id"])


async def finish(previews):
    await asyncio.gather(*list(previews.tasks))


async def test_preview_apply_save_and_delete_have_separate_retention_boundaries(repository, services):
    case = repository.start(StartCase(text=SENTINEL))
    services.registry["knowledge"] = ExtractorFixture()
    previews = AttachmentPreviews(repository)
    job = previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Synthetic attachment")
    started = previews.start(job, RAW)
    assert started["state"] == "processing"
    await finish(previews)
    preview = previews.view(job.id)
    assert preview["state"] == "ready" and preview["text"] == ATTACHMENT_SENTINEL
    assert preview["ocr"] == {"confidence": 0.65, "used": True}
    assert repository.get(case["id"])["text"] == SENTINEL
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL, SENTINEL)
    reviewed = preview["text"] + "\nA reviewed synthetic note"
    live = previews.apply(job.id, 1, reviewed)
    assert reviewed in live["text"] and live["dirty"] and not live["saved"]
    assert previews.view(job.id)["state"] == "applied"
    assert previews.view(job.id)["text"] == ""
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL, SENTINEL)
    repository.save(case["id"], live["revision"])
    assert reviewed in CaseRepository(services).get(case["id"])["text"]
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    repository.delete(case["id"], live["revision"])
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL, SENTINEL)


@pytest.mark.parametrize("mutation", ["cancel", "edit", "save", "close", "delete"])
async def test_late_extraction_cannot_publish_after_scope_or_session_change(repository, services, mutation):
    case = repository.start(StartCase(text="Synthetic case description"))
    extractor = ExtractorFixture(blocked=True)
    services.registry["knowledge"] = extractor
    previews = AttachmentPreviews(repository)
    job = previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
    previews.start(job, RAW)
    assert await asyncio.to_thread(extractor.started.wait, 1)
    if mutation == "cancel":
        previews.cancel(job.id)
    elif mutation == "edit":
        repository.edit(case["id"], EditCase(revision=1, title="Changed"))
    elif mutation == "save":
        repository.save(case["id"], 1)
    elif mutation == "close":
        repository.close(case["id"], 1)
    else:
        repository.delete(case["id"], 1)
    extractor.release.set()
    await finish(previews)
    result = previews.view(job.id)
    assert result["state"] == "cancelled"
    assert result["text"] == result["filename"] == ""
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


async def test_saved_case_canonical_change_rejects_extraction_preview(repository, services):
    case = repository.start(StartCase(text="Synthetic saved case"))
    repository.save(case["id"], 1)
    extractor = ExtractorFixture(blocked=True)
    services.registry["knowledge"] = extractor
    previews = AttachmentPreviews(repository)
    job = previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
    previews.start(job, RAW)
    assert await asyncio.to_thread(extractor.started.wait, 1)
    other = CaseRepository(services)
    edited = other.edit(case["id"], EditCase(revision=1, title="Updated"))
    other.save(case["id"], edited["revision"])
    extractor.release.set()
    await finish(previews)
    result = previews.view(job.id)
    assert result["state"] == "failed" and result["text"] == ""
    assert result["error"]["code"] == "case_revision_conflict"
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


async def test_engine_exception_never_exposes_or_logs_attachment_text(repository, services, caplog):
    case = repository.start(StartCase(text="Synthetic case"))
    services.registry["knowledge"] = ExtractorFixture(error=RuntimeError(ATTACHMENT_SENTINEL))
    previews = AttachmentPreviews(repository)
    job = previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
    previews.start(job, RAW)
    await finish(previews)
    assert previews.view(job.id)["state"] == "failed"
    assert ATTACHMENT_SENTINEL not in json.dumps(previews.view(job.id))
    assert ATTACHMENT_SENTINEL not in caplog.text
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


async def test_partial_engine_result_cannot_offer_case_text(repository, services):
    case = repository.start(StartCase(text="Synthetic case"))
    services.registry["knowledge"] = ExtractorFixture(status="partial")
    previews = AttachmentPreviews(repository)
    job = previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
    previews.start(job, RAW)
    await finish(previews)
    preview = previews.view(job.id)
    assert preview["state"] == "failed" and not preview["text"]
    assert preview["error"]["code"] == "incomplete_extraction"
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


@pytest.mark.parametrize("safe", [False, 1, "true", None])
def test_only_literal_producer_proof_enables_extraction(repository, services, safe):
    services.registry["knowledge"] = ExtractorFixture(safe=safe)
    capabilities = AttachmentPreviews(repository).capabilities()
    assert capabilities["supported"] is False
    assert capabilities["max_pages"] == 20 and capabilities["image_pixels"] == 12000000


async def test_cancelled_native_workers_keep_their_slots_until_they_finish(repository, services):
    case = repository.start(StartCase(text="Synthetic case"))
    extractor = ExtractorFixture(blocked=True)
    services.registry["knowledge"] = extractor
    previews = AttachmentPreviews(repository)
    try:
        jobs = []
        for _ in range(2):
            job = previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
            previews.start(job, RAW)
            jobs.append(job)
        assert await asyncio.to_thread(extractor.started.wait, 1)
        for job in jobs:
            previews.cancel(job.id)
        with pytest.raises(ApiError) as error:
            previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
        assert error.value.code == "case_extraction_busy"
    finally:
        extractor.release.set()
        await finish(previews)
    assert all(previews.view(job.id)["state"] == "cancelled" for job in jobs)
    assert previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment").state == "reading"
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


async def test_extracted_case_discussion_error_and_handoff_never_create_durable_evidence(repository, services, caplog):
    case = repository.start(StartCase(text="Synthetic question"))
    services.registry["knowledge"] = ExtractorFixture()
    previews = AttachmentPreviews(repository)
    job = previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
    previews.start(job, RAW)
    await finish(previews)
    case = previews.apply(job.id, 1, previews.view(job.id)["text"])
    services.registry["provider"] = ProviderFixture(error=RuntimeError(ATTACHMENT_SENTINEL))
    run, messages = repository.begin_discussion(case["id"], DiscussCase(
        revision=case["revision"], request_id="attachment-discuss", message="Explain the extracted case text"))
    events = [event async for event in discuss(repository, run, messages)]
    assert_terminals(events, "failed")
    assert ATTACHMENT_SENTINEL not in events[-1].model_dump_json()
    assert ATTACHMENT_SENTINEL not in caplog.text
    current = repository.get(case["id"])
    ticket = repository.handoff(case["id"], HandoffCase(
        revision=current["revision"], target="explain", question="Explore the extracted question"))
    context = repository.resolve_handoff(ticket["id"], "explain")
    assert ATTACHMENT_SENTINEL in ticket["case_text"]
    assert context["scope"].kind == Scope.TEMPORARY_CASE
    completed = repository.commit_handoff(ticket["id"], "explain", "Synthetic educational discussion",
        cancel=context["cancel"], scope=context["scope"])
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    repository.save(case["id"], completed["revision"])
    assert ATTACHMENT_SENTINEL in CaseRepository(services).get(case["id"])["text"]
    repository.delete(case["id"], completed["revision"])
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


@pytest.mark.parametrize("condition", ["scope", "capability", "revision", "name", "length", "multipart"])
async def test_raw_route_rejects_unapproved_inputs_before_reading_body(services, condition):
    router = create_router(services)
    repository = services.registry["cases"]
    case = repository.start(StartCase(text="Synthetic case"))
    services.registry["knowledge"] = ExtractorFixture(safe=condition != "capability")
    options = {"revision": 99 if condition == "revision" else 1,
               "scope": {"kind": "study" if condition == "scope" else "temporary-case", "entity_id": case["id"]}}
    headers = {"x-renulus-case-options": json.dumps(options),
               "x-renulus-filename": "../synthetic.pdf" if condition == "name" else "synthetic.pdf",
               "content-type": "multipart/form-data" if condition == "multipart" else "application/pdf"}
    if condition == "length":
        headers["content-length"] = str(MAX_ATTACHMENT_BYTES + 1)
    reads = []
    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": RAW, "more_body": False}
    request = Request({"type": "http", "method": "POST", "path": "/",
                       "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}, receive)
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/attachments/extract"))
    with pytest.raises(ApiError):
        await endpoint(case["id"], request)
    assert reads == []
    assert services.registry["knowledge"].calls == []
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


async def test_actual_stream_limit_is_checked_even_without_content_length(services):
    router = create_router(services)
    repository = services.registry["cases"]
    case = repository.start(StartCase(text="Synthetic case"))
    services.registry["knowledge"] = ExtractorFixture()
    headers = {"x-renulus-case-options": json.dumps({"revision": 1, "scope": scope(case).model_dump(mode="json")}),
               "x-renulus-filename": "synthetic.pdf", "content-type": "application/pdf"}
    async def receive():
        return {"type": "http.request", "body": b"X" * (MAX_ATTACHMENT_BYTES + 1), "more_body": False}
    request = Request({"type": "http", "method": "POST", "path": "/",
                       "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}, receive)
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/attachments/extract"))
    with pytest.raises(ApiError) as error:
        await endpoint(case["id"], request)
    assert error.value.code == "case_attachment_limit"
    assert services.registry["knowledge"].calls == []


@pytest.mark.parametrize("condition", ["cancel", "duplicate", "case", "expired", "capability"])
async def test_reserved_upload_is_guarded_before_any_file_bytes(services, condition):
    router = create_router(services)
    repository = services.registry["cases"]
    case = repository.start(StartCase(text="Synthetic case"))
    services.registry["knowledge"] = ExtractorFixture()
    headers = {"x-renulus-case-options": json.dumps({"revision": 1, "scope": scope(case).model_dump(mode="json")}),
               "x-renulus-filename": "synthetic.pdf", "content-type": "application/pdf"}
    reads = []
    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": RAW, "more_body": False}
    def request():
        return Request({"type": "http", "method": "POST", "path": "/",
                        "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}, receive)
    prepare = next(route.endpoint for route in router.routes if route.path.endswith("/attachments/prepare"))
    reserved = await prepare(case["id"], request())
    assert reserved["state"] == "reading" and reads == []
    headers["x-renulus-preview-id"] = reserved["id"]
    previews = services.registry["case_previews"]
    if condition == "cancel":
        previews.cancel(reserved["id"])
    elif condition == "duplicate":
        previews.claim_upload(reserved["id"], case["id"], 1, scope(case), "synthetic.pdf", "Attachment")
    elif condition == "case":
        case = repository.start(StartCase(text="Another synthetic case"))
        headers["x-renulus-case-options"] = json.dumps({"revision": 1, "scope": scope(case).model_dump(mode="json")})
    elif condition == "expired":
        previews.jobs[reserved["id"]].created -= UPLOAD_TIMEOUT_SECONDS + 1
    else:
        services.registry["knowledge"].safe = False
    extract = next(route.endpoint for route in router.routes if route.path.endswith("/attachments/extract"))
    with pytest.raises(ApiError):
        await extract(case["id"], request())
    assert reads == [] and services.registry["knowledge"].calls == []
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


def test_lost_reservation_response_expires_without_holding_capacity(repository, services):
    case = repository.start(StartCase(text="Synthetic case"))
    services.registry["knowledge"] = ExtractorFixture()
    previews = AttachmentPreviews(repository)
    pending = [previews.preflight(case["id"], 1, scope(case), "synthetic.pdf", "Attachment") for _ in range(2)]
    for job in pending:
        job.created -= UPLOAD_TIMEOUT_SECONDS + 1
    replacement = previews.preflight(case["id"], 1, scope(case), "replacement.pdf", "Attachment")
    assert replacement.state == "reading"
    assert all(job.state == "cancelled" and job.session is None and not job.filename for job in pending)
    assert not previews.tasks and services.registry["knowledge"].calls == []
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


@pytest.mark.parametrize("interruption", ["disconnect", "edit"])
async def test_partial_upload_is_cleared_after_disconnect_or_case_change(services, interruption):
    router = create_router(services)
    repository = services.registry["cases"]
    case = repository.start(StartCase(text="Synthetic case"))
    services.registry["knowledge"] = ExtractorFixture()
    headers = {"x-renulus-case-options": json.dumps({"revision": 1, "scope": scope(case).model_dump(mode="json")}),
               "x-renulus-filename": "synthetic.pdf", "content-type": "application/pdf"}
    reads = []
    async def receive():
        reads.append(True)
        if len(reads) == 1:
            return {"type": "http.request", "body": RAW, "more_body": True}
        if interruption == "disconnect":
            return {"type": "http.disconnect"}
        repository.edit(case["id"], EditCase(revision=1, title="Changed"))
        return {"type": "http.request", "body": b"more synthetic bytes", "more_body": False}
    request = Request({"type": "http", "method": "POST", "path": "/",
                       "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}, receive)
    endpoint = next(route.endpoint for route in router.routes if route.path.endswith("/attachments/extract"))
    with pytest.raises(ApiError) as error:
        await endpoint(case["id"], request)
    assert error.value.code in ("attachment_upload_interrupted", "case_extraction_cancelled")
    previews = services.registry["case_previews"]
    assert all(job.state == "cancelled" and job.session is None and not job.filename for job in previews.jobs.values())
    assert not previews.tasks and not services.registry["knowledge"].calls
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)


def test_raw_upload_returns_volatile_job_and_disabled_image_interpretation(tmp_path):
    app = create_app(tmp_path / "attachments-api")
    services = app.state.services
    services.registry["knowledge"] = ExtractorFixture()
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic case"}).json()
        caps = client.get("/api/v1/cases/capabilities").json()
        assert caps["inputs"]["pdf"]["supported"]
        assert caps["extraction"]["max_pages"] == 20 and caps["extraction"]["image_pixels"] == 12000000
        assert not caps["image_interpretation"]["supported"]
        legacy = client.post(f"/api/v1/cases/sessions/{case['id']}/attachments", json={"revision": 1, "kind": "pdf"})
        assert legacy.json()["error"]["code"] == "raw_attachment_required"
        result = client.post(f"/api/v1/cases/sessions/{case['id']}/attachments/extract", content=RAW,
            headers={"content-type": "application/pdf", "x-renulus-filename": "synthetic.pdf",
                     "x-renulus-case-options": json.dumps({"revision": 1, "scope": scope(case).model_dump(mode="json")})})
        assert result.status_code == 202 and result.headers["cache-control"] == "no-store"
        job = result.json()
        assert job["scope"]["kind"] == "temporary-case"
        assert client.delete(f"/api/v1/cases/attachments/{job['id']}").json()["state"] == "cancelled"
    assert_absent_from_profile(services, ATTACHMENT_SENTINEL)
