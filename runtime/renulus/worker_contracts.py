"""Source of truth for renulus-worker/1; generate JSON Schema and TS with
``python -m renulus.workers.generate``. No service or database imports here.
"""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal, Union

from pydantic import Field, TypeAdapter, field_validator, model_validator

from .workers.contract_base import (PROTOCOL, MAX_FRAME_BYTES, MAX_CHUNK_BYTES, MAX_ARTIFACT_BYTES,
    Id, Digest, Counter, Size, PathString, Retention, Model, ProcessIdentity, Identity,
    Revisions, OutputGrant, ArtifactResult)
from .workers.broker_models import (BrokerBounds, CredentialAuthority, CredentialResult, LoginId, Provider,
    TransportPlan, TransportResult)
from .workers.native_contracts import NativePaths, NativeInput
OUTCOMES = ("rejected_before_admission", "accepted_pending", "committed_reference",
            "cancelled_settled", "uncertain_after_disconnect")
UNAVAILABLE_COMMANDS = (
    "native.inspect", "native.publish", "native.dispose", "transport.send", "transport.cancel",
)
SUPPORTED_COMMANDS = ("worker.settle", "artifact.upload", "artifact.read",
                      "embedding.embed", "document.extract", "document.chunk",
                      "library.query", "library.stage", "library.remove", "library.maintain",
                      "memory.extract", "memory.recall", "memory.reconcile", "memory.purge",
                      "native.io", "transport.execute", "credential.activate", "credential.metadata",
                      "credential.connect", "credential.refresh", "credential.forget",
                      "credential.login-status", "credential.login-cancel")

PRODUCT_ENDPOINTS = ("https://api.openai.com/v1/responses",
                     "https://opencode.ai/zen/go/v1/chat/completions")


class Capacity(Model):
    max_frame_bytes: Annotated[int, Field(ge=8192, le=MAX_FRAME_BYTES)] = MAX_FRAME_BYTES
    max_chunk_bytes: Annotated[int, Field(ge=1, le=MAX_CHUNK_BYTES)] = MAX_CHUNK_BYTES
    data_in_flight: Annotated[int, Field(ge=1, le=16)] = 16
    data_queued: Annotated[int, Field(ge=0, le=64)] = 64
    control_slots: Annotated[int, Field(ge=1, le=8)] = 8
    document_tasks: Annotated[int, Field(ge=1, le=2)] = 2
    artifact_bytes: Annotated[int, Field(ge=1, le=128 * 1024 * 1024)] = 128 * 1024 * 1024
    artifact_count: Annotated[int, Field(ge=1, le=128)] = 128
    request_count: Annotated[int, Field(ge=1, le=4096)] = 4096


class HelperPaths(Model):
    helpers_root: PathString
    cache_root: PathString
    source_root: PathString


class DerivedPaths(Model):
    # Immutable host-selected, derived-only namespace. No command supplies paths.
    root: PathString
    namespace: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$(?![\s\S])")]
    library_tombstones: Annotated[list[Id], Field(max_length=4096)]
    memory_tombstones: Annotated[list[Id], Field(max_length=4096)]


class BrokerPaths(Model):
    # Protected launch authority only. No command can select these paths, bounds
    # or synthetic endpoints. Construction does not open the account store.
    profile_root: PathString
    state_root: PathString
    bounds: BrokerBounds = Field(default_factory=BrokerBounds)


class LaunchConfig(Model):
    protocol: Literal["renulus-worker/1"] = PROTOCOL
    identity: ProcessIdentity
    revisions: Revisions
    retention: Retention
    launch_token_sha256: Digest
    capacity: Capacity = Field(default_factory=Capacity)
    helpers: HelperPaths | None = None
    derived: DerivedPaths | None = None
    broker: BrokerPaths | None = None
    native: NativePaths | None = None


class Hello(Model):
    protocol: Literal["renulus-worker/1"]
    kind: Literal["hello"]
    launch_token: Annotated[str, Field(min_length=32, max_length=256)]
    expected_launcher_pid: Annotated[int, Field(ge=1, le=4294967295)]
    identity: ProcessIdentity
    capacity: Capacity


class ProcessAttestation(Model):
    launcher_pid: Annotated[int, Field(ge=1, le=4294967295)]
    actual_pid: Annotated[int, Field(ge=1, le=4294967295)]
    launcher_creation_filetime: Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[0-9]+$(?![\s\S])")]
    actual_creation_filetime: Annotated[str, Field(min_length=1, max_length=20, pattern=r"^[0-9]+$(?![\s\S])")]
    ancestry_depth: Annotated[int, Field(ge=0, le=16)]


class Ready(Model):
    protocol: Literal["renulus-worker/1"] = PROTOCOL
    kind: Literal["ready"] = "ready"
    identity: ProcessIdentity
    pid: Annotated[int, Field(ge=1, le=9007199254740991)]
    parent_pid: Annotated[int, Field(ge=0, le=9007199254740991)]
    process: ProcessAttestation
    capacity: Capacity
    supported_commands: Annotated[list[Id], Field(max_length=32)]
    unavailable_commands: Annotated[list[Id], Field(max_length=32)]


class Limits(Model):
    result_page_bytes: Annotated[int, Field(ge=1, le=MAX_CHUNK_BYTES)]
    cpu_seconds: Annotated[int, Field(ge=1, le=120)]


class ByteRange(Model):
    offset: Size
    length: Size


class ArtifactGrant(Model):
    """Minted by the trusted host; never a caller path, URL or database key."""
    artifact_handle: Id
    artifact_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    artifact_sha256: Digest
    bytes: Size
    expires_at_ms: Counter
    rights: Annotated[list[Literal["read", "extract", "chunk"]], Field(min_length=1, max_length=3)]
    permitted_ranges: Annotated[list[ByteRange], Field(min_length=1, max_length=8)]
    reservation_id: Id
    intent_id: Id


class UploadInput(Model):
    artifact: ArtifactGrant
    offset: Size
    data_base64: Annotated[str, Field(max_length=349528, pattern=r"^[A-Za-z0-9+/]*={0,2}$(?![\s\S])")]
    final: bool


class ReadInput(Model):
    artifact_handle: Id
    artifact_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    offset: Size
    length: Annotated[int, Field(ge=1, le=MAX_CHUNK_BYTES)]


class EmbedInput(Model):
    texts: Annotated[list[Annotated[str, Field(min_length=1, max_length=16384)]], Field(min_length=1, max_length=64)]
    query: bool
    output: OutputGrant


class ExtractInput(Model):
    artifact_handle: Id
    artifact_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    offset: Size
    length: Size
    format: Literal["txt", "md", "pdf", "png", "jpg", "jpeg", "tif", "tiff", "csv", "html", "xml", "docx", "xlsx"]
    title: Annotated[str, Field(min_length=1, max_length=256)]
    output: OutputGrant


class ChunkInput(Model):
    artifact_handle: Id
    artifact_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    offset: Size
    length: Size
    output: OutputGrant


class LibraryPassage(Model):
    passage_id: Id
    text: Annotated[str, Field(min_length=1, max_length=16384)]


class LibraryBatch(Model):
    passages: Annotated[list[LibraryPassage], Field(min_length=1, max_length=12000)]


class LibraryStageInput(ChunkInput):
    document_id: Id
    revision_id: Id


class LibraryQueryInput(Model):
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    allowed_revision_ids: Annotated[list[Id], Field(max_length=256)]
    limit: Annotated[int, Field(ge=1, le=30)]
    output: OutputGrant


class LibraryRemoveInput(Model):
    revision_ids: Annotated[list[Id], Field(max_length=256)]
    output: OutputGrant


class LibraryMaintainInput(LibraryRemoveInput):
    optimize: bool


class MemoryRecord(Model):
    id: Id
    revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    scope: Literal["study", "library", "generated-practice", "reviewed-assessment"]
    topic_id: Id | None
    kind: Literal["learning-point", "preference", "goal", "study-interest", "mistake"]


class MemoryBatch(Model):
    records: Annotated[list[MemoryRecord], Field(max_length=128)]


class MemoryRef(Model):
    canonical_id: Id
    canonical_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    engine_id: Id


class MemoryRecallInput(Model):
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    accepted: Annotated[list[MemoryRef], Field(max_length=256)]
    limit: Annotated[int, Field(ge=1, le=30)]
    output: OutputGrant


class MemoryReconcileInput(ChunkInput):
    # Stage canonical snapshots. Prior accepted rows survive until explicit purge.
    pass


class MemoryPurgeInput(Model):
    canonical_ids: Annotated[list[Id], Field(max_length=256)]
    output: OutputGrant


class CapturePlan(Model):
    plan_id: Id
    evidence_receipt: Id
    support_sha256: Digest
    source_sha256: Digest
    expires_at_ms: Counter
    max_calls: Literal[1]


class MemoryExtractInput(ChunkInput):
    capture_plan: CapturePlan


class GenerationMessage(Model):
    role: Literal["system", "user", "assistant"]
    content: Annotated[str, Field(max_length=131072)]


class GenerationSettlement(Model):
    callback_id: Id
    plan_id: Id
    generation_sha256: Digest
    status: Literal["completed", "cancelled", "failed"]
    output: Annotated[str, Field(max_length=16000)] | None


class SettleTarget(Model):
    identity: Identity
    request_sha256: Digest
    worker_lease: Id


class SettleInput(Model):
    action: Literal["query", "cancel", "revoke", "release", "close", "generation"]
    target: SettleTarget | None = None
    revisions: Revisions | None = None
    artifact_handle: Id | None = None
    generation: GenerationSettlement | None = None


class EmptyInput(Model):
    pass


class CredentialInput(Model):
    provider_id: Provider
    authority: CredentialAuthority


class CredentialLoginInput(CredentialInput):
    provider_id: Literal["codex"]
    login_id: LoginId


class Envelope(Identity):
    protocol: Literal["renulus-worker/1"]
    kind: Literal["command"]
    payload_sha256: Digest
    configuration_revision: Counter
    grant_revision: Counter
    context_epoch: Counter
    deletion_epoch: Counter
    cancellation_epoch: Counter
    retention: Retention
    expected_revision: Id | None
    limits: Limits


class UploadCommand(Envelope):
    command: Literal["artifact.upload"]
    input: UploadInput


class ReadCommand(Envelope):
    command: Literal["artifact.read"]
    input: ReadInput


class EmbedCommand(Envelope):
    command: Literal["embedding.embed"]
    input: EmbedInput


class ExtractCommand(Envelope):
    command: Literal["document.extract"]
    input: ExtractInput


class ChunkCommand(Envelope):
    command: Literal["document.chunk"]
    input: ChunkInput


class SettleCommand(Envelope):
    command: Literal["worker.settle"]
    input: SettleInput


class LibraryQueryCommand(Envelope):
    command: Literal["library.query"]
    input: LibraryQueryInput


class LibraryStageCommand(Envelope):
    command: Literal["library.stage"]
    input: LibraryStageInput


class LibraryRemoveCommand(Envelope):
    command: Literal["library.remove"]
    input: LibraryRemoveInput


class LibraryMaintainCommand(Envelope):
    command: Literal["library.maintain"]
    input: LibraryMaintainInput


class MemoryRecallCommand(Envelope):
    command: Literal["memory.recall"]
    input: MemoryRecallInput


class MemoryReconcileCommand(Envelope):
    command: Literal["memory.reconcile"]
    input: MemoryReconcileInput


class MemoryPurgeCommand(Envelope):
    command: Literal["memory.purge"]
    input: MemoryPurgeInput


class MemoryExtractCommand(Envelope):
    command: Literal["memory.extract"]
    input: MemoryExtractInput


class TransportExecuteCommand(Envelope):
    command: Literal["transport.execute"]
    # Exact broker plan, with product-only endpoint constraints also present in
    # JSON Schema. Synthetic launch injection is a Python test seam only.
    input: TransportPlan = Field(json_schema_extra={"allOf": [{"properties": {
        "route": {"properties": {"endpoint": {"enum": list(PRODUCT_ENDPOINTS)}}},
        "serialized_request": {"properties": {"url": {"enum": list(PRODUCT_ENDPOINTS)}}},
    }}]})

    @field_validator("input", mode="before")
    @classmethod
    def wire_plan(cls, value):
        # The pipe reader rejects duplicate keys/nonfinite JSON, then validates
        # a Python object. Strict broker tuples must retain JSON array semantics
        # here, without weakening any of the plan's strict scalar validation.
        return TransportPlan.model_validate_json(canonical_json(value)) if isinstance(value, dict) else value

    @model_validator(mode="after")
    def product_endpoint(self):
        expected = PRODUCT_ENDPOINTS[0 if self.input.route.provider_id == "codex" else 1]
        if self.input.route.endpoint != expected or self.input.serialized_request.url != expected:
            raise ValueError("transport requires an exact product endpoint")
        return self


class CredentialStateCommand(Envelope):
    command: Literal["credential.activate", "credential.metadata"]
    input: EmptyInput


class CredentialCommand(Envelope):
    command: Literal["credential.connect", "credential.refresh", "credential.forget"]
    input: CredentialInput


class CredentialLoginCommand(Envelope):
    command: Literal["credential.login-status", "credential.login-cancel"]
    input: CredentialLoginInput


class UnavailableCommand(Envelope):
    command: Literal[*UNAVAILABLE_COMMANDS]
    input: EmptyInput


class NativeIOCommand(Envelope):
    command: Literal['native.io']
    input: NativeInput


Command = Annotated[Union[UploadCommand, ReadCommand, EmbedCommand, ExtractCommand,
                          ChunkCommand, SettleCommand, UnavailableCommand, LibraryQueryCommand,
                          LibraryStageCommand, LibraryRemoveCommand, LibraryMaintainCommand,
                          MemoryRecallCommand, MemoryReconcileCommand, MemoryPurgeCommand,
                          MemoryExtractCommand, TransportExecuteCommand, CredentialStateCommand,
                          CredentialCommand, CredentialLoginCommand, NativeIOCommand], Field(discriminator="command")]
COMMAND = TypeAdapter(Command)


class ErrorResult(Model):
    tag: Literal["error"] = "error"
    code: Literal["unsupported_command", "invalid_command", "stale_identity", "stale_revision",
                  "digest_mismatch", "duplicate_request", "overloaded", "artifact_denied",
                  "artifact_invalid", "artifact_limit", "helper_unavailable", "engine_failed",
                  "worker_closed", "deadline_exceeded", "stale_target", "broker_unavailable",
                  "broker_not_activated", "credential_command_failed", "credential_command_invalid",
                  "broker_authority_unbound", "credential_authority_invalid", "credential_authority_expired",
                  "credential_authority_replayed", "credential_endpoint_denied"]
    retryable: bool = False


class UploadResult(Model):
    tag: Literal["upload"] = "upload"
    artifact_handle: Id
    received_bytes: Size
    complete: bool
    credits: Literal[1] = 1


class ReadResult(Model):
    tag: Literal["read"] = "read"
    artifact: ArtifactResult
    offset: Size
    data_base64: Annotated[str, Field(max_length=349528)]
    next_cursor: Size | None
    credits: Literal[1] = 1


class StateResult(Model):
    tag: Literal["state"] = "state"
    active: Annotated[int, Field(ge=0, le=80)]
    closing: bool


class PendingResult(Model):
    tag: Literal["pending"] = "pending"


class CancelledResult(Model):
    tag: Literal["cancelled"] = "cancelled"


Result = Annotated[Union[ErrorResult, ArtifactResult, UploadResult, ReadResult, StateResult,
                         PendingResult, CancelledResult, TransportResult, CredentialResult], Field(discriminator="tag")]


class Settlement(Model):
    worker_lease: Id
    state: Literal["pending", "settled", "uncertain"]


class Reply(Model):
    protocol: Literal["renulus-worker/1"] = PROTOCOL
    kind: Literal["reply"] = "reply"
    identity: Identity
    request_sha256: Digest
    revisions: Revisions
    outcome: Literal[*OUTCOMES]
    result: Result
    settlement: Settlement


class GenerationRequest(Model):
    protocol: Literal["renulus-worker/1"] = PROTOCOL
    kind: Literal["generation_request"] = "generation_request"
    target: SettleTarget
    revisions: Revisions
    retention: Retention
    capture_plan: CapturePlan
    callback_id: Id
    generation_sha256: Digest
    messages: Annotated[list[GenerationMessage], Field(max_length=4)]
    # A cancellation signal retains this same binding, with no prompt repetition.
    action: Literal["generate", "cancel"]

    @property
    def result(self):
        # Route callbacks through the existing Writer's reserved control lane.
        # This is not a serialized wire field.
        return StateResult(active=0, closing=False)


Frame = Union[Hello, Ready, Command, Reply, GenerationRequest]
FRAME = TypeAdapter(Frame)


def command_identity(command: Envelope) -> Identity:
    return Identity(**{key: getattr(command, key) for key in Identity.model_fields})


def command_revisions(command: Envelope) -> Revisions:
    return Revisions(configuration=command.configuration_revision, grant=command.grant_revision,
                     context=command.context_epoch, deletion=command.deletion_epoch,
                     cancellation=command.cancellation_epoch)


def canonical_json(value) -> bytes:
    # Sorted keys, compact UTF-8 JSON; input schemas contain no floating numbers.
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def payload_digest(input_value) -> str:
    """SHA256 of the exact *input object* as sent on the wire.
    Identity, epochs, command and limits are separately checked and reply-bound.
    """
    return hashlib.sha256(canonical_json(input_value)).hexdigest()
