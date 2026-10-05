# SPDX-License-Identifier: MIT
"""Cases API; the server mounts this router once under /api/v1."""

import asyncio
import json
from pathlib import PurePath
import sqlite3
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from renulus.contracts import ApiError
from renulus.runtime.inputs import MAX_IMAGE_BYTES

from .attachments import AttachmentPreviews, MEDIA, MAX_ATTACHMENT_BYTES
from .models import (ApplyPreview, AttachmentInput, DiscussCase, EditCase, ExtractionOptions,
                     HandoffCase, ImageDiscussion, RevisionInput, StartCase)
from .images import image_capabilities
from .repository import CaseRepository
from .streaming import cancel_provider, events


def create_router(services) -> APIRouter:
    repository = CaseRepository(services)
    previews = AttachmentPreviews(repository)
    services.registry["cases"] = repository
    services.registry["case_previews"] = previews
    async def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"

    router = APIRouter(prefix="/cases", tags=["cases"], dependencies=[Depends(no_store)])

    @router.get("/capabilities")
    async def capabilities():
        extraction = previews.capabilities()
        return {"inputs": {
            "text": {"supported": True, "max_characters": 50000},
            "image": dict(extraction), "pdf": dict(extraction)},
            "extraction": extraction,
            "image_interpretation": image_capabilities(services),
            "discussion": {"adapter_installed": "provider" in services.registry,
                           "scope": "temporary-case"},
            "teaching": {"content_installed": "content" in services.registry},
            "handoffs": {"explain": "guarded-reference",
                         "generated-practice": "guarded-reference"},
            "memory_capture": False}

    @router.get("/teaching")
    async def teaching():
        return {"cases": repository.list_teaching()}

    @router.get("/saved")
    async def saved():
        return {"cases": repository.list_saved()}

    @router.post("/sessions", status_code=201)
    async def start(body: StartCase):
        return repository.start(body)

    @router.get("/sessions/{case_id}")
    async def get(case_id: str):
        return repository.get(case_id)

    @router.patch("/sessions/{case_id}")
    async def edit(case_id: str, body: EditCase):
        return repository.edit(case_id, body)

    @router.delete("/sessions/{case_id}")
    async def delete(case_id: str, revision: int | None = Query(default=None, ge=1)):
        # Local invalidation precedes the adapter cancellation call.
        active = [run.id for run in repository._runs.values()
                  if run.case_id == case_id and not run.terminal]
        result = repository.delete(case_id, revision)
        for run_id in active:
            await cancel_provider(repository, run_id)
        return result

    @router.post("/sessions/{case_id}/close")
    async def close(case_id: str, body: RevisionInput):
        active = repository.get(case_id)["active_run_id"]
        result = repository.close(case_id, body.revision)
        if active:
            await cancel_provider(repository, active)
        return result

    @router.post("/sessions/{case_id}/save")
    async def save(case_id: str, body: RevisionInput):
        try:
            return repository.save(case_id, body.revision)
        except sqlite3.Error:
            raise ApiError("case_save_failed", "The case could not be saved. Your temporary work is still open",
                           503, True) from None

    @router.post("/sessions/{case_id}/reveal")
    async def reveal(case_id: str, body: RevisionInput):
        return repository.reveal(case_id, body.revision)

    @router.get('/sessions/{case_id}/attachments/{attachment_id}/original')
    async def original(case_id: str, attachment_id: str):
        metadata, data = repository.original(case_id, attachment_id)
        return Response(data, media_type=metadata['media_type'], headers={
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': "inline; filename*=UTF-8''" + quote(metadata['filename'], safe=''),
            'X-Renulus-SHA256': metadata['sha256']})

    @router.delete('/sessions/{case_id}/attachments/{attachment_id}')
    async def remove_original(case_id: str, attachment_id: str, revision: int = Query(ge=1)):
        return repository.remove_attachment(case_id, attachment_id, revision)

    @router.post("/sessions/{case_id}/handoff", status_code=201)
    async def handoff(case_id: str, body: HandoffCase):
        return repository.handoff(case_id, body)

    @router.delete("/handoffs/{ticket_id}")
    async def cancel_handoff(ticket_id: str):
        return repository.cancel_handoff(ticket_id)

    @router.post("/sessions/{case_id}/attachments")
    async def attachment(case_id: str, body: AttachmentInput):
        current = repository.get(case_id)
        if current["revision"] != body.revision:
            raise ApiError("case_revision_conflict", "Reload the current case and try again", 409, True)
        if previews.capabilities()["supported"]:
            raise ApiError("raw_attachment_required", "Select the file using the temporary text extraction route", 409)
        raise ApiError(f"volatile_{body.kind}_unavailable",
                       f"A verified in-memory {body.kind.upper()} route is not installed", 409)

    def attachment_headers(request: Request):
        options = request.headers.get("x-renulus-case-options", "")
        filename_header = request.headers.get("x-renulus-filename", "")
        try:
            if len(options) > 2048 or len(filename_header) > 1024:
                raise ValueError
            body = ExtractionOptions.model_validate(json.loads(options))
        except (ValueError, TypeError, ValidationError):
            raise ApiError("invalid_extraction_options", "Check the attachment's temporary scope and case revision", 422) from None
        filename = unquote(filename_header)
        if not filename or len(filename) > 255 or any(c in filename for c in ("/", "\\", ":", "\x00", "\r", "\n")):
            raise ApiError("invalid_attachment_name", "Choose a PDF, PNG or JPEG file with a plain filename", 422)
        suffix = PurePath(filename).suffix.lower()
        if suffix not in MEDIA or request.headers.get("content-type", "").split(";")[0].strip().lower() != MEDIA[suffix]:
            raise ApiError("unsupported_attachment", "Choose a PDF, PNG or JPEG file", 415)
        if request.headers.get("content-encoding", "identity") != "identity":
            raise ApiError("unsupported_attachment", "Send the original uncompressed file", 415)
        return body, filename, suffix

    @router.post("/sessions/{case_id}/attachments/prepare", status_code=201)
    async def prepare_attachment(case_id: str, request: Request):
        # Reserve a cancellation handle before the UI sends any file bytes.
        body, filename, _ = attachment_headers(request)
        job = previews.preflight(case_id, body.revision, body.scope, filename, body.title, body.mode)
        return previews.view(job.id)

    @router.post("/sessions/{case_id}/attachments/extract", status_code=202)
    async def extract(case_id: str, request: Request):
        # No UploadFile, multipart parser, original-copy path, disk staging or
        # spooled file. Scope and safety are checked before the first body read.
        body, filename, suffix = attachment_headers(request)
        byte_limit = MAX_IMAGE_BYTES if body.mode == "image" else MAX_ATTACHMENT_BYTES
        limit_message = "Images must be between 1 byte and 8 MiB" if body.mode == "image" else "Attachments must be between 1 byte and 10 MiB"
        length = request.headers.get("content-length")
        if length is not None:
            try:
                if not 0 < int(length) <= byte_limit:
                    raise ValueError
            except ValueError:
                raise ApiError("case_attachment_limit", limit_message, 413) from None
        preview_id = request.headers.get("x-renulus-preview-id")
        if preview_id is None:
            # Preserve the single-request seam for direct API consumers. The UI
            # uses prepare so cancellation cannot lose its handle during upload.
            preview_id = previews.preflight(case_id, body.revision, body.scope, filename, body.title, body.mode).id
        if not preview_id or len(preview_id) > 128:
            raise ApiError("invalid_attachment_preview", "Prepare the attachment again before uploading", 422)
        job = previews.claim_upload(preview_id, case_id, body.revision, body.scope, filename, body.title, body.mode)
        data = bytearray()
        try:
            async for block in request.stream():
                with repository._lock:
                    previews._guard(job)
                if len(data) + len(block) > byte_limit:
                    raise ApiError("case_attachment_limit", limit_message, 413)
                data.extend(block)
            valid = (suffix == ".pdf" and data[:1024].lstrip().startswith(b"%PDF-")) or (
                suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or (
                suffix in (".jpg", ".jpeg") and data.startswith(b"\xff\xd8\xff"))
            if not valid:
                raise ApiError("malformed_attachment", "The file does not match its PDF or image format", 422)
            return previews.start(job, bytes(data))
        except (ApiError, asyncio.CancelledError):
            previews.cancel(job.id)
            raise
        except Exception:
            previews.cancel(job.id)
            raise ApiError("attachment_upload_interrupted", "The attachment upload stopped. Select the file again", 409, True) from None
        finally:
            data.clear()

    @router.get("/attachments/{preview_id}")
    async def preview(preview_id: str):
        return previews.view(preview_id)

    @router.delete("/attachments/{preview_id}")
    async def discard_preview(preview_id: str):
        return previews.cancel(preview_id)

    @router.post("/attachments/{preview_id}/apply")
    async def apply_preview(preview_id: str, body: ApplyPreview):
        return previews.apply(preview_id, body.revision, body.text)

    @router.post('/attachments/{preview_id}/keep')
    async def keep_original(preview_id: str, body: RevisionInput):
        return previews.keep(preview_id, body.revision)

    @router.post("/sessions/{case_id}/discuss")
    async def discuss(case_id: str, body: DiscussCase):
        run, messages = repository.begin_discussion(case_id, body)
        return StreamingResponse(events(repository, run, messages), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no",
                                          "X-Renulus-Run-ID": run.id})

    @router.post('/attachments/{preview_id}/discuss-image')
    async def discuss_image(preview_id: str, body: ImageDiscussion):
        run, messages = previews.discuss_image(preview_id, body)
        return StreamingResponse(events(repository, run, messages), media_type='text/event-stream',
            headers={'Cache-Control': 'no-store', 'X-Accel-Buffering': 'no', 'X-Renulus-Run-ID': run.id})

    @router.get("/runs/{run_id}")
    async def run_status(run_id: str):
        return repository.run_status(run_id)

    @router.post("/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        result = repository.cancel(run_id)
        if result["status"] == "cancelled":
            await cancel_provider(repository, run_id)
        return result

    return router
