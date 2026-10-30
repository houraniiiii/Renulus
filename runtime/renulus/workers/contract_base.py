"""Shared strict worker contract primitives; no command or broker imports.

worker_contracts reexports these names for existing clients. Keeping this module
independent lets the closed command union refer to broker-owned models without
making their direct import circular.
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

PROTOCOL = "renulus-worker/1"
MAX_FRAME_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 256 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
Id = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$(?![\s\S])")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$(?![\s\S])")]
Counter = Annotated[int, Field(ge=0, le=9007199254740991)]
Size = Annotated[int, Field(ge=0, le=MAX_ARTIFACT_BYTES)]
PathString = Annotated[str, Field(min_length=1, max_length=4096)]
Retention = Literal["saved", "temporary"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False,
                              regex_engine="python-re")


class ProcessIdentity(Model):
    profile_id: Id
    domain_store_id: Id
    runtime_store_id: Id
    authority_epoch: Counter
    process_generation: Id


class Identity(ProcessIdentity):
    operation_id: Id
    attempt_id: Id
    request_id: Id


class Revisions(Model):
    configuration: Counter
    grant: Counter
    context: Counter
    deletion: Counter
    cancellation: Counter


class OutputGrant(Model):
    artifact_handle: Id
    artifact_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    max_bytes: Annotated[int, Field(ge=1, le=MAX_ARTIFACT_BYTES)]
    expires_at_ms: Counter
    reservation_id: Id
    intent_id: Id


class ArtifactResult(Model):
    tag: Literal["artifact"] = "artifact"
    artifact_handle: Id
    artifact_revision: Annotated[int, Field(ge=1, le=9007199254740991)]
    artifact_sha256: Digest
    bytes: Size
    engine: Annotated[str, Field(min_length=1, max_length=128)]
    pages: Annotated[int, Field(ge=0, le=300)] | None = None
    next_cursor: Size | None = None
