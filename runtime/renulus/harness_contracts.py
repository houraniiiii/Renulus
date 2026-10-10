# SPDX-License-Identifier: MIT
"""Additive Harness shapes and pure checks; no stores, migrations or dispatch.

Trusted owners resolve profile, store and retention facts before using these
contracts. Valid JSON is not proof of filesystem ownership or store validation.
"""
import math
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, JsonValue, field_validator, model_validator
from pydantic.json_schema import models_json_schema

from .design_c_contracts import (
    Contract, Conversation, ConversationIdentity, Identifier, Revision,
    require_durable_conversation,
)


CONTRACT_VERSION = "harness/1"
IPC_PROTOCOL = "renulus-harness/1"
OPENCODE_SOURCE = "4b6fea2875e4f2e3e8a8fee181803e54f7056845"
SourceCommit = Literal["4b6fea2875e4f2e3e8a8fee181803e54f7056845"]
RuntimeSchema = Literal["source:4b6fea2875e4f2e3e8a8fee181803e54f7056845"]
Outcome = Literal[
    "rejected_before_admission", "accepted_pending", "committed_reference",
    "cancelled_settled", "uncertain_after_disconnect",
]
_PATH_PART = r"[A-Za-z0-9_-](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?"
_WINDOWS_DEVICE = (r"(?:^|/)(?:[Cc][Oo][Nn]|[Pp][Rr][Nn]|[Aa][Uu][Xx]|[Nn][Uu][Ll]|"
                   r"[Cc][Oo][Mm][1-9]|[Ll][Pp][Tt][1-9])(?:\.|/|$)")
OwnedPath = Annotated[str, Field(min_length=1, max_length=512,
                                  pattern=rf"^{_PATH_PART}(/{_PATH_PART})*$",
                                  json_schema_extra={"not": {"pattern": _WINDOWS_DEVICE}})]


class HarnessContract(Contract):
    model_config = ConfigDict(strict=True)


class OpenCodeEngine(HarnessContract):
    name: Literal["opencode"]
    version: Literal["2.0.26"]
    source_commit: SourceCommit


class StoreSnapshot(HarnessContract):
    store_id: Identifier
    generation: Revision
    path: OwnedPath
    validation: Literal["pending", "valid"]

    @field_validator("path")
    @classmethod
    def no_windows_devices(cls, value: str) -> str:
        reserved = {"con", "prn", "aux", "nul"} | {
            f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
        }
        if any(part.split(".")[0].casefold() in reserved for part in value.split("/")):
            raise ValueError("Store path cannot name a Windows device")
        return value


class DomainStoreSnapshot(StoreSnapshot):
    engine: Literal["renulus-sqlite"]
    schema_version: Annotated[int, Field(ge=2, le=2)]


class RuntimeStoreSnapshot(StoreSnapshot):
    engine: OpenCodeEngine
    schema_version: RuntimeSchema


class PairedStoreManifest(HarnessContract):
    model_config = ConfigDict(json_schema_extra={
        "if": {"properties": {"state": {"const": "active"}}},
        "then": {"properties": {
            "domain_store": {"properties": {"validation": {"const": "valid"}}},
            "runtime_store": {"properties": {"validation": {"const": "valid"}}},
        }},
    })
    contract_version: Literal["harness/1"]
    profile_id: Identifier
    snapshot_generation: Revision
    cohort_source: SourceCommit
    state: Literal["prepared", "active"]
    domain_store: DomainStoreSnapshot
    runtime_store: RuntimeStoreSnapshot

    @model_validator(mode="after")
    def active_pair_is_valid(self):
        if self.domain_store.store_id == self.runtime_store.store_id:
            raise ValueError("Domain and runtime store identities must be distinct")
        domain_path, runtime_path = (store.path.casefold() for store in
                                     (self.domain_store, self.runtime_store))
        if (domain_path == runtime_path or domain_path.startswith(runtime_path + "/")
                or runtime_path.startswith(domain_path + "/")):
            raise ValueError("Domain and runtime store paths must be distinct and disjoint")
        if any(store.generation != self.snapshot_generation for store in
               (self.domain_store, self.runtime_store)):
            raise ValueError("Both stores must belong to the same snapshot generation")
        if self.state == "active" and any(store.validation != "valid" for store in
                                          (self.domain_store, self.runtime_store)):
            raise ValueError("Activation requires validation of both stores")
        return self


def validate_paired_store_manifest(value: object, *, profile_id: str,
                                  domain_store_id: str, runtime_store_id: str,
                                  snapshot_generation: int) -> PairedStoreManifest:
    """Bind an active manifest to the trusted caller's selected profile/stores."""
    manifest = PairedStoreManifest.model_validate(value)
    if (manifest.profile_id, manifest.domain_store.store_id, manifest.runtime_store.store_id,
        manifest.snapshot_generation) != (profile_id, domain_store_id, runtime_store_id,
                                          snapshot_generation):
        raise ValueError("Manifest does not match the caller's store selection")
    if manifest.state != "active":
        raise ValueError("Only an active manifest may be consumed")
    return manifest


class HarnessEngineReference(HarnessContract):
    contract_version: Literal["harness/1"]
    profile_id: Identifier
    store_id: Identifier
    engine: OpenCodeEngine
    session_id: Identifier


class SavedConversationMapping(HarnessContract):
    contract_version: Literal["harness/1"]
    conversation: ConversationIdentity
    retention: Literal["saved"]
    runtime: HarnessEngineReference


def map_saved_conversation(conversation: Conversation, reference: HarnessEngineReference,
                           *, manifest: PairedStoreManifest) -> SavedConversationMapping:
    """Compose an existing domain identity with its persistent engine reference."""
    require_durable_conversation(conversation)
    if (manifest.state != "active" or reference.profile_id != manifest.profile_id
            or reference.store_id != manifest.runtime_store.store_id
            or reference.engine != manifest.runtime_store.engine):
        raise ValueError("Mapping must reference this profile's active runtime store")
    return SavedConversationMapping(contract_version=CONTRACT_VERSION,
                                    conversation=conversation.identity, retention="saved",
                                    runtime=reference)


class HarnessCommandIdentity(HarnessContract):
    protocol: Literal["renulus-harness/1"]
    profile_id: Identifier
    store_id: Identifier
    generation: Identifier
    operation_id: Identifier
    attempt_id: Identifier
    request_id: Identifier


class HarnessCommandError(HarnessContract):
    code: Identifier
    message: str | None = None


class HarnessCommandOutcome(HarnessCommandIdentity):
    model_config = ConfigDict(json_schema_extra={
        "if": {"properties": {"outcome": {"not": {"const": "accepted_pending"}}}},
        "then": {"anyOf": [
            {"required": ["result"]},
            {"required": ["error"], "properties": {"error": {"type": "object"}}},
        ]},
    })
    kind: Literal["reply"]
    outcome: Outcome
    result: JsonValue = None
    error: HarnessCommandError | None = None

    @field_validator("result")
    @classmethod
    def finite_json_numbers(cls, value: JsonValue) -> JsonValue:
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Command result must contain only finite JSON numbers")
            if isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        return value

    @model_validator(mode="after")
    def terminal_result_is_present(self):
        if (self.outcome != "accepted_pending" and "result" not in self.model_fields_set
                and self.error is None):
            raise ValueError("Terminal reply requires a result or error")
        return self


def validate_command_outcome(value: object, *, expected: HarnessCommandIdentity
                             ) -> HarnessCommandOutcome:
    """Reject stale/misrouted replies without changing command admission state."""
    reply = HarnessCommandOutcome.model_validate(value)
    if any(getattr(reply, field) != getattr(expected, field)
           for field in HarnessCommandIdentity.model_fields):
        raise ValueError("Reply identity does not match the admitted command")
    return reply


def harness_json_schema() -> dict:
    """Portable shape schema; caller-bound equality and ownership remain local checks."""
    _, schema = models_json_schema([
        (PairedStoreManifest, "validation"), (HarnessEngineReference, "validation"),
        (SavedConversationMapping, "validation"), (HarnessCommandIdentity, "validation"),
        (HarnessCommandOutcome, "validation"),
    ], title="Renulus Harness contracts — harness/1")
    # Pydantic's Rust `$` means end-of-input. ECMAScript/Python also match before
    # a final newline. Preserve the stricter meaning in exported property patterns.
    for definition in schema["$defs"].values():
        for prop in definition.get("properties", {}).values():
            if prop.get("pattern", "").endswith("$"):
                prop["pattern"] += r"(?![\s\S])"
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "urn:renulus:harness:1", "$ref": "#/$defs/PairedStoreManifest", **schema}
