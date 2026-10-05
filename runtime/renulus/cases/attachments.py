# SPDX-License-Identifier: MIT
"""Volatile text/image previews. Engines belong to knowledge; no file writes here."""

import asyncio
import base64
from pathlib import PurePath
from dataclasses import dataclass, field
import math
from time import monotonic
from typing import Any

from renulus.contracts import ApiError, ContextScope, Scope, durable_id

from .images import image_capabilities, require_image_model
from .originals import accepted_original

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_PREVIEW_CHARACTERS = 50000
MAX_EXTRACTIONS = 2
MAX_PREVIEWS = 16
UPLOAD_TIMEOUT_SECONDS = 60
MEDIA = {".pdf": "application/pdf", ".png": "image/png",
         ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


@dataclass
class Preview:
    id: str
    case_id: str
    revision: int
    session: Any
    scope: ContextScope
    filename: str
    title: str
    state: str = "reading"
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    text: str = ""
    ocr: dict = field(default_factory=dict)
    error: dict | None = None
    created: float = field(default_factory=monotonic)
    upload_started: bool = False
    mode: str = 'text'
    image: dict | None = field(default=None, repr=False)
    original: bytes | None = field(default=None, repr=False)


class AttachmentPreviews:
    def __init__(self, repository):
        self.repository = repository
        self.services = repository.services
        self.jobs: dict[str, Preview] = {}
        self.tasks: set[asyncio.Task] = set()
        repository._attachment_invalidator = self.invalidate

    @staticmethod
    def original_capabilities() -> dict:
        from renulus.runtime.inputs import MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS
        return {'supported': True, 'max_bytes': MAX_IMAGE_BYTES,
                'image_pixels': MAX_IMAGE_PIXELS, 'formats': ['.png', '.jpg', '.jpeg'],
                'scope': 'temporary-case'}

    def _capability(self, mode):
        if mode == 'original':
            return self.original_capabilities()
        return image_capabilities(self.services) if mode == 'image' else self.capabilities()

    def capabilities(self) -> dict:
        knowledge = self.services.registry.get("knowledge")
        limits = {}
        try:
            capabilities = knowledge.capabilities() if knowledge else {}
            # Explicit proof is supplied by the engine owner, never inferred from
            # package availability or the durable library import capability.
            safe = capabilities.get("temporary_extraction") is True
            safe = safe and callable(getattr(knowledge, "extract_bytes", None))
            reported = capabilities.get("temporary_limits", {})
            if isinstance(reported, dict):
                for name in ("max_pages", "image_pixels"):
                    value = reported.get(name)
                    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                        limits[name] = value
        except Exception:
            safe = False
        return {"supported": bool(safe), "max_bytes": MAX_ATTACHMENT_BYTES,
                "max_text_characters": MAX_PREVIEW_CHARACTERS, **limits,
                "formats": list(MEDIA), "scope": "temporary-case",
                "code": None if safe else "temporary_extraction_unverified",
                "reason": None if safe else "Verified temporary extraction is not ready in this installation"}

    def _guard(self, job: Preview):
        repository = self.repository
        if job.state == "reading" and monotonic() - job.created >= UPLOAD_TIMEOUT_SECONDS:
            self.cancel(job.id)
        if job.cancel.is_set() or repository._sessions.get(job.case_id) is not job.session:
            raise ApiError("case_extraction_cancelled", "This attachment preview was discarded", 409)
        session = repository._load(job.case_id)
        repository._check_revision(session, job.revision)
        repository._check_idle(session)
        if job.scope != ContextScope(kind=Scope.TEMPORARY_CASE, entity_id=job.case_id):
            raise ApiError("case_scope_mismatch", "Attachment processing must stay temporary", 409)
        if session.saved_revision is not None:
            row = repository.db.fetch_one("SELECT revision FROM case_sessions WHERE id=?", (job.case_id,))
            if row is None or row["revision"] != session.saved_revision:
                raise ApiError("case_revision_conflict", "The saved case changed; reopen it", 409, True)
        return session

    def preflight(self, case_id: str, revision: int, scope: ContextScope,
                  filename: str, title: str, mode: str = 'text') -> Preview:
        with self.repository._lock:
            # An abandoned reservation contains no file bytes and must not keep
            # a worker slot forever when its response was lost.
            for pending in self.jobs.values():
                if pending.state == "reading" and monotonic() - pending.created >= UPLOAD_TIMEOUT_SECONDS:
                    self.cancel(pending.id)
            if scope != ContextScope(kind=Scope.TEMPORARY_CASE, entity_id=case_id):
                raise ApiError("case_scope_mismatch", "Attachment processing must stay temporary", 409)
            session = self.repository._load(case_id)
            self.repository._check_revision(session, revision)
            self.repository._check_idle(session)
            if session.kind != "daily":
                raise ApiError("teaching_case_immutable", "Original teaching cases use their installed material", 409)
            if mode in ('image', 'original') and PurePath(filename).suffix.lower() not in ('.png', '.jpg', '.jpeg'):
                raise ApiError('unsupported_attachment', 'Image discussion accepts PNG or JPEG; PDFs use text extraction', 415)
            capability = self._capability(mode)
            if not capability["supported"]:
                raise ApiError(capability["code"], capability["reason"],
                    403 if capability["code"] == "learning_use_unverified" else 409,
                    capability.get("retryable", False))
            if len(self.tasks) + sum(j.state == "reading" for j in self.jobs.values()) >= MAX_EXTRACTIONS:
                raise ApiError("case_extraction_busy", "Wait for the current extraction to finish", 429, True)
            if len(self.jobs) >= MAX_PREVIEWS:
                old = next((key for key, j in self.jobs.items() if j.state in ("failed", "cancelled", "applied")), None)
                if old is None:
                    raise ApiError("case_preview_capacity", "Discard an attachment preview before adding another", 429)
                del self.jobs[old]
            job = Preview(durable_id("case_extract"), case_id, revision, session,
                          scope.model_copy(deep=True), filename, title, mode=mode)
            self._guard(job)
            self.jobs[job.id] = job
            return job

    def claim_upload(self, job_id: str, case_id: str, revision: int, scope: ContextScope,
                     filename: str, title: str, mode: str = 'text') -> Preview:
        with self.repository._lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise ApiError("case_preview_not_found", "Prepare the attachment again before uploading", 404)
            if (job.case_id, job.revision, job.scope, job.filename, job.title) != (case_id, revision, scope, filename, title):
                raise ApiError("case_scope_mismatch", "The attachment reservation does not match this case", 409)
            if job.mode != mode:
                raise ApiError('case_scope_mismatch', 'The attachment mode changed; prepare it again', 409)
            self._guard(job)
            if job.state != "reading" or job.upload_started:
                raise ApiError("case_upload_already_started", "This attachment upload has already started", 409)
            capability = self._capability(mode)
            if not capability["supported"]:
                self.cancel(job.id)
                raise ApiError(capability["code"], capability["reason"],
                    403 if capability["code"] == "learning_use_unverified" else 409,
                    capability.get("retryable", False))
            job.upload_started = True
            return job

    def start(self, job: Preview, data: bytes) -> dict:
        with self.repository._lock:
            self._guard(job)
            if job.state != "reading":
                raise ApiError("case_upload_already_started", "This attachment upload has already started", 409)
            job.original = data
            if job.mode in ('image', 'original'):
                from renulus.runtime.inputs import validate_inputs
                part = {'type': 'image', 'media_type': MEDIA[PurePath(job.filename).suffix.lower()],
                        'data': base64.b64encode(data).decode('ascii'), 'detail': 'auto'}
                job.image = validate_inputs([{'role': 'user', 'content': [part]}])[0]['content'][0]
                job.state = 'ready'
                return self.view(job.id)
            job.state = "processing"
            task = asyncio.create_task(self._extract(job, data))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return self.view(job.id)

    async def _extract(self, job: Preview, data: bytes):
        try:
            # Native conversion cannot be forcibly interrupted. Cancellation
            # hides the preview immediately; its worker keeps its bounded slot
            # until completion, and the guard rejects all late output.
            knowledge = self.services.registry["knowledge"]
            with self.repository._lock:
                self._guard(job)
                if not self.capabilities()["supported"]:
                    raise ApiError("temporary_extraction_unverified", "Temporary extraction is unavailable", 409)
                filename, title = job.filename, job.title
            result = await asyncio.to_thread(knowledge.extract_bytes, data, filename, title)
            with self.repository._lock:
                self._guard(job)
                status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
                if status != "extracted":
                    raise ApiError("incomplete_extraction", "The attachment could not be read completely", 422)
                passages = result.get("passages") if isinstance(result, dict) else getattr(result, "passages", None)
                if not isinstance(passages, list) or len(passages) > 1000:
                    raise ApiError("invalid_extraction", "The attachment did not return a usable text preview", 422)
                text = "\n\n".join(p["text"] for p in passages if isinstance(p, dict) and isinstance(p.get("text"), str))
                if not text.strip():
                    raise ApiError("empty_extraction", "No readable text was found in this attachment", 422)
                if len(text) > MAX_PREVIEW_CHARACTERS:
                    raise ApiError("case_preview_limit", "The extracted text exceeds 50,000 characters; choose fewer pages", 413)
                ocr = result.get("ocr", {}) if isinstance(result, dict) else getattr(result, "ocr", {})
                confidence = ocr.get("confidence") if isinstance(ocr, dict) else None
                if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    confidence = None
                job.text = text
                job.ocr = {"confidence": confidence, "used": ocr.get("used") if isinstance(ocr, dict) and isinstance(ocr.get("used"), bool) else None}
                job.state = "ready"
        except asyncio.CancelledError:
            self.cancel(job.id)
            raise
        except Exception as error:
            with self.repository._lock:
                if job.cancel.is_set():
                    self._clear(job)
                    return
                self._clear(job)
                job.state = "failed"
                # Engine messages/paths can contain raw input. Keep only a fixed
                # recovery message and a known product code; never stringify it.
                code = error.code if isinstance(error, ApiError) and error.code in {
                    "empty_extraction", "case_preview_limit", "invalid_extraction", "incomplete_extraction",
                    "case_revision_conflict", "case_deleted", "extraction_failed",
                    "helper_assets_missing", "helper_package_unavailable"} else "case_extraction_failed"
                job.error = {"code": code, "message": "The attachment could not be read. Check the file and offline helpers, then try again.", "retryable": True}
        finally:
            data = b""

    @staticmethod
    def _clear(job: Preview):
        job.text = ""
        job.image = None
        job.original = None
        job.ocr = {}
        job.filename = ""
        job.title = ""
        job.session = None

    def invalidate(self, case_id: str):
        for job in self.jobs.values():
            if job.case_id == case_id:
                self.cancel(job.id)

    def cancel(self, job_id: str) -> dict:
        with self.repository._lock:
            job = self.jobs.get(job_id)
            if job:
                job.cancel.set()
                self._clear(job)
                job.error = None
                if job.state != "applied":
                    job.state = "cancelled"
            return {"id": job_id, "state": "cancelled"}

    def view(self, job_id: str) -> dict:
        with self.repository._lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise ApiError("case_preview_not_found", "The attachment preview is no longer available", 404)
            if job.state not in ("cancelled", "failed", "applied"):
                try:
                    self._guard(job)
                except ApiError:
                    self.cancel(job.id)
            return {"id": job.id, "case_id": job.case_id, "revision": job.revision,
                    "scope": job.scope.model_dump(mode="json"), "state": job.state,
                    "filename": job.filename, "title": job.title, "text": job.text,
                    "ocr": dict(job.ocr), "error": job.error, 'mode': job.mode,
                    'image': dict(job.image) if job.image else None, 'image_retained': False}

    def apply(self, job_id: str, revision: int, reviewed_text: str) -> dict:
        with self.repository._lock:
            job = self.jobs.get(job_id)
            if job is None or job.state != "ready":
                raise ApiError("case_preview_not_ready", "Extract and review the attachment before using its text", 409)
            if job.mode != 'text':
                raise ApiError('case_preview_not_ready', 'Images must be explicitly sent for image discussion', 409)
            session = self._guard(job)
            self.repository._check_revision(session, revision)
            merged = session.text + "\n\nReviewed attachment text:\n" + reviewed_text.strip()
            if not reviewed_text.strip() or len(merged) > MAX_PREVIEW_CHARACTERS:
                raise ApiError("case_text_limit", "Keep the combined case text within 50,000 characters", 413)
            attachment = self._original(job)
            result = self.repository.attach(job.case_id, revision, attachment, text=merged)
            job.state = "applied"
            return result

    @staticmethod
    def _original(job: Preview):
        return accepted_original(job.filename, job.title, MEDIA[PurePath(job.filename).suffix.lower()], job.original)

    def keep(self, job_id: str, revision: int) -> dict:
        with self.repository._lock:
            job = self.jobs.get(job_id)
            if job is None or job.state != 'ready' or job.mode not in ('image', 'original'):
                raise ApiError('case_preview_not_ready', 'Review an image before keeping its original', 409)
            session = self._guard(job)
            self.repository._check_revision(session, revision)
            result = self.repository.attach(job.case_id, revision, self._original(job))
            job.state = 'applied'
            return result

    def discuss_image(self, job_id, request):
        from .models import DiscussCase
        with self.repository._lock:
            job = self.jobs.get(job_id)
            if job is None or job.state != 'ready' or job.mode != 'image' or not job.image:
                raise ApiError('case_preview_not_ready', 'Review an image before explicitly sending it', 409)
            session = self._guard(job)
            self.repository._check_revision(session, request.revision)
            require_image_model(self.services, request.model)
            image = dict(job.image)
            attachment = self._original(job)
            message = request.message + '\n[Image input requested. The original stays temporary until you explicitly save this case.]'
            run, messages = self.repository.begin_discussion(job.case_id, DiscussCase(
                revision=request.revision, message=message, request_id=request.request_id), attachment=attachment)
            run.mode, run.model = 'image', request.model
            messages[-1]['content'] = [{'type': 'text', 'text': request.message}, image]
            self.cancel(job.id)
            return run, messages
