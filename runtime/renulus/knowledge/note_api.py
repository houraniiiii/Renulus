# SPDX-License-Identifier: MIT
"""The integration lead mounts this owner router after Knowledge and Projects."""
from fastapi import APIRouter, Depends, Header, Query, Response

from .note_models import CommandKey, CreateNote, DeleteNote, EditNote, NoteIdentifier
from .note_service import NotesService


def create_router(services):
    repository = NotesService(services)
    services.registry["notes"] = repository

    def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

    router = APIRouter(prefix="/library/notes", tags=["notes"], dependencies=[Depends(no_store)])

    @router.get("")
    def notes(project_id: NoteIdentifier | None = None, limit: int = Query(default=100, ge=1, le=100),
              offset: int = Query(default=0, ge=0)):
        return repository.list(project_id=project_id, limit=limit, offset=offset)

    @router.get("/{document_id}")
    def note(document_id: NoteIdentifier, revision_id: NoteIdentifier | None = None):
        return repository.get(document_id, revision_id=revision_id)

    @router.post("", status_code=201)
    def create(body: CreateNote):
        return repository.save(body)

    @router.put("/{document_id}")
    def edit(document_id: NoteIdentifier, body: EditNote):
        return repository.save(body, document_id=document_id)

    @router.delete("/{document_id}")
    def delete(document_id: NoteIdentifier, expected_revision_id: NoteIdentifier,
               idempotency_key: CommandKey = Header(alias="Idempotency-Key")):
        return repository.delete(document_id, DeleteNote(expected_revision_id=expected_revision_id,
            idempotency_key=idempotency_key))

    return router
