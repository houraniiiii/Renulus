# SPDX-License-Identifier: MIT
"""Bounded H02 Library tools; authority is supplied by the operation owner."""
from dataclasses import dataclass, replace
import asyncio
import inspect
from contextlib import closing
from threading import Event
from typing import Callable
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.storage.assessment_policy import require_assistance
from renulus.storage.invalidation import context_epoch_in


class _RetrieveArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=16000)
    limit: int = Field(default=5, ge=1, le=8)

    @field_validator("query")
    @classmethod
    def not_empty(cls, value):
        if not value.strip():
            raise ValueError("empty query")
        return value


class _CitationArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{32}$")
    document_revision: str = Field(pattern=r"^rev_[0-9a-f]{32}$")
    passage_id: str = Field(pattern=r"^passage_[0-9a-f]{32}$")
    page: int | None = Field(default=None, ge=1, le=300)

    @field_validator("page", mode="before")
    @classmethod
    def omit_unknown_page(cls, value):
        if value is None:
            raise ValueError("Omit page when the passage has no page locator")
        return value


def _arguments(model, value):
    try:
        return model.model_validate(value).model_dump(exclude_none=True)
    except ValidationError:
        raise ApiError("invalid_library_arguments", "Use bounded Library tool arguments without authority fields", 422) from None


def _local(callback, *arguments):
    result = callback(*arguments)
    if inspect.isawaitable(result):
        if inspect.iscoroutine(result):
            result.close()
        raise ApiError("invalid_library_authority", "Library owner callbacks must be synchronous local checks", 422)
    return result


class _CapturedScope(ContextScope):
    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True)
class LibraryAuthority:
    scope: ContextScope
    revision_ids: tuple[str, ...] | None
    policy_revision: int
    context_epoch: int
    cancelled: Callable[[], bool]
    guard: Callable[[object], None]
    record_dependencies: Callable[[list[dict]], None]
    topic_id: str | None = None
    current_only: bool = False

    def __post_init__(self):
        if self.scope.kind != Scope.STUDY:
            raise ApiError("invalid_library_authority", "Library tools require host-owned Study scope", 422)
        object.__setattr__(self, "scope", _CapturedScope.model_validate(self.scope.model_dump()))
        if self.revision_ids is not None:
            object.__setattr__(self, "revision_ids", tuple(self.revision_ids))


class HarnessLibrary:
    def __init__(self, repository):
        self.repository = repository

    def _check(self, authority, conn):
        if authority.cancelled():
            raise ApiError("harness_tool_cancelled", "This Library operation was cancelled", 409)
        require_assistance(conn, expected_revision=authority.policy_revision)
        if context_epoch_in(conn) != authority.context_epoch:
            raise ApiError("dependency_changed", "The learning context changed. Retry this request", 409, True)
        _local(authority.guard, conn)
        if authority.cancelled():
            raise ApiError("harness_tool_cancelled", "This Library operation was cancelled", 409)
        require_assistance(conn, expected_revision=authority.policy_revision)

    def retrieve(self, arguments, authority):
        arguments = _arguments(_RetrieveArguments, arguments)
        with closing(self.repository.db.connect()) as conn:
            self._check(authority, conn)
        result = self.repository.retrieve(arguments["query"], scope=authority.scope,
            limit=arguments.get("limit", 5), topic_id=authority.topic_id,
            current_only=authority.current_only,
            revision_ids=None if authority.revision_ids is None else list(authority.revision_ids))
        with closing(self.repository.db.connect()) as conn:
            self._check(authority, conn)
        self._require_evidence(result["passages"], authority)
        self._record(result["passages"], authority)
        return result

    def _record(self, passages, authority):
        _local(authority.record_dependencies, [{"document_id": passage["document_id"],
            "document_revision": passage["document_revision"],
            "passage_id": passage.get("id") or passage["passage_id"],
            "locators": passage["locators"]} for passage in passages])
        with closing(self.repository.db.connect()) as conn:
            self._check(authority, conn)
        self._require_evidence(passages, authority)
        if authority.cancelled():
            raise ApiError("harness_tool_cancelled", "This Library operation was cancelled", 409)

    def _require_evidence(self, passages, authority, *, conn=None):
        references = [{**passage, "id": passage.get("id") or passage.get("passage_id")} for passage in passages]
        if authority.revision_ids is not None and any(
                passage["document_revision"] not in authority.revision_ids for passage in references):
            raise ApiError("harness_sources_changed", "This source is outside the learning operation", 409)
        checked = self.repository.check_evidence(references, scope=authority.scope,
            topic_id=authority.topic_id, current_only=authority.current_only, conn=conn)
        if set(checked["eligible_ids"]) != {passage["id"] for passage in references}:
            raise ApiError("harness_sources_changed", "The cited Library evidence changed. Retry this request", 409, True)

    def open_citation(self, arguments, authority):
        arguments = _arguments(_CitationArguments, arguments)
        with closing(self.repository.db.connect()) as conn:
            self._check(authority, conn)
        self._require_evidence([arguments], authority)
        result = self.repository.citation(arguments["document_revision"],
            arguments.get("page"), passage_id=arguments["passage_id"])
        with closing(self.repository.db.connect()) as conn:
            self._check(authority, conn)
        self._require_evidence([arguments], authority)
        self._record([result], authority)
        return result

    def validate_publication(self, passages, authority, *, conn):
        if not conn.in_transaction:
            raise ApiError("harness_publication_transaction_required", "Validate evidence in the publication transaction", 409)
        self._check(authority, conn)
        self._require_evidence(passages, authority, conn=conn)

    async def execute(self, command, arguments, authority):
        method = {"library.retrieve": self.retrieve, "library.citation": self.open_citation}.get(command)
        if method is None:
            raise ApiError("unknown_library_tool", "Use a registered Library tool", 422)
        cancelled = Event()
        trusted = replace(authority, cancelled=lambda: cancelled.is_set() or authority.cancelled())
        worker = asyncio.create_task(asyncio.to_thread(method, arguments, trusted))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancelled.set()
            # Python cannot kill a CPU thread. Retain it through repeated aborts
            # until its read settles and its final cancellation check rejects.
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not worker.cancelled():
                worker.exception()
            raise
