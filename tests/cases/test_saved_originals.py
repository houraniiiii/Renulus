# SPDX-License-Identifier: MIT
"""Explicit Save rules with synthetic originals; no parser, model or native run."""
import base64
from contextlib import closing
import hashlib
from io import BytesIO
import json
import sqlite3

from fastapi.testclient import TestClient
from PIL import Image, PngImagePlugin
import pytest

from renulus.cases.attachments import AttachmentPreviews
from renulus.cases.models import StartCase
from renulus.cases.originals import accepted_original, CHUNK_BYTES
from renulus.cases.repository import CaseRepository
from renulus.contracts import ApiError
from renulus.server import create_app

from backup.conftest import text_pdf
from .conftest import assert_absent_from_profile
from .test_attachments import ExtractorFixture, finish, scope

ORIGINAL_SENTINEL = "RENULUS_SYNTHETIC_ORIGINAL_UNTIL_EXPLICIT_SAVE_5831"
FAILURE_SENTINEL = "RENULUS_SYNTHETIC_SQL_FAILURE_DO_NOT_EXPOSE_3941"
PUBLIC_METADATA = {"id", "filename", "title", "media_type", "bytes", "sha256",
                   "saved", "original_available"}


def synthetic_original(kind="pdf", *, marker=ORIGINAL_SENTINEL):
    """Valid small PDF/PNG bytes, each exceeding two canonical 48-KiB parts."""
    padding = marker + "\n" + "SYNTHETIC-ORIGINAL-PADDING-" * 4400
    if kind == "pdf":
        raw = text_pdf("Synthetic saved case original") + ("\n%" + padding).encode()
        media_type = "application/pdf"
    else:
        output = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Synthetic", padding)
        Image.new("RGB", (12, 8), "white").save(output, format="PNG", pnginfo=metadata)
        raw, media_type = output.getvalue(), "image/png"
    assert len(raw) > 2 * 49152
    return accepted_original(f"synthetic.{kind}", "Synthetic original", media_type, raw)


def attach(repository, case, original):
    return repository.attach(case["id"], case["revision"], original)


def canonical_state(services):
    return {table: services.db.fetch_all(f"SELECT * FROM {table} ORDER BY rowid")
            for table in ("case_sessions", "case_attachments", "case_attachment_parts")}


def assert_metadata(view, original, *, saved):
    metadata = next(item for item in view["attachments"] if item["id"] == original["id"])
    assert set(metadata) == PUBLIC_METADATA
    for key in ("id", "filename", "title", "media_type", "bytes", "sha256"):
        assert metadata[key] == original[key]
    assert metadata["saved"] is saved and metadata["original_available"] is True
    assert ORIGINAL_SENTINEL not in json.dumps(view)
    assert base64.b64encode(original["data"]).decode() not in json.dumps(view)
    return metadata


@pytest.mark.parametrize("kind", ["pdf", "png"])
async def test_text_apply_stages_exact_original_without_durable_bytes(repository, services, kind):
    original = synthetic_original(kind)
    services.registry["knowledge"] = ExtractorFixture()
    case = repository.start(StartCase(text="Synthetic attachment case"))
    previews = AttachmentPreviews(repository)
    job = previews.preflight(case["id"], case["revision"], scope(case),
                             original["filename"], original["title"])
    previews.start(job, original["data"])
    await finish(previews)
    result = previews.apply(job.id, case["revision"], "Reviewed synthetic extraction")
    staged = result["attachments"][0]
    assert staged["sha256"] == original["sha256"] and staged["bytes"] == original["bytes"]
    assert not staged["saved"] and staged["original_available"]
    assert "Reviewed synthetic extraction" in result["text"]
    assert repository.original(case["id"], staged["id"])[1] == original["data"]
    assert canonical_state(services) == {table: [] for table in canonical_state(services)}
    assert_absent_from_profile(services, ORIGINAL_SENTINEL,
                               base64.b64encode(original["data"]).decode())
    with pytest.raises(ApiError) as rejected:
        previews.keep(job.id, result["revision"])
    assert rejected.value.code == "case_preview_not_ready"


@pytest.mark.parametrize("kind", ["pdf", "png"])
def test_save_restart_exact_original_parts_and_metadata(repository, services, kind):
    original = synthetic_original(kind)
    raw = original["data"]
    case = attach(repository, repository.start(StartCase(text="Synthetic saved case")), original)
    assert_metadata(case, original, saved=False)
    assert_absent_from_profile(services, ORIGINAL_SENTINEL, base64.b64encode(raw).decode())
    saved = repository.save(case["id"], case["revision"])
    assert saved["saved"] and not saved["dirty"]
    assert_metadata(saved, {**original, "data": raw}, saved=True)
    assert CHUNK_BYTES == 49152
    parts = services.db.fetch_all(
        "SELECT part,data FROM case_attachment_parts WHERE attachment_id=? ORDER BY part", (original["id"],))
    assert [part["part"] for part in parts] == list(range((len(raw) + 49151) // 49152))
    decoded = [base64.b64decode(part["data"], validate=True) for part in parts]
    assert decoded == [raw[offset:offset + 49152] for offset in range(0, len(raw), 49152)]
    assert hashlib.sha256(b"".join(decoded)).hexdigest() == original["sha256"]
    # Reopen SQLite-backed state through a new repository, not the live snapshot.
    restarted = CaseRepository(services)
    assert_metadata(restarted.get(case["id"]), {**original, "data": raw}, saved=True)
    assert restarted.original(case["id"], original["id"])[1] == raw
    assert repository.save(case["id"], saved["revision"]) == saved
    with closing(services.db.connect()) as conn:
        assert {row["table"] for row in conn.execute("PRAGMA foreign_key_list(case_attachments)")} == {"case_sessions"}
        assert {row["table"] for row in conn.execute("PRAGMA foreign_key_list(case_attachment_parts)")} == {"case_attachments"}


def test_failed_save_rolls_back_case_metadata_and_parts_and_keeps_temporary_original(repository, services):
    first = synthetic_original("pdf", marker="SYNTHETIC_SAVED_ORIGINAL_A")
    case = attach(repository, repository.start(StartCase(text="Synthetic prior snapshot")), first)
    raw_first = first["data"]
    saved = repository.save(case["id"], case["revision"])
    before = canonical_state(services)
    second = synthetic_original("png")
    edited = repository.remove_attachment(case["id"], first["id"], saved["revision"])
    edited = attach(repository, edited, second)
    raw_second = second["data"]
    services.db.execute("CREATE TRIGGER reject_original_part BEFORE INSERT ON case_attachment_parts "
                        f"BEGIN SELECT RAISE(ABORT, '{FAILURE_SENTINEL}'); END")
    with pytest.raises(sqlite3.IntegrityError):
        repository.save(case["id"], edited["revision"])
    assert canonical_state(services) == before
    live = repository.get(case["id"])
    assert live["dirty"] and live["attachments"][0]["saved"] is False
    assert repository.original(case["id"], second["id"])[1] == raw_second
    assert CaseRepository(services).original(case["id"], first["id"])[1] == raw_first
    services.db.execute("DROP TRIGGER reject_original_part")
    repository.save(case["id"], live["revision"])
    assert CaseRepository(services).original(case["id"], second["id"])[1] == raw_second
    assert not services.db.fetch_all("SELECT * FROM case_attachment_parts WHERE attachment_id=?", (first["id"],))


def test_close_unsaved_attachment_edits_restores_saved_snapshot(repository, services):
    first = synthetic_original("pdf")
    raw = first["data"]
    case = attach(repository, repository.start(StartCase(text="Synthetic retained snapshot")), first)
    saved = repository.save(case["id"], case["revision"])
    before = canonical_state(services)
    edited = repository.remove_attachment(case["id"], first["id"], saved["revision"])
    second = synthetic_original("png", marker="SYNTHETIC_UNSAVED_ORIGINAL_B")
    edited = attach(repository, edited, second)
    assert canonical_state(services) == before
    with pytest.raises(ApiError) as removed:
        repository.original(case["id"], first["id"])
    assert removed.value.status == 404
    repository.close(case["id"], edited["revision"])
    assert repository.get(case["id"])["attachments"] == saved["attachments"]
    assert repository.original(case["id"], first["id"])[1] == raw
    with pytest.raises(ApiError) as discarded:
        repository.original(case["id"], second["id"])
    assert discarded.value.status == 404


@pytest.mark.parametrize("corruption", ["missing", "number", "bytes", "hash"])
def test_original_get_validates_complete_parts_and_hash(repository, services, corruption):
    original = synthetic_original()
    case = attach(repository, repository.start(StartCase(text="Synthetic integrity case")), original)
    repository.save(case["id"], case["revision"])
    if corruption == "missing":
        services.db.execute("DELETE FROM case_attachment_parts WHERE attachment_id=? AND part=1", (original["id"],))
    elif corruption == "number":
        services.db.execute("UPDATE case_attachment_parts SET part=99 WHERE attachment_id=? AND part=1", (original["id"],))
    else:
        raw = b"x" if corruption == "bytes" else b"x" * 49152
        services.db.execute("UPDATE case_attachment_parts SET data=? WHERE attachment_id=? AND part=0",
                            (base64.b64encode(raw).decode(), original["id"]))
    with pytest.raises(ApiError) as rejected:
        CaseRepository(services).original(case["id"], original["id"])
    assert rejected.value.code == ("case_original_integrity" if corruption == "hash" else "case_original_unavailable")


def test_original_api_is_case_bound_no_store_and_failed_save_redacts_sql_detail(tmp_path, caplog):
    app = create_app(tmp_path / "original-api")
    services, repository = app.state.services, app.state.services.registry["cases"]
    original = synthetic_original()
    raw = original["data"]
    case = attach(repository, repository.start(StartCase(text="Synthetic original API")), original)
    other = repository.start(StartCase(text="Synthetic other case"))
    path = f"/api/v1/cases/sessions/{case['id']}/attachments/{original['id']}"
    with TestClient(app) as client:
        response = client.get(path + "/original")
        assert response.status_code == 200 and response.content == raw
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["content-type"] == "application/pdf"
        wrong = client.get(f"/api/v1/cases/sessions/{other['id']}/attachments/{original['id']}/original")
        assert wrong.status_code == 404 and ORIGINAL_SENTINEL not in wrong.text
        wrong_delete = client.delete(f"/api/v1/cases/sessions/{other['id']}/attachments/{original['id']}",
                                     params={"revision": other["revision"]})
        assert wrong_delete.status_code == 404
        stale = client.delete(path, params={"revision": case["revision"] - 1})
        assert stale.status_code == 409
        assert repository.original(case["id"], original["id"])[1] == raw
        services.db.execute("CREATE TRIGGER reject_original_api BEFORE INSERT ON case_attachment_parts "
                            f"BEGIN SELECT RAISE(ABORT, '{FAILURE_SENTINEL}'); END")
        failed = client.post(f"/api/v1/cases/sessions/{case['id']}/save", json={"revision": case["revision"]})
        assert failed.status_code == 503 and failed.json()["error"]["code"] == "case_save_failed"
        assert FAILURE_SENTINEL not in failed.text and FAILURE_SENTINEL not in caplog.text
        assert ORIGINAL_SENTINEL not in failed.text and ORIGINAL_SENTINEL not in caplog.text
        assert canonical_state(services) == {table: [] for table in canonical_state(services)}
        assert client.get(path + "/original").content == raw
