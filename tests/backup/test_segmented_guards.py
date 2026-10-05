# SPDX-License-Identifier: MIT
"""ZIP64, budgets, real original volume and crash recovery for format 2."""
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import own_text_rights, SourceMetadata
from renulus.server import create_app
from renulus.storage.recovery_limits import SEGMENTED_LIMITS
from renulus.storage.recovery_segmented import file_digest
from renulus.storage.recovery_zip import directory as validate_zip_directory

from .conftest import preview, state
from .test_segmented_recovery import download, restore_v2


def zip64_archive(data, monkeypatch, *, descriptor=False):
    output = io.BytesIO()
    class NoSeek:
        def write(self, block): return output.write(block)
        def tell(self): return output.tell()
        def flush(self): return None
    with monkeypatch.context() as limits:
        # Force the real CPython writer to emit all ZIP64 size/offset/trailer
        # structures using a small synthetic archive, including descriptors.
        limits.setattr(zipfile, "ZIP64_LIMIT", 256)
        with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(NoSeek() if descriptor else output, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                target.writestr(item.filename, source.read(item))
    result = output.getvalue()
    assert b"PK\x06\x06" in result and b"PK\x06\x07" in result
    if descriptor:
        assert b"PK\x07\x08" in result
    return result


@pytest.mark.parametrize("crossing", ["payload", "descriptor", "signature"])
def test_bounded_zip_inventory_refuses_descriptor_that_overlaps_directory_before_unpack(tmp_path, crossing):
    output = io.BytesIO()
    class NoSeek:
        def write(self, block): return output.write(block)
        def tell(self): return output.tell()
        def flush(self): return None
    with zipfile.ZipFile(NoSeek(), "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", b"{}")
    bad = bytearray(output.getvalue())
    start = struct.unpack_from("<L", bad, len(bad) - 6)[0]
    data_start = 30 + len("manifest.json")
    remaining = {"payload": -len(bad), "descriptor": 8, "signature": 2}[crossing]
    struct.pack_into("<L", bad, start + 20, start - data_start - remaining)
    path = tmp_path / "selected-forged-descriptor.zip"
    path.write_bytes(bad)
    with pytest.raises(ApiError) as rejected:
        validate_zip_directory(path, SEGMENTED_LIMITS)
    assert rejected.value.code == "backup_zip"


@pytest.mark.parametrize("descriptor", [False, True])
def test_cp_python_zip64_headers_offsets_trailers_and_stream_descriptors_restore_exact_originals(source, target, monkeypatch, descriptor):
    data, _ = download(source[0])
    archive = zip64_archive(data, monkeypatch, descriptor=descriptor)
    result = restore_v2(target, archive)
    assert result["restored_originals"] == 4
    for selected in source[1]:
        row = target.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (selected["revision_id"],))
        assert Path(row["original_path"]).read_bytes() == selected["bytes"]


@pytest.mark.parametrize("mutation", ["zip64-length", "zip64-count", "zip64-offset", "locator-disk", "local-name", "local-size", "encryption", "trailing", "duplicate"])
def test_forged_zip64_or_local_headers_fail_before_promotion(source, target, monkeypatch, mutation):
    data, _ = download(source[0])
    bad = bytearray(zip64_archive(data, monkeypatch))
    record, locator = bad.rfind(b"PK\x06\x06"), bad.rfind(b"PK\x06\x07")
    if mutation == "zip64-length": struct.pack_into("<Q", bad, record + 4, 45)
    elif mutation == "zip64-count": struct.pack_into("<Q", bad, record + 32, 20001)
    elif mutation == "zip64-offset": struct.pack_into("<Q", bad, record + 48, 1)
    elif mutation == "locator-disk": struct.pack_into("<L", bad, locator + 4, 1)
    elif mutation == "local-name": bad[30] ^= 32
    elif mutation == "local-size": struct.pack_into("<L", bad, 22, 1)
    elif mutation == "encryption":
        struct.pack_into("<H", bad, 6, struct.unpack_from("<H", bad, 6)[0] | 1)
        central = bad.index(b"PK\x01\x02")
        struct.pack_into("<H", bad, central + 8, struct.unpack_from("<H", bad, central + 8)[0] | 1)
    elif mutation == "trailing": bad.extend(b"SYNTHETIC_JUNK")
    else:
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(data)) as archive, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as duplicate:
            for item in archive.infolist(): duplicate.writestr(item.filename, archive.read(item))
            with pytest.warns(UserWarning, match="Duplicate"):
                duplicate.writestr("manifest.json", archive.read("manifest.json"))
        bad = bytearray(output.getvalue())
    before = state(target)
    with pytest.raises(ApiError):
        preview(target, bytes(bad))
    assert state(target) == before
    assert not list((target.paths.cache / "recovery/previews").iterdir())


@pytest.mark.parametrize("bound", ["row_bytes", "segment_bytes", "canonical_bytes", "records", "original_bytes",
    "originals", "total_original_bytes", "expanded_bytes", "archive_bytes", "manifest_bytes", "directory_bytes", "graph_edges", "workspace_bytes"])
def test_version2_size_count_graph_and_disk_budgets_refuse_without_changing_profile(source, target, bound):
    data, _ = download(source[0])
    recovery = target.registry["data_recovery"]
    recovery.segmented_limits = replace(SEGMENTED_LIMITS, **{bound: 1})
    before = state(target)
    with pytest.raises(ApiError) as error:
        preview(target, data)
    assert error.value.status == 413
    assert state(target) == before
    assert not list((target.paths.cache / "recovery/previews").iterdir())


def test_staged_canonical_database_tampering_is_detected_before_sql_or_file_promotion(source, target):
    data, _ = download(source[0])
    checked = preview(target, data)
    recovery = target.registry["data_recovery"]
    staged = recovery._preview[2].stage
    with staged.open("r+b") as file:
        file.seek(-1, os.SEEK_END)
        value = file.read(1)
        file.seek(-1, os.SEEK_END)
        file.write(bytes([value[0] ^ 1]))
    before = state(target)
    with pytest.raises(ApiError) as error:
        recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert error.value.code == "backup_integrity"
    assert state(target) == before


def test_actual_265_mib_synthetic_originals_exceed_legacy_budget_and_stream_into_fresh_profile(source, target, tmp_path):
    services, _ = source
    inputs = tmp_path / "selected-large-synthetic-inputs"
    inputs.mkdir()
    imported = []
    block = b"SYNTHETIC educational recovery volume only.\n" * 24000
    for number in range(5):
        path = inputs / f"synthetic-volume-{number}.txt"
        remaining, digest = 53 * 1024 * 1024, hashlib.sha256()
        with path.open("xb") as file:
            header = f"SYNTHETIC original {number}\n".encode()
            file.write(header)
            digest.update(header)
            remaining -= len(header)
            while remaining:
                chunk = block[:min(remaining, len(block))]
                file.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
        document = services.registry["knowledge"].import_file(path, process=False,
            rights=own_text_rights(), metadata=SourceMetadata(source_id="R02", edition="Synthetic large-volume recovery"))
        imported.append((document, path, {"bytes": 53 * 1024 * 1024, "sha256": digest.hexdigest()}))
    with pytest.raises(ApiError) as error:
        services.registry["data_recovery"].backup()
    assert error.value.code == "backup_limit"
    data, manifest = download(services)
    assert sum(entry["bytes"] for entry in manifest["originals"]) > 256 * 1024 * 1024
    result = restore_v2(target, data)
    assert result["restored_originals"] == 9
    for document, external, expected in imported:
        revision = target.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (document["revision_id"],))
        path = Path(revision["original_path"])
        assert path.is_relative_to(target.paths.library)
        assert file_digest(path) == expected
        assert file_digest(external) == expected
        assert json.loads(revision["metadata_json"])["edition"] == "Synthetic large-volume recovery"


@pytest.mark.parametrize("point", ["before_receipt", "after_commit"])
def test_version2_restart_receipt_preserves_file_outcome_and_five_digit_staged_identity(source, target, tmp_path, point):
    services, selected = source
    data, _ = download(services)
    restore_v2(target, data)
    before = state(target)
    services.registry["knowledge"].import_text("SYNTHETIC new renal study original", process=False)
    services.db.mark_deleted("knowledge-document", selected[0]["document_id"])
    data, _ = download(services)
    archive = tmp_path / "explicit-synthetic-v2.zip"
    archive.write_bytes(data)
    code = """
import os, sys
from pathlib import Path
from renulus.server import create_app
from renulus.storage.recovery_files import OriginalTransaction
services = create_app(sys.argv[1]).state.services
recovery = services.registry['data_recovery']
identifier, directory = recovery.begin_preview()
(directory / 'input.zip').write_bytes(Path(sys.argv[2]).read_bytes())
checked = recovery.complete_preview(identifier, directory)
recovery.end_upload(directory, keep=True)
entry = next(item for item in recovery._preview[2].originals if not (services.paths.root / item['path']).exists())
renamed = entry['staged'].parent / '10001'
entry['staged'].rename(renamed)
entry['staged'] = renamed
if sys.argv[3] == 'before_receipt':
    original = OriginalTransaction.promote
    def crash(self):
        original(self)
        os._exit(79)
    OriginalTransaction.promote = crash
else:
    OriginalTransaction.finish = lambda self: os._exit(80)
recovery.restore_preview(checked['preview_token'], checked['exported_at'], True)
raise AssertionError('Crash injection did not run')
"""
    environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "runtime")}
    crashed = subprocess.run([sys.executable, "-B", "-c", code, str(target.paths.root), str(archive), point],
        env=environment, capture_output=True, timeout=60)
    assert crashed.returncode == (79 if point == "before_receipt" else 80), crashed.stderr.decode()
    journals = list((target.paths.state / "recovery/transactions").glob("*/journal.json"))
    assert len(journals) == 1
    journal = json.loads(journals[0].read_bytes())
    assert journal["version"] == 2
    assert any(entry.get("staged", "").endswith("/10001") for entry in journal["entries"])
    restarted = create_app(target.paths.root).state.services
    assert not list((target.paths.state / "recovery/transactions").iterdir())
    assert not list((target.paths.cache / "recovery/previews").iterdir())
    if point == "before_receipt":
        assert state(restarted) == before
    else:
        assert restarted.db.is_deleted("knowledge-document", selected[0]["document_id"])
        assert not restarted.db.fetch_one("SELECT id FROM knowledge_documents WHERE id=?", (selected[0]["document_id"],))
        assert len(list(target.paths.library.rglob("original.*"))) == 4
        assert restarted.registry["data_recovery"].status()["rebuild"]["status"] == "required"
