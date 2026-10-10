# SPDX-License-Identifier: MIT
"""The integration lead mounts this exported router once under /api/v1."""
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response

from renulus.design_c_contracts import ConversationDraft
from .conversation_models import NewConversation
from .conversation_repository import ConversationRepository


def create_router(services):
    repository = ConversationRepository(services)
    services.registry["conversations"] = repository
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
    def messages(kind: Literal["learning", "case"], identifier: str, limit: int = Query(default=50, ge=1, le=100),
                 cursor: str | None = Query(default=None, max_length=2048)):
        return repository.messages(kind, identifier, limit, cursor)

    @router.get("/{kind}/{identifier}/draft")
    def draft(kind: Literal["learning", "case"], identifier: str):
        return repository.draft(kind, identifier)

    @router.put("/{kind}/{identifier}/draft")
    def save_draft(kind: Literal["learning", "case"], identifier: str, body: ConversationDraft,
                   idempotency_key: str | None = Header(default=None)):
        return repository.save_draft(kind, identifier, body, idempotency_key)

    return router
