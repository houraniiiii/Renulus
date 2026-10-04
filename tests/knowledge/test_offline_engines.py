"""Real selected-engine checks with explicitly provisioned offline artifacts."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import socket
import ipaddress

import pytest

from renulus.contracts import ContextScope, Scope
from renulus.knowledge.engines import DoclingExtractor, OfflineAssets
from renulus.knowledge.models import own_text_rights
from renulus.knowledge.repository import KnowledgeRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database


@pytest.fixture
def live_repository(monkeypatch):
    profile = os.environ.get("RENULUS_KNOWLEDGE_TEST_PROFILE")
    if not profile:
        pytest.skip("Set an explicit provisioned offline profile; engine capability is not simulated")
    try:
        from renulus.runtime.helpers import HelperAssets
    except ImportError:
        helper_path = os.environ.get("RENULUS_KNOWLEDGE_HELPER_MODULE")
        if not helper_path:
            pytest.skip("F0 HelperAssets is required for the offline engine proof")
        spec = importlib.util.spec_from_file_location("renulus_test_f0_helpers", helper_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        HelperAssets = module.HelperAssets
    source_root = Path(helper_path).parents[3] if 'helper_path' in locals() else None
    paths = AppPaths.create(profile, source_root=source_root)
    db = Database(paths.database)
    schema = Path(__file__).parents[2] / "runtime/renulus/knowledge/schema.sql"
    db.apply_migration("knowledge-001", schema.read_text())
    services = Services(paths, db)
    services.registry["helpers"] = HelperAssets(paths)
    services.registry["helpers"].embedding_config()
    services.registry["helpers"].docling_config()
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    def local_only(original):
        def guarded(sock, address):
            # Windows asyncio implements its self-pipe with a loopback socket.
            # The embedded Lance runtime needs this OS primitive; external
            # connections remain forbidden throughout the engine proof.
            if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
                return original(sock, address)
            raise AssertionError("External network access is forbidden during offline engine checks")
        return guarded
    monkeypatch.setattr(socket.socket, "connect", local_only(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", local_only(original_connect_ex))
    startup = services.registry["helpers"].startup
    asyncio.run(startup.start())
    try:
        yield KnowledgeRepository(services)
    finally:
        startup.close()


def test_real_text_hybrid_roundtrip_and_shared_token_budget(live_repository):
    repository = live_repository
    result = repository.import_text("Dialysis access surveillance assesses fistula flow and stenosis.\n\nTransplant rejection assessment uses biopsy and clinical context.\n\nGlomerulonephritis can cause hematuria and proteinuria.",
        title="Synthetic cross-domain nephrology note", scope=ContextScope(kind=Scope.LIBRARY))
    assert result["status"] == "ready", result
    hits = repository.retrieve("fistula stenosis", scope=ContextScope(kind=Scope.STUDY))
    assert any(p["document_revision"] == result["revision_id"] and "fistula" in p["text"] for p in hits["passages"]), hits
    assert hits["passages"][0]["locators"][0]["page"] is None
    repository.delete_document(result["document_id"])


def _pdf_bytes(text):
    content = ("BT /F1 18 Tf 50 760 Td (" + text + ") Tj ET").encode()
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"]
    data, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for i, item in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{i} 0 obj\n".encode() + item + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend(f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(data)


@pytest.mark.parametrize("kind", ["pdf", "image"])
def test_real_docling_cpu_page_region_original_roundtrip(live_repository, tmp_path, kind):
    repository = live_repository
    if kind == "pdf":
        path = tmp_path / "synthetic-dialysis.pdf"
        path.write_bytes(_pdf_bytes("Dialysis access fistula flow review"))
    else:
        from PIL import Image, ImageDraw, ImageFont
        path = tmp_path / "synthetic-transplant.png"
        image = Image.new("RGB", (1200, 350), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 38)
        draw.text((40, 80), "Transplant rejection biopsy review", fill="black", font=font)
        image.save(path)
    result = repository.import_file(path, title="Synthetic CPU extraction", rights=own_text_rights(),
                                    scope=ContextScope(kind=Scope.LIBRARY))
    assert result["status"] == "ready", result
    citation = repository.citation(result["revision_id"], 1)
    assert citation["locators"] and all(x["bbox"] and x["page_size"] for x in citation["locators"])
    original, _ = repository.original(result["revision_id"])
    assert original.read_bytes() == path.read_bytes()
    hits = repository.retrieve("fistula" if kind == "pdf" else "transplant", scope=ContextScope(kind=Scope.STUDY))
    assert any(p["document_revision"] == result["revision_id"] for p in hits["passages"])
    repository.delete_document(result["document_id"])
