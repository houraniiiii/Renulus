from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import zipfile

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.server import create_app
from renulus.storage.recovery_archive import DEFAULT_LIMITS

from .conftest import forge, preview, restore, state, zip_bytes


@pytest.mark.parametrize("name", ["../outside.txt", "/absolute.txt", "C:/SYNTHETIC.txt",
    "library/knowledge/doc_fake/rev_fake/../original.txt", "library\\knowledge\\doc_fake\\rev_fake\\original.txt",
    "state/protected.bin", "indexes/knowledge/data.bin", "helpers/weights.bin", "library/unreferenced.txt",
    "library/knowledge/doc_fake/rev_fake/original.txt:alternate"])
def test_unexpected_traversal_absolute_alternate_stream_and_nonoriginal_members_never_touch_profile(source, target, name):
    def extra(manifest, bundle, members):
        members[name] = b"SYNTHETIC_FORGED_MEMBER"
    before = state(target)
    with pytest.raises(ApiError):
        preview(target, forge(zip_bytes(source[0]), extra))
    assert state(target) == before
    assert not list((target.paths.cache / "recovery/previews").iterdir())
    assert not (target.paths.root.parent / "outside.txt").exists()


def repack(data, *, duplicate=False, linked=False, compression=zipfile.ZIP_DEFLATED):
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(output, "w", compression) as target:
        for item in source.infolist():
            if linked and item.filename == "manifest.json":
                info = zipfile.ZipInfo(item.filename)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                target.writestr(info, source.read(item))
            else:
                target.writestr(item.filename, source.read(item))
        if duplicate:
            target.writestr("records.json", source.read("records.json"))
    return output.getvalue()


@pytest.mark.parametrize("mutation", ["duplicate", "linked", "encrypted", "local-encrypted", "trailing", "unsupported", "crc", "overlap", "size-header"])
def test_forged_zip_headers_crc_links_encryption_duplicates_and_junk_fail_before_promotion(source, target, mutation):
    original = zip_bytes(source[0])
    if mutation == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate"):
            bad = repack(original, duplicate=True)
    elif mutation == "linked":
        bad = repack(original, linked=True)
    elif mutation == "unsupported":
        bad = repack(original, compression=zipfile.ZIP_BZIP2)
    elif mutation == "trailing":
        bad = original + b"SYNTHETIC_TRAILING_DATA"
    else:
        bad = bytearray(original)
        central = bad.index(b"PK\x01\x02")
        if mutation in ("encrypted", "local-encrypted"):
            struct.pack_into("<H", bad, 6, struct.unpack_from("<H", bad, 6)[0] | 1)
            if mutation == "encrypted":
                struct.pack_into("<H", bad, central + 8, struct.unpack_from("<H", bad, central + 8)[0] | 1)
        elif mutation == "crc":
            value = struct.unpack_from("<L", bad, 14)[0] ^ 0xFFFF
            struct.pack_into("<L", bad, 14, value)
            struct.pack_into("<L", bad, central + 16, value)
        elif mutation == "overlap":
            struct.pack_into("<L", bad, central + 42, 1)
        elif mutation == "size-header":
            struct.pack_into("<L", bad, 22, 1)
        bad = bytes(bad)
    before = state(target)
    with pytest.raises(ApiError):
        preview(target, bad)
    assert state(target) == before
    assert not list(target.paths.library.rglob("original.*"))


@pytest.mark.parametrize("mutation", ["hash", "size", "missing", "duplicate-record", "foreign-key", "content-key", "malformed-descriptor", "nonportable-catalogue", "provider-preference", "temporary-scope", "schema-type", "rights-type", "deleted-document", "integer-range"])
def test_valid_zip_crcs_do_not_make_forged_canonical_content_or_manifest_valid(source, target, mutation):
    def change(manifest, bundle, members):
        entry = manifest["originals"][0]
        revision = bundle["records"]["knowledge_revisions"][0]
        if mutation == "hash":
            members[entry["path"]] = b"X" * entry["bytes"]
        elif mutation == "size":
            entry["bytes"] += 1
        elif mutation == "missing":
            del members[entry["path"]]
        elif mutation == "duplicate-record":
            bundle["records"]["knowledge_revisions"].append(dict(revision))
        elif mutation == "foreign-key":
            bundle["records"]["knowledge_jobs"][0]["revision_id"] = "rev_nonexistent"
        elif mutation == "content-key":
            bundle["records"]["content_question_versions"][0]["body_json"] = '{"forged":"Unchanged digest must not conceal a changed key"}'
        elif mutation == "malformed-descriptor":
            entry["revision_id"] = ["unhashable forged ID"]
        elif mutation == "nonportable-catalogue":
            bundle["records"]["knowledge_catalogue"] = []
        elif mutation == "provider-preference":
            bundle["records"]["preferences"].append({"key": "runtime.selected_provider", "value": "SYNTHETIC_FORGED_PROVIDER", "updated_at": "2026-10-04T22:00:00Z"})
        elif mutation == "temporary-scope":
            bundle["records"]["knowledge_documents"][0]["scope_kind"] = "temporary-case"
        elif mutation == "schema-type":
            manifest["schema_version"] = True
        elif mutation == "rights-type":
            revision["rights_json"] = json.dumps({"cache": "false", "display": "false"})
        elif mutation == "deleted-document":
            bundle["records"]["knowledge_documents"][0]["deleted_at"] = "2026-10-04T23:00:00Z"
        elif mutation == "integer-range":
            bundle["records"]["knowledge_documents"][0]["reserved"] = 2**80
    before = state(target)
    with pytest.raises(ApiError):
        preview(target, forge(zip_bytes(source[0]), change))
    assert state(target) == before


def test_duplicate_json_fields_are_rejected_even_when_manifest_hash_is_valid(source, target):
    data = zip_bytes(source[0])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    manifest = json.loads(members["manifest.json"])
    records = members["records.json"].replace(b'"format_version":1', b'"format_version":1,"format_version":1', 1)
    manifest["records"].update(bytes=len(records), sha256=hashlib.sha256(records).hexdigest())
    members["records.json"], members["manifest.json"] = records, json.dumps(manifest).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)
    before = state(target)
    with pytest.raises(ApiError) as error:
        preview(target, output.getvalue())
    assert error.value.code == "backup_json"
    assert state(target) == before


@pytest.mark.parametrize("limit", ["archive_bytes", "json_bytes", "original_bytes", "total_original_bytes", "originals"])
def test_limits_bound_compressed_upload_expanded_members_json_total_and_count(source, target, limit):
    data = zip_bytes(source[0])
    value = 22 if limit == "archive_bytes" else 16 if limit == "json_bytes" else 1
    target.registry["data_recovery"].limits = replace(DEFAULT_LIMITS, **{limit: value})
    before = state(target)
    with pytest.raises(ApiError) as failure:
        preview(target, data)
    assert failure.value.status == 413
    assert state(target) == before


def test_an_external_original_reference_is_not_read_or_copied_by_zip_export(source, monkeypatch):
    services, selected = source
    external = selected[0]["input"]
    services.db.execute("UPDATE knowledge_revisions SET original_path=? WHERE id=?", (str(external), selected[0]["revision_id"]))
    actual_open = Path.open
    def forbidden(path, *args, **kwargs):
        if path == external:
            pytest.fail("Recovery attempted to read an external original")
        return actual_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(ApiError) as failure:
        zip_bytes(services)
    assert failure.value.code == "backup_path"


def test_hard_linked_profile_original_is_not_treated_as_an_owned_copy(source, tmp_path):
    services, selected = source
    row = services.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (selected[0]["revision_id"],))
    os.link(row["original_path"], tmp_path / "synthetic-second-link.txt")
    with pytest.raises(ApiError) as failure:
        zip_bytes(services)
    assert failure.value.code == "backup_path"


def test_staged_bytes_are_checked_again_before_promotion(source, target):
    checked = preview(target, zip_bytes(source[0]))
    recovery = target.registry["data_recovery"]
    staged = recovery._preview[2].originals[0]["staged"]
    staged.write_bytes(b"SYNTHETIC_STAGE_TAMPERING")
    before = state(target)
    with pytest.raises(ApiError) as failure:
        recovery.restore_preview(checked["preview_token"], checked["exported_at"], True)
    assert failure.value.code == "backup_integrity"
    assert state(target) == before


def test_http_stream_bounds_and_duplicate_json_cannot_bypass_read_limits(source, tmp_path):
    app = create_app(tmp_path / "bounded-http")
    services = app.state.services
    services.registry["data_recovery"].limits = replace(DEFAULT_LIMITS, archive_bytes=128, json_bytes=128)
    client = TestClient(app)
    before = state(services)
    result = client.post("/api/v1/data/backup/preview", content=iter([b"X" * 100, b"Y" * 100]))
    assert result.status_code == 413
    result = client.post("/api/v1/data/restore", content=b'{"bundle":{},"bundle":{},"confirm_backup_date":true}')
    assert result.status_code == 400
    assert result.json()["error"]["code"] == "backup_json"
    result = client.post("/api/v1/data/restore", content=b"X" * 5000)
    assert result.status_code == 413
    assert state(services) == before
    assert not list((services.paths.cache / "recovery/previews").iterdir())
