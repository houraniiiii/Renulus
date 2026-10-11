# SPDX-License-Identifier: MIT
"""The integration lead mounts this exported router once under /api/v1."""
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import StreamingResponse

from renulus.design_c_contracts import ConversationDraft
from .conversation_models import (Mutation, NewConversation, Rename, ProjectMove, Send,
    CaseMutation, CaseContextEdit, CaseAttachmentRemove, CasePreviewApply, CasePreviewKeep, CasePreviewText, CaseHandoffRequest)
from .conversation_case import ConversationCases
from .conversation_repository import ConversationRepository
from .conversation_stream import ConversationStreams


def create_router(services):
    repository = ConversationRepository(services)
    services.registry["conversations"] = repository
    streaming = ConversationStreams(repository)
    repository.streaming = streaming
    cases = ConversationCases(repository)
    def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"
    router = APIRouter(prefix="/conversations", tags=["conversations"], dependencies=[Depends(no_store)])

    @router.post("", status_code=201)
    def create(body: NewConversation, idempotency_key: str | None = Header(default=None)):
        return repository.create(body, idempotency_key)

    @router.get("")
    def conversations(limit: int = Query(default=50, ge=1, le=100), cursor: str | None = Query(default=None, max_length=2048),
                      lifecycle: Literal["active", "archived"] = "active", project_id: str | None = None):
        return repository.list(limit, cursor, lifecycle, project_id)

    @router.get("/{kind}/{identifier}")
    def get(kind: Literal["learning", "case"], identifier: str):
        return repository.get(kind, identifier)

    @router.get("/{kind}/{identifier}/messages")
    async def messages(kind: Literal["learning", "case"], identifier: str, limit: int = Query(default=50, ge=1, le=100),
                 cursor: str | None = Query(default=None, max_length=2048)):
        harness = services.registry.get('learning_harness') if kind == 'learning' else None
        if harness is not None and hasattr(harness, 'messages'):
            return await harness.messages(identifier, limit, cursor)
        return repository.messages(kind, identifier, limit, cursor)

    @router.get('/case/{identifier}/context')
    def case_context(identifier: str):
        return cases.context(identifier)

    @router.post('/case/{identifier}/handoff', status_code=201)
    def case_handoff(identifier: str, body: CaseHandoffRequest):
        return cases.handoff(identifier, body)

    @router.patch('/case/{identifier}/context')
    def case_edit(identifier: str, body: CaseContextEdit, idempotency_key: str | None = Header(default=None)):
        return cases.change(identifier, body, 'context-edit', idempotency_key)

    @router.post('/case/{identifier}/context/reveal')
    def case_reveal(identifier: str, body: CaseMutation, idempotency_key: str | None = Header(default=None)):
        return cases.change(identifier, body, 'teaching-reveal', idempotency_key)

    @router.delete('/case/{identifier}/attachments/{attachment_id}')
    def case_remove(identifier: str, attachment_id: str, expected_revision: int = Query(ge=1),
                    case_revision: int = Query(ge=1), idempotency_key: str | None = Header(default=None)):
        return cases.change(identifier, CaseAttachmentRemove(expected_revision=expected_revision,
            case_revision=case_revision, attachment_id=attachment_id), 'attachment-remove', idempotency_key)

    @router.post('/case/{identifier}/previews/{preview_id}/apply')
    def case_apply(identifier: str, preview_id: str, body: CasePreviewApply,
                   idempotency_key: str | None = Header(default=None)):
        return cases.change(identifier, CasePreviewText(**body.model_dump(), preview_id=preview_id), 'preview-apply', idempotency_key)

    @router.post('/case/{identifier}/previews/{preview_id}/keep')
    def case_keep(identifier: str, preview_id: str, body: CaseMutation,
                  idempotency_key: str | None = Header(default=None)):
        return cases.change(identifier, CasePreviewKeep(**body.model_dump(), preview_id=preview_id), 'preview-keep', idempotency_key)

    @router.post('/{kind}/{identifier}/messages')
    async def send(kind: Literal['learning','case'], identifier: str, body: Send, idempotency_key: str | None = Header(default=None)):
        entry,receipt=streaming.begin(kind,identifier,body,idempotency_key)
        streaming.launch(entry)
        return StreamingResponse(streaming.events(entry,receipt),media_type='text/event-stream',
            headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})

    @router.post('/{kind}/{identifier}/runs/{run_id}/cancel')
    async def cancel(kind: Literal['learning','case'], identifier: str, run_id: str):
        return await streaming.cancel(kind,identifier,run_id)

    @router.get('/{kind}/{identifier}/runs')
    def runs(kind: Literal['learning','case'], identifier: str, limit: int = Query(default=20,ge=1,le=100),
             cursor: str | None = Query(default=None,max_length=2048)):
        return streaming.list(kind,identifier,limit,cursor)

    @router.get('/{kind}/{identifier}/runs/{run_id}')
    def run(kind: Literal['learning','case'], identifier: str, run_id: str, neutral: bool = False):
        return streaming.status(kind,identifier,run_id,neutral=neutral)

    @router.get("/{kind}/{identifier}/draft")
    def draft(kind: Literal["learning", "case"], identifier: str):
        return repository.draft(kind, identifier)

    @router.put("/{kind}/{identifier}/draft")
    def save_draft(kind: Literal["learning", "case"], identifier: str, body: ConversationDraft,
                   idempotency_key: str | None = Header(default=None)):
        return repository.save_draft(kind, identifier, body, idempotency_key)

    @router.patch("/{kind}/{identifier}")
    def rename(kind: Literal["learning", "case"], identifier: str, body: Rename, idempotency_key: str | None = Header(default=None)):
        return repository.change(kind, identifier, body, "rename", idempotency_key)

    @router.put('/{kind}/{identifier}/project')
    def move(kind: Literal['learning','case'], identifier: str, body: ProjectMove, idempotency_key: str | None = Header(default=None)):
        return repository.move(kind,identifier,body,idempotency_key)

    @router.post('/{kind}/{identifier}/save')
    def save(kind: Literal['learning','case'], identifier: str, body: Mutation, idempotency_key: str | None = Header(default=None)):
        return repository.promote(kind,identifier,body,idempotency_key)

    @router.post("/{kind}/{identifier}/archive")
    def archive(kind: Literal["learning", "case"], identifier: str, body: Mutation, idempotency_key: str | None = Header(default=None)):
        return repository.change(kind, identifier, body, "archive", idempotency_key)

    @router.post("/{kind}/{identifier}/restore")
    def restore(kind: Literal["learning", "case"], identifier: str, body: Mutation, idempotency_key: str | None = Header(default=None)):
        return repository.change(kind, identifier, body, "restore", idempotency_key)

    @router.delete("/{kind}/{identifier}")
    async def delete(kind: Literal["learning", "case"], identifier: str, expected_revision: int = Query(ge=1),
                     idempotency_key: str | None = Header(default=None)):
        return await repository.delete(kind, identifier, Mutation(expected_revision=expected_revision), idempotency_key)

    return router
