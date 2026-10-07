"""Opt-in selected text engines; public assets are shared read-only.

No installed profile, Docling PDF/OCR models, downloads or providers are used.
Set RENULUS_RESPONSIVENESS_HELPERS to an already provisioned helper directory.
"""
import builtins
from concurrent.futures import ThreadPoolExecutor
import io
import os
from pathlib import Path
import socket
from threading import Event

import pytest

from renulus.contracts import ContextScope, Scope
from renulus.knowledge.repository import KnowledgeRepository
from renulus.runtime.helpers import HelperAssets
from renulus.services import Services
from renulus.storage import AppPaths, Database


@pytest.fixture
def selected_text_repository(tmp_path, monkeypatch):
    configured = os.environ.get("RENULUS_RESPONSIVENESS_HELPERS")
    if not configured:
        pytest.skip("Set RENULUS_RESPONSIVENESS_HELPERS to already validated public assets")
    helper_root = Path(configured).resolve()
    assert (helper_root / "manifest.json").is_file()

    class ReadOnlyHelpers(AppPaths):
        @property
        def helpers(self):
            return helper_root

    paths = ReadOnlyHelpers.create(tmp_path / "synthetic-profile")
    db = Database(paths.database)
    schema = paths.source_root / "runtime/renulus/knowledge/schema.sql"
    db.apply_migration("knowledge-001", schema.read_text())
    for migration in sorted((schema.parent / "migrations").glob("*.sql")):
        db.apply_migration("knowledge-" + migration.stem, migration.read_text())
    services = Services(paths, db)
    helpers = services.registry["helpers"] = HelperAssets(paths)
    # Configure isolation/offline settings without warming the PDF/OCR stack.
    helpers.startup.configure()

    def no_helper_write(path, writing):
        if (writing and isinstance(path, (str, bytes, os.PathLike))
                and Path(os.fsdecode(path)).resolve().is_relative_to(helper_root)):
            raise AssertionError("Public helper artifacts are read-only")

    def guarded_open(operation):
        def open_file(file, mode="r", *args, **kwargs):
            no_helper_write(file, any(flag in mode for flag in "wax+"))
            return operation(file, mode, *args, **kwargs)
        return open_file

    original_os_open = os.open
    def open_descriptor(path, flags, *args, **kwargs):
        no_helper_write(path, bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        return original_os_open(path, flags, *args, **kwargs)

    def guarded_connect(operation):
        def connect(sock, address):
            if not isinstance(address, tuple) or address[0] not in ("localhost", "127.0.0.1", "::1"):
                raise AssertionError("External network is forbidden")
            return operation(sock, address)
        return connect

    monkeypatch.setattr(builtins, "open", guarded_open(builtins.open))
    monkeypatch.setattr(io, "open", guarded_open(io.open))
    monkeypatch.setattr(os, "open", open_descriptor)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect(socket.socket.connect_ex))
    repository = KnowledgeRepository(services)
    try:
        yield repository
    finally:
        repository.index.close()
        helpers.startup.close()


def test_selected_text_engines_keep_metadata_available_during_query(selected_text_repository):
    repository = selected_text_repository
    initial = repository.import_text(
        "Dialysis adequacy review includes urea clearance and vascular access.\n\n"
        "Transplant rejection assessment uses biopsy and clinical context.\n\n"
        "Glomerulonephritis can cause hematuria and proteinuria.",
        title="Synthetic nephrology study")
    assert initial["status"] == "ready", initial
    # Queued inputs are deliberately synthetic and use this isolated profile.
    queued = [repository.import_text("Synthetic queued kidney note",
              title=f"Synthetic queue {number}", process=False) for number in range(100)]
    selected = repository.embedder
    started, release = Event(), Event()

    class BlockedQuery:
        def embed(self, texts, *, query=False):
            assert query
            started.set()
            assert release.wait(10), "Query barrier was not released"
            return selected.embed(texts, query=True)

    repository.embedder = BlockedQuery()
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            query = pool.submit(repository.retrieve, "dialysis adequacy",
                                scope=ContextScope(kind=Scope.STUDY))
            assert started.wait(10)
            try:
                page = pool.submit(repository.list_documents, limit=100).result(timeout=5)
                assert page["total"] == 101 and len(page["documents"]) == 100
                assert page["counts"] == {"queued": 100, "ready": 1}
                assert repository.get_document(initial["document_id"])["active_revision"] == initial["revision_id"]
                assert repository.get_job(queued[0]["job"]["id"])["state"] == "queued"
            finally:
                release.set()
            hits = query.result(timeout=30)
        assert any(hit["document_revision"] == initial["revision_id"]
                   and "Dialysis" in hit["text"] for hit in hits["passages"]), hits
        assert selected._model.__class__.__module__.startswith("fastembed")
        assert repository.index._table.__class__.__module__.startswith("lancedb")
        assert repository.extractor._converter is None  # No PDF/OCR model instance.
    finally:
        release.set()
        repository.embedder = selected
