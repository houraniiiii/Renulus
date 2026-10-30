"""Bounded RAM staging. Handles are minted by the host; payloads never name paths.

Both retention modes stay in RAM in BF00. Reservations precede allocation, and
partial uploads remain owned until explicit release, revoke, or worker settlement.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import json
from threading import RLock
import time

from renulus.worker_contracts import (ArtifactGrant, ArtifactResult, ByteRange, Capacity,
                                     OutputGrant, ReadResult, Revisions, UploadInput, UploadResult)


class Refused(Exception):
    def __init__(self, code):
        self.code = code


@dataclass
class Artifact:
    grant: ArtifactGrant | OutputGrant
    revisions: Revisions
    reservation: int
    body: bytearray = field(default_factory=bytearray)
    complete: bool = False
    engine: str = "host-upload"
    pages: int | None = None
    pins: int = 0
    retiring: bool = False


class Artifacts:
    def __init__(self, capacity: Capacity):
        self.capacity = capacity
        self.lock = RLock()
        self.items: dict[str, Artifact] = {}
        self.retired: set[str] = set()
        self.used = 0

    def _reserve(self, grant, revisions, size):
        handle = grant.artifact_handle
        if handle in self.items or handle in self.retired:
            raise Refused("artifact_invalid")
        if (len(self.items) >= self.capacity.artifact_count
                or self.used + size > self.capacity.artifact_bytes):
            raise Refused("artifact_limit")
        if grant.expires_at_ms <= int(time.time() * 1000):
            raise Refused("artifact_denied")
        artifact = Artifact(grant, revisions, size)
        self.items[handle] = artifact
        self.used += size
        return artifact

    def reserve_output(self, grant: OutputGrant, revisions: Revisions):
        with self.lock:
            artifact = self._reserve(grant, revisions, grant.max_bytes)
            artifact.pins = 1  # Native task owns staging through actual settlement.
            return artifact

    def upload(self, input: UploadInput, revisions: Revisions):
        try:
            chunk = base64.b64decode(input.data_base64, validate=True)
        except (ValueError, TypeError):
            raise Refused("artifact_invalid") from None
        if len(chunk) > self.capacity.max_chunk_bytes:
            raise Refused("artifact_limit")
        grant = input.artifact
        if (len(set(grant.rights)) != len(grant.rights)
                or any(r.offset + r.length > grant.bytes for r in grant.permitted_ranges)):
            raise Refused("artifact_invalid")
        with self.lock:
            artifact = self.items.get(grant.artifact_handle)
            if artifact is None:
                if input.offset != 0:
                    raise Refused("artifact_invalid")
                artifact = self._reserve(grant, revisions, grant.bytes)
            if (artifact.grant != grant or artifact.revisions != revisions or artifact.complete
                    or artifact.retiring or grant.expires_at_ms <= int(time.time() * 1000)
                    or len(artifact.body) != input.offset or input.offset + len(chunk) > grant.bytes
                    or (input.final != (input.offset + len(chunk) == grant.bytes))):
                raise Refused("artifact_invalid")
            artifact.body.extend(chunk)
            if input.final:
                if hashlib.sha256(artifact.body).hexdigest() != grant.artifact_sha256:
                    self.release(grant.artifact_handle)
                    raise Refused("digest_mismatch")
                artifact.complete = True
            return UploadResult(artifact_handle=grant.artifact_handle,
                                received_bytes=len(artifact.body), complete=artifact.complete)

    def pin(self, handle, revision, offset, length, right, revisions):
        with self.lock:
            artifact = self.items.get(handle)
            if artifact is None or not artifact.complete or artifact.retiring:
                raise Refused("artifact_denied")
            grant = artifact.grant
            if (grant.artifact_revision != revision or artifact.revisions != revisions
                    or grant.expires_at_ms <= int(time.time() * 1000)):
                raise Refused("artifact_denied")
            ranges = grant.permitted_ranges if isinstance(grant, ArtifactGrant) else [
                ByteRange(offset=0, length=len(artifact.body))]
            rights = grant.rights if isinstance(grant, ArtifactGrant) else ["read", "chunk"]
            if (right not in rights or offset + length > len(artifact.body)
                    or not any(offset >= r.offset and offset + length <= r.offset + r.length
                               for r in ranges)):
                raise Refused("artifact_denied")
            artifact.pins += 1
            return artifact

    def unpin(self, artifact):
        with self.lock:
            artifact.pins -= 1
            if artifact.pins == 0 and artifact.retiring:
                self._drop(artifact.grant.artifact_handle)

    def publish(self, artifact, value, *, engine, pages=None):
        # Stream encoding into the reservation; never allocate an unbounded JSON frame.
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        for fragment in encoder.iterencode(value):
            chunk = fragment.encode("utf-8")
            if len(artifact.body) + len(chunk) > artifact.reservation:
                raise Refused("artifact_limit")
            artifact.body.extend(chunk)
        with self.lock:
            if artifact.retiring or artifact.grant.expires_at_ms <= int(time.time() * 1000):
                raise Refused("artifact_denied")
            # Runtime makes this readable only after its final cancellation and
            # authority checks, under the same lock used by artifact.read admission.
            artifact.engine, artifact.pages = engine, pages
            return self.reference(artifact)

    def reference(self, artifact):
        return ArtifactResult(artifact_handle=artifact.grant.artifact_handle,
            artifact_revision=artifact.grant.artifact_revision,
            artifact_sha256=hashlib.sha256(artifact.body).hexdigest(), bytes=len(artifact.body),
            engine=artifact.engine, pages=artifact.pages)

    def read(self, input, revisions, page_bytes):
        with self.lock:
            artifact = self.items.get(input.artifact_handle)
            if artifact is None or input.offset > len(artifact.body):
                raise Refused("artifact_denied")
            length = min(input.length, page_bytes, self.capacity.max_chunk_bytes,
                         len(artifact.body) - input.offset)
        artifact = self.pin(input.artifact_handle, input.artifact_revision,
                            input.offset, length, "read", revisions)
        try:
            end = input.offset + length
            return ReadResult(artifact=self.reference(artifact), offset=input.offset,
                data_base64=base64.b64encode(artifact.body[input.offset:end]).decode("ascii"),
                next_cursor=end if end < len(artifact.body) else None)
        finally:
            self.unpin(artifact)

    def _drop(self, handle):
        artifact = self.items.pop(handle)
        self.retired.add(handle)  # A released immutable handle can never be rebound.
        self.used -= artifact.reservation
        artifact.body.clear()

    def release(self, handle):
        with self.lock:
            artifact = self.items.get(handle)
            if artifact is None:
                raise Refused("artifact_denied")
            artifact.retiring = True
            if not artifact.pins:
                self._drop(handle)

    def discard(self):
        with self.lock:
            for handle in list(self.items):
                self.release(handle)
