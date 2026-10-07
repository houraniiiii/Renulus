"""Local backup preview, atomic merge/promotion and provider-free rebuild seams."""
from contextlib import contextmanager, ExitStack
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sqlite3
from threading import Lock, RLock
from uuid import uuid4

from ..contracts import ApiError
from .backup import (apply_records, portable_records, record_references, records_only_bundle,
                     snapshot_omissions)
from .database import utc_now
from .recovery_archive import (DEFAULT_LIMITS, backup_to, descriptor_for, original_path,
                               owned_path, strict_json, verify_file)
from .recovery_files import OriginalTransaction, recover_file_journals, remove_owned_tree
from .recovery_limits import SEGMENTED_LIMITS
from .recovery_records import apply_staged, installed_schema
from .recovery_segmented import (ValidatedRecordStage, ValidatedSegmentedArchive,
                                 backup_segmented_to, stage_legacy_bundle, stage_record_rows, validate_archive_auto)

PREVIEWS = "cache/recovery/previews"
EXPORTS = "cache/recovery/exports"
PREVIEW_MINUTES = 15
REBUILD_MODULES = ("knowledge", "memory")


class Recovery:
    def __init__(self, services, *, limits=DEFAULT_LIMITS, segmented_limits=SEGMENTED_LIMITS):
        self.services, self.limits, self.segmented_limits = services, limits, segmented_limits
        self._lock, self._mutation, self._upload = RLock(), Lock(), Lock()
        self._pending_recovery = False
        self._preview = None
        self._preview_leases, self._retired_previews = 0, []
        schema = Path(__file__).with_name("recovery_schema.sql").read_text(encoding="utf-8")
        services.db.apply_migration("storage-recovery-001", schema)
        recover_file_journals(services)
        # Previews never authorise a restore across restarts. Discard only our scratch trees.
        for location in (PREVIEWS, EXPORTS):
            directory = owned_path(services.paths, location)
            directory.mkdir(parents=True, exist_ok=True)
            for child in directory.iterdir():
                if not re.fullmatch(r"[0-9a-f]{32}", child.name):
                    raise ApiError("recovery_cache", "Unrecognised recovery cache needs inspection", 409)
                remove_owned_tree(services.paths, child)
        previous = self._last_run()
        if previous and json.loads(previous["rebuild_json"])["status"] == "running":
            self._save_rebuild(previous["id"], {"status": "blocked", "modules": {},
                "error_code": "rebuild_interrupted", "message": "The local rebuild was interrupted. Retry it to check the indexes."})

    @contextmanager
    def mutation(self):
        if not self._mutation.acquire(blocking=False):
            raise ApiError("recovery_busy", "Wait for the current backup, restore or rebuild to finish", 409, True)
        try:
            if self._pending_recovery:
                raise ApiError("recovery_pending", "Original-file rollback is pending. Restart Renulus before another recovery operation", 409, True)
            with ExitStack() as stack:
                for name in REBUILD_MODULES:
                    adapter = self.services.registry.get(name)
                    guard = getattr(adapter, "recovery_guard", None)
                    if callable(guard):
                        stack.enter_context(guard())
                        continue
                    # Baseline runtimes without an active worker remain usable.
                    # A status check cannot lock an idle worker against its next job.
                    worker = self.services.registry.get(name + "_worker")
                    if worker and callable(getattr(worker, "status", None)):
                        status = worker.status()
                        if status.get("running") or status.get("active_job"):
                            raise ApiError("recovery_busy", "The running library worker needs recovery coordination before backup or restore. Retry in the integrated runtime.", 409, True)
                yield
        finally:
            self._mutation.release()

    def begin_preview(self):
        if not self._upload.acquire(blocking=False):
            raise ApiError("recovery_busy", "Another backup file is being checked; wait and retry", 409, True)
        identifier = uuid4().hex
        try:
            directory = owned_path(self.services.paths, PREVIEWS + "/" + identifier)
            directory.mkdir()
            return identifier, directory
        except BaseException:
            self._upload.release()
            raise

    def complete_preview(self, identifier, directory):
        validated = validate_archive_auto(self.services, directory, self.limits, self.segmented_limits)
        return self._accept_preview(identifier, validated)

    def _accept_preview(self, identifier, validated):
        expires = datetime.now(timezone.utc) + timedelta(minutes=PREVIEW_MINUTES)
        with self._lock:
            self._discard_locked()
            self._preview = (identifier, expires, validated)
        return {**validated.public(), "preview_token": identifier, "expires_at": expires.isoformat()}

    def preview_records(self, records, *, exported_at, omissions=None, originals=()):
        """Local developer seam for filtered, iterable records, not an HTTP route.

        Use only a fresh scratch app for packaging. The caller selects tables and
        verified descriptors; storage validates the complete stage and owns the
        same confirmation, atomic merge/promotion and rebuild receipt lifecycle.
        """
        identifier, directory = self.begin_preview()
        keep = False
        try:
            validated = stage_record_rows(self.services, directory, records, exported_at=exported_at,
                omissions=omissions, originals=originals, limits=self.segmented_limits)
            result = self._accept_preview(identifier, validated)
            keep = True
            return result
        finally:
            self.end_upload(directory, keep=keep)

    def end_upload(self, directory, *, keep=False):
        try:
            if not keep:
                remove_owned_tree(self.services.paths, directory)
        finally:
            self._upload.release()

    def _discard_locked(self):
        if self._preview:
            preview = self._preview
            self._preview = None
            if self._preview_leases:
                self._retired_previews.append(preview[2].directory)
            else:
                remove_owned_tree(self.services.paths, preview[2].directory)

    def discard_preview(self, identifier):
        with self._lock:
            if self._preview and self._preview[0] == identifier:
                self._discard_locked()

    @contextmanager
    def validated_preview(self, identifier):
        """Local packaging lease for iterable rows and verified descriptors.

        Holds this scratch app's preview lock while a filtered stage consumes
        it. preview_records() may replace it only after all selected bytes have
        been copied. Close SQL readers inside this context; retired staging is
        removed on exit. Do not retain the yielded object beyond this context.
        """
        with self._lock:
            if not self._preview or self._preview[0] != identifier:
                raise ApiError("backup_preview", "Verify the backup again before selecting its records", 409)
            if self._preview[1] <= datetime.now(timezone.utc):
                self._discard_locked()
                raise ApiError("backup_preview_expired", "The backup preview expired; verify it again", 409, True)
            self._preview_leases += 1
            try:
                yield self._preview[2]
            finally:
                self._preview_leases -= 1
                if not self._preview_leases:
                    retired, self._retired_previews = self._retired_previews, []
                    for directory in retired:
                        remove_owned_tree(self.services.paths, directory)

    def backup(self, *, format_version=1):
        if type(format_version) is not int or format_version not in (1, 2):
            raise ApiError("backup_format", "Select supported full backup format 1 or 2")
        directory = owned_path(self.services.paths, EXPORTS + "/" + uuid4().hex)
        directory.mkdir()
        try:
            with self.mutation():
                producer, limits = (backup_segmented_to, self.segmented_limits) if format_version == 2 else (backup_to, self.limits)
                manifest = producer(self.services, directory / "backup.zip", limits)
            return directory, manifest
        except BaseException:
            remove_owned_tree(self.services.paths, directory)
            raise

    def restore_preview(self, identifier, confirmed_exported_at, acknowledge_deletion_limits):
        with self._lock:
            preview = self._preview
            if not preview or preview[0] != identifier:
                raise ApiError("backup_preview", "Select and verify the backup again before restoring", 409)
            if preview[1] <= datetime.now(timezone.utc):
                self._discard_locked()
                raise ApiError("backup_preview_expired", "The backup confirmation expired. Verify the file again", 409, True)
            if acknowledge_deletion_limits is not True or confirmed_exported_at != preview[2].bundle["exported_at"]:
                raise ApiError("restore_confirmation", "Confirm this backup's exact date and its deletion limits", 409)
            try:
                staged = preview[2] if isinstance(preview[2], (ValidatedSegmentedArchive, ValidatedRecordStage)) else None
                result = self._restore(preview[2].bundle, preview[2].originals, staged=staged)
            except BaseException as error:
                # A failed promotion may have consumed a staged file during rollback.
                # Require complete verification again before granting another restore.
                if isinstance(error, ApiError) and error.code == "recovery_pending":
                    # A pending journal still needs these staged-source identities
                    # to distinguish our moves from a destination collision.
                    self._preview = None
                else:
                    self._discard_locked()
                raise
            self._discard_locked()
            return result

    def restore_json(self, bundle, *, confirm_backup_date=False, confirmed_exported_at=None):
        if not confirm_backup_date or (confirmed_exported_at is not None and confirmed_exported_at != bundle.get("exported_at")):
            raise ApiError("restore_confirmation", "Confirm the backup date and its deletion limits before restoring", 409)
        bundle = records_only_bundle(bundle)
        identifier, directory = self.begin_preview()
        try:
            staged = stage_legacy_bundle(self.services, directory, {**bundle, "data_kind": "records-only"}, self.segmented_limits)
            return self._restore(staged.bundle, [], staged=staged)
        finally:
            self.end_upload(directory)

    def _restore(self, bundle, originals, *, staged=None):
        identifier, file_transaction = uuid4().hex, None
        limits = staged.limits if staged else self.limits
        if staged:
            rebased = bundle
        else:
            # Rebase only the explicit supported original column. Never use a source path.
            records = portable_records(bundle["records"], originals=True)
            descriptors = {entry["revision_id"]: entry for entry in originals}
            for row in records.get("knowledge_revisions", []):
                entry = descriptors.get(row["id"])
                row["original_path"] = str(original_path(self.services.paths, entry)) if entry else None
            rebased = {**bundle, "records": records}
        with self.mutation():
            try:
                if staged:
                    # Guard acquisition can wait for CPU ingestion. Recheck
                    # the exact stage after that wait, before attaching it.
                    staged.verify_stage(self.services.paths)
                with self.services.db.transaction() as conn:
                    if staged:
                        conn.execute("PRAGMA temp_store=FILE")
                        conn.execute("PRAGMA cache_size=-2048")
                        result, removed_revisions = apply_staged(conn, staged.stage, installed_schema(conn, limits), limits, bundle["exported_at"])
                        current = {"knowledge_revisions": removed_revisions}
                        def is_blocked(*identifiers):
                            return bool(conn.execute("SELECT 1 FROM temp.recovery_blocked WHERE id IN (" + ",".join("?" for _ in identifiers) + ") LIMIT 1", identifiers).fetchone())
                    else:
                        result, blocked, current = apply_records(conn, rebased)
                        def is_blocked(*identifiers):
                            return bool(blocked.intersection(identifiers))
                    promotions, removals, restored = [], [], 0
                    for entry in originals:
                        # The union of newer target and imported markers is already applied.
                        if is_blocked(entry["revision_id"], entry["document_id"]):
                            continue
                        row = conn.execute("SELECT * FROM knowledge_revisions WHERE id=?", (entry["revision_id"],)).fetchone()
                        if not row:
                            continue
                        document = conn.execute("SELECT scope_kind,deleted_at FROM knowledge_documents WHERE id=?", (row["document_id"],)).fetchone()
                        rights = strict_json(row["rights_json"])
                        if not document or document["scope_kind"] != "personal-library" or document["deleted_at"] or \
                                not isinstance(rights, dict) or rights.get("cache") is not True or rights.get("display") is not True:
                            raise ApiError("backup_rights", "The target revision no longer permits this original's local caching and display; no records were restored", 409)
                        target = original_path(self.services.paths, entry)
                        if row["original_path"] not in (None, str(target)):
                            raise ApiError("backup_original_conflict", "An existing revision has a different original location", 409)
                        owned_path(self.services.paths, entry["staged"].relative_to(self.services.paths.root).as_posix())
                        verify_file(entry["staged"], entry)
                        if target.exists():
                            verify_file(target, entry)
                        else:
                            promotions.append(entry)
                        conn.execute("UPDATE knowledge_revisions SET original_path=? WHERE id=?", (str(target), entry["revision_id"]))
                        restored += 1
                    for row in current.get("knowledge_revisions", []):
                        if not row["original_path"] or not is_blocked(*record_references(row)):
                            continue
                        try:
                            relative = Path(row["original_path"]).relative_to(self.services.paths.root).as_posix()
                        except ValueError:
                            raise ApiError("backup_path", "A deleted revision references a non-owned original; recovery will not touch it", 409) from None
                        entry = descriptor_for(row, relative, limits)
                        if original_path(self.services.paths, entry).exists():
                            removals.append(entry)
                    # All file conflicts/bytes are checked while canonical writes remain uncommitted.
                    file_transaction = OriginalTransaction(self.services, identifier, promotions, removals,
                        limits=limits, version=2 if staged else 1)
                    file_transaction.prepare()
                    file_transaction.promote()
                    result.update({"recovery_id": identifier, "restored_originals": restored,
                                   "excluded_originals": len(originals) - restored,
                                   "data_kind": bundle.get("data_kind", "records-only"),
                                   "format_version": getattr(staged, "archive_version", 2) if staged else 1,
                                   "omissions": bundle.get("omissions", {}), "cleanup_pending": False})
                    rebuild = {"status": "required", "modules": {}, "updated_at": utc_now()}
                    conn.execute("INSERT INTO storage_recovery_runs VALUES(?,?,?,?)", (
                        identifier, utc_now(), json.dumps(result), json.dumps(rebuild)))
                # The canonical receipt and original paths have committed together.
            except BaseException as error:
                if file_transaction:
                    try:
                        file_transaction.rollback()
                    except Exception:
                        self._pending_recovery = True
                        raise ApiError("recovery_pending", "Original-file rollback is pending. Restart Renulus before trying another restore", 409, True) from None
                if isinstance(error, sqlite3.DatabaseError):
                    raise ApiError("backup_references", "The export has invalid or incomplete linked records; no records were restored") from None
                if isinstance(error, OSError):
                    raise ApiError("backup_file", "Original promotion failed and was rolled back. Check disk space and retry", 409, True) from None
                raise
            try:
                file_transaction.finish()
            except (OSError, ApiError):
                result["cleanup_pending"] = True
                self.services.db.execute("UPDATE storage_recovery_runs SET result_json=? WHERE id=?", (json.dumps(result), identifier))
        result["rebuild"] = rebuild
        return result

    def _last_run(self):
        return self.services.db.fetch_one("SELECT * FROM storage_recovery_runs ORDER BY completed_at DESC,rowid DESC LIMIT 1")

    def _save_rebuild(self, identifier, rebuild):
        rebuild = {**rebuild, "updated_at": utc_now()}
        self.services.db.execute("UPDATE storage_recovery_runs SET rebuild_json=? WHERE id=?", (json.dumps(rebuild), identifier))
        return rebuild

    def status(self):
        with self._lock:
            if self._preview and self._preview[1] <= datetime.now(timezone.utc):
                self._discard_locked()
        conn = self.services.db.connect()
        try:
            omissions = snapshot_omissions(conn)
        finally:
            conn.close()
        last = self._last_run()
        return {"last_restore": json.loads(last["result_json"]) if last else None,
                "rebuild": json.loads(last["rebuild_json"]) if last else {"status": "idle", "modules": {}},
                "limits": self.limits.public(), "backup_formats": {"1": self.limits.public(), "2": self.segmented_limits.public()}, "omissions": omissions,
                "backup_scope": "Retained canonical learning records and app-owned personal-library originals. Acquisition catalogue, external originals, credentials, provider settings, indexes and managed helper weights are excluded."}

    def request_rebuild(self):
        with self._lock:
            if self._pending_recovery:
                raise ApiError("recovery_pending", "Original-file rollback is pending. Restart Renulus before rebuilding indexes", 409, True)
            last = self._last_run()
            if not last:
                raise ApiError("rebuild_unnecessary", "Restore a backup before requesting its local index rebuild", 409)
            rebuild = json.loads(last["rebuild_json"])
            if rebuild["status"] == "running":
                return last["id"], rebuild, False
            rebuild = self._save_rebuild(last["id"], {"status": "running", "modules": {
                name: {"status": "queued"} for name in REBUILD_MODULES}})
            return last["id"], rebuild, True

    def rebuild(self, identifier):
        # Public module seams own extraction/index staging/switching and their
        # serial engine locks. Storage never scans their originals or indexes.
        if not self._mutation.acquire(blocking=False):
            self._save_rebuild(identifier, {"status": "blocked", "modules": {},
                "error_code": "recovery_busy", "message": "Another recovery operation is running. Retry the local rebuild."})
            return
        try:
            if self._pending_recovery:
                self._save_rebuild(identifier, {"status": "blocked", "modules": {},
                    "error_code": "recovery_pending", "message": "Original-file rollback is pending. Restart Renulus before rebuilding indexes."})
                return
            last = self._last_run()
            if not last or last["id"] != identifier:
                return
            modules = {}
            for name in REBUILD_MODULES:
                adapter = self.services.registry.get(name)
                # These are the supplied public seams, not fallback engine scans.
                method = getattr(adapter, "reindex" if name == "memory" else "rebuild_index", None)
                if adapter is None:
                    modules[name] = {"status": "not-installed", "rebuilt_records": 0}
                elif not callable(method):
                    modules[name] = {"status": "blocked", "error_code": "rebuild_seam_missing",
                        "message": f"The {name} runtime does not expose its local rebuild yet."}
                else:
                    try:
                        outcome = method()
                        if name == "memory" and isinstance(outcome, dict) and outcome.get("ready") is True and \
                                type(outcome.get("count")) is int and outcome["count"] >= 0:
                            outcome = {"status": "complete", "rebuilt_records": outcome["count"],
                                       "rebuilt_unit": "records"}
                        elif name == "knowledge" and isinstance(outcome, dict) and outcome.get("status") == "ready":
                            if type(outcome.get("passages")) is not int or outcome["passages"] < 0 or \
                                    type(outcome.get("cleanup_pending")) is not bool:
                                raise ValueError("invalid knowledge rebuild outcome")
                            cleanup_pending = outcome["cleanup_pending"]
                            outcome = {"status": "partial" if cleanup_pending else "complete",
                                       "rebuilt_records": outcome["passages"], "rebuilt_unit": "passages",
                                       "cleanup_pending": cleanup_pending}
                            if cleanup_pending:
                                outcome["message"] = "Library search is ready; retired index cleanup is pending. Retry the local rebuild to finish cleanup."
                        if not isinstance(outcome, dict) or outcome.get("status") not in ("complete", "blocked", "partial", "failed"):
                            raise ValueError("invalid rebuild outcome")
                        modules[name] = {key: value for key, value in outcome.items()
                                         if key in ("status", "rebuilt_records", "rebuilt_unit", "cleanup_pending", "error_code", "message")}
                    except ApiError as error:
                        modules[name] = {"status": "blocked" if error.retryable or error.status == 503 else "failed",
                            "error_code": error.code, "message": error.message}
                    except Exception:
                        modules[name] = {"status": "failed", "error_code": "rebuild_failed",
                            "message": f"The {name} index could not be rebuilt. Check installed offline helpers and retry."}
                self._save_rebuild(identifier, {"status": "running", "modules": modules})
            states = {module["status"] for module in modules.values()}
            state = "failed" if "failed" in states else "blocked" if "blocked" in states else (
                "partial" if "partial" in states else "complete")
            self._save_rebuild(identifier, {"status": state, "modules": modules})
        finally:
            self._mutation.release()
