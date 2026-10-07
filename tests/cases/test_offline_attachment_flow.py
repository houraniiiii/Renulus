"""Opt-in actual engine + Cases API check with isolated canonical application state."""

import asyncio
import builtins
import hashlib
import importlib.util
import io
from io import BytesIO
import json
import os
from pathlib import Path
import socket
import sys
import time
from types import ModuleType
import warnings

import pytest
from fastapi.testclient import TestClient

from renulus.contracts import ApiError, Scope
from renulus.server import create_app
from renulus.storage import AppPaths

from .conftest import assert_absent_from_profile


@pytest.fixture
def actual_offline_engine(tmp_path, monkeypatch):
    producer = os.environ.get("RENULUS_CASES_KNOWLEDGE_SOURCE")
    helper_profile = os.environ.get("RENULUS_CASES_HELPER_PROFILE")
    helper_module = os.environ.get("RENULUS_CASES_HELPER_MODULE")
    if not all((producer, helper_profile, helper_module)):
        pytest.skip("Explicit knowledge source and validated public offline helpers are required")
    import renulus
    monkeypatch.setattr(renulus, "__path__", [*renulus.__path__, str(Path(producer).resolve() / "runtime/renulus")])
    from renulus.knowledge import repository as producer_module
    if not Path(producer_module.__file__).resolve().is_relative_to(Path(producer).resolve()):
        pytest.skip("Another knowledge source is already loaded; run the configured actual-engine checks in a fresh process")
    from renulus.knowledge.repository import KnowledgeRepository
    helper_path = Path(helper_module).resolve()
    # Load the exact F0 helpers as a package so its approved startup dependency
    # uses relative imports without importing the provider/account runtime.
    package_name = "cases_test_offline_helpers"
    package = ModuleType(package_name)
    package.__path__ = [str(helper_path.parent)]
    monkeypatch.setitem(sys.modules, package_name, package)
    spec = importlib.util.spec_from_file_location(package_name + ".helpers", helper_path)
    helper = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, helper)
    spec.loader.exec_module(helper)

    class ReadOnlyAssetPaths(AppPaths):
        @property
        def helpers(self):
            # Only already provisioned public helper artifacts are read from the
            # producer profile. Canonical state/cache/history/export are isolated.
            return Path(helper_profile).resolve() / "helpers"

    app = create_app(tmp_path / "case-real-extraction")
    services = app.state.services
    services.paths = ReadOnlyAssetPaths(services.paths.root, helper_path.parents[3])
    services.registry["helpers"] = helper.HelperAssets(services.paths)
    knowledge = KnowledgeRepository(services)
    services.registry["knowledge"] = knowledge
    for name in ("history", "export", "backups"):
        (services.paths.root / name).mkdir()
    def local_only(original):
        def checked(sock, address):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original(sock, address)
            raise AssertionError("External connections are forbidden in the offline case proof")
        return checked
    monkeypatch.setattr(socket.socket, "connect", local_only(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", local_only(socket.socket.connect_ex))
    startup = getattr(services.registry["helpers"], "startup", None)
    try:
        if startup is not None:
            # The approved F0 startup runs before any synthetic input is built.
            # It owns dependency warmup and explicit cache/TEMP isolation.
            asyncio.run(startup.start())
        yield app, services, knowledge
    finally:
        if startup is not None:
            startup.close()


def synthetic_attachment(kind, text):
    if kind == "pdf":
        stream = f"BT /F1 18 Tf 50 760 Td ({text}) Tj ET".encode()
        objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>", b"<</Length " + str(len(stream)).encode() + b">>\nstream\n" + stream + b"\nendstream"]
        data = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for number, value in enumerate(objects, 1):
            offsets.append(len(data))
            data.extend(f"{number} 0 obj\n".encode() + value + b"\nendobj\n")
        xref = len(data)
        data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
        for position in offsets[1:]:
            data.extend(f"{position:010} 00000 n \n".encode())
        data.extend(f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode())
        return bytes(data), "application/pdf"
    else:
        from PIL import Image, ImageDraw, ImageFont
        image = Image.new("RGB", (1200, 350), "white")
        ImageDraw.Draw(image).text((40, 80), text, fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 38))
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue(), "image/png"


@pytest.mark.parametrize("kind", ["pdf", "png"])
def test_actual_proven_byte_extractor_through_case_preview_apply_save_delete(actual_offline_engine, kind):
    app, services, knowledge = actual_offline_engine
    if knowledge.capabilities()["temporary_extraction"] is not True:
        pytest.skip("The actual producer has not published its no-payload-write proof")
    text = "RENULUSCASEBYTESENTINEL Dialysis access learning" if kind == "pdf" else "Transplant rejection biopsy review"
    raw, media = synthetic_attachment(kind, text)
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": "Synthetic learning question"}).json()
        assert client.get("/api/v1/cases/capabilities").json()["extraction"]["supported"]
        headers = {"content-type": media, "x-renulus-filename": "synthetic." + kind,
            "x-renulus-case-options": json.dumps({"revision": 1,
                "scope": {"kind": Scope.TEMPORARY_CASE, "entity_id": case["id"]}})}
        reservation = client.post(f"/api/v1/cases/sessions/{case['id']}/attachments/prepare", headers=headers)
        assert reservation.status_code == 201 and reservation.json()["state"] == "reading"
        headers["x-renulus-preview-id"] = reservation.json()["id"]
        response = client.post(f"/api/v1/cases/sessions/{case['id']}/attachments/extract", content=raw, headers=headers)
        assert response.status_code == 202, response.text
        job = response.json()
        deadline = time.monotonic() + 180
        while job["state"] in ("reading", "processing") and time.monotonic() < deadline:
            time.sleep(0.5)
            job = client.get(f"/api/v1/cases/attachments/{job['id']}").json()
        assert job["state"] == "ready", job.get("error")
        assert text.lower() in job["text"].lower()
        assert job["ocr"]["confidence"] is None
        assert_absent_from_profile(services, text)
        applied = client.post(f"/api/v1/cases/attachments/{job['id']}/apply",
            json={"revision": 1, "text": job["text"]}).json()
        assert text.lower() in applied["text"].lower() and not applied["saved"]
        original = applied["attachments"][0]
        assert not original["saved"] and original["original_available"]
        assert original["bytes"] == len(raw) and original["sha256"] == hashlib.sha256(raw).hexdigest()
        original_path = f"/api/v1/cases/sessions/{case['id']}/attachments/{original['id']}/original"
        binary = client.get(original_path)
        assert binary.status_code == 200 and binary.content == raw
        assert binary.headers["cache-control"] == "no-store"
        assert_absent_from_profile(services, text)
        cases = services.registry["cases"]
        for target in ("explain", "generated-practice"):
            response = client.post(f"/api/v1/cases/sessions/{case['id']}/handoff", json={
                "revision": applied["revision"], "target": target, "question": "Explore the extracted learning question"})
            assert response.status_code == 201
            ticket = response.json()
            assert ticket["scope"] == {"kind": "temporary-case", "entity_id": case["id"]}
            assert text.lower() in ticket["case_text"].lower()
            context = cases.resolve_handoff(ticket["id"], target)
            assert context["scope"].kind == Scope.TEMPORARY_CASE and not context["cancel"].is_set()
            assert text.lower() in " ".join(m["content"] for m in context["messages"]).lower()
            client.delete(f"/api/v1/cases/handoffs/{ticket['id']}")
            assert context["cancel"].is_set()
            assert_absent_from_profile(services, text)
        saved = client.post(f"/api/v1/cases/sessions/{case['id']}/save", json={"revision": applied["revision"]})
        assert saved.status_code == 200
        assert saved.json()["attachments"][0]["saved"]
        closed = client.post(f"/api/v1/cases/sessions/{case['id']}/close", json={"revision": applied["revision"]})
        assert closed.status_code == 200
        reopened = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert reopened["attachments"] == saved.json()["attachments"]
        binary = client.get(original_path)
        assert binary.status_code == 200 and binary.content == raw
        assert binary.headers["cache-control"] == "no-store"
        pending = []
        for target in ("explain", "generated-practice"):
            ticket = client.post(f"/api/v1/cases/sessions/{case['id']}/handoff", json={
                "revision": applied["revision"], "target": target, "question": "Study the saved snapshot temporarily"}).json()
            assert ticket["scope"]["kind"] == "temporary-case"
            context = cases.resolve_handoff(ticket["id"], target)
            pending.append((target, ticket, context))
        assert client.delete(f"/api/v1/cases/sessions/{case['id']}").json()["deleted"]
        assert client.get(original_path).status_code == 410
        assert not services.db.fetch_all("SELECT * FROM case_attachment_parts WHERE attachment_id=?", (original["id"],))
        for target, ticket, context in pending:
            assert context["cancel"].is_set()
            with pytest.raises(ApiError):
                cases.resolve_handoff(ticket["id"], target)
    assert_absent_from_profile(services, text)


def test_actual_native_stream_after_approved_startup_has_no_filesystem_writes(actual_offline_engine, monkeypatch, caplog):
    _, services, knowledge = actual_offline_engine
    helpers = services.registry["helpers"]
    startup = getattr(helpers, "startup", None)
    if startup is None or not knowledge.capabilities()["pdf_image_import"]:
        pytest.skip("The approved F0 startup and validated native offline assets are required")
    assert startup.status()["configured"]
    assert all(group["ready"] for group in startup.status()["imports"].values())
    text = "TEMPORARYCASEPROOFSENTINEL Dialysis access learning"
    inputs = [(synthetic_attachment(kind, text)[0], "private-title." + kind) for kind in ("pdf", "png")]
    def inventory():
        return {str(path.relative_to(services.paths.root)): (path.stat().st_size, path.stat().st_mtime_ns)
                for path in services.paths.root.rglob("*") if path.is_file()}
    before = inventory()
    attempts = []
    def checked_open(original):
        def checked(file, mode="r", *args, **kwargs):
            if isinstance(mode, str) and any(value in mode for value in ("w", "a", "x", "+")):
                attempts.append(str(file))
                raise AssertionError("Temporary extraction attempted a file write")
            return original(file, mode, *args, **kwargs)
        return checked
    original_os_open = os.open
    def checked_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            attempts.append(str(path))
            raise AssertionError("Temporary extraction attempted a low-level file write")
        return original_os_open(path, flags, *args, **kwargs)
    def denied(*args, **kwargs):
        attempts.append(str(args[0]) if args else "filesystem mutation or socket")
        raise AssertionError("Temporary extraction attempted a filesystem mutation or connection")
    results = []
    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", checked_open(builtins.open))
        guard.setattr(io, "open", checked_open(io.open))
        guard.setattr(os, "open", checked_os_open)
        for name in ("mkdir", "makedirs", "remove", "unlink", "rename", "replace", "rmdir", "link", "symlink"):
            guard.setattr(os, name, denied)
        guard.setattr(socket.socket, "connect", denied)
        guard.setattr(socket.socket, "connect_ex", denied)
        with warnings.catch_warnings(record=True) as recorded:
            for data, filename in inputs:
                # Exercise the actual parser producer, without changing its
                # capability flag or invoking the gated Cases upload API.
                result = knowledge.extractor.extract_bytes(data, filename, "PRIVATE_TITLE_SENTINEL")
                assert text.lower() in " ".join(p["text"] for p in result.passages).lower()
                assert result.ocr["confidence"] is None
                results.append(result)
            assert not any(text in str(item.message) or "PRIVATE_TITLE_SENTINEL" in str(item.message) for item in recorded)
    assert not attempts, attempts
    assert inventory() == before
    assert all("private-title" not in str(result.document.get("origin", {})) for result in results)
    assert text not in caplog.text and "PRIVATE_TITLE_SENTINEL" not in caplog.text and "private-title" not in caplog.text
    assert_absent_from_profile(services, text)
