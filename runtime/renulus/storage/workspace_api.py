# SPDX-License-Identifier: MIT
"""Workspace operations carry references, never arbitrary paths or originals."""
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from renulus.design_c_contracts import ContentReference, Identity
from .workspace import WorkspacePreferences, WorkspaceRepository


class WorkspaceContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    identity: Identity
    retention: Literal["saved", "temporary"]

    @model_validator(mode="after")
    def supported(self):
        if self.identity.type not in ("learn_thread", "case", "project") or (self.retention == "temporary" and self.identity.type == "project"):
            raise ValueError("Use a chat or project context")
        return self


class PolicyReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1, strict=True)
    active_test_id: str | None = None
    assistance_allowed: bool = Field(strict=True)


class AccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["content", "section"]
    context: WorkspaceContext | None = None
    policy: PolicyReference
    reference: ContentReference | None = None
    section: Literal["Files", "Sources", "Notes", "Goals"] | None = None

    @model_validator(mode="after")
    def complete(self):
        if (self.kind == "content") != (self.reference is not None) or (self.kind == "section") != (self.section is not None):
            raise ValueError("Specify the content reference or section")
        return self


def create_router(services):
    repository = WorkspaceRepository(services)
    services.registry["workspace"] = repository
    router = APIRouter(prefix="/workspace", tags=["workspace"])

    @router.get("/preferences")
    def preferences():
        return repository.preferences()

    @router.put("/preferences")
    def save_preferences(body: WorkspacePreferences):
        return repository.save_preferences(body)

    @router.post("/authorize")
    def authorize(body: AccessRequest):
        return repository.authorize(body)

    @router.get("/entries")
    def entries(section: Literal["Files", "Sources", "Notes", "Goals"] = "Files",
                context_type: Literal["learn_thread", "case", "project"] | None = None,
                context_id: str | None = Query(default=None, min_length=1, max_length=256)):
        if (context_type is None) != (context_id is None):
            from renulus.contracts import ApiError
            raise ApiError("invalid_context", "Choose a complete context identity", 422)
        return repository.entries(section, Identity(type=context_type, id=context_id) if context_type else None)

    return router
