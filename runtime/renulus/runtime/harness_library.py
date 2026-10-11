# SPDX-License-Identifier: MIT
"""Bounded H02 Library tools; authority is supplied by the operation owner."""
from dataclasses import dataclass, replace
import asyncio
import inspect
import json
from contextlib import closing
from threading import Event
from typing import TYPE_CHECKING, Callable
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import Dependency, Identity, canonical_digest
from renulus.knowledge.saved_extraction import _reference as _reader_reference
from renulus.storage.assessment_policy import require_assistance
from renulus.storage.invalidation import context_epoch_in

if TYPE_CHECKING:
    from renulus.memory.lineage import AnswerInputs


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


class _ConsumedReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_id: str = Field(pattern=r"^doc_[0-9a-f]{32}$")
    document_revision: str = Field(pattern=r"^rev_[0-9a-f]{32}$")
    passage_id: str = Field(pattern=r"^passage_[0-9a-f]{32}$")
    locators: list[dict] = Field(max_length=12000)


# Only source coordinates and reference labels may cross saved provenance.
# Mapping validity (ordered ranges, physical pages) remains with the reader.
_GEOMETRY = {"l": (int, float), "t": (int, float), "r": (int, float), "b": (int, float), "coord_origin": str}
_SIZE = {"width": (int, float), "height": (int, float)}
_CONTENT_LOCATION = {"kind": str, "item_ref": str, "section": str, "start": int, "end": int,
    "format": str, "sheet_name": str, "first_row": int, "last_row": int,
    "first_column": int, "last_column": int, "physical_page": int, "printed_label": str,
    "frame": int, "bounds": [(int, float)]}
_SOURCE_LOCATION = {"item_ref": str, "table_ref": str, "page": int, "char_span": [int],
    "bbox": _GEOMETRY, "page_size": _SIZE, "format": str, "slide": int, "slide_size": _SIZE,
    "sheet": int, "sheet_name": str, "cell_bbox": _GEOMETRY, "content_locator": _CONTENT_LOCATION}


def _reference_shape(value, shape):
    if value is None:
        return True
    if isinstance(shape, dict):
        return (isinstance(value, dict) and not set(value) - shape.keys()
            and all(_reference_shape(item, shape[key]) for key, item in value.items()))
    if isinstance(shape, list):
        return isinstance(value, list) and all(_reference_shape(item, shape[0]) for item in value)
    return type(value) in shape if isinstance(shape, tuple) else type(value) is shape


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
        if context_epoch_in(conn) != authority.context_epoch:
            raise ApiError("dependency_changed", "The learning context changed. Retry this request", 409, True)

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
        self._check(authority, conn)

    def project_content_reference(self, conn, reference, *, authority: LibraryAuthority) -> dict:
        """Project exact consumed provenance in the caller's canonical transaction.

        Reader offsets come only from the saved-extraction mapping. Raw Docling
        locators remain separate provenance; no passage body or original is read.
        The supplied reference must match canonical locators, not model claims.
        """
        reference = _arguments(_ConsumedReference, reference)
        if not conn.in_transaction:
            raise ApiError("harness_publication_transaction_required", "Project references in the publication transaction", 409)
        self._check(authority, conn)
        self._require_evidence([reference], authority, conn=conn)
        row = conn.execute("SELECT p.locators_json,r.media_type FROM knowledge_passages p "
            "JOIN knowledge_revisions r ON r.id=p.revision_id WHERE p.id=? AND r.id=? AND r.document_id=?",
            (reference["passage_id"], reference["document_revision"], reference["document_id"])).fetchone()
        locators = json.loads(row["locators_json"])
        if (not isinstance(locators, list) or any(not isinstance(location, dict)
                or not _reference_shape(location, _SOURCE_LOCATION) for location in locators)):
            raise ApiError("harness_source_locators_invalid", "Canonical source provenance needs repair", 503)
        if locators != reference["locators"]:
            raise ApiError("harness_sources_changed", "Consumed source locators no longer match the canonical passage", 409, True)
        projected = {"content_ref": _reader_reference(reference["document_revision"], locators, row["media_type"]),
            "document_id": reference["document_id"], "revision_id": reference["document_revision"],
            "passage_id": reference["passage_id"], "locators": locators}
        self._check(authority, conn)
        self._require_evidence([reference], authority, conn=conn)
        if authority.cancelled():
            raise ApiError("harness_tool_cancelled", "This Library operation was cancelled", 409)
        return projected

    def resolve_dependency(self, conn, identity: Identity, *, authority: LibraryAuthority,
                           for_support: bool = False) -> str | None:
        """Resolve a library_revision in the caller's canonical snapshot.

        This composes into an owner's dependency resolver, so it deliberately
        does not recurse through guard or record_dependencies. No body, original,
        index or engine work occurs; None means unavailable in this host scope.

        A trusted local caller may validate retained support with for_support=True
        while Test temporarily restricts assistance. This omits only assistance
        admission; source rights, active revision, scope/pins, cancellation and
        context checks still apply. This flag never grants retrieval/disclosure.
        """
        if (identity.type != "library_revision" or _local(authority.cancelled)
                or authority.revision_ids is not None and identity.id not in authority.revision_ids):
            return None
        if not for_support:
            require_assistance(conn, expected_revision=authority.policy_revision)
        if context_epoch_in(conn) != authority.context_epoch:
            return None
        token = self._source_dependency(conn, identity, scope=authority.scope,
            topic_id=authority.topic_id, current_only=authority.current_only)
        return None if _local(authority.cancelled) else token

    def _source_dependency(self, conn, identity, *, scope, topic_id=None, current_only=False):
        row = conn.execute("SELECT r.id,r.document_id,r.sha256,r.metadata_json,r.rights_json,d.title,d.source_id "
            "FROM knowledge_revisions r JOIN knowledge_documents d ON d.active_revision=r.id "
            "WHERE r.id=? AND r.status='ready' AND d.deleted_at IS NULL AND d.reserved=0 "
            "AND d.scope_kind='personal-library' AND (d.scope_entity IS NULL OR d.scope_entity=?) "
            "AND NOT EXISTS (SELECT 1 FROM deletion_ledger WHERE "
            "(entity_type IN ('knowledge-document','document') AND entity_id=d.id) OR "
            "(entity_type IN ('knowledge-revision','revision') AND entity_id=r.id))",
            (identity.id, scope.entity_id)).fetchone()
        if row is None:
            return None
        passage = conn.execute("SELECT p.id,p.locators_json FROM knowledge_passages p WHERE p.revision_id=? "
            "AND NOT EXISTS (SELECT 1 FROM json_each(p.locators_json) l JOIN "
            "json_each(?, '$.excluded_pages') x ON json_extract(l.value, '$.page')=x.value) "
            "ORDER BY p.ordinal LIMIT 1", (identity.id, row["metadata_json"])).fetchone()
        if passage is None:
            return None
        checked = self.repository.check_evidence([{"id": passage["id"],
            "document_id": row["document_id"], "document_revision": identity.id}],
            scope=scope, topic_id=topic_id, current_only=current_only, conn=conn)
        if checked["eligible_ids"] != [passage["id"]]:
            return None
        return canonical_digest({"identity": identity.model_dump(mode="json"),
            "document_id": row["document_id"], "sha256": row["sha256"], "title": row["title"],
            "source_id": row["source_id"], "metadata": json.loads(row["metadata_json"]),
            "rights": json.loads(row["rights_json"]), "passage_id": passage["id"],
            "locators": json.loads(passage["locators_json"])})

    def resolve_dependency_in(self, conn, dependency: Dependency, *,
                              project_id: str | None, for_support: bool) -> "AnswerInputs":
        """Validate an independent persistent Library root without a live run.

        Prebind this object before Memory opens. The canonical group owns
        project_id; no model payload, historical thread or streaming owner may
        supply scope. Empty AnswerInputs attest an eligible independent root.
        The caller owns the transaction and canonical project/group identity;
        archived projects retain support, missing/deleted projects cannot grant it.
        """
        from renulus.memory.lineage import AnswerInputs
        if not conn.in_transaction:
            raise ApiError("harness_publication_transaction_required", "Resolve retained sources in the canonical transaction", 409)
        if dependency.target.type != "library_revision":
            raise ApiError("memory_dependency_unknown", "Use the Library resolver only for Library revisions", 409)
        if not for_support:
            require_assistance(conn)
        if project_id is not None and not conn.execute("SELECT 1 FROM study_projects WHERE id=? "
                "AND lifecycle!='deleted' AND NOT EXISTS (SELECT 1 FROM deletion_ledger "
                "WHERE entity_type='project' AND entity_id=study_projects.id)", (project_id,)).fetchone():
            raise ApiError("memory_project_scope", "Retained Library support requires its canonical project", 409)
        token = self._source_dependency(conn, dependency.target,
            scope=ContextScope(kind=Scope.STUDY, entity_id=project_id))
        if token is None or token != dependency.expected_revision:
            raise ApiError("memory_dependency_revoked", "The retained Library source changed or is unavailable", 409)
        return AnswerInputs()

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
