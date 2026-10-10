# SPDX-License-Identifier: MIT
"""Matching installed recovery proof, with no developer/runtime fallback.

prepare reserves a compact future schema1 profile. The parent seeds it through
the reviewed old runtime and freezes seed.json. verify upgrades and exercises
actual bundled owners. --help/importing this module performs no application work.
diagnose-import records one public Library import failure; it is not acceptance.
No Electron, pytest, providers, installation or profile discovery is used.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import secrets
import shutil
import sqlite3
import sys
import tempfile
from threading import Lock
from datetime import datetime, timezone
from types import MappingProxyType
import zipfile
from urllib.parse import unquote, urlsplit, parse_qs

DELIVERY = Path("C:/Renulus/scratch/design-c/delivery")
OLD_COMMIT = "1b30a89687cfcc5fb13b1cf824bbc43c19f870ed"
SEED_FORMAT = "renulus-installed-recovery-seed/1"
PROFILES = ("u", "j", "z1", "z2")
PYTHON_PATHS = ("python/python314.zip", "python", "dependencies", "dependencies/win32",
                "dependencies/win32/lib", "dependencies/pywin32_system32", "runtime",
                "upstream/hermes", ".")
ENV_PATHS = ("USERPROFILE", "HOME", "LOCALAPPDATA", "APPDATA", "ALLUSERSPROFILE", "PROGRAMDATA",
             "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP", "TMPDIR",
             "HF_HOME", "HF_HUB_CACHE", "TRANSFORMERS_CACHE", "HF_MODULES_CACHE", "TORCH_HOME",
             "FASTEMBED_CACHE_PATH", "MEM0_DIR")
MAX_SEED_BYTES = 32 * 1024 * 1024
MAX_RUN_BYTES = 2 * 1024 * 1024 * 1024
HISTORY_TABLES = ("learn_threads", "learn_messages", "learn_runs", "case_sessions",
    "case_attachments", "assessment_sessions", "assessment_items",
    "assessment_attempts", "assessment_exposure", "assessment_generated_sessions",
    "assessment_generated_items", "assessment_generated_attempts", "memory_facts",
    "memory_history", "learning_evidence")
TEXT = ("SYNTHETIC installed recovery learning original: dialysis fistula flow and "
        "access stenosis are distinct teaching concepts.\n\n"
        "Compare haemodialysis access surveillance mechanisms during study.")
FACT = "SYNTHETIC installed recovery preference: revisit glomerular proteinuria mechanisms."


class ProofError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ProofError(message)


def no_reparse(path):
    for item in (path.absolute(), *path.absolute().parents):
        require(not item.is_symlink() and not getattr(item, "is_junction", lambda: False)(),
                "Reparse paths are excluded")
        if item.exists():
            require(not (item.stat().st_file_attributes & 0x400) if os.name == "nt" else True,
                    "Reparse paths are excluded")


def checked_run(value, *, fresh=False):
    value = Path(value)
    require(value.is_absolute() and ".." not in value.parts, "Run path must be absolute without traversal")
    require(value.parent == DELIVERY and re.fullmatch(r"r-[0-9a-f]{8}", value.name),
            "Use the exact delivery/r-<8 lowercase hex> run root")
    no_reparse(value)
    require(not fresh or not value.exists(), "Run already exists; preserve its evidence")
    return value.resolve()


def checked_profile(root, name, *, fresh=False):
    root = checked_run(root)
    require(name in PROFILES, "Only compact u/j/z1/z2 profiles are admitted")
    result = root / name
    require(len(str(result)) <= 60, "Profile path exceeds the 60-character native bound")
    no_reparse(result)
    require(not fresh or not result.exists(), "Profile already exists; preserve its evidence")
    return result


def sha256(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def checked_hash(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "An exact SHA256 is required")
    return value


def read_json(path, *, max_bytes=16 * 1024 * 1024):
    require(path.is_file() and path.stat().st_size <= max_bytes, "JSON file missing or exceeds bound")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON member")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def relative_file(root, name):
    require(isinstance(name, str) and name and "\\" not in name and ":" not in name,
            "Inventory paths must be local POSIX relatives")
    parts = name.split("/")
    require(all(part not in ("", ".", "..") and not part.endswith((".", " "))
                and not re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", part)
                for part in parts), "Invalid inventory path")
    relative = PurePosixPath(name)
    require(not relative.is_absolute(), "Absolute inventory path")
    value = Path(root).joinpath(*relative.parts)
    no_reparse(value)
    require(value.resolve().is_relative_to(Path(root).resolve()), "Inventory leaves its root")
    return value


def files_in(root, *, exclude=()):
    # Each child is inspected before recursion; a junction cannot hide files.
    result, directories = {}, [Path(root)]
    while directories:
        directory = directories.pop()
        no_reparse(directory)
        for entry in directory.iterdir():
            no_reparse(entry)
            if entry.is_dir():
                directories.append(entry)
            else:
                require(entry.is_file(), "Unsupported file type")
                name = entry.relative_to(root).as_posix()
                if name not in exclude:
                    result[name] = entry
    return result


def validate_inventory(root, records, *, exclude=()):
    require(isinstance(records, list) and records, "A complete byte inventory is required")
    declared = {}
    for record in records:
        require(isinstance(record, dict) and set(record) == {"path", "size", "sha256"}, "Invalid file descriptor")
        path = relative_file(root, record["path"])
        folded = record["path"].casefold()
        require(folded not in declared, "Duplicate inventory path")
        require(type(record["size"]) is int and record["size"] >= 0, "Invalid file size")
        checked_hash(record["sha256"])
        require(path.is_file() and path.stat().st_size == record["size"]
                and sha256(path) == record["sha256"], "File bytes differ from frozen inventory: " + record["path"])
        declared[folded] = record["path"]
    actual = files_in(root, exclude=exclude)
    require(set(actual) == set(declared.values()), "Complete file inventory differs; extra/missing files are refused")
    return {"files": len(records), "bytes": sum(record["size"] for record in records)}


def runtime_snapshot():
    return {"platform": sys.platform, "version": ".".join(map(str, sys.version_info[:3])),
            "executable": sys.executable, "prefix": sys.prefix, "base_prefix": sys.base_prefix,
            "isolated": sys.flags.isolated, "no_site": sys.flags.no_site,
            "no_user_site": sys.flags.no_user_site, "bytecode_disabled": sys.dont_write_bytecode,
            "sys_path": list(sys.path)}


def validate_runtime(bundle, metadata, runtime, expected_source):
    bundle = Path(bundle).resolve()
    require(re.fullmatch(r"[0-9a-f]{40}", expected_source or ""), "Exact source commit required")
    require(metadata.get("format") == "embedded-cpython-windows-v1"
            and metadata.get("source_revision") == expected_source, "Installed source mismatch")
    python = metadata.get("python", {})
    require(python.get("version") == "3.14.4" and python.get("executable") == "python/python.exe",
            "Unexpected bundled Python contract")
    require(runtime["platform"] == "win32" and runtime["version"] == "3.14.4", "Matching Windows CPython required")
    require(Path(runtime["executable"]).resolve() == bundle / "python/python.exe"
            and Path(runtime["prefix"]).resolve() == bundle / "python"
            and Path(runtime["base_prefix"]).resolve() == bundle / "python", "Interpreter must be this installed bundle")
    require(runtime["isolated"] == runtime["no_site"] == runtime["no_user_site"] == 1
            and runtime["bytecode_disabled"] is True, "Use isolated -I -B -S; site and bytecode are refused")
    expected_paths = [(bundle / item).resolve() for item in PYTHON_PATHS]
    require([Path(item).resolve() for item in runtime["sys_path"]] == expected_paths,
            "sys.path differs from the reviewed embedded path list")
    for path in expected_paths:
        no_reparse(path)
    require("renulus" not in sys.modules, "Admission must run before Renulus imports")


def validate_identity(args, *, complete):
    bundle = args.bundle
    require(bundle.is_absolute() and ".." not in bundle.parts, "Explicit installed bundle required")
    require(bundle.parent.name == "resources" and bundle.name == "backend"
            and bundle.parent.parent.parent == DELIVERY
            and re.fullmatch(r"installed-[0-9a-f]{8}", bundle.parent.parent.name), "Use the exact installed delivery bundle")
    no_reparse(bundle)
    metadata_path, inventory_path = bundle / "bundle.json", bundle / "inventory.json"
    for path, expected in ((metadata_path, args.bundle_sha256), (inventory_path, args.inventory_sha256),
                           (bundle / "python/python.exe", args.python_sha256), (Path(__file__), args.driver_sha256)):
        require(sha256(path) == checked_hash(expected), "Identity hash mismatch: " + path.name)
    driver = Path(__file__).absolute()
    require(driver.is_relative_to(DELIVERY / "proofs"), "Copy the hash-frozen source-only driver into delivery/proofs")
    no_reparse(driver)
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", args.slot or ""), "Parent-assigned serial helper slot required")
    metadata = read_json(metadata_path)
    validate_runtime(bundle, metadata, runtime_snapshot(), args.expected_source)
    require(metadata["python"]["executable_sha256"] == args.python_sha256, "Python hash differs from bundle contract")
    checked = validate_inventory(bundle, read_json(inventory_path), exclude=("inventory.json",)) if complete else None
    return {"source_revision": args.expected_source, "bundle": str(bundle),
            "bundle_sha256": args.bundle_sha256, "inventory_sha256": args.inventory_sha256,
            "python_sha256": args.python_sha256, "driver_sha256": args.driver_sha256,
            "driver_path": str(driver.resolve()),
            "slot": args.slot, "runtime": runtime_snapshot(), "inventory": checked}


def validate_seed_files(root, manifest):
    require(isinstance(manifest, dict) and set(manifest) == {"format", "old_commit", "run_root", "profile",
        "synthetic", "closed", "schema_version", "old_source_archive_sha256", "seed_driver_sha256",
        "fixture_sha256", "files", "exports"}, "Unexpected seed manifest fields")
    require(manifest["format"] == SEED_FORMAT and manifest["old_commit"] == OLD_COMMIT,
            "Use the parent's genuine committed schema1 producer")
    require(manifest["run_root"] == str(root) and manifest["profile"] == str(root / "u"),
            "Seed must bind the exact reserved future u profile")
    require(manifest["synthetic"] is True and manifest["closed"] is True
            and type(manifest["schema_version"]) is int and manifest["schema_version"] == 1,
            "A closed synthetic schema1 seed is required")
    for name in ("old_source_archive_sha256", "seed_driver_sha256", "fixture_sha256"):
        checked_hash(manifest[name])
    require(manifest["exports"] == {"json": "old.json", "zip1": "old1.zip", "zip2": "old2.zip"},
            "Use the exact three old export names")
    records = manifest["files"]
    require(isinstance(records, list) and 4 <= len(records) <= 256, "Bounded full seed inventory required")
    for record in records:
        name = record.get("path", "")
        require(name in manifest["exports"].values() or name.startswith("u/"), "Seed inventory leaves reserved inputs")
        require(not re.search(r"(?i)(?:^|/)(?:runtime|credentials?|secrets?|connections?)(?:/|\.|$)", name)
                and not name.endswith(("-wal", "-shm", ".dpapi", ".pem", ".key", ".token"))
                and not any(part == ".env" for part in name.split("/")),
                "Credentials and open-WAL seeds are refused")
    require(sum(record["size"] for record in records) <= MAX_SEED_BYTES, "Compact seed exceeds 32MiB")
    inventory = validate_inventory(root, records, exclude=("prepared.json", "seed.json"))
    require("u/state/renulus.sqlite3" in {record["path"] for record in records}, "Seed database missing")
    return inventory


def assert_preserved_rows(expected, actual, label):
    for row in expected:
        require(any(all(candidate.get(key) == value for key, value in row.items()) for candidate in actual),
                "Preserved row/score/pin changed: " + label)


def assert_effective_rebuild(before, after, report, passages, facts, *, revision, fact):
    require(report.get("status") == "complete", "Public local rebuild did not complete")
    for name, unit in (("knowledge", "passages"), ("memory", "records")):
        module = report.get("modules", {}).get(name, {})
        require(module.get("status") == "complete" and module.get("rebuilt_unit") == unit
                and type(module.get("rebuilt_records")) is int and module["rebuilt_records"] > 0,
                "No-op/partial local rebuild refused: " + name)
        require(after.get(name) and after[name] != before.get(name), "Index generation did not switch: " + name)
    require(revision in passages and fact in facts, "Actual retrieval did not recover expected IDs")


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def prepare(args, identity):
    root = checked_run(DELIVERY / ("r-" + (args.run_id or secrets.token_hex(4))), fresh=True)
    root.mkdir()
    plan = {"format": "renulus-installed-recovery-plan/1", "run_root": str(root),
            "profile": str(checked_profile(root, "u")), "seed_manifest": str(root / "seed.json"),
            "old_commit": OLD_COMMIT, "identity": identity, "max_seed_bytes": MAX_SEED_BYTES,
            "exports": {"json": "old.json", "zip1": "old1.zip", "zip2": "old2.zip"},
            "instructions": ["Parent seeds exact future u through the reviewed old producer, never current DDL.",
                             "Close all old connections and checkpoint/truncate WAL before full inventory.",
                             "Copy actual old exports to old.json/old1.zip/old2.zip; freeze seed.json and its SHA256.",
                             "Run verify only with the matching isolated installed Python and assigned helper slot."]}
    write_json(root / "prepared.json", plan)
    return plan


def isolated_environment(root, inherited):
    result = {name: inherited[name] for name in ("SystemRoot", "WINDIR", "SystemDrive",
              "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE") if name in inherited}
    for name in ENV_PATHS:
        result[name] = str(root / "e" / name.lower())
    result.update(PYTHONDONTWRITEBYTECODE="1", HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                  HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1", ANONYMIZED_TELEMETRY="False",
                  TOKENIZERS_PARALLELISM="false", RAYON_NUM_THREADS="2", OMP_NUM_THREADS="2",
                  MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2")
    result["PATH"] = str(Path(result.get("SystemRoot", "C:/Windows")) / "System32")
    return result


class FrozenSourceRead:
    """One admitted source file; retain a read handle to avoid recursive audit opens."""
    def __init__(self, path, expected_sha256):
        path = Path(path)
        require(path.is_absolute() and ".." not in path.parts, "Exact frozen source path required")
        no_reparse(path)
        self.path, self.sha256 = path.resolve(), checked_hash(expected_sha256)
        self._lock = Lock()
        self._file = self.path.open("rb")
        try:
            self.require_unchanged()
        except Exception:
            self._file.close()
            raise

    def require_unchanged(self):
        with self._lock:
            try:
                no_reparse(self.path)
                require(os.path.samestat(self.path.stat(), os.fstat(self._file.fileno())),
                        "Frozen source identity changed")
                self._file.seek(0)
                require(hashlib.file_digest(self._file, "sha256").hexdigest() == self.sha256,
                        "Frozen source bytes changed")
            except OSError:
                raise ProofError("Frozen source is unavailable") from None

    def close(self):
        self._file.close()


class SafetyBoundary:
    """Python audit refusal boundary; never supplies simulated application results."""
    def __init__(self, root, helpers, snapshot, bundle=None, *, driver_source=None):
        self.root, self.helpers, self.snapshot = root.resolve(), helpers.resolve(), snapshot.resolve()
        self.bundle = Path(bundle).resolve() if bundle else None
        self.driver_source = driver_source
        self.provisioning = False
        self.attempts = []
        self.refused_details = []
        self.reparse_refusals = 0

    def _path_diagnostic(self, value):
        # Describe the attempted path lexically; never open or resolve a denied
        # target while recording it. Outside roots expose only a basename.
        if isinstance(value, int):
            return {"root": "descriptor"}
        if not isinstance(value, (str, bytes, os.PathLike)):
            return {"root": "unavailable"}
        raw = os.fsdecode(value)
        if raw.startswith("file:"):
            uri = urlsplit(raw)
            if uri.netloc:
                return {"root": "outside"}
            raw = unquote(uri.path)
            if re.match(r"^/[A-Za-z]:/", raw):
                raw = raw[1:]
        if raw.replace("/", "\\").lower() in ("nul", "\\\\.\\nul"):
            return {"root": "device", "basename": "NUL"}
        candidate = PureWindowsPath(os.path.abspath(raw))
        for name, root in (("snapshot", self.snapshot), ("helpers", self.helpers),
                           ("bundle", self.bundle), ("run", self.root)):
            if root is not None and candidate.is_relative_to(PureWindowsPath(root)):
                relative = candidate.relative_to(PureWindowsPath(root)).as_posix()
                if relative.isprintable() and len(relative) <= 240:
                    return {"root": name, "relative_path": relative}
                return {"root": name, "basename": "<redacted>"}
        basename = candidate.name
        return {"root": "outside", "basename": basename if basename.isprintable() and len(basename) <= 120
                else "<redacted>"}

    def _record_refusal(self, event, args):
        if len(self.refused_details) >= 16:
            return
        detail = {"event": event}
        try:
            if event == "open":
                file, mode, flags = args
                detail["path"] = self._path_diagnostic(file)
                detail["mode"] = mode if mode is None or (isinstance(mode, str) and
                    re.fullmatch(r"[rwaxbt+]{1,8}", mode)) else "<redacted>"
                detail["flags"] = flags if type(flags) is int else None
            elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime",
                           "shutil.rmtree", "sqlite3.connect"):
                detail["path"] = self._path_diagnostic(args[0])
            elif event in ("os.rename", "os.link"):
                detail["paths"] = [self._path_diagnostic(value) for value in args[:2]]
            frame = sys._getframe(1)
            try:
                for unused in range(12):
                    if frame is None:
                        break
                    caller = self._path_diagnostic(frame.f_code.co_filename)
                    if caller.get("root") == "bundle":
                        detail["caller"] = {**caller, "line": frame.f_lineno}
                        break
                    frame = frame.f_back
            finally:
                del frame
        except Exception:
            # Diagnostic formatting cannot replace the original denial.
            detail = {"event": event, "path": {"root": "unavailable"}}
        self.refused_details.append(detail)

    def path(self, value, *, writing):
        if not isinstance(value, (str, bytes, os.PathLike)):
            return  # Already-open file descriptors have no new path to admit.
        path = Path(os.fsdecode(value)).absolute()
        # Resolve only after ancestor reparses are checked. Auditing stat/realpath
        # does not open files, so this cannot recurse into the open audit event.
        no_reparse(path)
        path = path.resolve()
        if self.driver_source is not None and path == self.driver_source.path:
            require(not writing, "Frozen QA source is read-only")
            self.driver_source.require_unchanged()
            return
        if writing:
            require(path.is_relative_to(self.root), "Write leaves owned recovery evidence")
            require(not path.is_relative_to(self.snapshot), "Preupgrade snapshot is immutable")
            require(self.provisioning or not path.is_relative_to(self.helpers), "Shared helpers are read-only")
        else:
            require(path.is_relative_to(self.root) or (self.bundle and path.is_relative_to(self.bundle)),
                    "Read leaves installed bundle/owned evidence")

    def check(self, event, args):
        try:
            if event == "open":
                file, mode, flags = args
                writing = (isinstance(mode, str) and any(flag in mode for flag in "wax+")) or bool(
                    flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
                self.path(file, writing=writing)
            elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime", "shutil.rmtree"):
                self.path(args[0], writing=True)
            elif event in ("os.rename", "os.link"):
                self.path(args[0], writing=True)
                self.path(args[1], writing=True)
            elif event == "os.symlink":
                self.path(args[1], writing=True)
                # filelock probes symlink support during cold import and handles
                # OSError. Deny the syscall without creating any reparse path.
                self.reparse_refusals += 1
                raise PermissionError("Reparse creation is unavailable in this proof")
            elif event == "sqlite3.connect":
                value = args[0]
                if value != ":memory:":
                    writing = True
                    if isinstance(value, str) and value.startswith("file:"):
                        uri = urlsplit(value)
                        require(not uri.netloc, "Remote SQLite URI refused")
                        value = unquote(uri.path)
                        if re.match(r"^/[A-Za-z]:/", value):
                            value = value[1:]
                        writing = parse_qs(uri.query).get("mode") != ["ro"]
                    self.path(value, writing=writing)
            elif event in ("socket.connect", "socket.sendto"):
                address = args[-1]
                require(isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"),
                        "External sockets are refused")
            elif event == "socket.getaddrinfo":
                require(args[0] in ("127.0.0.1", "::1", "localhost"), "External resolution is refused")
            elif event in ("subprocess.Popen", "os.system", "os.startfile", "os.posix_spawn", "os.exec"):
                require(False, "Child processes/external handoffs are refused")
        except ProofError:
            self.attempts.append(event)
            self._record_refusal(event, args)
            raise


def configure_safety(root, bundle, *, identity):
    # Identity admission already checked this exact executing copy and its hash.
    # Bind it before the hook; hashing its retained handle never reopens a path.
    require(Path(identity["driver_path"]) == Path(__file__).absolute(),
            "Admitted executing source path changed")
    source = FrozenSourceRead(identity["driver_path"], identity["driver_sha256"])
    environment = isolated_environment(root, os.environ)
    for name in ENV_PATHS:
        Path(environment[name]).mkdir(parents=True, exist_ok=True)
    os.environ.clear()
    os.environ.update(environment)
    os.chdir(root)
    tempfile.tempdir = environment["TEMP"]
    boundary = SafetyBoundary(root, root / "h", root / "b", bundle, driver_source=source)
    sys.addaudithook(boundary.check)
    return boundary


def diagnose_import(args, identity):
    """Parent serial public-import probe; no old seed or recovery acceptance."""
    root = checked_run(DELIVERY / ("r-" + (args.run_id or secrets.token_hex(4))), fresh=True)
    root.mkdir()
    boundary = configure_safety(root, args.bundle, identity=identity)
    result, helper_copy, error_type = None, None, None
    try:
        helper_copy, contract = provision_helpers(args.bundle, root, boundary)
        with application(root, "u", args.bundle, boundary) as services:
            from renulus.knowledge.models import SourceMetadata, own_text_rights
            source = root / "synthetic-current-1.txt"
            source.write_text(TEXT + "\nSynthetic retained revision 1.\n", encoding="utf-8")
            imported = services.get("knowledge").import_file(source,
                title="SYNTHETIC installed recovery 1", metadata=SourceMetadata(),
                rights=own_text_rights(), process=True)
            result = {key: imported[key] for key in ("document_id", "revision_id", "status")}
            result["job"] = {key: imported["job"].get(key) for key in
                             ("id", "state", "phase", "error_code", "error_message")}
        assert_helpers(root, contract)
        assert_bundled_modules(args.bundle)
    except Exception as error:
        error_type = type(error).__name__
    receipt = {"format": "renulus-installed-recovery-diagnostic/1", "status": "diagnostic-only",
               "acceptance": False, "identity": identity, "run_root": str(root),
               "operation": "public knowledge.import_file", "helpers": helper_copy,
               "result": result, "error_type": error_type,
               "refused_operations": boundary.attempts, "refused_details": boundary.refused_details,
               "reparse_syscalls_refused": boundary.reparse_refusals}
    write_json(root / "diagnostic.json", receipt)
    return receipt


def rows(db, table):
    require(re.fullmatch(r"[a-z][a-z0-9_]*", table), "Invalid table name")
    with closing(db.connect()) as conn:
        return [dict(row) for row in conn.execute('SELECT * FROM "' + table + '"')]


def legacy_assertions(services, old, *, deleted_fact=None):
    for table in HISTORY_TABLES:
        expected = old["records"].get(table, [])
        if table == "memory_facts":
            expected = [row for row in expected if row["id"] != deleted_fact]
        elif table == "memory_history":
            expected = [row for row in expected if row["record_id"] != deleted_fact]
        assert_preserved_rows(expected, rows(services.db, table), table)


def validate_old_seed(root, seed):
    old = read_json(root / "old.json")
    require(old.get("format") == "renulus-canonical-export" and old.get("schema_version") == 1
            and old.get("format_version") == 1 and isinstance(old.get("records"), dict), "Genuine old JSON export required")
    records = old["records"]
    require(records.get("assessment_items") and records.get("assessment_attempts")
            and records.get("assessment_generated_items") and records.get("memory_facts")
            and records.get("case_attachments") and records.get("knowledge_revisions"),
            "Seed lacks the frozen populated producer/history coverage")
    require(any(row["assisted"] == 1 for row in records["assessment_attempts"]), "Old assisted score missing")
    require(any(sum(item["session_id"] == row["id"] for item in records["assessment_items"])
                > sum(item["session_id"] == row["id"] for item in records["assessment_attempts"])
                for row in records["assessment_sessions"]), "Old partial denominator missing")
    for version in (1, 2):
        with zipfile.ZipFile(root / ("old%d.zip" % version)) as archive:
            member = archive.getinfo("manifest.json")
            require(member.file_size <= 1024 * 1024, "Old ZIP manifest exceeds bound")
            manifest = json.loads(archive.read(member))
            require(manifest.get("format") == "renulus-full-backup" and manifest.get("format_version") == version
                    and manifest.get("schema_version") == 1, "Genuine supported old ZIP required")
    database = root / "u/state/renulus.sqlite3"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        require(conn.execute("PRAGMA user_version").fetchone()[0] == 1, "Seed database must still be schema1")
        require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "Seed database integrity failed")
        for table in HISTORY_TABLES:
            actual = [dict(row) for row in conn.execute('SELECT * FROM "' + table + '"')]
            assert_preserved_rows(records.get(table, []), actual, "seed " + table)
    return old


def library_original_expectations(stored, originals, inventory):
    """Freeze only closed-seed identities; target paths never determine absence."""
    present, absent, seen = {}, set(), set()
    archived = {row["revision_id"]: row for row in originals}
    require(len(archived) == len(originals), "Duplicate seed original revision")
    for row in stored:
        identifier = row["id"]
        require(identifier not in seen, "Duplicate closed-seed Library revision")
        seen.add(identifier)
        if row["original_path"] is None:
            require(identifier not in archived, "Archived original missing from closed seed")
            prefix = "library/knowledge/" + row["document_id"] + "/" + identifier + "/original."
            require(not any(path.startswith(prefix) for path in inventory),
                    "Inventoried original missing from closed seed")
            absent.add(identifier)
            continue
        item = archived.get(identifier)
        metadata = (row["document_id"], row["bytes"], row["sha256"])
        require(item is not None and (item["document_id"], item["bytes"], item["sha256"]) == metadata
                and item["path"] == row["original_path"], "Closed seed and archive original differ")
        record = inventory.get(item["path"])
        require(record is not None and (record["size"], record["sha256"]) == metadata[1:],
                "Seed original missing or changed in hash inventory")
        present[identifier] = metadata
    require(present and set(archived) == set(present), "Seed needs matching genuine original coverage")
    return MappingProxyType(present), frozenset(absent)


def freeze_library_originals(root, seed, old):
    """Read the verified immutable snapshot before any current application opens."""
    database = relative_file(root / "b", "state/renulus.sqlite3")
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        stored = [dict(row) for row in conn.execute(
            "SELECT id,document_id,bytes,sha256,original_path FROM knowledge_revisions")]
    exported = old["records"]["knowledge_revisions"]
    require({row["id"] for row in stored} == {row["id"] for row in exported},
            "Closed-seed Library inventory differs from canonical export")
    assert_preserved_rows([{key: row[key] for key in ("id", "document_id", "bytes", "sha256")}
                           for row in exported], stored, "closed-seed Library originals")
    inventory = {row["path"][2:]: row for row in seed["files"] if row["path"].startswith("u/")}
    for row in stored:
        if row["original_path"] is not None:
            path = Path(row["original_path"])
            require(path.is_absolute() and path.is_relative_to(root / "u") and ".." not in path.parts,
                    "Seed original path leaves its exact profile")
            relative = path.relative_to(root / "u").as_posix()
            require(relative.startswith("library/knowledge/" + row["document_id"] + "/" + row["id"] + "/"),
                    "Seed original path differs from revision ownership")
            snapshot = relative_file(root / "b", relative)
            require(snapshot.is_file() and snapshot.stat().st_size == row["bytes"] and sha256(snapshot) == row["sha256"],
                    "Preserved seed original bytes changed")
            row["original_path"] = relative
    archives = []
    for number in (1, 2):
        with zipfile.ZipFile(root / ("old%d.zip" % number)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            originals = manifest.get("originals")
            require(isinstance(originals, list), "Seed archive original inventory missing")
            archives.append(library_original_expectations(stored, originals, inventory))
    require(archives[0] == archives[1], "Supported seed ZIP original identities differ")
    return archives[0]


def partition_library_originals(library, expectations):
    present, absent = expectations
    identifiers = {row["id"] for row in library}
    require(len(identifiers) == len(library), "Duplicate canonical Library revision")
    require((set(present) | set(absent)) <= identifiers, "Frozen seed revision disappeared from canonical records")
    expected, unavailable = [], []
    for row in library:
        if row["id"] in present:
            require((row["document_id"], row["bytes"], row["sha256"]) == present[row["id"]],
                    "Frozen original metadata changed")
        (unavailable if row["id"] in absent else expected).append(row)
    return expected, unavailable


def provision_helpers(bundle, root, boundary):
    # helper_copy itself and every asset were verified by the full installed
    # inventory before this first non-stdlib import. No development assets.
    import helper_copy
    require(Path(helper_copy.__file__).resolve() == bundle / "helper_copy.py", "Bundled helper copier required")
    contract = read_json(bundle / "packaging/runtime/helper-assets.json")
    require(read_json(bundle / "helper-assets/manifest.json") == contract, "Bundled helper manifest differs from source")
    boundary.provisioning = True
    try:
        result = helper_copy.copy_assets(bundle / "helper-assets", root / "h")
    finally:
        boundary.provisioning = False
    require(read_json(root / "h/manifest.json") == contract, "Copied helper contract changed")
    return result, contract


def assert_helpers(root, contract):
    for group in contract["groups"].values():
        for record in group["files"]:
            path = relative_file(root / "h", record["path"])
            require(path.stat().st_size == record["size"] and sha256(path) == record["sha256"],
                    "Shared helper bytes changed")


def assert_bundled_modules(bundle):
    for name, module in list(sys.modules.items()):
        if name == "renulus" or name.startswith("renulus."):
            value = getattr(module, "__file__", None)
            if value:
                admitted = bundle / "runtime/renulus"
                if name == "renulus.memory._vendored_hermes_backend":
                    require(Path(value).resolve() == bundle / "upstream/hermes/plugins/memory/mem0/_backend.py",
                            "Only the exact bundled Hermes Mem0 adapter is admitted")
                else:
                    require(Path(value).resolve().is_relative_to(admitted), "Developer Renulus module refused")


@contextmanager
def application(root, name, bundle, boundary):
    from renulus import server
    from renulus.storage import AppPaths
    profile = checked_profile(root, name)
    class SharedHelpers(AppPaths):
        @property
        def helpers(self):
            return root / "h"
    previous = server.AppPaths
    server.AppPaths = SharedHelpers
    try:
        services = server.create_app(profile, source_root=bundle).state.services
    finally:
        server.AppPaths = previous
    require(services.paths.source_root == bundle and services.paths.root == profile, "Runtime source/profile mismatch")
    require(services.paths.helpers == root / "h", "Only the verified shared helper copy is admitted")
    class RefuseProvider:
        async def stream(self, *args, **kwargs):
            boundary.attempts.append("provider")
            raise ProofError("Recovery must not infer")
            yield  # Retain the real asynchronous stream call shape.
        async def cancel(self, *args, **kwargs):
            boundary.attempts.append("provider")
            raise ProofError("No provider run exists in recovery proof")
    services.registry["provider"] = RefuseProvider()
    helpers = services.get("helpers")
    helpers.startup.configure()
    try:
        # Manual indexing uses real Mem0 infer=False, never its LLM. Refuse the
        # LLM seam even if future code accidentally enables capture/inference.
        from renulus.memory.engine import bootstrap
        bootstrap(services)
        from renulus.memory.providers import ApprovedLLM
        def refused(*args, **kwargs):
            boundary.attempts.append("mem0-inference")
            raise ProofError("Manual Memory/reindex cannot call an LLM")
        ApprovedLLM.generate_response = refused
        assert_bundled_modules(bundle)
        require(services.get("memory")._worker is None, "Automatic Memory worker must stay stopped")
        require(services.get("knowledge_worker").status()["running"] is False, "No ingestion worker may auto-start")
        yield services
    finally:
        try:
            asyncio.run(services.get("memory").close())
        finally:
            services.get("knowledge").index.close()
            helpers.startup.close()
    require(not boundary.attempts, "Refused external/provider/ownership operation occurred")


def assert_originals(services, library, attachments, *, expectations):
    expected, unavailable = partition_library_originals(library, expectations)
    for row in expected:
        path, _ = services.get("knowledge").original(row["id"])
        require(path.is_relative_to(services.paths.library) and path.stat().st_size == row["bytes"]
                and sha256(path) == row["sha256"], "Actual Library original differs")
    for row in unavailable:
        expect_unavailable(lambda: services.get("knowledge").original(row["id"]), {"original_missing"})
    for row in attachments:
        metadata, data = services.get("cases").original(row["case_id"], row["id"])
        require(len(data) == row["bytes"] and hashlib.sha256(data).hexdigest() == row["sha256"]
                and metadata["id"] == row["id"], "Actual Case original differs")


def expect_unavailable(operation, codes):
    from renulus.contracts import ApiError
    try:
        operation()
    except ApiError as error:
        require(error.code in codes, "Unexpected unavailable-original error: " + error.code)
    else:
        raise ProofError("Records-only/deleted original was exposed")


def assert_json_omits_originals(services, bundle, *, expectations):
    require(bundle.get("data_kind") == "records-only" and bundle.get("artifacts") == {}, "JSON must remain records-only")
    require(all(row.get("original_path") is None for row in bundle["records"].get("knowledge_revisions", [])),
            "JSON may not retain source original paths")
    partition_library_originals(bundle["records"].get("knowledge_revisions", []), expectations)
    for row in bundle["records"].get("knowledge_revisions", []):
        expect_unavailable(lambda: services.get("knowledge").original(row["id"]), {"original_missing"})
    for row in bundle["records"].get("case_attachments", []):
        expect_unavailable(lambda: services.get("cases").original(row["case_id"], row["id"]), {"case_original_unavailable"})


def generations(services):
    row = services.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.index_generation'")
    return {"knowledge": json.loads(row["value"]) if row else None,
            "memory": services.db.fetch_one("SELECT generation FROM memory_index_state WHERE singleton=1")["generation"]}


def restore(services, archive, kind):
    from renulus.storage.invalidation import context_epoch
    before = context_epoch(services.db)
    memory_epoch = services.db.fetch_one("SELECT epoch FROM memory_index_state WHERE singleton=1")["epoch"]
    recovery = services.get("data_recovery")
    if kind == "json":
        bundle = read_json(archive)
        result = recovery.restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle["exported_at"])
    else:
        identifier, directory = recovery.begin_preview()
        keep = False
        try:
            shutil.copyfile(archive, directory / "input.zip")
            preview = recovery.complete_preview(identifier, directory)
            keep = True
        finally:
            recovery.end_upload(directory, keep=keep)
        result = recovery.restore_preview(preview["preview_token"], preview["exported_at"], True)
    require(context_epoch(services.db) == before + 1, "Restore did not advance local context epoch")
    state = services.db.fetch_one("SELECT epoch,state FROM memory_index_state WHERE singleton=1")
    require(state["epoch"] == memory_epoch + 1 and state["state"] != "ready", "Restore retained ready Memory cache")
    require(services.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.restore_dirty'")["value"] == "true",
            "Restore failed to invalidate Library search")
    require(services.get("memory")._worker is None, "Restore resumed automatic capture")
    return result


def rebuild(services, *, revision, fact):
    from renulus.contracts import ContextScope, Scope
    scope = ContextScope(kind=Scope.STUDY)
    before = generations(services)
    recovery = services.get("data_recovery")
    identifier, _, should_run = recovery.request_rebuild()
    require(should_run is True, "Explicit public rebuild request was not runnable")
    recovery.rebuild(identifier)
    report = recovery.status()["rebuild"]
    # Capture state BEFORE retrieve, since Memory.retrieve can independently
    # rebuild a dirty index. It must not conceal a no-op public recovery seam.
    after = generations(services)
    require(services.get("memory").status()["index"]["ready"] is True, "Recovery did not make Memory ready")
    require(services.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.restore_dirty'") is None,
            "Recovery did not clear Library dirty marker at switch")
    library = services.get("knowledge").retrieve("dialysis fistula access stenosis", scope=scope)
    memory = services.get("memory").retrieve("glomerular proteinuria learning preference", scope=scope)
    assert_effective_rebuild(before, after, report,
        [row["document_revision"] for row in library["passages"]], [row["id"] for row in memory["records"]],
        revision=revision, fact=fact)
    knowledge_engine, memory_engine = services.get("knowledge"), services.get("memory")._engine
    require(knowledge_engine.index._table.__class__.__module__.startswith("lancedb")
            and knowledge_engine.embedder._model.__class__.__module__.startswith("fastembed"), "Actual Library CPU engines required")
    require(memory_engine.memory.__class__.__module__ == "mem0.memory.main"
            and memory_engine.memory.vector_store.client._client.__class__.__name__ == "QdrantLocal"
            and memory_engine.memory.embedding_model.delegate.model.__class__.__module__.startswith("fastembed"),
            "Actual Mem0/local Qdrant/FastEmbed required")
    require(knowledge_engine.index.path.is_relative_to(services.paths.indexes)
            and memory_engine.path.is_relative_to(services.paths.indexes), "Derived engine index leaves profile")
    require(memory_engine.memory.db.connection.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 0,
            "Derivative Mem0 history was not purged")
    return {"report": report, "generations": after, "expected_ids_retrieved": True,
            "engines": ["LanceDB", "FastEmbed", "Mem0", "QdrantLocal"]}


def produce_current(services, root):
    from renulus.contracts import ContextScope, Scope
    from renulus.knowledge.models import SourceMetadata, own_text_rights
    from renulus.memory.models import ManualFact
    from renulus.assessment.test_models import CreateReviewedTestRequest
    from renulus.assessment.attempt_models import StartAttempt, SubmitAttempt, DraftState
    documents = []
    for ordinal in (1, 2):
        path = root / ("synthetic-current-%d.txt" % ordinal)
        path.write_text(TEXT + "\nSynthetic retained revision %d.\n" % ordinal, encoding="utf-8")
        result = services.get("knowledge").import_file(path, title="SYNTHETIC installed recovery %d" % ordinal,
            metadata=SourceMetadata(), rights=own_text_rights(), process=True)
        require(result["status"] == "ready", "Actual current original extraction was not ready")
        documents.append(result)
    fact = services.get("memory").add(ManualFact(text=FACT, kind="preference",
        scope=ContextScope(kind=Scope.STUDY), idempotency_key="installed-recovery-manual"))
    edited = services.get("memory").edit(fact["id"], FACT + " Personally corrected.", fact["revision"])
    require(edited["revision"] == 2 and edited["purge_pending"] is False, "Current canonical Memory correction failed")
    require(services.get("memory").reindex()["count"] >= 2, "Actual manual index did not preserve old plus current Memory")
    require(services.get("knowledge").rebuild_index()["passages"] >= 2, "Actual Library index did not contain current passages")
    reviewed = services.get("saved_tests").create_reviewed(CreateReviewedTestRequest(
        idempotency_key="installed-recovery-reviewed", count=2, title="SYNTHETIC installed partial test"))
    with services.db.transaction() as conn:
        version = services.get("saved_tests").pinned_version(conn, reviewed["version_id"])
    attempt = services.get("whole_attempts").start(StartAttempt(
        version={"type": "saved_test_version", "id": version.id}, mode="test"), "installed-recovery-attempt")
    answers = [{"item_id": item.item_id, "option_ids": list(item.correct_option_ids) if number == 0 else []}
               for number, item in enumerate(version.items)]
    completed = services.get("whole_attempts").submit(attempt["id"], SubmitAttempt(
        expected_draft_revision=attempt["draft_revision"], latest_draft=DraftState(position=0, answers=answers)),
        "installed-recovery-submit")
    require(completed["result"]["denominator"] == 2 and completed["result"]["correct"] == 1
            and completed["result"]["unanswered"] == 1, "Actual partial Test result changed denominator")
    return {"documents": documents, "fact": edited, "version_id": version.id, "attempt_id": completed["id"]}


def current_assertions(services, current):
    for table in ("assessment_test_versions", "assessment_test_attempts", "assessment_attempt_drafts",
                  "assessment_attempt_exposure"):
        assert_preserved_rows(current["records"][table], rows(services.db, table), table)


def export_current(services, root):
    from renulus.storage.backup import export_records
    current = export_records(services)
    require(current["schema_version"] == 2, "Current producer must export schema2")
    require(all(row["key"] not in {"design_c.context_epoch", "knowledge.restore_dirty", "nightly.state"}
                for row in current["records"]["preferences"]), "Local state leaked into backup")
    require(not any("index" in table or "connections" in table for table in current["records"]),
            "Derived/private state leaked into backup")
    write_json(root / "current.json", current)
    for number in (1, 2):
        directory, _ = services.get("data_recovery").backup(format_version=number)
        shutil.copyfile(directory / "backup.zip", root / ("current%d.zip" % number))
        shutil.rmtree(directory)
    return current


def verify(args, identity):
    root = checked_run(args.run_root)
    plan = read_json(root / "prepared.json", max_bytes=256 * 1024)
    require(plan["run_root"] == str(root) and plan["profile"] == str(root / "u"), "Prepare/seed profile differs")
    for field in ("source_revision", "bundle", "bundle_sha256", "inventory_sha256", "python_sha256", "driver_sha256", "slot"):
        require(plan["identity"][field] == identity[field], "Prepared installed identity changed")
    require(sha256(root / "seed.json") == checked_hash(args.seed_sha256), "Seed manifest hash mismatch")
    seed = read_json(root / "seed.json", max_bytes=256 * 1024)
    seed_inventory = validate_seed_files(root, seed)
    old = validate_old_seed(root, seed)
    for name in PROFILES[1:]:
        checked_profile(root, name, fresh=True)
    require(not (root / "b").exists() and not (root / "h").exists(), "Snapshot/helper locations must be fresh")
    write_json(root / "verify.claim", {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()})
    # Preserve the consistent, verified seed before a current owner can write it.
    shutil.copytree(root / "u", root / "b")
    snapshot_files = [{**row, "path": row["path"][2:]} for row in seed["files"] if row["path"].startswith("u/")]
    validate_inventory(root / "b", snapshot_files)
    original_expectations = freeze_library_originals(root, seed, old)
    boundary = configure_safety(root, args.bundle, identity=identity)
    journal = (root / "events.jsonl").open("x", encoding="utf-8")
    gates = {}
    def mark(name, evidence):
        gates[name] = evidence
        journal.write(json.dumps({"gate": name, "evidence": evidence}, allow_nan=False) + "\n")
        journal.flush()
        print(json.dumps({"gate": name, "status": "passed"}), flush=True)
    try:
        helper_copy, contract = provision_helpers(args.bundle, root, boundary)
        mark("identity-and-seed", {"seed": seed_inventory, "schema1_snapshot_preserved": str(root / "b"),
            "helpers": helper_copy, "library_originals": {"present": sorted(original_expectations[0]),
                                                         "absent": sorted(original_expectations[1])}})
        with application(root, "u", args.bundle, boundary) as services:
            legacy_assertions(services, old)
            assert_originals(services, old["records"]["knowledge_revisions"], old["records"]["case_attachments"],
                             expectations=original_expectations)
            with closing(services.db.connect()) as conn:
                require(conn.execute("PRAGMA user_version").fetchone()[0] == 2, "Actual coordinated upgrade did not reach schema2")
                require(not conn.execute("PRAGMA foreign_key_check").fetchall(), "Upgrade broke live relations")
            count = services.get("saved_tests").backfill_legacy()
            require(count["created"] == len(old["records"]["assessment_sessions"]) + len(old["records"]["assessment_generated_sessions"]),
                    "Legacy backfill did not preserve every original session")
            pins = rows(services.db, "assessment_test_versions")
        with application(root, "u", args.bundle, boundary) as services:
            legacy_assertions(services, old)
            require(services.get("saved_tests").backfill_legacy()["created"] == 0, "Reopen duplicated legacy versions")
            assert_preserved_rows(pins, rows(services.db, "assessment_test_versions"), "reopened immutable versions")
            mark("legacy-upgrade-reopen", {"backfilled_versions": len(pins), "history_tables_preserved": len(HISTORY_TABLES),
                                         "reopen": "closed owners then assembled again in this interpreter"})
            produced = produce_current(services, root)
            current = export_current(services, root)
            assert_originals(services, current["records"]["knowledge_revisions"], current["records"]["case_attachments"],
                             expectations=original_expectations)
            mark("actual-current-producers", {"library_originals": len(produced["documents"]), "manual_memory_revision": 2,
                "version_id": produced["version_id"], "attempt_id": produced["attempt_id"], "partial_denominator": 2})
        old_fact = next(row for row in old["records"]["memory_facts"] if row["revision"] >= 2)
        for name, kind in (("j", "json"), ("z1", "zip1"), ("z2", "zip2")):
            old_archive = root / ("old.json" if kind == "json" else "old" + kind[-1] + ".zip")
            current_archive = root / ("current.json" if kind == "json" else "current" + kind[-1] + ".zip")
            with application(root, name, args.bundle, boundary) as services:
                restore(services, old_archive, kind)
                legacy_assertions(services, old)
                services.get("saved_tests").backfill_legacy()
                if kind == "json":
                    assert_json_omits_originals(services, old, expectations=original_expectations)
                else:
                    assert_originals(services, old["records"]["knowledge_revisions"], old["records"]["case_attachments"],
                                     expectations=original_expectations)
                restore(services, current_archive, kind)
                current_assertions(services, current)
                if kind == "json":
                    assert_json_omits_originals(services, current, expectations=original_expectations)
                    restore(services, root / "current1.zip", "zip1")
                assert_originals(services, current["records"]["knowledge_revisions"], current["records"]["case_attachments"],
                                 expectations=original_expectations)
                evidence = rebuild(services, revision=produced["documents"][1]["revision_id"], fact=produced["fact"]["id"])
                mark(kind + "-restored", evidence)
                removed = produced["documents"][0]
                result = services.get("knowledge").delete_document(removed["document_id"])
                require(result["status"] == "deleted" and result["cleanup_pending"] is False, "Actual Library deletion cleanup incomplete")
                require(services.get("memory").delete(old_fact["id"], old_fact["revision"])["purge_pending"] is False,
                        "Actual old Memory deletion cleanup incomplete")
                restore(services, old_archive, kind)
                restore(services, current_archive, kind)
                require(services.db.is_deleted("memory_fact", old_fact["id"])
                        and services.db.is_deleted("knowledge-document", removed["document_id"]), "Typed tombstones were lost")
                require(not services.db.fetch_one("SELECT id FROM memory_facts WHERE id=?", (old_fact["id"],)), "Deleted old Memory returned")
                expect_unavailable(lambda: services.get("knowledge").original(removed["revision_id"]), {"original_missing"})
                require(not list((services.paths.library / "knowledge" / removed["document_id"]).rglob("original.*")),
                        "Replay restored physically deleted original bytes")
                legacy_assertions(services, old, deleted_fact=old_fact["id"])
                current_assertions(services, current)
                kept = [row for row in current["records"]["knowledge_revisions"] if row["document_id"] != removed["document_id"]]
                assert_originals(services, kept, current["records"]["case_attachments"], expectations=original_expectations)
                evidence = rebuild(services, revision=produced["documents"][1]["revision_id"], fact=produced["fact"]["id"])
                mark(kind + "-deletion-replay", {**evidence, "older_and_current_backups_replayed": True})
        assert_bundled_modules(args.bundle)
        assert_helpers(root, contract)
        validate_inventory(root / "b", snapshot_files)
        require(not boundary.attempts, "A refused operation occurred")
        size = sum(path.stat().st_size for path in files_in(root).values())
        require(size <= MAX_RUN_BYTES, "Run exceeded its 2GiB evidence bound")
        receipt = {"format": "renulus-installed-recovery-evidence/1", "status": "passed", "identity": identity,
                   "seed_sha256": args.seed_sha256, "old_commit": OLD_COMMIT, "run_root": str(root),
                   "gates": gates, "bytes": size, "external_provider_calls": 0,
                   "reparse_syscalls_refused": boundary.reparse_refusals,
                   "limits": ["No Electron or fresh-process/native reopen was executed by this driver.",
                              "No native Save dialog, account, signing, separate machine or ordinary capture inference proof.",
                              "JSON is records-only; its target is hydrated through the real full ZIP owner before retrieval.",
                              "Parent composes hidden upgraded-profile reopen and final installed acceptance."]}
        write_json(root / "recovery-evidence.json", receipt)
        return receipt
    except Exception as error:
        failure = {"status": "failed", "passed_gates": list(gates), "error_type": type(error).__name__,
                   "error_code": getattr(error, "code", None), "refused_operations": boundary.attempts,
                   "refused_details": boundary.refused_details}
        if isinstance(error, ProofError):
            failure["assertion"] = str(error)
        write_json(root / "recovery-failure.json", failure)
        raise
    finally:
        journal.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="phase", required=True)
    for name in ("prepare", "verify", "diagnose-import"):
        command = commands.add_parser(name)
        command.add_argument("--bundle", required=True, type=Path)
        command.add_argument("--expected-source", required=True)
        for field in ("bundle", "inventory", "python", "driver"):
            command.add_argument("--" + field + "-sha256", required=True)
        command.add_argument("--slot", required=True)
        if name in ("prepare", "diagnose-import"):
            command.add_argument("--run-id", help="Optional eight lowercase hex; otherwise fresh random")
        else:
            command.add_argument("--run-root", required=True, type=Path)
            command.add_argument("--seed-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        identity = validate_identity(args, complete=args.phase in ("verify", "diagnose-import"))
        if args.phase == "prepare":
            result = prepare(args, identity)
        elif args.phase == "diagnose-import":
            result = diagnose_import(args, identity)
        else:
            result = verify(args, identity)
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__,
                          "error_code": getattr(error, "code", None),
                          "assertion": str(error) if isinstance(error, ProofError) else "Inspect owned failure receipt"}), flush=True)
        return 1
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
