# SPDX-License-Identifier: MIT
"""Integration lead mounts this router under /api/v1 after conversations."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import ValidationError

from ..contracts import ApiError
from ..design_c_contracts import ConversationIdentity
from .attachment_models import AttachmentRemoval, AttachmentUpload
from .attachments import KnowledgeAttachments


def create_router(services):
    repository = services.registry.get("knowledge_attachments")
    if not isinstance(repository, KnowledgeAttachments):
        repository = KnowledgeAttachments(services)
        services.registry["knowledge_attachments"] = repository
    services.registry["chat_attachments"] = repository

    def no_store(response: Response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

    router = APIRouter(prefix="/attachments", tags=["attachments"], dependencies=[Depends(no_store)])

    @router.post("", status_code=201)
    async def upload(request: Request):
        header = request.headers.get("x-renulus-attachment-options", "")
        if len(header) > 16000:
            raise ApiError("attachment_options_invalid", "The attachment options exceed their limit", 422)
        try:
            body = AttachmentUpload.model_validate(json.loads(header))
        except (ValueError, TypeError, ValidationError):
            raise ApiError("attachment_options_invalid", "Check the attachment conversation and permissions", 422) from None
        limit = repository.preflight(body)
        blocks, size = [], 0
        async for block in request.stream():
            size += len(block)
            if size > limit:
                raise ApiError("attachment_limit", "The selected file exceeds this conversation's attachment limit", 413)
            blocks.append(block)
        return repository.upload(body, b"".join(blocks))

    @router.post("/{attachment_id}/remove")
    def remove(attachment_id: str, body: AttachmentRemoval):
        return repository.remove(attachment_id, body)

    @router.get("/{kind}/{chat_id}")
    def attachments(kind: Literal["learning", "case"], chat_id: str):
        return repository.list(ConversationIdentity(type="case" if kind == "case" else "learn_thread", id=chat_id))

    return router
