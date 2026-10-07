"""Module inputs never grant a case permission to become learner memory."""
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from renulus.contracts import ApiError, ContextScope, Scope

FactKind = Literal['learning-point', 'preference', 'goal', 'study-interest', 'mistake']
ELIGIBLE_SCOPES = frozenset((Scope.STUDY, Scope.LIBRARY, Scope.GENERATED_PRACTICE,
                             Scope.REVIEWED_ASSESSMENT))


def require_eligible(scope: ContextScope):
    # This check precedes lookup, hashing, logging, jobs and helper initialisation.
    if scope.kind not in ELIGIBLE_SCOPES:
        raise ApiError('memory_scope_excluded', 'Case and unclassified material cannot enter learner memory', 409)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def clean_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ApiError('invalid_memory_text', 'Use a learning note of 1–2,000 characters', 422)
    return text.strip()


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ManualFact(Input):
    text: str = Field(min_length=1, max_length=2000, repr=False)
    kind: FactKind = 'learning-point'
    topic_id: str | None = Field(default=None, max_length=120)
    scope: ContextScope
    idempotency_key: str = Field(min_length=1, max_length=128)


class EditFact(Input):
    text: str = Field(min_length=1, max_length=2000, repr=False)
    expected_revision: int = Field(ge=1)


class Capture(Input):
    evidence_id: str = Field(min_length=1, max_length=200)
    scope: ContextScope


class Search(Input):
    query: str = Field(min_length=1, max_length=2000, repr=False)
    scope: ContextScope
    limit: int = Field(default=10, ge=1, le=30)
    budget_chars: int = Field(default=4000, ge=0, le=12000)
