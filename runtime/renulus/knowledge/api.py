import asyncio
import json
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..contracts import ApiError, ContextScope, Event, Scope
from .collection import CollectionCatalogue
from .engines import MAX_BYTES
from .models import Rights, SourceMetadata, own_text_rights
from .repository import KnowledgeRepository, MEDIA, TERMINAL


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


def create_router(services) -> APIRouter:
    repository = KnowledgeRepository(services)
    services.registry["knowledge"] = repository
    collection = CollectionCatalogue(repository)
    services.registry["knowledge_catalogue"] = collection
    repository.recover()
    router = APIRouter(prefix="/library", tags=["library"])

    @router.get("/capabilities")
    def capabilities():
        return repository.capabilities()

    @router.get("/documents")
    def documents():
        return repository.list_documents()

    @router.get("/documents/{document_id}")
    def document(document_id: str):
        return repository.get_document(document_id)

    @router.post("/import/text", status_code=202)
    def import_text(body: TextImport, tasks: BackgroundTasks):
        result = repository.import_text(**body.model_dump(), process=False)
        if result["status"] == "queued":
            tasks.add_task(repository.run_job, result["job"]["id"])
        return result

    @router.post("/import/file", status_code=202)
    async def import_file(request: Request, tasks: BackgroundTasks):
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
            raise ApiError("unsupported_file", "Choose a PDF, image or text file", 415)
        parts, size = [], 0
        async for block in request.stream():
            size += len(block)
            if size > MAX_BYTES:
                raise ApiError("document_limit", "The maximum file size is 64 MiB", 413)
            parts.append(block)
        data = b"".join(parts)
        if suffix == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
            raise ApiError("malformed_pdf", "The selected file has no PDF signature", 422)
        result = repository._import(data, suffix, body.title, body.metadata, body.rights,
            scope, body.idempotency_key, body.document_id, body.reserved, False)
        if result["status"] == "queued":
            tasks.add_task(repository.run_job, result["job"]["id"])
        return result

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
    def citation(revision_id: str, page: int | None = None):
        return repository.citation(revision_id, page)

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
    def catalogue_entries(source_id: str | None = None, limit: int = 250, offset: int = 0):
        return collection.list(source_id=source_id, limit=max(1, limit), offset=max(0, offset))

    @router.post("/collection/import", status_code=202)
    def import_selected(body: SelectedBatch, tasks: BackgroundTasks):
        repository._import_scope(body.scope)
        result = collection.import_selected(body.entry_ids)
        for item in result["results"]:
            if item["status"] == "queued":
                tasks.add_task(repository.run_job, item["job"]["id"])
        return result

    @router.post("/cleanup")
    def cleanup():
        return {"pending": repository.cleanup()}

    return router
