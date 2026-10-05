# SPDX-License-Identifier: MIT
"""Prepare a fresh local Library/content profile through supported ZIP recovery.

Developer packaging tool. Acquired originals are local data, never public bundle
assets. The source is accessed only through its guarded loopback backup API.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
from urllib.parse import urlsplit
import zipfile


# Enumerate current canonical schemas. A future prefix match must never import
# a new credential, discovery, learner or derived table into a delivery profile.
CONTENT_TABLES = frozenset({
    "content_packs", "content_topics", "content_case_versions",
    "content_question_versions", "content_pack_topics", "content_pack_cases",
    "content_pack_questions", "content_active_pack",
    "content_question_withdrawals", "content_pack_withdrawals",
})
KNOWLEDGE_TABLES = frozenset({
    "knowledge_documents", "knowledge_revisions", "knowledge_jobs",
    "knowledge_passages", "knowledge_cleanup", "knowledge_source_status_events",
})
CANONICAL_TABLES = CONTENT_TABLES | KNOWLEDGE_TABLES | {"deletion_ledger", "retrieval_imports"}
TOMBSTONES = {"knowledge-document": ("doc_",), "document": ("doc_",),
    "knowledge-revision": ("rev_",), "knowledge-passage": ("passage_", "pass_"), "knowledge-job": ("ingest_", "job_")}
FRESH_APP_SEEDS = frozenset({"update_source_checks", "update_schedule"})
BLOCK = 1024 * 1024


class DeliveryError(Exception):
    """A safe, reviewable preparation failure without source payloads."""


def checked_directory(value, *, fresh=False):
    path = Path(value)
    if fresh and os.path.lexists(path):
        raise DeliveryError("Output profile already exists; select a new path. Nothing was cleared.")
    if not path.is_absolute() or ".." in path.parts:
        raise DeliveryError("Use explicit absolute directories without parent traversal.")
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise DeliveryError("Profile and asset directories cannot follow links or Windows junctions.")
    path = path.resolve()
    if fresh:
        if not path.parent.is_dir():
            raise DeliveryError("The output profile's parent must already be an explicit directory.")
        if os.name == "nt" and len(str(path)) > 60:
            raise DeliveryError("Use a compact output profile of at most 60 characters for native LanceDB.")
    elif not path.is_dir():
        raise DeliveryError("The explicitly selected directory is missing.")
    return path


def backup_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in ("localhost", "127.0.0.1") or \
            parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise DeliveryError("Source URL must be a credential-free HTTP loopback app URL.")
    if parsed.path.rstrip("/") not in ("", "/api/v1/data/backup"):
        raise DeliveryError("Use the local app base URL or its exact /api/v1/data/backup endpoint.")
    try:
        parsed.port
    except ValueError:
        raise DeliveryError("The source URL has an invalid local port.") from None
    return value.rstrip("/") if parsed.path.rstrip("/") else value.rstrip("/") + "/api/v1/data/backup"


def runtime_from(source_root):
    runtime = source_root / "runtime"
    if not (runtime / "renulus/server.py").is_file() or not (source_root / "packaging/runtime/helper-assets.json").is_file():
        raise DeliveryError("Source-root must contain the app runtime and reviewed public helper contract.")
    sys.path.insert(0, str(runtime))
    from renulus import server
    if not Path(server.__file__).resolve().is_relative_to(runtime):
        raise DeliveryError("A different app runtime is already imported; run the tool in its own process.")
    return server


def public_helper_paths(root, source_root, helper_root):
    from renulus.storage import AppPaths
    class PublicHelpers(AppPaths):
        @property
        def helpers(self):
            return helper_root
    return PublicHelpers(root, source_root)


@contextmanager
def local_app(server, root, source_root, helper_root, *, configure=False):
    from renulus.runtime.helpers import HelperAssets
    app = server.create_app(root, source_root=source_root)
    services = app.state.services
    # The public helper registry owns validation. All writable state still uses
    # this new profile; only declared, trusted CPU artifacts come from elsewhere.
    services.paths = public_helper_paths(root, source_root, helper_root)
    helpers = HelperAssets(services.paths)
    services.registry["helpers"] = helpers
    if configure:
        helpers.startup.configure()
    try:
        # Do not enter the app lifespan: delivery keeps queued ingestion durable
        # and never starts learner-memory capture or source/retrieval scheduling.
        yield app, services
    finally:
        services.registry["knowledge_worker"].stop(timeout=10)
        services.registry["knowledge"].index.close()
        asyncio.run(services.registry["memory"].close())
        asyncio.run(services.registry["provider"].close())
        helpers.startup.close()


def download_backup(url, path, limits, timeout):
    import httpx
    size, digest, deadline = 0, hashlib.sha256(), time.monotonic() + timeout
    # No environment proxies, redirects, cookies, authentication or token files.
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=timeout) as client:
        with client.stream("GET", url, headers={"Accept": "application/zip"}) as response:
            if response.status_code != 200:
                raise DeliveryError(f"Source backup API refused export (HTTP {response.status_code}). "
                    "The source must fit the explicitly selected format bounds before trimming.")
            if response.headers.get("content-type", "").split(";")[0] != "application/zip":
                raise DeliveryError("Source API did not return a supported ZIP backup.")
            declared = response.headers.get("content-length")
            if declared is not None and (len(declared) > 20 or not declared.isascii() or
                    not declared.isdecimal() or int(declared) > limits.archive_bytes):
                raise DeliveryError("Source ZIP content length exceeds the bounded archive limit or is invalid.")
            with path.open("xb") as destination:
                for block in response.iter_bytes(BLOCK):
                    size += len(block)
                    if size > limits.archive_bytes or time.monotonic() > deadline:
                        raise DeliveryError("Source download exceeded its bounded archive size or deadline.")
                    digest.update(block)
                    destination.write(block)
    if declared is not None and size != int(declared):
        raise DeliveryError("Source ZIP download is incomplete.")
    return {"bytes": size, "sha256": digest.hexdigest()}


def delivery_tombstone(row):
    return any(re.fullmatch(re.escape(prefix) + r"[A-Za-z0-9_-]{1,100}", row["entity_id"])
        for prefix in TOMBSTONES.get(row["entity_type"], ()))


def delivery_records(bundle):
    records = bundle["records"]
    selected = {name: rows for name, rows in records.items() if name in CONTENT_TABLES}
    documents = [row for row in records.get("knowledge_documents", [])
        if row["scope_kind"] == "personal-library" and row["scope_entity"] is None
        and row["reserved"] == 0 and not row["deleted_at"]]
    document_ids = {row["id"] for row in documents}
    revisions = [row for row in records.get("knowledge_revisions", []) if row["document_id"] in document_ids]
    revision_ids = {row["id"] for row in revisions}
    for document in documents:
        for key in ("active_revision", "latest_revision"):
            if document[key] is not None and document[key] not in revision_ids:
                raise DeliveryError("A retained Library document has an incomplete revision binding.")
    selected["knowledge_documents"], selected["knowledge_revisions"] = documents, revisions
    for name in ("knowledge_jobs", "knowledge_passages", "knowledge_cleanup"):
        selected[name] = [row for row in records.get(name, []) if row["revision_id"] in revision_ids]
    selected["knowledge_source_status_events"] = records.get("knowledge_source_status_events", [])
    selected["deletion_ledger"] = [row for row in records.get("deletion_ledger", []) if delivery_tombstone(row)]
    # The current producer omits this table. If a coordinated future producer
    # includes it, retain only complete bindings to documents kept by this slice.
    if "retrieval_imports" in records:
        by_revision = {row["id"]: row["document_id"] for row in revisions}
        by_job = {row["id"]: row["revision_id"] for row in selected["knowledge_jobs"]}
        selected["retrieval_imports"] = [row for row in records["retrieval_imports"]
            if row["document_id"] in document_ids and by_revision.get(row["revision_id"]) == row["document_id"]
            and by_job.get(row["job_id"]) == row["revision_id"]]
    return {**bundle, "records": selected}


def report_source_snapshot(*, source_url, source_root, timeout=300):
    """Measure a bounded records-only API response, without originals or a profile.

    This is capacity evidence, never a ZIP integrity or rebuild readiness proof.
    A producer refusal is returned honestly; no direct source-database fallback.
    """
    import httpx
    url = backup_url(source_url).rsplit("/", 1)[0] + "/export"
    runtime_from(checked_directory(source_root))
    from renulus.storage.backup import MAX_RECORDS
    from renulus.storage.recovery_archive import DEFAULT_LIMITS, canonical_json, strict_json
    if not 1 <= timeout <= 1800:
        raise DeliveryError("Choose a source download timeout between 1 and 1800 seconds.")
    report = {"mode": "metadata-only", "limits": DEFAULT_LIMITS.public(),
        "canonical_record_limit": MAX_RECORDS, "zip_bytes": None,
        "originals_verified": False, "rebuild_verified": False}
    deadline, data = time.monotonic() + timeout, bytearray()
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=timeout) as client:
        with client.stream("GET", url, headers={"Accept": "application/json"}) as response:
            report["http_status"] = response.status_code
            # Never follow redirects or read an unbounded error body.
            bound = DEFAULT_LIMITS.json_bytes if response.status_code == 200 else 64 * 1024
            declared = response.headers.get("content-length")
            if declared is not None and (len(declared) > 20 or not declared.isascii() or
                    not declared.isdecimal() or int(declared) > bound):
                raise DeliveryError("Source metadata response exceeds its bounded size or has an invalid content length.")
            for block in response.iter_bytes(BLOCK):
                if len(data) + len(block) > bound or time.monotonic() > deadline:
                    raise DeliveryError("Source metadata response exceeded its bounded size or deadline.")
                data.extend(block)
            if declared is not None and len(data) != int(declared):
                raise DeliveryError("Source metadata response is incomplete.")
            if response.status_code != 200:
                report.update(status="blocked", error_code="source_export_refused")
                if response.status_code == 413:
                    report["error_code"] = "backup_limit"
                return report
            if response.headers.get("content-type", "").split(";")[0] != "application/json":
                raise DeliveryError("Source metadata API did not return canonical JSON.")
    bundle = strict_json(data)
    if not isinstance(bundle, dict) or bundle.get("format") != "renulus-canonical-export" or \
            not isinstance(bundle.get("records"), dict) or any(
                not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
                for rows in bundle["records"].values()):
        raise DeliveryError("Source metadata response is not a canonical record snapshot.")
    counts = {name: len(rows) for name, rows in bundle["records"].items()}
    if sum(counts.values()) > MAX_RECORDS:
        raise DeliveryError("Source metadata exceeds the canonical record limit.")
    filtered = delivery_records(bundle)
    report.update(status="within_canonical_bounds", exported_at=bundle.get("exported_at"),
        canonical_json_bytes=len(data), canonical_json_sha256=hashlib.sha256(data).hexdigest(),
        canonical_records=sum(counts.values()), tables=counts,
        candidate_tables={name: len(rows) for name, rows in filtered["records"].items()},
        candidate_records_only_json_bytes=len(canonical_json(filtered)),
        candidate_library_revision_bytes=sum(row["bytes"] for row in filtered["records"]["knowledge_revisions"]),
        catalogue_present="knowledge_catalogue" in counts,
        discovery_omission=bundle.get("omissions", {}).get("knowledge_catalogue", {}).get("records"))
    return report


def write_delivery_archive(validated, path, limits):
    from renulus.storage.recovery_archive import canonical_json, FULL_FORMAT, verify_file
    bundle = delivery_records(validated.bundle)
    document_ids = {row["id"] for row in bundle["records"]["knowledge_documents"]}
    originals = [entry for entry in validated.originals if entry["document_id"] in document_ids]
    backed_revisions = {entry["revision_id"] for entry in originals}
    for row in bundle["records"]["knowledge_documents"]:
        if any(row[key] is not None and row[key] not in backed_revisions for key in ("active_revision", "latest_revision")):
            raise DeliveryError("A retained active/latest Library revision has no verified original; repair the source first.")
    data = canonical_json(bundle)
    if len(data) > limits.json_bytes:
        raise DeliveryError("Filtered canonical records exceed the unchanged JSON bound.")
    manifest = {"format": FULL_FORMAT, "format_version": bundle["format_version"],
        "schema_version": bundle["schema_version"], "exported_at": bundle["exported_at"],
        "records": {"path": "records.json", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
        "originals": [{key: value for key, value in entry.items() if key != "staged"} for entry in originals]}
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=False) as archive:
        archive.writestr("manifest.json", canonical_json(manifest))
        archive.writestr("records.json", data)
        for entry in originals:
            verify_file(entry["staged"], entry)
            digest, size = hashlib.sha256(), 0
            with entry["staged"].open("rb") as source, archive.open(entry["path"], "w") as destination:
                while block := source.read(BLOCK):
                    size += len(block)
                    if size > entry["bytes"]:
                        raise DeliveryError("A staged original grew while writing the filtered archive.")
                    digest.update(block)
                    destination.write(block)
            if size != entry["bytes"] or digest.hexdigest() != entry["sha256"]:
                raise DeliveryError("A staged original changed while writing the filtered archive.")
    if path.stat().st_size > limits.archive_bytes:
        raise DeliveryError("Filtered ZIP exceeds the unchanged archive bound.")
    return bundle, manifest


async def restore_through_api(app, archive, *, format_version=1):
    import httpx
    def checked(response):
        if response.status_code != 200:
            error = response.json().get("error", {})
            raise DeliveryError("Target recovery API refused preparation: " + error.get("code", "invalid_response"))
        return response.json()
    async def blocks():
        with archive.open("rb") as source:
            while block := source.read(BLOCK):
                yield block
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://testserver", trust_env=False) as client:
        preview = checked(await client.post("/api/v1/data/backup/preview?format_version=" + str(format_version), content=blocks(),
            headers={"content-type": "application/zip", "content-length": str(archive.stat().st_size)}))
        restored = checked(await client.post("/api/v1/data/backup/restore", json={
            "preview_token": preview["preview_token"], "confirmed_exported_at": preview["exported_at"],
            "acknowledge_deletion_limits": True}))
        report = checked(await client.get("/api/v1/data/recovery"))
    if report["rebuild"]["status"] != "complete" or restored.get("cleanup_pending"):
        raise DeliveryError("Verified restore is present, but rebuild/cleanup is incomplete; the fresh output was retained for inspection.")
    if report["rebuild"]["modules"]["memory"].get("rebuilt_records") != 0:
        raise DeliveryError("Delivery unexpectedly rebuilt learner memories.")
    return restored, report["rebuild"]


DELIVERY_DOCUMENT = "d.scope_kind='personal-library' AND d.scope_entity IS NULL AND d.reserved=0 AND d.deleted_at IS NULL"


@contextmanager
def delivery_stage(validated, services):
    """Read a verified owned stage; archive SQL and source databases are unused."""
    validated.verify_stage(services.paths)
    with closing(sqlite3.connect(validated.stage.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA cache_size=-2048")
        conn.execute("BEGIN")
        yield conn
    validated.verify_stage(services.paths)


def selected_stage_rows(validated, services):
    available = validated.manifest["canonical"]["tables"]
    with delivery_stage(validated, services) as conn:
        for pointer in ("active_revision", "latest_revision"):
            missing = conn.execute(f"SELECT d.id FROM knowledge_documents d LEFT JOIN knowledge_revisions r ON r.id=d.{pointer} WHERE " + DELIVERY_DOCUMENT +
                f" AND d.{pointer} IS NOT NULL AND (r.id IS NULL OR r.document_id<>d.id OR r.original_path IS NULL) LIMIT 1").fetchone()
            if missing:
                raise DeliveryError("A retained active/latest Library revision has no verified original; repair the source first.")
        for name in sorted(CANONICAL_TABLES & available.keys()):
            # The table inventory and SQL below are installed selection policy.
            # References are joined on disk, without whole-corpus identity sets.
            if name in CONTENT_TABLES or name == "knowledge_source_status_events":
                sql = f'SELECT * FROM "{name}" ORDER BY rowid'
            elif name == "knowledge_documents":
                sql = "SELECT d.* FROM knowledge_documents d WHERE " + DELIVERY_DOCUMENT + " ORDER BY d.rowid"
            elif name == "knowledge_revisions":
                sql = "SELECT r.* FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE " + DELIVERY_DOCUMENT + " ORDER BY r.rowid"
            elif name in {"knowledge_jobs", "knowledge_passages", "knowledge_cleanup"}:
                sql = f'SELECT v.* FROM "{name}" v JOIN knowledge_revisions r ON r.id=v.revision_id JOIN knowledge_documents d ON d.id=r.document_id WHERE ' + DELIVERY_DOCUMENT + " ORDER BY v.rowid"
            elif name == "retrieval_imports":
                sql = "SELECT v.* FROM retrieval_imports v JOIN knowledge_documents d ON d.id=v.document_id JOIN knowledge_revisions r ON r.id=v.revision_id AND r.document_id=d.id JOIN knowledge_jobs j ON j.id=v.job_id AND j.revision_id=r.id WHERE " + DELIVERY_DOCUMENT + " ORDER BY v.rowid"
            elif name == "deletion_ledger":
                sql = "SELECT * FROM deletion_ledger ORDER BY rowid"
            else:
                raise DeliveryError("An unreviewed delivery table needs an explicit selection policy.")
            for raw in conn.execute(sql):
                row = dict(raw)
                if name == "deletion_ledger" and not delivery_tombstone(row):
                    continue
                yield name, row


def selected_stage_originals(validated, services):
    with delivery_stage(validated, services) as conn:
        for entry in validated.originals:
            if conn.execute("SELECT d.id FROM knowledge_documents d WHERE d.id=? AND " + DELIVERY_DOCUMENT, (entry["document_id"],)).fetchone():
                yield entry


def prepare_segmented_archive(validator, url, work, timeout):
    """Verify all source bytes, select on disk, restore a scratch, re-export 2."""
    from renulus.storage.recovery_files import remove_owned_tree
    from renulus.storage.recovery_limits import SEGMENTED_LIMITS
    recovery = validator.registry["data_recovery"]
    identifier, directory = recovery.begin_preview()
    keep = False
    try:
        downloaded = download_backup(url + "?format_version=2", directory / "input.zip", SEGMENTED_LIMITS, timeout)
        checked = recovery.complete_preview(identifier, directory)
        keep = True
    finally:
        recovery.end_upload(directory, keep=keep)
    with recovery.validated_preview(identifier) as validated:
        if checked.get("format_version") != 2:
            raise DeliveryError("The source did not supply the requested segmented backup format.")
        source_counts = validated.manifest["canonical"]["tables"]
        selected = recovery.preview_records(selected_stage_rows(validated, validator),
            exported_at=checked["exported_at"], omissions=checked["omissions"],
            originals=selected_stage_originals(validated, validator))
    # This scratch does not run learners, providers, workers or derived rebuild.
    restored = recovery.restore_preview(selected["preview_token"], selected["exported_at"], True)
    if restored.get("cleanup_pending") or restored.get("restored_originals") != selected["original_count"]:
        raise DeliveryError("Filtered scratch originals were not promoted completely.")
    # The scratch constructor creates reviewed public source-check defaults.
    # Leave the final target to seed its own fresh values instead of importing
    # this scratch profile's timestamps/configuration through the re-export.
    with validator.db.transaction() as conn:
        for name in FRESH_APP_SEEDS:
            conn.execute(f'DELETE FROM "{name}"')
    directory, manifest = recovery.backup(format_version=2)
    try:
        if any(count for name, count in manifest["canonical"]["tables"].items() if name not in CANONICAL_TABLES):
            raise DeliveryError("Filtered scratch re-export contains non-delivery canonical records.")
        shutil.copyfile(directory / "backup.zip", work / "delivery.zip")
    finally:
        remove_owned_tree(validator.paths, directory)
    return downloaded, manifest, source_counts


def fresh_app_seeds(services):
    with closing(services.db.connect()) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: [dict(row) for row in conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
            for name in FRESH_APP_SEEDS & names}


def audit_target(services, manifest, seeds):
    from renulus.storage.recovery_archive import original_path, verify_file
    with closing(services.db.connect()) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        bookkeeping = {"migration_ledger", "memory_index_state", "preferences", "storage_recovery_runs"}
        for name in names:
            if name in CANONICAL_TABLES | bookkeeping or name.startswith("sqlite_"):
                continue
            if name in FRESH_APP_SEEDS:
                current = [dict(row) for row in conn.execute(f'SELECT * FROM "{name}" ORDER BY rowid')]
                if current != seeds.get(name):
                    raise DeliveryError("Source configuration/history changed fresh app defaults: " + name)
                continue
            if conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]:
                raise DeliveryError("Non-delivery records appeared in the fresh target: " + name)
        if any(row[0] != "knowledge.index_generation" for row in conn.execute("SELECT key FROM preferences")):
            raise DeliveryError("Learner/config preferences appeared in the delivery profile.")
        for row in conn.execute("SELECT * FROM deletion_ledger"):
            if not delivery_tombstone(row):
                raise DeliveryError("Non-knowledge deletion history appeared in the delivery profile.")
        queued = conn.execute("SELECT COUNT(*) FROM knowledge_jobs WHERE state='queued'").fetchone()[0]
        for entry in manifest["originals"]:
            stored = conn.execute("SELECT original_path,sha256,bytes FROM knowledge_revisions WHERE id=?", (entry["revision_id"],)).fetchone()
            path = original_path(services.paths, entry)
            if not stored or stored["original_path"] != str(path) or stored["sha256"] != entry["sha256"] or stored["bytes"] != entry["bytes"]:
                raise DeliveryError("A restored original's canonical hash/size/rebased path differs.")
            verify_file(path, entry)
    if (services.paths.state / "runtime/connections.dpapi").exists():
        raise DeliveryError("Credentials unexpectedly appeared in the fresh target.")
    return queued


def prepare_delivery_profile(*, source_url, output_profile, helper_root, source_root, timeout=300, format_version=1):
    output = checked_directory(output_profile, fresh=True)
    url = backup_url(source_url)
    helpers = checked_directory(helper_root)
    source = checked_directory(source_root)
    if type(format_version) is not int or format_version not in (1, 2):
        raise DeliveryError("Choose the explicit supported backup format 1 or 2.")
    if not 1 <= timeout <= 1800:
        raise DeliveryError("Choose a source download timeout between 1 and 1800 seconds.")
    for other in (helpers, source):
        if output.is_relative_to(other) or other.is_relative_to(output):
            raise DeliveryError("Use an independent output profile outside the app source and public helper directory.")
    server = runtime_from(source)
    from renulus.runtime.helpers import HelperAssets
    from renulus.storage.recovery_archive import DEFAULT_LIMITS, validate_archive
    from renulus.storage.recovery_limits import SEGMENTED_LIMITS
    from renulus.contracts import ApiError
    assets = HelperAssets(public_helper_paths(output, source, helpers))
    try:
        assets.embedding_config()
        assets.docling_config()
    except ApiError as error:
        raise DeliveryError(error.code + ": " + error.message + " No output profile was created.") from None
    work = Path(tempfile.mkdtemp(prefix=".rnl-dp-", dir=output.parent)).resolve()
    created = False
    try:
        with local_app(server, work / "v", source, helpers) as (_, validator):
            if format_version == 2:
                downloaded, manifest, source_counts = prepare_segmented_archive(validator, url, work, timeout)
                counts = {name: count for name, count in manifest["canonical"]["tables"].items() if name in CANONICAL_TABLES}
                canonical = {"format_version": 2, "canonical_bytes": manifest["canonical"]["bytes"],
                    "canonical_segments": len(manifest["canonical"]["segments"])}
                limits = SEGMENTED_LIMITS
            else:
                directory = validator.paths.cache / "delivery-source"
                directory.mkdir()
                downloaded = download_backup(url, directory / "input.zip", DEFAULT_LIMITS, timeout)
                validated = validate_archive(validator, directory, DEFAULT_LIMITS)
                filtered, manifest = write_delivery_archive(validated, work / "delivery.zip", DEFAULT_LIMITS)
                source_counts = {name: len(rows) for name, rows in validated.bundle["records"].items()}
                counts = {name: len(rows) for name, rows in filtered["records"].items()}
                canonical = {"format_version": 1, "canonical_json_bytes": manifest["records"]["bytes"], "canonical_json_sha256": manifest["records"]["sha256"]}
                limits = DEFAULT_LIMITS
                # The entire original source archive was checked before trimming.
                (directory / "input.zip").unlink()
        checked_directory(output, fresh=True)
        output.mkdir(exist_ok=False)  # Atomic refusal if another owner won the path.
        created = True
        with local_app(server, output, source, helpers, configure=True) as (app, target):
            seeds = fresh_app_seeds(target)
            restored, rebuild = asyncio.run(restore_through_api(app, work / "delivery.zip", format_version=format_version))
            queued = audit_target(target, manifest, seeds)
            if restored["restored_originals"] != len(manifest["originals"]):
                raise DeliveryError("The fresh delivery did not restore every selected original.")
        return {"status": "ready", "profile": str(output), "exported_at": manifest["exported_at"],
            "source_archive": downloaded, **canonical, "tables": counts,
            "omitted_tables": {name: count for name, count in source_counts.items() if name not in CANONICAL_TABLES},
            "originals": len(manifest["originals"]), "verified_originals": len(manifest["originals"]),
            "original_bytes": sum(row["bytes"] for row in manifest["originals"]),
            "queued_jobs": queued, "rebuild": rebuild, "limits": limits.public(),
            "helper_policy": "Verified public assets were used read-only; the native package supplies managed helpers separately.",
            "retrieval_imports_policy": "Current source ZIP omits replay bindings; retained Library publication metadata/originals remain canonical."}
    except ApiError as error:
        suffix = " The newly created output is incomplete and was not cleared." if created else " No output profile was created."
        raise DeliveryError(error.code + ": " + error.message + suffix) from None
    finally:
        # This exact temporary root was created by this invocation, never a
        # profile supplied by the user. Check its resolved ownership before purge.
        if work.parent != output.parent or work.resolve() != work or not work.name.startswith(".rnl-dp-"):
            raise DeliveryError("Temporary workspace ownership changed; cleanup was refused.")
        shutil.rmtree(work)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", required=True, help="Proxy-authenticated local app URL; no token is read")
    parser.add_argument("--output-profile", type=Path, help="Fresh absolute compact profile, at most 60 characters on Windows")
    parser.add_argument("--helper-root", type=Path, help="Exact verified public CPU asset directory, used read-only")
    parser.add_argument("--source-root", required=True, type=Path, help="Explicit app source/bundle root containing runtime, content and trusted helper contract")
    parser.add_argument("--report-only", action="store_true", help="Measure bounded records-only metadata; do not download originals, load helpers or create a profile")
    parser.add_argument("--timeout", type=float, default=300, help="Bounded source download timeout in seconds (default 300)")
    parser.add_argument("--format-version", type=int, choices=(1, 2), default=2, help="Full backup format for preparation; default segmented 2, legacy 1 remains supported")
    args = parser.parse_args(argv)
    if not args.report_only and (args.output_profile is None or args.helper_root is None):
        parser.error("Preparation requires --output-profile and --helper-root; use --report-only for metadata capacity.")
    try:
        if args.report_only:
            result = report_source_snapshot(source_url=args.source_url, source_root=args.source_root, timeout=args.timeout)
        else:
            result = prepare_delivery_profile(**{key: value for key, value in vars(args).items() if key != "report_only"})
    except DeliveryError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Delivery preparation failed ({type(error).__name__}); no existing profile was cleared.", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
