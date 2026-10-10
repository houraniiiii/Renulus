# SPDX-License-Identifier: MIT
"""Additive Design C shapes and pure boundary checks, not a storage/router layer.

Only trusted backend resolution may construct eligibility/privacy attestations.
Parsing these shapes never grants permission or proves semantic fictionalisation.
Legacy ContextScope and assessment session/answer meanings remain unchanged.
"""
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
import hashlib
import json
from typing import Annotated, Literal
import unicodedata

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

CONTRACT_VERSION = "design-c/1"
Identifier = Annotated[str, Field(min_length=1, max_length=256, strict=True,
                                  pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
Revision = Annotated[int, Field(ge=1, strict=True)]
ChatKind = Literal["learning", "case"]
Lifecycle = Literal["active", "archived", "deleted"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Identity(Contract):
    type: Literal[
        "learn_thread", "case", "project", "project_chat", "project_document",
        "library_document", "library_revision", "attachment", "attachment_original",
        "attachment_preview", "note_revision", "saved_test", "saved_test_version",
        "test_attempt", "attempt_draft", "message", "run", "exposure",
        "memory", "memory_revision", "learning_evidence", "goal", "preferences",
        "job", "fictional_test_artifact",
    ]
    id: Identifier

    @property
    def key(self) -> tuple[str, str]:
        return self.type, self.id


class ConversationIdentity(Identity):
    type: Literal["learn_thread", "case"]


class ContentIdentity(Identity):
    type: Literal["library_revision", "attachment", "note_revision", "saved_test_version"]


class TestVersionIdentity(Identity):
    type: Literal["saved_test_version"] = "saved_test_version"


class PdfLocator(Contract):
    kind: Literal["pdf"] = "pdf"
    physical_page: Annotated[int, Field(ge=1, strict=True)]
    printed_label: Annotated[str, Field(max_length=80)] | None = None


class TextLocator(Contract):
    kind: Literal["text"] = "text"
    item_ref: Annotated[str, Field(min_length=1, max_length=256)]
    section: Annotated[str, Field(max_length=240)] | None = None
    start: Annotated[int, Field(ge=0, strict=True)]
    end: Annotated[int, Field(gt=0, strict=True)]

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Text offsets must define a nonempty half-open range")
        return self


class TableLocator(Contract):
    kind: Literal["table"] = "table"
    format: Literal["csv", "xlsx"]
    sheet_name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    first_row: Annotated[int, Field(ge=1, strict=True)]
    last_row: Annotated[int, Field(ge=1, strict=True)]
    first_column: Annotated[int, Field(ge=1, strict=True)]
    last_column: Annotated[int, Field(ge=1, strict=True)]

    @model_validator(mode="after")
    def ordered(self):
        if self.last_row < self.first_row or self.last_column < self.first_column:
            raise ValueError("Table coordinates must be ordered inclusive ranges")
        if (self.format == "xlsx") != (self.sheet_name is not None):
            raise ValueError("Only XLSX coordinates require a sheet name")
        return self


class ImageLocator(Contract):
    kind: Literal["image"] = "image"
    frame: Annotated[int, Field(ge=1, strict=True)] = 1
    # Optional normalised top-left coordinates, independent of Docling geometry.
    bounds: tuple[float, float, float, float] | None = None

    @model_validator(mode="after")
    def ordered(self):
        if self.bounds is not None:
            left, top, right, bottom = self.bounds
            if not 0 <= left < right <= 1 or not 0 <= top < bottom <= 1:
                raise ValueError("Image bounds must be ordered normalised coordinates")
        return self


Locator = Annotated[PdfLocator | TextLocator | TableLocator | ImageLocator, Field(discriminator="kind")]


class ContentReference(Contract):
    target: ContentIdentity
    locator: Locator | None = None

    @model_validator(mode="after")
    def test_has_no_document_locator(self):
        if self.target.type == "saved_test_version" and self.locator is not None:
            raise ValueError("Test versions do not use document locators")
        return self


class Conversation(Contract):
    identity: ConversationIdentity
    kind: ChatKind
    retention: Literal["saved", "temporary"]
    lifecycle: Lifecycle = "active"
    revision: Revision
    title: Annotated[str, Field(min_length=1, max_length=120)]
    project_id: Identifier | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def coherent_kind(self):
        expected = "learn_thread" if self.kind == "learning" else "case"
        if self.identity.type != expected:
            raise ValueError("Conversation identity must preserve its original owner")
        if self.retention == "temporary" and (self.project_id or self.lifecycle != "active"):
            raise ValueError("Temporary metadata cannot enter project/archive records")
        return self


class CreateConversation(Contract):
    kind: ChatKind = "learning"
    title: Annotated[str, Field(min_length=1, max_length=120)] = "New chat"
    temporary: Annotated[bool, Field(strict=True)] = False
    project_id: Identifier | None = None

    @model_validator(mode="after")
    def no_temporary_membership(self):
        if self.temporary and self.project_id is not None:
            raise ValueError("Temporary conversations cannot have durable membership")
        return self


def server_retention(request: CreateConversation) -> Literal["saved", "temporary"]:
    """Create intent only; subsequent writes resolve the canonical owner."""
    return "temporary" if request.temporary else "saved"


class ConversationDraft(Contract):
    expected_revision: Revision
    text: Annotated[str, Field(max_length=16000)] = ""
    content_refs: tuple[ContentReference, ...] = Field(default=(), max_length=20)


class Message(Contract):
    id: Identifier
    run_id: Identifier
    role: Literal["user", "assistant"]
    content: Annotated[str, Field(max_length=100000)]
    created_at: AwareDatetime
    content_refs: tuple[ContentReference, ...] = Field(default=(), max_length=50)


class MessagePage(Contract):
    conversation: ConversationIdentity
    items: tuple[Message, ...] = Field(max_length=100)
    next_cursor: Annotated[str, Field(min_length=1, max_length=2048)] | None = None

    @model_validator(mode="after")
    def stable_order(self):
        keys = [(item.created_at, item.id) for item in self.items]
        if keys != sorted(keys) or len({item.id for item in self.items}) != len(keys):
            raise ValueError("Message pages must be ordered and contain unique IDs")
        return self


class PageRequest(Contract):
    limit: Annotated[int, Field(ge=1, le=100, strict=True)] = 50
    cursor: Annotated[str, Field(min_length=1, max_length=2048)] | None = None


class Relation(Contract):
    source: Identity
    target: Identity
    relationship: Literal["owned", "link"]

    @model_validator(mode="after")
    def ownership_is_explicit(self):
        owned_pairs = {
            ("learn_thread", "message"), ("learn_thread", "run"),
            ("learn_thread", "attachment"), ("case", "attachment"),
            ("attachment", "attachment_original"), ("attachment", "attachment_preview"),
            ("project", "goal"), ("library_document", "library_revision"),
            ("saved_test", "saved_test_version"),
            ("test_attempt", "attempt_draft"), ("test_attempt", "exposure"),
        }
        if self.source.key == self.target.key:
            raise ValueError("A reference cannot own or link itself")
        if self.relationship == "owned" and (self.source.type, self.target.type) not in owned_pairs:
            raise ValueError("Undeclared ownership cannot cascade deletion")
        return self


def owned_deletion_closure(deleted: Iterable[Identity], relations: Iterable[Relation]) -> frozenset[Identity]:
    result = set(deleted)
    relations = tuple(relations)
    while True:
        descendants = {edge.target for edge in relations
                       if edge.relationship == "owned" and edge.source in result}
        if descendants <= result:
            return frozenset(result)
        result.update(descendants)


class RelationColumn(Contract):
    parent_table: str
    parent_column: str = "id"
    child_table: str
    child_column: str
    relationship: Literal["owned", "link"]
    on_missing: Literal["delete_row", "unavailable"] = "delete_row"
    discriminator_column: str | None = None
    discriminator_value: str | None = None

    @model_validator(mode="after")
    def discriminator_is_complete(self):
        if (self.discriminator_column is None) != (self.discriminator_value is None):
            raise ValueError("Polymorphic relations require both discriminator column and value")
        return self


# Reviewed proposals, never executed SQL. Parent extends its installed registry.
RELATION_PROPOSALS = (
    RelationColumn(parent_table="learn_threads", child_table="learn_conversations", child_column="thread_id", relationship="owned"),
    RelationColumn(parent_table="case_sessions", child_table="case_conversations", child_column="case_id", relationship="owned"),
    RelationColumn(parent_table="study_projects", child_table="study_project_chats", child_column="project_id", relationship="link"),
    RelationColumn(parent_table="study_projects", child_table="study_project_documents", child_column="project_id", relationship="link"),
    RelationColumn(parent_table="knowledge_revisions", child_table="study_project_documents", child_column="revision_id", relationship="link"),
    RelationColumn(parent_table="study_projects", child_table="study_project_goals", child_column="project_id", relationship="owned"),
    *(RelationColumn(parent_table=table, child_table=child, child_column="chat_id",
                     relationship=relationship, discriminator_column="chat_kind", discriminator_value=kind)
      for table, kind in (("learn_threads", "learning"), ("case_sessions", "case"))
      for child, relationship in (("study_project_chats", "link"), ("knowledge_attachments", "owned"))),
    RelationColumn(parent_table="knowledge_attachments", child_table="knowledge_attachment_originals", child_column="attachment_id", relationship="owned"),
    RelationColumn(parent_table="assessment_tests", child_table="assessment_test_versions", child_column="test_id", relationship="owned"),
    RelationColumn(parent_table="assessment_test_attempts", child_table="assessment_attempt_drafts", child_column="attempt_id", relationship="owned"),
    RelationColumn(parent_table="assessment_test_attempts", child_table="assessment_attempt_exposure", child_column="attempt_id", relationship="owned"),
)
# Provenance is never a pruning edge or a hard version FK. Keep pinned IDs and
# independent payloads; only the separate live pointer may become unavailable.
UNAVAILABLE_REFERENCE_COLUMNS = (
    ("assessment_test_attempts", "version_id", "live_version_id"),
    ("assessment_question_reports", "version_id", "live_version_id"),
    ("assessment_question_reports", "attempt_id", "live_attempt_id"),
    ("assessment_test_jobs", "published_version_id", "live_published_version_id"),
)
MIGRATION_RESERVATIONS = {
    "learn-002": "saved Learn sidecar", "cases-003": "saved Case sidecar",
    "knowledge-003": "owned attachment references", "study-002": "projects and memberships",
    "assessment-003": "saved tests, versions, reports and jobs",
    "assessment-004": "new whole-attempt drafts, exposure and timing",
}

# Scalar row inventories for the producer's additive migration proposal. These
# describe only new tables. They neither execute DDL nor modify legacy columns.
TABLE_COLUMNS = {
    "learn_conversations": ("thread_id", "lifecycle", "revision", "draft_text", "draft_refs_json", "draft_revision", "updated_at"),
    "case_conversations": ("case_id", "lifecycle", "revision", "draft_text", "draft_refs_json", "draft_revision", "updated_at"),
    "study_projects": ("id", "title", "lifecycle", "revision", "created_at", "updated_at"),
    "study_project_chats": ("id", "project_id", "chat_kind", "chat_id", "position", "revision", "created_at"),
    "study_project_documents": ("id", "project_id", "revision_id", "position", "revision", "created_at"),
    "study_project_goals": ("id", "project_id", "title", "topic_id", "target_date", "progress_kind", "revision", "created_at", "updated_at"),
    "knowledge_attachments": ("id", "chat_kind", "chat_id", "title", "media_type", "revision", "extraction_state", "index_state", "created_at", "updated_at"),
    "knowledge_attachment_originals": ("id", "attachment_id", "role", "original_path", "sha256", "bytes", "created_at"),
    "assessment_tests": ("id", "title", "lifecycle", "revision", "created_at", "updated_at"),
    "assessment_test_versions": ("id", "test_id", "ordinal", "origin", "review_quality", "status", "items_json", "source_refs_json", "terms", "sha256", "created_at"),
    "assessment_test_attempts": ("id", "version_id", "live_version_id", "version_snapshot_json", "mode", "status", "draft_revision", "committed_json", "result_json", "timing_kind", "duration_seconds", "started_at", "deadline_at", "paused_seconds", "last_reconciled_at", "created_at", "updated_at", "finalized_at"),
    "assessment_attempt_drafts": ("attempt_id", "revision", "position", "answers_json", "updated_at"),
    "assessment_attempt_exposure": ("id", "attempt_id", "item_id", "question_id", "question_version", "key_version", "family_id", "family_version", "kind", "created_at"),
    "assessment_question_reports": ("id", "version_id", "live_version_id", "attempt_id", "live_attempt_id", "item_id", "question_id", "question_version", "key_version", "family_id", "family_version", "report_text", "idempotency_key", "created_at"),
    "assessment_test_jobs": ("id", "operation", "state", "idempotency_key", "request_hash", "inputs_json", "checkpoint_json", "settings_revision", "policy_revision", "context_epoch", "requested_count", "validated_count", "published_version_id", "live_published_version_id", "error_code", "created_at", "updated_at"),
}


class WorkspaceTab(Contract):
    content: ContentReference
    context: Identity
    retention: Literal["saved"] = "saved"
    position: Locator | None = None

    @model_validator(mode="after")
    def saved_context(self):
        if self.context.type not in ("learn_thread", "case", "project"):
            raise ValueError("Workspace context must resolve to a saved chat or project")
        return self


class Option(Contract):
    id: Identifier
    text: Annotated[str, Field(min_length=1, max_length=2000)]


class QuestionSnapshot(Contract):
    item_id: Identifier
    question_id: Identifier
    question_version: Identifier
    key_version: Identifier | None = None
    family_id: Identifier
    family_version: Identifier
    topic_id: Identifier
    stem: Annotated[str, Field(min_length=1, max_length=6000)]
    options: tuple[Option, ...] = Field(min_length=2, max_length=20)
    correct_option_ids: tuple[Identifier, ...] = Field(default=(), max_length=20)
    explanation: Annotated[str, Field(max_length=6000)] = ""

    @model_validator(mode="after")
    def usable_options(self):
        options = {option.id for option in self.options}
        if len(options) != len(self.options) or len(set(self.correct_option_ids)) != len(self.correct_option_ids):
            raise ValueError("Question options and keys must be unique")
        if not set(self.correct_option_ids) <= options:
            raise ValueError("Keys must identify supplied options")
        return self


class SavedTest(Contract):
    id: Identifier
    title: Annotated[str, Field(min_length=1, max_length=120)]
    lifecycle: Lifecycle = "active"
    revision: Revision


class SavedTestVersion(Contract):
    id: Identifier
    test_id: Identifier
    ordinal: Revision
    origin: Literal["reviewed_bank", "generated", "imported", "nightly"]
    review_quality: Literal["reviewed", "personal", "needs_review"]
    status: Literal["ready", "needs_review"]
    items: tuple[QuestionSnapshot, ...] = Field(min_length=1, max_length=50)
    source_refs: tuple[ContentReference, ...] = Field(default=(), max_length=50)
    terms: Annotated[str, Field(min_length=1, max_length=2000)]
    created_at: AwareDatetime

    @model_validator(mode="after")
    def ready_and_distinct(self):
        if self.review_quality == "reviewed" and self.origin != "reviewed_bank":
            raise ValueError("Personal tests cannot acquire reviewed-bank quality")
        if self.status == "ready" and (self.review_quality == "needs_review" or any(
                not item.correct_option_ids or not item.key_version for item in self.items)):
            raise ValueError("Ready requires resolved question/key versions")
        for values in ((item.item_id for item in self.items), (item.family_id for item in self.items)):
            values = tuple(values)
            if len(set(values)) != len(values):
                raise ValueError("A saved version cannot duplicate item/family identity")
        return self

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def bank_cohort_eligible(self) -> bool:
        return self.origin == "reviewed_bank" and self.review_quality == "reviewed" and self.status == "ready"


class Timing(Contract):
    kind: Literal["untimed", "timed"] = "untimed"
    duration_seconds: Annotated[int, Field(ge=1, le=86400, strict=True)] | None = None
    started_at: AwareDatetime | None = None
    deadline_at: AwareDatetime | None = None
    paused_seconds: Annotated[int, Field(ge=0, strict=True)] = 0
    last_reconciled_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def coherent_timing(self):
        if self.kind == "untimed" and any(value is not None for value in
                (self.duration_seconds, self.started_at, self.deadline_at)):
            raise ValueError("Untimed attempts cannot have an active deadline")
        if self.kind == "timed" and (self.duration_seconds is None or self.started_at is None or self.deadline_at is None):
            raise ValueError("Running timed attempts need backend start/deadline")
        if self.deadline_at and self.started_at and self.deadline_at <= self.started_at:
            raise ValueError("Deadline must follow start")
        return self


class CommittedAnswer(Contract):
    item_id: Identifier
    option_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)
    committed_at: AwareDatetime
    correct: Annotated[bool, Field(strict=True)]
    assisted: Annotated[bool, Field(strict=True)]
    repeat: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("Committed choices must be unique")
        return self


class AttemptResult(Contract):
    item_count: Annotated[int, Field(ge=1, le=50, strict=True)]
    answered_count: Annotated[int, Field(ge=0, le=50, strict=True)]
    unanswered_count: Annotated[int, Field(ge=0, le=50, strict=True)]
    excluded_count: Annotated[int, Field(ge=0, le=50, strict=True)]
    scored_count: Annotated[int, Field(ge=0, le=50, strict=True)]
    correct_count: Annotated[int, Field(ge=0, le=50, strict=True)]
    completed_at: AwareDatetime

    @model_validator(mode="after")
    def coherent_counts(self):
        if self.answered_count + self.unanswered_count + self.excluded_count != self.item_count:
            raise ValueError("Result categories must cover the actual selected count")
        if not self.correct_count <= self.scored_count <= self.item_count - self.excluded_count:
            raise ValueError("Result denominator must exclude invalid items")
        return self


class TestAttempt(Contract):
    id: Identifier
    version: TestVersionIdentity
    mode: Literal["study", "test"]
    status: Literal["active", "paused", "timer_expired", "submitted", "ended"]
    draft_revision: Annotated[int, Field(ge=0, strict=True)] = 0
    committed: tuple[CommittedAnswer, ...] = Field(default=(), max_length=50)
    result: AttemptResult | None = None
    timing: Timing = Field(default_factory=Timing)

    @model_validator(mode="after")
    def test_never_pauses(self):
        if self.mode == "test" and (self.status in ("paused", "timer_expired", "ended") or self.timing.paused_seconds):
            raise ValueError("Test deadlines cannot pause or leave an unsubmitted expiry")
        if self.mode == "test" and self.status == "active" and (self.committed or self.result is not None):
            raise ValueError("Active Test responses cannot expose scored answers or results")
        if len({answer.item_id for answer in self.committed}) != len(self.committed):
            raise ValueError("Committed answers must be unique per item")
        if self.result is not None and self.status not in ("submitted", "ended"):
            raise ValueError("Only finalised attempts have terminal results")
        return self


def disclosure_allowed(attempt: TestAttempt | None, operation: str) -> bool:
    """Backend-owned active attempt only; permissions remain separate checks."""
    if attempt is None or attempt.mode != "test" or attempt.status == "submitted":
        return True
    return operation in {"health", "connection_status", "settings", "recovery_status",
                         "present_question", "save_draft", "resume_attempt", "submit_test", "report_question"}


def test_deadline_reached(attempt: TestAttempt, now: datetime) -> bool:
    """Reconcile with persisted clock high-water; producer atomically finalises."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Clock reconciliation requires an aware server timestamp")
    if attempt.mode != "test" or attempt.status != "active" or attempt.timing.kind != "timed":
        return False
    effective_now = max(now, attempt.timing.last_reconciled_at or now)
    return effective_now >= attempt.timing.deadline_at


class PersistedAttemptPin(Contract):
    """Private storage shape; never return its keys in a pre-submit response."""
    attempt_id: Identifier
    version_id: Identifier
    live_version_id: Identifier | None
    version_snapshot: SavedTestVersion

    @model_validator(mode="after")
    def pinned_original_survives(self):
        if self.version_id != self.version_snapshot.id:
            raise ValueError("The independent attempt snapshot must retain the original version ID")
        if self.live_version_id is not None and self.live_version_id != self.version_id:
            raise ValueError("A live pointer cannot repin historical work")
        return self


class DraftAnswer(Contract):
    item_id: Identifier
    option_ids: tuple[Identifier, ...] = Field(default=(), max_length=20)
    marked: Annotated[bool, Field(strict=True)] = False

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("Draft choices must be unique")
        return self


class AttemptDraft(Contract):
    attempt_id: Identifier
    version_id: Identifier
    revision: Annotated[int, Field(ge=0, strict=True)]
    position: Annotated[int, Field(ge=0, le=49, strict=True)]
    answers: tuple[DraftAnswer, ...] = Field(max_length=50)

    @model_validator(mode="after")
    def unique_items(self):
        if len({answer.item_id for answer in self.answers}) != len(self.answers):
            raise ValueError("A draft must contain one choice set per item")
        return self


def validate_attempt_draft(draft: AttemptDraft, attempt: TestAttempt, version: SavedTestVersion):
    if draft.attempt_id != attempt.id or draft.version_id != version.id or attempt.version.id != version.id:
        raise ValueError("Draft and attempt must pin the same saved version")
    if draft.position >= version.item_count:
        raise ValueError("Draft position is outside the pinned version")
    items = {item.item_id: item for item in version.items}
    for answer in draft.answers:
        if answer.item_id not in items or not set(answer.option_ids) <= {o.id for o in items[answer.item_id].options}:
            raise ValueError("Draft choices must belong to the pinned item")
    return draft


class Exposure(Contract):
    id: Identifier
    attempt_id: Identifier
    version_id: Identifier
    item_id: Identifier
    question_id: Identifier
    question_version: Identifier
    key_version: Identifier
    family_id: Identifier
    family_version: Identifier
    kind: Literal["presented", "hint", "sources", "notes", "chat", "answered", "reviewed"]
    created_at: AwareDatetime


class Dependency(Contract):
    target: Identity
    expected_revision: Identifier


class EligibleInput(Contract):
    kind: Literal["memory", "learning_summary", "fictional_case_summary", "goal", "preferences", "committed_evidence"]
    dependency: Dependency
    retention: Literal["saved"] = "saved"
    content_class: Literal["general_learning"] = "general_learning"

    @model_validator(mode="after")
    def no_raw_context(self):
        expected = {"memory": "memory_revision", "learning_summary": "learning_evidence",
                    "fictional_case_summary": "learning_evidence", "goal": "goal",
                    "preferences": "preferences", "committed_evidence": "learning_evidence"}
        if self.dependency.target.type != expected[self.kind]:
            raise ValueError("Personalisation accepts eligible learning references, not raw case/key/original references")
        return self


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


class FictionalTestArtifact(Contract):
    id: Identifier
    boundary_version: Literal["fictional-test/1"] = "fictional-test/1"
    validation_id: Identifier
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    questions: tuple[QuestionSnapshot, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validated_shape(self):
        content = [question.model_dump(mode="json") for question in self.questions]
        if canonical_digest(content) != self.sha256:
            raise ValueError("Fictional artifact must match its validated content digest")
        if any(not q.correct_option_ids or not q.key_version for q in self.questions):
            raise ValueError("Fictional artifact requires validated questions/keys")
        if len({q.family_id for q in self.questions}) != len(self.questions):
            raise ValueError("Fictional artifact cannot duplicate question families")
        return self


def _normalise(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def reject_temporary_metadata(value: Contract, forbidden_fragments: Iterable[str]):
    """Trusted volatile registry supplies IDs/sentinels, never persisted here."""
    def strings(item):
        if isinstance(item, str):
            yield _normalise(item)
        elif isinstance(item, dict):
            for key, child in item.items():
                yield _normalise(key)
                yield from strings(child)
        elif isinstance(item, (tuple, list)):
            for child in item:
                yield from strings(child)
    content = tuple(strings(value.model_dump(mode="json")))
    if any(fragment and any(_normalise(fragment) in text for text in content)
           for fragment in forbidden_fragments):
        raise ValueError("Temporary content or metadata cannot cross the durable boundary")


def validate_fictional_artifact(
    questions: Iterable[QuestionSnapshot], *, artifact_id: str, validation_id: str,
    privacy_check: Callable[[tuple[QuestionSnapshot, ...]], bool],
    forbidden_fragments: Iterable[str],
) -> FictionalTestArtifact:
    """Producer must run a real privacy review in memory; no renderer attestation."""
    questions = tuple(questions)
    artifact = FictionalTestArtifact(id=artifact_id, validation_id=validation_id, questions=questions,
                                    sha256=canonical_digest([q.model_dump(mode="json") for q in questions]))
    reject_temporary_metadata(artifact, forbidden_fragments)
    if privacy_check(questions) is not True:
        raise ValueError("Fictional artifact requires a successful trusted privacy review")
    return artifact


class Job(Contract):
    id: Identifier
    operation: Literal["daily_suggestions", "generate_test", "nightly_test"]
    idempotency_key: Annotated[str, Field(min_length=8, max_length=128)]
    state: Literal["queued", "running", "needs_review", "failed", "cancelled", "published"]
    inputs: tuple[EligibleInput, ...] = Field(default=(), max_length=100)
    settings_revision: Revision
    policy_revision: Revision
    context_epoch: Annotated[int, Field(ge=0, strict=True)] = 0
    requested_count: Literal[5, 10, 20] | None = None
    validated_count: Annotated[int, Field(ge=0, le=20, strict=True)] = 0
    fictional_artifact: FictionalTestArtifact | None = None
    published_version: TestVersionIdentity | None = None

    @model_validator(mode="after")
    def publication(self):
        if self.operation != "daily_suggestions" and self.requested_count is None:
            raise ValueError("Test jobs require an explicit 5/10/20 count")
        if self.requested_count and self.validated_count > self.requested_count:
            raise ValueError("Validated progress cannot exceed the requested count")
        if self.operation != "daily_suggestions":
            if (self.state == "published") != (self.published_version is not None):
                raise ValueError("Only a published job may carry its durable result")
            if self.state == "published" and self.validated_count != self.requested_count:
                raise ValueError("Incomplete work cannot become a Ready test")
        if self.operation == "nightly_test" and self.fictional_artifact is not None:
            raise ValueError("Nightly input cannot come from temporary transformation")
        return self


def publication_decision(job: Job, current_revisions: Mapping[tuple[str, str], str], *,
                         settings_revision: int, policy_revision: int, context_epoch: int,
                         enabled: bool = True) -> str:
    """Pure proposal; caller must perform these checks inside its write transaction."""
    if job.state in ("published", "cancelled"):
        return job.state
    if job.state not in ("queued", "running"):
        return "not_ready"
    if not enabled or job.settings_revision != settings_revision or job.policy_revision != policy_revision or job.context_epoch != context_epoch:
        return "invalidated"
    if any(current_revisions.get(item.dependency.target.key) != item.dependency.expected_revision for item in job.inputs):
        return "invalidated"
    if job.requested_count and job.validated_count != job.requested_count:
        return "not_ready"
    return "publishable"


def require_durable_conversation(conversation: Conversation):
    if conversation.retention != "saved" or conversation.lifecycle == "deleted":
        raise ValueError("Only live saved conversation metadata may be durable")
    return conversation


class ErrorDetail(Contract):
    code: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")]
    message: Annotated[str, Field(min_length=1, max_length=500)]
    retryable: Annotated[bool, Field(strict=True)]


class ErrorEnvelope(Contract):
    error: ErrorDetail


def request_fingerprint(operation: str, target: Identity, request: Contract) -> str:
    return canonical_digest({"operation": operation, "target": target.model_dump(mode="json"),
                             "request": request.model_dump(mode="json")})


class LegacyAssessmentView(Contract):
    session_id: Identifier
    origin: Literal["reviewed", "generated"]
    compatibility: Literal["legacy_study"] = "legacy_study"
    committed_answer_ids: tuple[Identifier, ...]
    denominator: Annotated[int, Field(ge=0, strict=True)]
    unanswered_not_scored: Annotated[int, Field(ge=0, strict=True)]
    presented_item_ids: tuple[Identifier, ...]
    assisted_item_ids: tuple[Identifier, ...]


def legacy_contract_views(bundle: dict) -> tuple[tuple[Conversation, ...], tuple[LegacyAssessmentView, ...]]:
    """Read-only fixture adapter, not production backup conversion/validation.

    Parent validates complete source inventory/media and installs additive rows.
    This helper never rewrites records or interprets absence as Save.
    """
    if bundle.get("format") != "renulus-canonical-export" or type(bundle.get("format_version")) is not int or \
            bundle["format_version"] != 1 or type(bundle.get("schema_version")) is not int or bundle["schema_version"] != 1:
        raise ValueError("Only known schema-1 record exports have legacy views")
    records = bundle["records"]
    conversations = []
    for table, kind, owner in (("learn_threads", "learning", "learn_thread"), ("case_sessions", "case", "case")):
        for row in records.get(table, []):
            if table == "case_sessions" and not row.get("saved_at"):
                raise ValueError("A legacy case needs its explicit saved snapshot")
            conversations.append(Conversation(identity=ConversationIdentity(type=owner, id=row["id"]),
                kind=kind, retention="saved", revision=row.get("revision", 1), title=row["title"],
                created_at=row["created_at"], updated_at=row["updated_at"]))
    sessions = []
    for prefix, origin in (("assessment", "reviewed"), ("assessment_generated", "generated")):
        for row in records.get(prefix + "_sessions", []):
            items = [item for item in records.get(prefix + "_items", []) if item["session_id"] == row["id"]]
            answers = [answer for answer in records.get(prefix + "_attempts", []) if answer["session_id"] == row["id"]]
            sessions.append(LegacyAssessmentView(session_id=row["id"], origin=origin,
                committed_answer_ids=tuple(answer["id"] for answer in answers), denominator=len(answers),
                unanswered_not_scored=len(items) - len(answers),
                presented_item_ids=tuple(item["id"] for item in items if item.get("presented_at") or item.get("presented")),
                assisted_item_ids=tuple(item["id"] for item in items if item["assisted"])))
    return tuple(conversations), tuple(sessions)
