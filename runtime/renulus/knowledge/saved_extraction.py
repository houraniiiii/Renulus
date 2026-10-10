# SPDX-License-Identifier: MIT
"""Trusted saved extraction for private test imports; caller owns the snapshot.

This adapter consumes canonical passages, never a renderer preview or a new
conversion. Its original descriptor stays in backend provenance. Reinvoke it
with the captured pins in the final publication transaction.
"""
import hashlib
import json
from pathlib import Path
import re

from pydantic import ValidationError

from ..contracts import ApiError
from ..design_c_contracts import ContentReference
from ..storage.assessment_policy import require_assistance
from ..storage.invalidation import context_epoch_in
from ..storage.relations import TOMBSTONES
from .engines import MAX_BYTES, MAX_PASSAGES
from .models import Rights, SourceMetadata

MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_EXTRACTION_BYTES = 16 * 1024 * 1024
SUPPORTED_MEDIA = frozenset({
    "application/pdf", "text/plain", "text/markdown", "text/csv",
    "text/html", "application/xml", "text/xml", "image/png",
    "image/jpeg", "image/tiff",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
})


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fail(code, message, status=409, retryable=False):
    raise ApiError("saved_extraction_" + code, message, status, retryable)


def _reference(revision_id, locators, media_type):
    reference = {"target": {"type": "library_revision", "id": revision_id}}
    # Docling item IDs and geometry remain extraction provenance. They are not
    # automatically the inert reader's text offsets or selectable block IDs.
    for location in locators:
        locator = location.get("content_locator")
        if locator is None and isinstance(location.get("page"), int):
            page = location["page"]
            if not 1 <= page <= 300:
                continue
            if media_type == "application/pdf":
                locator = {"kind": "pdf", "physical_page": page}
            elif media_type.startswith("image/"):
                locator = {"kind": "image", "frame": page}
        if locator is not None:
            try:
                return ContentReference.model_validate({**reference, "locator": locator}).model_dump(mode="json")
            except ValidationError:
                continue
    return ContentReference.model_validate(reference).model_dump(mode="json")


def _original(repository, row):
    identifier = re.compile(r"[A-Za-z0-9_-]{1,128}")
    if (not identifier.fullmatch(row["document_id"]) or not identifier.fullmatch(row["id"])
            or not row["original_path"] or not 0 < row["bytes"] <= MAX_BYTES):
        raise ApiError("original_missing", "The private original is unavailable", 404)
    root = repository.paths.root.resolve()
    folder = repository.paths.library / "knowledge" / row["document_id"] / row["id"]
    path = Path(row["original_path"])
    try:
        # Reject redirected private locations rather than adopting another file
        # that happens to have matching bytes. No caller-supplied path is used.
        if (path.is_symlink() or path.resolve().parent != folder.resolve()
                or not path.name.startswith("original.")
                or not folder.resolve().is_relative_to(root)):
            raise OSError()
        for parent in (folder, *folder.parents):
            if parent == root:
                break
            if parent.is_symlink() or parent.is_junction():
                raise OSError()
        if not path.is_file() or path.stat().st_size != row["bytes"]:
            raise OSError()
        digest, size = hashlib.sha256(), 0
        with path.open("rb") as source:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > row["bytes"]:
                    raise OSError()
                digest.update(chunk)
        if size != row["bytes"] or digest.hexdigest() != row["sha256"]:
            raise OSError()
        relative_path = path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        raise ApiError("original_missing", "The private original is missing or changed", 404) from None
    return {"kind": "library-original", "document_id": row["document_id"],
            "revision_id": row["id"], "relative_path": relative_path,
            "media_type": row["media_type"], "bytes": size, "sha256": row["sha256"]}


def _source_in(repository, conn, revision_id, *, operation, expected_policy_revision=None,
               expected_context_epoch=None):
    if not conn.in_transaction:
        fail("snapshot_required", "Begin the caller transaction before resolving a source", 422)
    if not isinstance(operation, str) or operation not in {"import", "read"}:
        fail("operation_invalid", "Choose import or read source permission", 422)
    policy_revision = require_assistance(conn, expected_revision=expected_policy_revision)
    epoch = context_epoch_in(conn)
    if expected_context_epoch is not None and epoch != expected_context_epoch:
        fail("context_changed", "Learning context changed; reopen the import source", retryable=True)
    if not isinstance(revision_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", revision_id):
        fail("not_found", "The saved source revision is unavailable", 404)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"knowledge_documents", "knowledge_revisions", "knowledge_passages",
            "knowledge_source_status_events"} <= tables:
        fail("unavailable", "Saved extraction storage is unavailable", 503, True)
    row = conn.execute("SELECT r.*,d.title,d.source_id,d.scope_kind,d.scope_entity,d.reserved,"
                       "d.deleted_at,d.active_revision,d.latest_revision FROM knowledge_revisions r "
                       "JOIN knowledge_documents d ON d.id=r.document_id WHERE r.id=?", (revision_id,)).fetchone()
    if row is None or row["deleted_at"] or row["status"] == "deleted":
        fail("not_found", "The saved source revision is unavailable", 404)
    for kind, table in TOMBSTONES.items():
        value = row["id"] if table == "knowledge_revisions" else row["document_id"] if table == "knowledge_documents" else None
        if value and conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type=? AND entity_id=?", (kind, value)).fetchone():
            fail("not_found", "The saved source revision is unavailable", 404)
    if row["scope_kind"] != "personal-library" or row["scope_entity"] is not None or row["reserved"]:
        fail("denied", "This source cannot enter a saved private test import", 403)
    if operation == "import" and row["media_type"] not in SUPPORTED_MEDIA:
        fail("unsupported", "This saved format is not supported for test import; paste text instead", 415)
    try:
        rights = Rights.model_validate_json(row["rights_json"], strict=True).model_dump()
        metadata = SourceMetadata.model_validate_json(row["metadata_json"], strict=True)
        if metadata.source_id != row["source_id"]:
            raise ValueError()
        metadata = repository.source_status.effective(metadata,
            repository.source_status.events(row["source_id"], conn)).model_dump()
    except (ValueError, TypeError):
        fail("unavailable", "Source permissions or provenance need repair", 503)
    operations = ("display", "cache", "model_input", "derivation") if operation == "import" else ("display", "cache")
    if not all(rights[key] is True for key in operations):
        fail("denied", "Current source permissions do not permit this operation", 403)
    if operation == "import" and (
            any(metadata[key] for key in ("retracted", "superseded", "repository_removed", "access_changed", "replaced_topics"))
            or metadata["publication_status"] in ("draft", "preprint")
            or metadata["correction"] and not metadata["content_reviewed"]):
        fail("denied", "Current source permissions or status do not permit test import", 403)
    return row, rights, metadata, policy_revision, epoch


def require_original_display_in(repository, conn, pin):
    """Authorize DC17's own immutable retained text/locators without regenerating.

    The pin must come from the canonical import row, never renderer attestation.
    Ready extraction/active revision is unnecessary for inspecting that retained
    body. Display/cache, tombstones, shared policy and actual original integrity
    still apply. No body is read from or accepted in the supplied pin.
    """
    if (not isinstance(pin, dict) or not isinstance(pin.get("revision_id"), str)
            or not isinstance(pin.get("original_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", pin["original_sha256"])):
        fail("invalid_pin", "Use the source pin from the canonical private import", 422)
    row, rights, metadata, policy_revision, epoch = _source_in(repository, conn, pin["revision_id"], operation="read")
    original = _original(repository, row)
    if original["sha256"] != pin["original_sha256"] or (
            pin.get("document_id") is not None and pin["document_id"] != row["document_id"]):
        fail("stale", "The retained source original changed")
    return {"allowed": True, "rights": rights, "metadata": metadata, "original": original,
            "policy_revision": policy_revision, "context_epoch": epoch}


def saved_extraction_in(repository, conn, revision_id, *, operation="import", expected_fingerprint=None,
                        expected_policy_revision=None, expected_context_epoch=None):
    """Resolve saved successful extraction without a new connection or engine.

    The caller owns its snapshot/publication transaction. Private original
    existence/integrity is a bounded read; the result remains backend-only.
    """
    row, rights, metadata, policy_revision, epoch = _source_in(repository, conn, revision_id, operation=operation,
        expected_policy_revision=expected_policy_revision, expected_context_epoch=expected_context_epoch)
    if expected_fingerprint is not None and (not isinstance(expected_fingerprint, str)
            or not re.fullmatch(r"[a-f0-9]{64}", expected_fingerprint)):
        fail("invalid_pin", "Use the fingerprint captured by the trusted source resolver", 422)
    if row["status"] in ("queued", "processing"):
        fail("pending", "This saved source has not finished extraction", retryable=True)
    if row["status"] in ("failed", "cancelled"):
        fail("failed", "Saved extraction failed or was cancelled; retry or paste text", 422, True)
    if row["status"] != "ready":
        fail("unavailable", "Successful saved extraction is unavailable", 503, True)
    if operation == "import" and (row["active_revision"] != row["id"] or row["latest_revision"] != row["id"]):
        fail("stale", "This saved revision was replaced; select the current source", retryable=True)
    extraction_json = row["extraction_json"]
    try:
        if not extraction_json or len(extraction_json.encode()) > MAX_EXTRACTION_BYTES:
            raise ValueError()
        extraction = json.loads(extraction_json)
        if not isinstance(extraction, dict) or extraction.get("schema_name") != "DoclingDocument":
            raise ValueError()
    except (ValueError, TypeError):
        fail("unavailable", "Successful canonical extraction is unavailable; retry extraction", 503, True)
    rows = conn.execute("SELECT id,text,locators_json,headings_json FROM knowledge_passages "
                        "WHERE revision_id=? ORDER BY ordinal LIMIT ?", (revision_id, MAX_PASSAGES + 1)).fetchall()
    if len(rows) > MAX_PASSAGES:
        fail("limit", "The saved extraction exceeds the private import limit", 413)
    segments, texts, position, text_bytes = [], [], 0, 0
    excluded = set(metadata["excluded_pages"])
    try:
        for passage in rows:
            locators, headings = json.loads(passage["locators_json"]), json.loads(passage["headings_json"])
            if (not isinstance(locators, list) or not all(isinstance(value, dict) for value in locators)
                    or not isinstance(headings, list) or not all(isinstance(value, str) for value in headings)):
                raise ValueError()
            if operation == "import" and any(locator.get("page") in excluded for locator in locators):
                fail("denied", "The source contains excluded pages; a whole-source import is unavailable", 403)
            text = passage["text"]
            if not isinstance(text, str) or not text.strip():
                raise ValueError()
            text_bytes += len(text.encode()) + (2 if texts else 0)
            if text_bytes > MAX_TEXT_BYTES:
                fail("limit", "The saved extraction exceeds the 4 MiB private import limit", 413)
            position += 2 if texts else 0
            segments.append({"start": position, "end": position + len(text),
                "passage_id": passage["id"], "reference": _reference(revision_id, locators, row["media_type"]),
                "locators": locators, "headings": headings})
            texts.append(text)
            position += len(text)
    except (ValueError, TypeError):
        fail("unavailable", "Canonical extraction passages need repair", 503)
    if not texts:
        fail("unavailable", "No successful canonical text exists; retry extraction or paste text", 503, True)
    original = _original(repository, row)
    text = "\n\n".join(texts)
    content_sha256 = hashlib.sha256(text.encode()).hexdigest()
    pin = {"contract": "saved-extraction/1", "document_id": row["document_id"],
           "revision_id": revision_id, "source_id": row["source_id"], "title": row["title"],
           "original": original, "metadata": metadata, "rights": rights, "segments": segments,
           "content_sha256": content_sha256,
           "extraction_sha256": hashlib.sha256(canonical(extraction).encode()).hexdigest()}
    fingerprint = hashlib.sha256(canonical(pin).encode()).hexdigest()
    if expected_fingerprint is not None and fingerprint != expected_fingerprint:
        fail("stale", "The saved source changed; reopen the import source", retryable=True)
    return {**pin, "text": text, "fingerprint": fingerprint, "original_sha256": row["sha256"],
            "reference": _reference(revision_id, [], row["media_type"]),
            "terms": {key: rights[key] for key in ("licence", "permission_reference", "attribution")},
            "policy_revision": policy_revision, "context_epoch": epoch,
            "diagnostics": [{"code": "canonical_passage_text",
                "message": "Text preserves canonical passage order and table headers; passages are separated by two newlines."}]}
