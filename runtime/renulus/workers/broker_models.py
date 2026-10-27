"""Private BF01 worker transport contracts, reusable by the worker schema owner.

These objects are host inputs, never model tool arguments. The native host owns
serialization, counters and final admission. Frozen tuples keep nested plans
immutable; JSON Schema generation can include these models without a new RPC.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from .contract_base import (ArtifactResult, Counter, Digest, Id, Identity,
    Model, OutputGrant, ProcessIdentity, Retention, Revisions)

Provider = Literal["codex", "opencode-go"]
OpaquePermit = Annotated[str, Field(min_length=32, max_length=256,
    pattern=r"^[A-Za-z0-9_-]+$(?![\s\S])")]
LoginId = Annotated[str, Field(min_length=1, max_length=128,
    pattern=r"^[A-Za-z0-9_-]+$(?![\s\S])")]
Endpoint = Annotated[str, Field(min_length=1, max_length=2048)]


class BrokerBounds(Model):
    max_request_bytes: Annotated[int, Field(ge=1, le=32 * 1024 * 1024)] = 1024 * 1024
    max_response_bytes: Annotated[int, Field(ge=1, le=16 * 1024 * 1024)] = 1024 * 1024
    timeout_seconds: Annotated[int, Field(ge=1, le=300)] = 120
    permit_count: Annotated[int, Field(ge=1, le=4096)] = 4096


class BrokerLaunch(Model):
    identity: ProcessIdentity
    revisions: Revisions
    retention: Retention
    profile_root: Annotated[str, Field(min_length=1, max_length=4096)]
    state_root: Annotated[str, Field(min_length=1, max_length=4096)]
    native_manifest_sha256: Digest
    registry_sha256: Digest
    bounds: BrokerBounds = Field(default_factory=BrokerBounds)
    # Test-only launch authority: exact numeric IPv4 loopback URLs, never a
    # wildcard/hostname/ambient environment override. Empty in product launches.
    synthetic_endpoints: Annotated[tuple[Endpoint, ...], Field(max_length=8)] = ()


class TransportRoute(Model):
    provider_id: Provider
    model_id: Id
    wire_model_id: Id
    endpoint: Endpoint
    protocol: Literal["openai-responses", "openai-chat"]
    credential_ref: Id
    credential_revision: Counter


class NativeHeader(Model):
    name: Annotated[str, Field(min_length=1, max_length=64)]
    value: Annotated[str, Field(max_length=256)]


class NativeRequest(Model):
    method: Literal["POST"]
    url: Endpoint
    headers: Annotated[tuple[NativeHeader, ...], Field(max_length=8)]
    body_base64: Annotated[str, Field(min_length=4, max_length=44739244)] = Field(repr=False)


class TransportPlan(Model):
    permit_id: OpaquePermit = Field(repr=False)
    # Reference to the TS final admission commit, not a Python-issued permit.
    admission_receipt: Id
    identity: Identity
    revisions: Revisions
    retention: Retention
    route: TransportRoute
    native_manifest_sha256: Digest
    registry_sha256: Digest
    request_sha256: Digest
    request_bytes: Annotated[int, Field(ge=1, le=32 * 1024 * 1024)]
    # Digest of exact native envelope bytes (host's sorted compact JSON). This
    # binds headers/URL as well as the already serialized request body.
    envelope_sha256: Digest
    max_output_tokens: Annotated[int, Field(ge=1, le=9007199254740991)]
    expires_at_ms: Counter
    output: OutputGrant
    serialized_request: NativeRequest = Field(repr=False)


class TransportResult(Model):
    tag: Literal["transport"] = "transport"
    admission_receipt: Id
    identity: Identity
    revisions: Revisions
    request_sha256: Digest
    outcome: Literal["rejected_before_admission", "committed_reference",
        "cancelled_settled", "uncertain_after_disconnect"]
    # 'settled' means actual local socket/client cleanup. It never certifies
    # that cancellation undid a remote effect or refunded its TS debit.
    settlement: Literal["settled"] = "settled"
    effect: Literal["not_sent", "response_received", "uncertain"]
    network_started: bool
    code: Id | None = None
    http_status: Annotated[int, Field(ge=100, le=599)] | None = None
    content_type: Literal["text/event-stream"] | None = None
    artifact: ArtifactResult | None = None


class CredentialMetadata(Model):
    provider_id: Provider
    credential_ref: Id
    credential_revision: Counter
    configured: bool
    usable: bool
    selected: bool
    selected_model: Id | None


class CredentialAuthority(Model):
    """One authenticated Settings intent, minted by the host, never a tool."""
    authority_id: Id
    source: Literal["settings"]
    action: Literal["connect", "refresh", "forget", "login-status", "login-cancel"]
    provider_id: Provider
    identity: Identity
    revisions: Revisions
    retention: Retention
    credential_ref: Id
    credential_revision: Counter
    expires_at_ms: Counter


class CredentialResult(Model):
    tag: Literal["credentials"] = "credentials"
    credentials: tuple[CredentialMetadata, ...]
    login_id: LoginId | None = None
    login_status: Literal["pending", "exchanging", "connected", "cancelled", "error"] | None = None
    authorization_url: Annotated[str, Field(max_length=8192)] | None = Field(default=None, repr=False)
    remote_revocation: Literal["failed"] | None = None
