import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
from threading import Event as CancelEvent
from typing import Literal
from urllib.parse import unquote

from fastapi import APIRouter, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..contracts import ApiError, ContextScope, Event, Scope
from .collection import CollectionCatalogue
from .engines import MAX_BYTES
from .models import Rights, SourceMetadata, own_text_rights
from .repository import KnowledgeRepository, MEDIA, TERMINAL
from .worker import IngestionWorker


class TextImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    title: str = Field(default="Personal study note", min_length=1, max_length=500)
    scope: ContextScope
    metadata: SourceMetadata = Field(default_factory=SourceMetadata)
    rights: Rights = Field(default_factory=own_text_rights)
    idempotency_key: str = Field(min_length=1, max_length=200)
    document_id: str | None = None
    reserved: bool = False


class Retrieve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(max_length=16000)
    scope: ContextScope
    topic_id: str | None = None
    current_only: bool = False
    limit: int = Field(default=8, ge=1, le=50)


class SelectedBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_ids: list[str] = Field(max_length=250)
    scope: ContextScope


class NextAcquiredBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: ContextScope
    source_id: Literal["L02"] = "L02"
    query: str = Field(default="", max_length=200)
    limit: int = Field(default=100, ge=1, le=250)
    cursor: str | None = Field(default=None, max_length=1000)


def create_router(services) -> APIRouter:
    repository = KnowledgeRepository(services)
    services.registry["knowledge"] = repository
    collection = CollectionCatalogue(repository)
    services.registry["knowledge_catalogue"] = collection
    worker = IngestionWorker(repository)
    services.registry["knowledge_worker"] = worker

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(worker.start)
        try:
            yield
        finally:
            await asyncio.to_thread(worker.stop)

    router = APIRouter(prefix="/library", tags=["library"], lifespan=lifespan)

    @router.get("/capabilities")
    def capabilities():
        return {**repository.capabilities(), "ingestion_worker": worker.status()}

    @router.get("/queue")
    def queue_status():
        return worker.status()

    @router.get("/source-versions")
    def source_versions(source_id: str = Query(pattern=r"^[A-Z]\d{2}$"),
                        canonical_url: str | None = Query(default=None, max_length=2000),
                        doi: str | None = Query(default=None, max_length=500),
                        pmid: str | None = Query(default=None, max_length=12),
                        pmcid: str | None = Query(default=None, max_length=15)):
        identity = {key: value for key, value in {"canonical_url": canonical_url,
            "doi": doi, "pmid": pmid, "pmcid": pmcid}.items() if value}
        return repository.source_status.version_targets(source_id, identity)

    @router.get("/documents")
    def documents(limit: int | None = Query(default=None, ge=1, le=100),
                  offset: int = Query(default=0, ge=0),
                  query: str = Query(default="", max_length=200),
                  status: Literal["ready", "queued", "processing", "failed", "cancelled", "empty"] | None = None):
        return repository.list_documents(limit=limit, offset=offset, query=query, status=status)

    @router.get("/documents/{document_id}")
    def document(document_id: str):
        return repository.get_document(document_id)

    @router.get("/documents/{document_id}/import-status")
    def import_status(document_id: str):
        document = repository.get_document(document_id)
        job = services.db.fetch_one("SELECT id FROM knowledge_jobs WHERE revision_id=?", (document["latest_revision"],))
        if not job:
            raise ApiError("job_missing", "This document has no import job", 404)
        return repository._result(job["id"])

    @router.post("/import/text", status_code=202)
    def import_text(body: TextImport):
        return worker.import_interactive(lambda: repository.import_text(**body.model_dump(), process=False))

    @router.post("/import/file", status_code=202)
    async def import_file(request: Request):
        # Validate scope BEFORE consuming the body. Stock multipart UploadFile
        # can spool to disk before endpoint validation, which is unsafe for
        # temporary cases. This route accepts a bounded raw file body only.
        try:
            parsed = json.loads(request.headers.get("x-renulus-import-options", ""))
            body = TextImport.model_validate({"text": "", **parsed})
        except (ValueError, TypeError, ValidationError):
            raise ApiError("invalid_import_options", "Check the file import scope and permissions", 422) from None
        scope = repository._import_scope(body.scope)
        suffix = Path(unquote(request.headers.get("x-renulus-filename", ""))).suffix.lower()
        if suffix not in MEDIA:
            raise ApiError("unsupported_file", "Choose a PDF, image, text or supported Office file", 415)
        parts, size = [], 0
        async for block in request.stream():
            size += len(block)
            if size > MAX_BYTES:
                raise ApiError("document_limit", "The maximum file size is 64 MiB", 413)
            parts.append(block)
        data = b"".join(parts)
        if suffix == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
            raise ApiError("malformed_pdf", "The selected file has no PDF signature", 422)
        return worker.import_interactive(lambda: repository._import(data, suffix, body.title, body.metadata, body.rights,
            scope, body.idempotency_key, body.document_id, body.reserved, False))

    @router.post("/retrieve")
    def retrieve(body: Retrieve):
        return repository.retrieve(**body.model_dump())

    @router.get("/jobs/{job_id}")
    def job(job_id: str):
        return repository.get_job(job_id)

    @router.post("/jobs/{job_id}/cancel")
    def cancel(job_id: str):
        return repository.cancel_job(job_id)

    @router.get("/jobs/{job_id}/events")
    async def events(job_id: str, request: Request):
        repository.get_job(job_id)
        async def stream():
            sequence, previous = 0, None
            while not await request.is_disconnected():
                job = repository.get_job(job_id)
                identity = (job["state"], job["phase"])
                if identity != previous:
                    sequence += 1
                    terminal = job["state"] in TERMINAL
                    event = Event(run_id=job_id, sequence=sequence,
                                  type=job["state"] if terminal else "progress", payload={"job": job})
                    yield "data: " + event.model_dump_json() + "\n\n"
                    previous = identity
                    if terminal:
                        return
                await asyncio.sleep(0.25)
        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store"})

    @router.delete("/documents/{document_id}")
    def delete(document_id: str):
        return repository.delete_document(document_id)

    @router.get("/revisions/{revision_id}/citation")
    def citation(revision_id: str, page: int | None = None,
                 passage_id: str | None = Query(default=None, pattern=r"^passage_[0-9a-f]{32}$")):
        return repository.citation(revision_id, page, passage_id=passage_id)

    @router.get("/revisions/{revision_id}/original")
    def original(revision_id: str):
        path, media_type = repository.original(revision_id)
        return FileResponse(path, media_type=media_type, filename="document" + path.suffix,
            content_disposition_type="inline", headers={"Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'"})

    @router.get("/collection/preview")
    def preview(source_id: str | None = None, limit: int = 250, offset: int = 0):
        return collection.preview(source_id=source_id, limit=max(1, limit), offset=max(0, offset))

    @router.post("/collection/catalogue")
    def catalogue(source_id: str | None = None):
        return collection.register(source_id=source_id)

    @router.get("/collection/catalogue")
    def catalogue_entries(source_id: str | None = None,
                          limit: int = Query(default=250, ge=1, le=1000),
                          offset: int = Query(default=0, ge=0),
                          eligibility: Literal["eligible", "inspection_required", "reserved", "unavailable"] | None = None,
                          query: str = Query(default="", max_length=200)):
        return collection.list(source_id=source_id, limit=limit, offset=offset,
                               eligibility=eligibility, query=query)

    @router.post("/collection/import", status_code=202)
    def import_selected(body: SelectedBatch):
        repository._import_scope(body.scope)
        result = collection.import_selected(body.entry_ids)
        if result["queued"]:
            worker.wake()
        return result

    @router.post("/collection/import-next", status_code=202)
    async def import_next(body: NextAcquiredBatch, request: Request):
        repository._import_scope(body.scope)
        cancelled = CancelEvent()
        task = asyncio.create_task(asyncio.to_thread(collection.import_next,
            source_id=body.source_id, query=body.query, limit=body.limit,
            cursor=body.cursor, cancelled=cancelled.is_set))
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=0.1)
                if await request.is_disconnected():
                    cancelled.set()
            result = await task
        finally:
            # A disconnected/cancelled request stops further adoption. Jobs
            # already committed remain durable and use normal job cancellation.
            cancelled.set()
        if result["queued"]:
            worker.wake()
        return result

    @router.post("/cleanup")
    def cleanup():
        return {"pending": repository.cleanup()}

    return router
