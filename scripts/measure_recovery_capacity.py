# SPDX-License-Identifier: MIT
"""Synthetic recovery capacity measurement; no live profile or production format.

Every CLI run claims a fresh explicit workspace. Child processes compare the
unchanged bounded exporter with a row/segment-bounded disk staging experiment.
Only synthetic canonical rows and published app content are used. No originals,
helpers, indexes, provider calls or existing-profile restore are performed.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import closing, contextmanager
import ctypes
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import sys
import threading
import time
import tracemalloc

MIB = 1024 * 1024
FORMAT = "renulus-capacity-segments-experiment-v1"
TABLES = frozenset({
    "content_packs", "content_topics", "content_case_versions", "content_question_versions",
    "content_pack_topics", "content_pack_cases", "content_pack_questions", "content_active_pack",
    "content_question_withdrawals", "content_pack_withdrawals", "deletion_ledger",
    "knowledge_documents", "knowledge_revisions", "knowledge_jobs", "knowledge_passages",
    "knowledge_cleanup", "knowledge_source_status_events",
})
STAMP = "2026-10-04T00:00:00+00:00"
TOPICS = ("ckd", "dialysis", "transplant", "glomerular")


class CapacityError(Exception):
    pass


def directory(value, *, fresh=False):
    path = Path(value)
    if fresh and os.path.lexists(path):
        raise CapacityError("Capacity workspace already exists; nothing was cleared.")
    if not path.is_absolute() or ".." in path.parts:
        raise CapacityError("Select an explicit absolute path without parent traversal.")
    for candidate in (path, *path.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise CapacityError("Capacity workspaces/code cannot follow links or junctions.")
    if fresh and not path.parent.is_dir():
        raise CapacityError("The explicit workspace parent must already exist.")
    return path.resolve()


def runtime(source):
    sys.path.insert(0, str(source / "runtime"))
    from renulus import server
    if not Path(server.__file__).resolve().is_relative_to(source / "runtime"):
        raise CapacityError("Run the selected app runtime in an isolated process.")
    return server


@contextmanager
def app_services(source, work):
    services = runtime(source).create_app(work / "s", source_root=source).state.services
    try:
        yield services  # No lifespan/worker/helper startup.
    finally:
        services.registry["knowledge_worker"].stop(timeout=5)
        services.registry["knowledge"].index.close()
        asyncio.run(services.registry["memory"].close())
        asyncio.run(services.registry["provider"].close())


@lru_cache(maxsize=1)
def native_sampler():
    """Windows process metrics include SQLite/native allocations, unlike tracemalloc."""
    if os.name != "nt":
        return None
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
            *[(name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    query = psapi.GetProcessMemoryInfo
    query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    query.restype = wintypes.BOOL
    def sample():
        counts = Counters()
        counts.cb = ctypes.sizeof(counts)
        if not query(kernel.GetCurrentProcess(), ctypes.byref(counts), counts.cb):
            raise CapacityError("Windows process memory measurement failed.")
        return {"working_set_bytes": counts.WorkingSetSize, "private_bytes": counts.PrivateUsage,
            "lifetime_peak_working_set_bytes": counts.PeakWorkingSetSize,
            "lifetime_peak_commit_bytes": counts.PeakPagefileUsage}
    return sample


def native_memory():
    sampler = native_sampler()
    return sampler() if sampler else None


def workspace_bytes(work):
    size = 0
    for path in work.rglob("*"):
        try:
            if path.is_file():
                size += path.stat().st_size
        except FileNotFoundError:
            pass  # SQLite may finish/remove a journal between enumeration/stat.
    return size


class Measurement:
    def __init__(self, work):
        self.work, self.stop = work, threading.Event()
        self.peaks, self.samples, self.disk_peak = {}, 0, 0

    def sample(self):
        current = native_memory()
        if current:
            for key, value in current.items():
                self.peaks[key] = max(self.peaks.get(key, 0), value)
        self.disk_peak = max(self.disk_peak, workspace_bytes(self.work))
        self.samples += 1

    def watch(self):
        while not self.stop.wait(0.02):
            self.sample()

    def __enter__(self):
        self.initial = native_memory()
        self.sample()
        tracemalloc.start()
        self.started = time.perf_counter()
        self.thread = threading.Thread(target=self.watch, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *unused):
        self.stop.set()
        self.thread.join(timeout=5)
        self.sample()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.report = {"elapsed_seconds": round(time.perf_counter() - self.started, 4),
            "python_peak_bytes": peak, "native_initial": self.initial,
            "native_peaks": self.peaks or None, "native_sample_count": self.samples,
            "sample_interval_seconds": 0.02, "workspace_peak_bytes": self.disk_peak}


def check_disk(work, config):
    if workspace_bytes(work) > config["disk_budget_bytes"]:
        raise CapacityError("Experimental workspace disk budget exceeded; artifacts retained for inspection.")


def synthetic_fixture(services, config):
    from renulus.knowledge.models import SourceMetadata, own_text_rights
    from renulus.storage.recovery_archive import canonical_json
    metadata = SourceMetadata(source_id="R02", edition="SYNTHETIC capacity edition").model_dump_json()
    rights = own_text_rights().model_copy(update={"attribution": "Synthetic capacity fixture; CC BY 4.0"}).model_dump_json()
    docs, passages, width = config["documents"], config["passages"], config["text_bytes"]
    with services.db.transaction() as conn:
        for i in range(docs):
            doc, rev, job = f"doc_{i:010d}", f"rev_{i:010d}", f"job_{i:010d}"
            conn.execute("INSERT INTO knowledge_documents(id,title,source_id,scope_kind,scope_entity,reserved,active_revision,latest_revision,deleted_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (doc, f"SYNTHETIC {TOPICS[i % 4]} capacity {i}", "R02", "personal-library", None, 0,
                 rev, rev, None, STAMP, STAMP))
            # Explicit columns keep synthetic generation separate from shared DDL.
            conn.execute("INSERT INTO knowledge_revisions(id,document_id,ordinal,status,sha256,media_type,bytes,original_path,metadata_json,rights_json,extraction_json,created_at,activated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rev, doc, 1, "ready", hashlib.sha256(doc.encode()).hexdigest(), "text/plain", 0,
                 None, metadata, rights, '{"synthetic_rebuildable_projection":true}', STAMP, STAMP))
            conn.execute("INSERT INTO knowledge_jobs(id,revision_id,idempotency_key,request_hash,state,phase,created_at,finished_at) VALUES(?,?,?,?,?,?,?,?)",
                (job, rev, "synthetic-capacity-" + doc, "0" * 64, "ready", "ready", STAMP, STAMP))
        for i in range(passages):
            topic, ordinal = TOPICS[i % docs % 4], i // docs
            seed = f"SYNTHETIC {topic} capacity doc {i % docs} passage {ordinal}; Δ µ provenance, educational fixture only. "
            raw = seed.encode("utf-8")
            text = (raw * (width // len(raw) + 1))[:width].decode("utf-8", errors="ignore")
            conn.execute("INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)",
                (f"pass_{i:010d}", f"rev_{i % docs:010d}", ordinal, text, f"SYNTHETIC {topic} heading\n" + text,
                 canonical_json([{"page": ordinal + 1, "item_id": f"#/texts/{ordinal}"}]).decode(),
                 canonical_json([f"SYNTHETIC {topic} heading"]).decode()))
    services.registry["knowledge"].update_source_status({"contract_version": 1,
        "event_id": "synthetic-capacity-journal", "source_id": "R02",
        "identity": {"canonical_url": "https://example.invalid/synthetic-capacity"},
        "changes": {"content_reviewed": False}, "scope": {}})


def schema(conn):
    result = {}
    for name in sorted(TABLES):
        definition = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        if definition:
            columns = list(conn.execute(f'PRAGMA table_info("{name}")'))
            result[name] = {"sql": definition[0], "columns": [row["name"] for row in columns],
                "keys": [row["name"] for row in columns if row["pk"]]}
    return result


def rows(conn, definitions, config):
    """Only selected generated tables; no catalogue/provider/derived-state cursor."""
    from renulus.storage.backup import portable_records
    for name, definition in definitions.items():
        projection = ["NULL AS " + column if name == "knowledge_revisions" and column == "extraction_json" or column.endswith("_path")
            else '"' + column + '"' for column in definition["columns"]]
        # Avoid bringing a giant scalar into Python before applying the row bound.
        lengths = ["0" if column == "extraction_json" or column.endswith("_path")
            else f'COALESCE(length(CAST("{column}" AS BLOB)),0)' for column in definition["columns"]]
        largest = conn.execute(f'SELECT MAX({"+".join(lengths)}) FROM "{name}"').fetchone()[0] or 0
        if largest > config["row_bytes"]:
            raise CapacityError("A scalar/row exceeds the experimental row bound before Python projection.")
        for row in conn.execute(f'SELECT {",".join(projection)} FROM "{name}" ORDER BY rowid'):
            yield name, portable_records({name: [dict(row)]})[name][0]


def write_segments(conn, definitions, destination, config):
    from renulus.storage.recovery_archive import canonical_json
    destination.mkdir(exist_ok=False)
    segments, counts, total, digest = [], {name: 0 for name in definitions}, 0, hashlib.sha256()
    output, descriptor, segment_hash = None, None, None
    def finish():
        if output is not None:
            output.close()
            descriptor["sha256"] = segment_hash.hexdigest()
            segments.append(descriptor)
    try:
        for table, row in rows(conn, definitions, config):
            line = canonical_json({"table": table, "row": row}) + b"\n"
            if len(line) > config["row_bytes"]:
                raise CapacityError("A serialized record exceeds the experimental row bound.")
            if total + len(line) > config["canonical_budget_bytes"] or sum(counts.values()) >= config["record_budget"]:
                raise CapacityError("Experimental aggregate canonical/record budget exceeded; no truncation.")
            if output is None or descriptor["bytes"] + len(line) > config["segment_bytes"]:
                finish()
                if len(segments) >= 512:
                    raise CapacityError("Experimental segment inventory bound exceeded.")
                descriptor = {"path": f"records_{len(segments):06d}.jsonl", "bytes": 0, "rows": 0}
                segment_hash = hashlib.sha256()
                output = (destination / descriptor["path"]).open("xb")
            output.write(line)
            descriptor["bytes"] += len(line)
            descriptor["rows"] += 1
            segment_hash.update(line)
            digest.update(line)
            total += len(line)
            counts[table] += 1
            if sum(counts.values()) % 512 == 0:
                check_disk(destination.parent, config)
        finish()
        output = None
        manifest = {"format": FORMAT, "production_restore_supported": False, "segments": segments,
            "bytes": total, "tables": counts, "row_digest": digest.hexdigest()}
        data = canonical_json(manifest)
        if len(data) > MIB:
            raise CapacityError("Experimental manifest exceeds 1 MiB.")
        (destination / "manifest.json").write_bytes(data)
        return manifest
    finally:
        if output is not None:
            output.close()


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400 or info.st_nlink != 1:
        raise CapacityError("Experimental staging refuses linked/junction members.")


def stage_segments(destination, target, definitions, config):
    """Validate into one new scratch transaction; never promote a profile/original."""
    from renulus.storage.recovery_archive import strict_json
    destination = directory(destination)
    target = directory(target, fresh=True)
    regular(destination / "manifest.json")
    if (destination / "manifest.json").stat().st_size > MIB:
        raise CapacityError("Experimental manifest exceeds its bound.")
    manifest = strict_json((destination / "manifest.json").read_bytes())
    if not isinstance(manifest, dict) or set(manifest) != {"format", "production_restore_supported", "segments", "bytes", "tables", "row_digest"} or manifest["format"] != FORMAT or manifest["production_restore_supported"] is not False:
        raise CapacityError("Unsupported experimental manifest.")
    entries = manifest["segments"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 512 or set(manifest["tables"]) != set(definitions):
        raise CapacityError("Experimental inventory/table declaration is invalid.")
    expected_names, declared = set(), 0
    for number, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "rows", "sha256"} or entry["path"] != f"records_{number:06d}.jsonl" or type(entry["bytes"]) is not int or not 0 < entry["bytes"] <= config["segment_bytes"] or type(entry["rows"]) is not int or entry["rows"] <= 0 or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise CapacityError("Experimental member descriptor exceeds its bound or is unsafe.")
        declared += entry["bytes"]
        expected_names.add(entry["path"])
        regular(destination / entry["path"])
        if (destination / entry["path"]).stat().st_size != entry["bytes"]:
            raise CapacityError("Experimental member exact size differs.")
    if declared != manifest["bytes"] or declared > config["canonical_budget_bytes"]:
        raise CapacityError("Experimental aggregate byte budget exceeded or declaration differs.")
    for number, path in enumerate(destination.iterdir()):
        if number > 512 or path.name not in expected_names | {"manifest.json"}:
            raise CapacityError("Unexpected experimental member; nothing was promoted.")
    target.open("xb").close()  # Refuse existing scratch data atomically.
    counts, digest, consumed = {name: 0 for name in definitions}, hashlib.sha256(), 0
    with closing(sqlite3.connect(target)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-2048")
        for definition in definitions.values():
            conn.execute(definition["sql"])
        conn.commit()
        conn.execute("BEGIN")
        conn.execute("PRAGMA defer_foreign_keys=ON")
        try:
            for entry in entries:
                hash_segment, size, count = hashlib.sha256(), 0, 0
                with (destination / entry["path"]).open("rb") as member:
                    while line := member.readline(config["row_bytes"] + 1):
                        if len(line) > config["row_bytes"] or not line.endswith(b"\n"):
                            raise CapacityError("Experimental row exceeds its bounded read.")
                        size += len(line)
                        if size > entry["bytes"] or consumed >= config["record_budget"]:
                            raise CapacityError("Experimental member/record budget exceeded.")
                        frame = strict_json(line)
                        if not isinstance(frame, dict) or set(frame) != {"table", "row"} or frame["table"] not in definitions:
                            raise CapacityError("Experimental record/table is invalid.")
                        table, row = frame["table"], frame["row"]
                        columns = definitions[table]["columns"]
                        if not isinstance(row, dict) or set(row) != set(columns) or any(
                                value is not None and (type(value) not in (str, int, float) or isinstance(value, float) and not math.isfinite(value)) for value in row.values()) or any(row[key] is None for key in definitions[table]["keys"]):
                            raise CapacityError("Experimental record shape/scalars/keys are invalid.")
                        conn.execute(f'INSERT INTO "{table}"({",".join(chr(34)+name+chr(34) for name in columns)}) VALUES({",".join("?" for _ in columns)})', [row[name] for name in columns])
                        hash_segment.update(line)
                        digest.update(line)
                        counts[table] += 1
                        consumed += 1
                        count += 1
                        if consumed % 512 == 0:
                            check_disk(destination.parent, config)
                if size != entry["bytes"] or count != entry["rows"] or hash_segment.hexdigest() != entry["sha256"]:
                    raise CapacityError("Experimental segment integrity differs; scratch transaction rolled back.")
            if counts != manifest["tables"] or digest.hexdigest() != manifest["row_digest"] or conn.execute("PRAGMA foreign_key_check").fetchone():
                raise CapacityError("Experimental record totals/digest/references differ.")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return {"status": "validated", "segments": len(entries), "bytes": declared, "tables": counts,
        "source_digest": manifest["row_digest"], "staged_digest": digest.hexdigest()}


def measure_worker(source, work, config, mode):
    from renulus.contracts import ApiError
    from renulus.storage.backup import export_records
    from renulus.storage.recovery_archive import canonical_json, DEFAULT_LIMITS
    with app_services(source, work) as services:
        measurement = Measurement(work)
        try:
            with measurement:
                if mode == "legacy":
                    with services.registry["data_recovery"].mutation():
                        bundle = export_records(services)
                    data = canonical_json(bundle)
                    if len(data) > DEFAULT_LIMITS.json_bytes:
                        raise CapacityError("Current canonical JSON bound exceeded.")
                    with (work / "legacy.json").open("xb") as output:
                        output.write(data)
                    result = {"status": "within_bounds", "bytes": len(data),
                        "records": sum(len(rows) for rows in bundle["records"].values())}
                else:
                    with closing(services.db.connect()) as conn:
                        conn.execute("BEGIN")
                        definitions = schema(conn)
                        write_segments(conn, definitions, work / "segments", config)
                    result = stage_segments(work / "segments", work / "stage.sqlite3", definitions, config)
                    check_disk(work, config)
        except (CapacityError, ApiError, sqlite3.IntegrityError) as error:
            result = {"status": "blocked", "error_code": getattr(error, "code", type(error).__name__),
                "reason": str(error) if isinstance(error, CapacityError) else "Current bounds or canonical constraints refused the experiment."}
        result["measurement"] = measurement.report
        return result


def validate_config(config):
    expected = {"documents", "passages", "text_bytes", "row_bytes", "segment_bytes",
        "record_budget", "canonical_budget_bytes", "disk_budget_bytes"}
    if not isinstance(config, dict) or set(config) != expected or any(type(value) is not int for value in config.values()):
        raise CapacityError("Synthetic capacity configuration has an invalid shape.")
    if not 1 <= config["documents"] <= 13000 or not 0 <= config["passages"] <= 150000 or not 128 <= config["text_bytes"] <= 16384:
        raise CapacityError("Synthetic inputs exceed the finite experiment scope.")
    if not 4096 <= config["row_bytes"] <= config["segment_bytes"] <= 4 * MIB or not 1 <= config["record_budget"] <= 200000 or not MIB <= config["canonical_budget_bytes"] <= 256 * MIB or not 16 * MIB <= config["disk_budget_bytes"] <= 2 * 1024 * MIB:
        raise CapacityError("Select bounded row/segment/record/canonical/disk budgets.")
    if config["passages"] * config["text_bytes"] * 2 > config["canonical_budget_bytes"]:
        raise CapacityError("Requested synthetic text already exceeds the experimental canonical budget.")
    if 4 * config["canonical_budget_bytes"] > config["disk_budget_bytes"]:
        raise CapacityError("Reserve at least four canonical budgets for synthetic source/segments/staging and SQLite overhead.")


def run(config, source, work):
    work = directory(work, fresh=True)  # Check before source/runtime access.
    source = directory(source)
    if work.is_relative_to(source) or source.is_relative_to(work):
        raise CapacityError("Use a separate task-owned workspace outside app code.")
    validate_config(config)
    work.mkdir(exist_ok=False)
    (work / "config.json").write_text(json.dumps({"synthetic_capacity_only": True, **config}), encoding="utf-8")
    with app_services(source, work) as services:
        synthetic_fixture(services, config)
    check_disk(work, config)
    from renulus.storage.backup import MAX_RECORDS
    from renulus.storage.recovery_archive import DEFAULT_LIMITS
    results = {}
    for mode in ("legacy", "segmented"):
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "--source-root", str(source), "--work-dir", str(work), "--worker", mode]
        child = subprocess.run(command, capture_output=True, text=True, timeout=900)
        if child.returncode != 0:
            raise CapacityError(f"Isolated {mode} measurement failed; owned artifacts remain at {work}.")
        results[mode] = json.loads(child.stdout)
    report = {"format": "renulus-recovery-capacity-report-v1", "production_restore_supported": False,
        "work_dir": str(work), "source_root": str(source), "synthetic": config,
        "current_limits": {**DEFAULT_LIMITS.public(), "records": MAX_RECORDS}, **results,
        "workspace_final_bytes": workspace_bytes(work),
        "limitations": ["Canonical Library/content experiment, not an actual backup/profile or production restore format.",
            "No acquired originals, helpers, provider generation or derived index rebuild measured.",
            "Sampled native/private peaks can miss very short spikes; Python tracing adds overhead.",
            "SQLite disk observation is not a filesystem quota or power-loss/atomic profile promotion proof."]}
    (work / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path, help="Explicit app code root, never a live profile")
    parser.add_argument("--work-dir", required=True, type=Path, help="Fresh absolute task-owned measurement directory")
    parser.add_argument("--documents", type=int, default=156)
    parser.add_argument("--passages", type=int, default=6000)
    parser.add_argument("--text-bytes", type=int, default=1536, help="Synthetic UTF-8 passage bytes; context duplicates this text")
    parser.add_argument("--segment-bytes", type=int, default=4 * MIB)
    parser.add_argument("--row-bytes", type=int, default=256 * 1024)
    parser.add_argument("--canonical-budget-bytes", type=int, default=64 * MIB)
    parser.add_argument("--record-budget", type=int, default=200000)
    parser.add_argument("--disk-budget-bytes", type=int, default=1024 * MIB)
    parser.add_argument("--worker", choices=("legacy", "segmented"), help=argparse.SUPPRESS)
    args = vars(parser.parse_args(argv))
    source, work, mode = args.pop("source_root"), args.pop("work_dir"), args.pop("worker")
    try:
        if mode:
            work = directory(work)
            marker = work / "config.json"
            if not marker.is_file() or marker.stat().st_size > 32768:
                raise CapacityError("Only generated synthetic capacity workspaces may be measured.")
            config = json.loads(marker.read_text(encoding="utf-8"))
            if config.pop("synthetic_capacity_only", None) is not True:
                raise CapacityError("Synthetic workspace marker missing; live profiles are not accepted.")
            validate_config(config)
            runtime(directory(source))
            report = measure_worker(source, work, config, mode)
        else:
            report = run(args, source, work)
    except (CapacityError, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0 if mode or report["segmented"]["status"] == "validated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
