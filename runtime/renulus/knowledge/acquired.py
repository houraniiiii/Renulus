"""Offline, selected PMC article-version imports. No discovery or network I/O.

The manifest is a receipt, not a permission grant. Only a hash-checked matched
version metadata object plus the existing strict JATS route can grant the local
text operations below. All external originals remain untouched.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PureWindowsPath
import re
from urllib.parse import parse_qs, urlsplit

from ..contracts import ApiError
from ..retrieval.literature import PMCID, licensed_article
from .models import Rights, SourceMetadata

MANIFEST = "metadata/acquisition-2026-10-04/acquisition-manifest.jsonl"
MARKER = "acquired-jats"
EVIDENCE_PREFIX = "renulus-acquired-v1:"
MAX_XML_BYTES = 64 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")
MD5 = re.compile(r"[0-9a-f]{32}")
EXCLUSIONS = "Figures, tables, media, supplementary material, quotations, boxed text and marked third-party blocks omitted; original JATS unchanged"


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate metadata field")
        value[key] = item
    return value


def failure(code, message, status=409):
    return ApiError(code, message, status)


def collection_path(root: Path, value, *, must_exist=True) -> Path:
    """Validate an exact manifest path, including Windows traversal/ADS forms."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise failure("collection_path_invalid", "A collection path is required")
    windows = PureWindowsPath(value)
    if ".." in windows.parts or any(":" in part for part in windows.parts if part != windows.anchor):
        raise failure("collection_path_invalid", "Collection paths cannot traverse or use alternate data streams")
    if windows.anchor.startswith("\\") or (windows.drive and not windows.root):
        raise failure("collection_path_invalid", "Network and drive-relative collection paths are unavailable")
    # A catalogue receipt is lexical metadata only. Resolving every unselected
    # path probes the collection filesystem and is needlessly expensive. Exact
    # selection resolves and validates linked components before opening bytes.
    root = Path(root).resolve() if must_exist else Path(root).absolute()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve() if must_exist else path.absolute()
    if not resolved.is_relative_to(root) or resolved == root:
        raise failure("collection_path_invalid", "The selected file must stay within the authorised collection")
    if must_exist:
        if not resolved.is_file():
            raise failure("collection_path_invalid", "The selected collection file is unavailable")
        # Refuse linked components, even when their current target is inside.
        for component in (path, *path.parents):
            if component == root:
                break
            if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
                raise failure("collection_path_invalid", "Linked collection files require a reviewed import")
    return resolved


def asset_id(source_id: str, relative: str) -> str:
    return "asset_" + hashlib.sha256((source_id + "\n" + relative).encode()).hexdigest()[:24]


def version_identity(item) -> tuple[str, int]:
    pmcid, version = item.get("pmcid"), item.get("article_version")
    if not isinstance(pmcid, str) or not PMCID.fullmatch(pmcid) or type(version) is not int or not 1 <= version <= 100000:
        raise failure("article_version_invalid", "An explicit PMC article and positive version number are required")
    return pmcid, version


def version_name(identity) -> str:
    return identity[0] + "." + str(identity[1])


def acquisition_topic_ids(item) -> list[str]:
    """Retain query tags as observations, without inferring content review."""
    topics = item.get("topics", [])
    return sorted({t["topic_id"] for t in topics if isinstance(t, dict) and isinstance(t.get("topic_id"), str)}) if isinstance(topics, list) else []


def licence_family(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("identifier")
    if not isinstance(value, str):
        return None
    value = value.strip().upper().replace("-", " ")
    if value in ("CC BY", "CC BY 2.0", "CC BY 3.0", "CC BY 4.0"):
        return "by"
    if value in ("CC0", "CC0 1.0"):
        return "zero"
    return None


def catalogue_policy(item) -> tuple[str, str] | None:
    """Metadata-only explanation. Never labels an uninspected body eligible."""
    sid, role = item.get("source_id"), str(item.get("artifact_type", ""))
    if sid not in ("L01", "L02", "L03", "L04", "L05", "L06", "L07", "L08"):
        return None
    if item.get("reserved"):
        return "reserved", "Reserved acquired material is not study evidence"
    if "tdm" in role.lower() or str(item.get("licence", "")).upper() == "TDM":
        return "article_tdm_unavailable", "TDM/manuscript permissions are outside automatic text import"
    if sid == "L02" and role == "fulltext-jats":
        try:
            version_identity(item)
        except ApiError as error:
            return error.code, error.message
        if item.get("status") != "acquired-unreviewed":
            return "acquired_payload_unavailable", "Only a successful acquired article body can be inspected"
        if item.get("retracted") is True:
            return "article_retracted", "The acquisition record reports retraction"
        if not licence_family(item.get("licence")):
            return "article_permission_required", "The recorded licence is outside the strict CC BY/CC0 route"
        return "inspection_required", "Select this JATS candidate to inspect its exact version metadata, licence and hashes before queuing text"
    if sid == "L02" and role in ("fulltext-pdf", "fulltext-text"):
        return "alternate_asset_unavailable", "Select the matching article-version JATS candidate; alternate PDF/text is not independently imported"
    if role == "article-media-or-supplement":
        return "article_asset_excluded", "Figures, tables, media and supplements are excluded from this text route"
    return "acquired_payload_unavailable", "Metadata, diagnostics and other acquired payloads are not eligible article text"


def _receipt(item):
    if item.get("status") != "acquired-unreviewed" or item.get("reserved") or item.get("retracted") is True:
        raise failure("acquired_payload_unavailable", "This receipt does not permit article inspection")
    digest, size = item.get("sha256"), item.get("bytes")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest) or type(size) is not int or size <= 0:
        raise failure("article_hash_required", "A valid acquisition SHA-256 and byte count are required")
    provenance = item.get("acquisition_provenance")
    if not isinstance(provenance, list) or not any(isinstance(p, dict) and p.get("source_id") == "L02" and p.get("sha256") == digest
            and p.get("artifact_type") == item.get("artifact_type") and p.get("status") == "acquired-unreviewed"
            and isinstance(p.get("manifest"), str) and p["manifest"] and type(p.get("line")) is int and p["line"] > 0 for p in provenance):
        raise failure("article_provenance_required", "An exact acquisition provenance record is required")
    scope = item.get("processing_scope")
    if isinstance(scope, dict):
        for operation in ("display", "cache", "index", "embedding", "model_input", "derivation", "human_reading", "caching", "indexing", "indexing_embedding", "ai_processing"):
            value = scope.get(operation)
            if value is False or (isinstance(value, str) and re.search(r"prohibit|not authori[sz]ed|reading.only|reference verification only", value, re.I)):
                raise failure("article_permission_required", "Explicit operation restrictions override automatic import", 403)
    elif isinstance(scope, str) and re.search(r"reading.only|reference verification only|AI.{0,20}(?:prohibit|not authori[sz]ed)", scope, re.I):
        raise failure("article_permission_required", "The acquisition record restricts processing", 403)


def _read(root, item, bound):
    _receipt(item)
    try:
        path = collection_path(root, item.get("local_path") or item.get("path"))
        if item["bytes"] > bound or path.stat().st_size > bound:
            raise failure("article_size_limit", "The selected article artifact exceeds the inspection limit", 413)
        with path.open("rb") as stream:
            raw = stream.read(bound + 1)
    except OSError:
        raise failure("article_file_unavailable", "The selected acquired artifact cannot be read; no text was queued") from None
    if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
        raise failure("source_hash_changed", "The selected artifact differs from its acquisition receipt")
    return raw, path.relative_to(Path(root).resolve()).as_posix()


def _object_url(url, expected_key, *, checksum=False):
    try:
        parsed = urlsplit(url)
        valid = ((parsed.scheme == "s3" and parsed.hostname == "pmc-oa-opendata") or
                 (parsed.scheme == "https" and parsed.hostname == "pmc-oa-opendata.s3.amazonaws.com"))
        valid = valid and not (parsed.username or parsed.password or parsed.port or parsed.fragment) and parsed.path == "/" + expected_key
        query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
        valid = valid and set(query).issubset({"md5"})
        md5 = query.get("md5", [])
        valid = valid and (not md5 or (len(md5) == 1 and MD5.fullmatch(md5[0])))
        if not valid or (checksum and not md5):
            raise ValueError()
        return md5[0] if md5 else None
    except (ValueError, TypeError, AttributeError):
        raise failure("article_origin_invalid", "The source URL does not identify the exact official PMC object") from None


@dataclass
class InspectedArticle:
    text: str
    title: str
    metadata: SourceMetadata
    rights: Rights
    evidence: dict

    @property
    def key(self):
        # Changed receipts/licences need a revision even with unchanged prose.
        # Identical artifacts at alternate paths still share this key.
        fingerprint = hashlib.sha256(json.dumps([self.evidence["original_sha256"],
            self.evidence["metadata_sha256"], self.evidence["derivative_sha256"],
            self.rights.licence], separators=(",", ":")).encode()).hexdigest()
        return "acquired:L02:" + self.metadata.edition + ":" + fingerprint


class AcquiredLiterature:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def selections(self, entries):
        """Read only manifest metadata; retain exact selections and matching metadata."""
        wanted = {entry["id"]: entry for entry in entries}
        identities = set()
        for entry in entries:
            meta = json.loads(entry["metadata_json"])
            edition = meta.get("edition", "")
            if isinstance(edition, str) and re.fullmatch(r"PMC[1-9][0-9]{0,10}\.[1-9][0-9]{0,5}", edition):
                pmcid, version = edition.rsplit(".", 1)
                identities.add((pmcid, int(version)))
        selected, metadata = {}, {}
        path = collection_path(self.root, MANIFEST)
        with path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                    if not isinstance(item, dict) or item.get("source_id") != "L02":
                        continue
                    role = item.get("artifact_type")
                    if role not in ("fulltext-jats", "article-version-metadata"):
                        continue
                    identity = version_identity(item)
                    if identity not in identities:
                        continue
                    # Strict parsing is needed only for matched evidence, not
                    # every unrelated media/metadata receipt in the manifest.
                    item = json.loads(line, object_pairs_hook=unique_object)
                    relative = collection_path(self.root, item.get("local_path") or item.get("path"), must_exist=False).relative_to(self.root).as_posix()
                    identifier = asset_id("L02", relative)
                    if role == "fulltext-jats" and identifier in wanted:
                        entry = wanted[identifier]
                        if identifier in selected and selected[identifier] != item:
                            selected[identifier] = failure("article_receipt_ambiguous", "Conflicting receipts require a reviewed import")
                        else:
                            selected[identifier] = item
                    if role == "article-version-metadata":
                        metadata.setdefault(identity, {})[(relative, item.get("sha256"))] = item
                except (ValueError, TypeError, KeyError, ApiError):
                    continue  # Malformed unrelated metadata cannot broaden selection.
        return selected, metadata

    def inspect(self, item, matched):
        identity = version_identity(item)
        name = version_name(identity)
        if len(matched) != 1:
            raise failure("article_metadata_required", "Exactly one matching acquired article-version metadata receipt is required")
        receipt = next(iter(matched.values()))
        raw_metadata, metadata_path = _read(self.root, receipt, MAX_METADATA_BYTES)
        try:
            record = json.loads(raw_metadata, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError):
            raise failure("article_metadata_invalid", "The version metadata is not valid JSON") from None
        if not isinstance(record, dict) or record.get("pmcid") != identity[0] or type(record.get("version")) is not int or record["version"] != identity[1]:
            raise failure("article_identity_mismatch", "The acquired metadata identifies a different article version")
        if record.get("is_retracted") is not False:
            raise failure("article_retraction_unavailable", "Explicit nonretraction in the acquired version metadata is required")
        if record.get("is_pmc_openaccess") is not True or record.get("is_manuscript") is not False or record.get("is_historical_ocr") is not False:
            raise failure("article_oa_version_required", "Only explicit OA article versions outside the manuscript/OCR route are supported")
        family = licence_family(record.get("license_code"))
        if not family or family != licence_family(item.get("licence")) or family != licence_family(receipt.get("licence")):
            raise failure("article_permission_required", "Receipt and version metadata licences must agree within the CC BY/CC0 route", 403)
        _object_url(receipt.get("origin_url"), "metadata/" + name + ".json")
        if receipt.get("final_url"):
            _object_url(receipt["final_url"], "metadata/" + name + ".json")
        key = name + "/" + name + ".xml"
        publisher_md5 = _object_url(record.get("xml_url"), key, checksum=True)
        for value in (item.get("origin_url"), item.get("final_url"), item.get("cloud_origin_url")):
            if value and _object_url(value, key, checksum=True) != publisher_md5:
                raise failure("article_identity_mismatch", "The selected receipt and metadata reference different XML objects")
        if not item.get("origin_url") or (item.get("publisher_md5") is not None and item["publisher_md5"] != publisher_md5):
            raise failure("article_origin_invalid", "An exact source object and checksum are required")
        raw, original_path = _read(self.root, item, MAX_XML_BYTES)
        if hashlib.md5(raw).hexdigest() != publisher_md5:
            raise failure("article_publisher_hash_changed", "The JATS bytes differ from the version metadata checksum")
        article = licensed_article(raw, identity[0])
        if licence_family(article["licence"]) != family:
            raise failure("article_permission_required", "The inspected JATS licence disagrees with version metadata", 403)
        for label in (item.get("licence"), receipt.get("licence"), record.get("license_code")):
            label = label.get("identifier") if isinstance(label, dict) else label
            normal = str(label).strip().upper().replace(" ", "-")
            if normal not in ("CC-BY", "CC0") and normal != article["licence"]:
                raise failure("article_permission_required", "An explicit licence version conflicts with the inspected JATS licence", 403)
        if re.search(r"non.commercial|no.derivatives|share.alike|all rights reserved", article["licence_statement"], re.I):
            raise failure("article_permission_required", "Conflicting licence language requires a reviewed import", 403)
        for field in ("doi", "pmid"):
            values = [str(x[field]).strip().lower() for x in (item, receipt, record, article) if x.get(field) is not None]
            if len(set(values)) > 1:
                raise failure("article_identity_mismatch", "Article identifiers disagree across JATS, metadata and receipts")
        derivative = hashlib.sha256(article["text"].encode("utf-8")).hexdigest()
        evidence = {"adapter": "pmc-acquired-jats-v1", "article_version": name,
            "original_path": original_path, "original_sha256": item["sha256"], "original_bytes": len(raw),
            "metadata_path": metadata_path, "metadata_sha256": receipt["sha256"],
            "xml_url": record["xml_url"], "publisher_md5": publisher_md5,
            "licence": article["licence"], "licence_url": article["licence_url"], "licence_statement": article["licence_statement"],
            "metadata_nonretracted": True, "retrieved_at": item.get("retrieved_utc"),
            "provenance": item["acquisition_provenance"], "metadata_provenance": receipt["acquisition_provenance"],
            "derivative_sha256": derivative, "derivative_bytes": len(article["text"].encode("utf-8")),
            "modifications": EXCLUSIONS, "currentness": "unknown"}
        credit = "; ".join(filter(None, [", ".join(article["authors"]), article["title"],
            article["copyright_statement"], article["copyright_holder"], article["copyright_year"],
            "https://pmc.ncbi.nlm.nih.gov/articles/" + identity[0] + "/", article["licence"], article["licence_url"], EXCLUSIONS]))
        rights = Rights(display=True, cache=True, index=True, embedding=True, model_input=True, derivation=True,
            licence=article["licence"], permission_reference=article["licence_url"] + " Inspected JATS and hash-validated version metadata: " + name, attribution=credit)
        metadata = SourceMetadata(source_id="L02", source_owner=article["publisher"],
            canonical_url="https://pmc.ncbi.nlm.nih.gov/articles/" + identity[0] + "/",
            access_class="open-licence-inspected", edition=name, publication_date=article["publication_date"],
            original_sha256=item["sha256"],
            retrieved_at=item.get("retrieved_utc"), doi=article["doi"] or record.get("doi"),
            pmid=article["pmid"] or (str(record["pmid"]) if record.get("pmid") else None), pmcid=identity[0],
            topic_ids=acquisition_topic_ids(item), asset_role=[MARKER, "extracted-article-text"],
            notes=["Acquired nonretraction is a dated metadata observation; currentness and clinical review remain unknown",
                   EXCLUSIONS, EVIDENCE_PREFIX + json.dumps(evidence, ensure_ascii=False, sort_keys=True)])
        return InspectedArticle(article["text"], article["title"], metadata, rights, evidence)
