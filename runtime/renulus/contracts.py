"""Small versioned process contracts; payloads never control retention policy."""
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

API_VERSION = 1


class Scope(StrEnum):
    STUDY = "study"
    LIBRARY = "personal-library"
    TEMPORARY_CASE = "temporary-case"
    SAVED_CASE = "saved-case"
    GENERATED_PRACTICE = "generated-practice"
    REVIEWED_ASSESSMENT = "reviewed-assessment"
    UNCLASSIFIED = "unclassified"


class ContextScope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Scope
    entity_id: str | None = None

    @property
    def persistent(self) -> bool:
        return self.kind not in (Scope.TEMPORARY_CASE, Scope.UNCLASSIFIED)


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False):
        self.code, self.message, self.status, self.retryable = code, message, status, retryable
        super().__init__(message)


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    sequence: int
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


def durable_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
