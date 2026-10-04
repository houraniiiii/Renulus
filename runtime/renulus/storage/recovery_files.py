"""Journalled original-file promotion, paired with a canonical SQLite receipt.

SQLite chooses the outcome. On restart a committed receipt finishes cleanup;
without it, only verified files from this operation are rolled back. Journals
contain bounded relative app-owned paths, never user collection paths.
"""
import os
from pathlib import Path
import re
import shutil

from ..contracts import ApiError
from .recovery_archive import (DEFAULT_LIMITS, ORIGINAL, canonical_json, original_path,
                               owned_path, strict_json, verify_file)

TRANSACTIONS = "state/recovery/transactions"
STAGED = re.compile(r"cache/recovery/previews/[0-9a-f]{32}/verified/[0-9]{1,4}")


def remove_owned_tree(paths, directory):
    relative = directory.relative_to(paths.root).as_posix()
    owned_path(paths, relative)
    if directory.exists():
        for folder, directories, files in os.walk(directory, followlinks=False):
            for name in [*directories, *files]:
                owned_path(paths, (Path(folder) / name).relative_to(paths.root).as_posix())
        shutil.rmtree(directory)


def _move_no_replace(source, destination):
    # Windows rename refuses an existing target. Both directories are in the
    # same profile/volume. The link variant preserves that guarantee in POSIX tests.
    if os.name == "nt":
        os.rename(source, destination)
    else:
        os.link(source, destination)
        source.unlink()


class OriginalTransaction:
    def __init__(self, services, identifier, promotions, removals):
        self.services, self.paths = services, services.paths
        self.id, self.promotions, self.removals = identifier, promotions, removals
        self.directory = owned_path(self.paths, TRANSACTIONS + "/" + identifier)
        self.entries = []
        for action, entries in (("promote", promotions), ("remove", removals)):
            for entry in entries:
                descriptor = {key: entry[key] for key in ("path", "document_id", "revision_id", "bytes", "sha256")}
                descriptor["action"] = action
                if action == "promote":
                    descriptor["staged"] = entry["staged"].relative_to(self.paths.root).as_posix()
                self.entries.append(descriptor)

    def prepare(self):
        # All conflicts and bytes are checked before the first move.
        if len(self.entries) > 2 * DEFAULT_LIMITS.originals or sum(entry["bytes"] for entry in self.removals) > DEFAULT_LIMITS.total_original_bytes:
            raise ApiError("backup_limit", "Reconciled original cleanup exceeds this bounded restore", 413)
        for entry in self.promotions:
            target = original_path(self.paths, entry)
            if target.exists():
                raise ApiError("backup_original_conflict", "A target original appeared during restore; retry without changing it", 409)
            owned_path(self.paths, entry["staged"].relative_to(self.paths.root).as_posix())
            verify_file(entry["staged"], entry)
        for entry in self.removals:
            verify_file(original_path(self.paths, entry), entry)
        self.directory.mkdir(parents=True, exist_ok=False)
        (self.directory / "removed").mkdir()
        data = canonical_json({"version": 1, "id": self.id, "entries": self.entries})
        if len(data) > DEFAULT_LIMITS.manifest_bytes:
            raise ApiError("backup_limit", "The file recovery journal exceeds its size limit", 413)
        with (self.directory / "journal.json").open("xb") as journal:
            journal.write(data)
            journal.flush()
            os.fsync(journal.fileno())

    def promote(self):
        for index, entry in enumerate(self.entries):
            target = original_path(self.paths, entry)
            if entry["action"] == "remove":
                _move_no_replace(target, self.directory / "removed" / str(index))
        for entry in self.promotions:
            target = original_path(self.paths, entry)
            target.parent.mkdir(parents=True, exist_ok=True)
            # Recheck parents after creation, before any file move.
            original_path(self.paths, entry)
            _move_no_replace(entry["staged"], target)

    def rollback(self):
        _rollback(self.paths, self.directory, self.entries)
        remove_owned_tree(self.paths, self.directory)

    def finish(self):
        remove_owned_tree(self.paths, self.directory)


def _rollback(paths, directory, entries):
    for index, entry in reversed(list(enumerate(entries))):
        target = original_path(paths, entry)
        if entry["action"] == "promote":
            staged = owned_path(paths, entry["staged"])
            if staged.exists():
                # The move did not consume its source. A same-byte file that
                # appeared at the destination belongs to someone else.
                if target.exists() and os.name != "nt" and staged.samefile(target):
                    # POSIX link/unlink may have failed between the two calls.
                    verify_file(target, entry, unique=False)
                    target.unlink()
                continue
            if target.exists():
                verify_file(target, entry)
                target.unlink()
        else:
            saved = directory / "removed" / str(index)
            if not saved.exists():
                continue
            owned_path(paths, saved.relative_to(paths.root).as_posix())
            verify_file(saved, entry)
            if target.exists():
                verify_file(target, entry)
                saved.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                original_path(paths, entry)
                _move_no_replace(saved, target)


def recover_file_journals(services):
    root = owned_path(services.paths, TRANSACTIONS)
    root.mkdir(parents=True, exist_ok=True)
    for directory in root.iterdir():
        if not re.fullmatch(r"[0-9a-f]{32}", directory.name):
            raise ApiError("recovery_journal", "Unrecognised recovery state needs inspection before another restore", 409)
        owned_path(services.paths, directory.relative_to(services.paths.root).as_posix())
        journal = directory / "journal.json"
        owned_path(services.paths, journal.relative_to(services.paths.root).as_posix())
        if not journal.exists():
            # A crash between mkdir and journal creation cannot have moved a file.
            if any(item.is_file() for item in directory.rglob("*")):
                raise ApiError("recovery_journal", "An incomplete recovery journal needs inspection", 409)
            remove_owned_tree(services.paths, directory)
            continue
        if journal.stat().st_size > DEFAULT_LIMITS.manifest_bytes:
            raise ApiError("recovery_journal", "Recovery journal exceeds its bounded format", 409)
        data = strict_json(journal.read_bytes())
        if not isinstance(data, dict) or set(data) != {"version", "id", "entries"} or \
                type(data["version"]) is not int or data["version"] != 1 or data["id"] != directory.name or not isinstance(data["entries"], list) or \
                len(data["entries"]) > 2 * DEFAULT_LIMITS.originals:
            raise ApiError("recovery_journal", "Recovery journal has an invalid format", 409)
        seen = set()
        for entry in data["entries"]:
            if not isinstance(entry, dict) or set(entry) != ({"path", "document_id", "revision_id", "bytes", "sha256", "action"} |
                    ({"staged"} if entry.get("action") == "promote" else set())) or \
                    entry["action"] not in ("promote", "remove") or type(entry["bytes"]) is not int or \
                    not 0 <= entry["bytes"] <= DEFAULT_LIMITS.original_bytes or \
                    not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
                raise ApiError("recovery_journal", "Recovery journal has an invalid original descriptor", 409)
            if entry["action"] == "promote" and (not isinstance(entry["staged"], str) or not STAGED.fullmatch(entry["staged"])):
                raise ApiError("recovery_journal", "Recovery journal has an invalid staged original path", 409)
            original_path(services.paths, entry)
            if entry["path"] in seen:
                raise ApiError("recovery_journal", "Recovery journal contains duplicate original paths", 409)
            seen.add(entry["path"])
        committed = services.db.fetch_one("SELECT 1 FROM storage_recovery_runs WHERE id=?", (data["id"],))
        if not committed:
            _rollback(services.paths, directory, data["entries"])
        remove_owned_tree(services.paths, directory)
