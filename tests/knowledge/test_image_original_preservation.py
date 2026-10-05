"""Image-original application seams; no OCR, PDF pipeline or embedding model runs.

Chunking uses real DoclingDocument/HybridChunker and the supplied local tokenizer.
The converter and derived index are controlled doubles, not native helper proof.
"""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from threading import Event
from types import ModuleType, SimpleNamespace
from zipfile import ZipFile

from docling_core.types.doc import (
    BoundingBox, DocItemLabel, DoclingDocument, ProvenanceItem, Size,
)
from PIL import Image
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge import office
from renulus.knowledge.engines import DoclingExtractor, LanceIndex
from renulus.knowledge.models import own_text_rights
from renulus.knowledge.repository import KnowledgeRepository
from renulus.knowledge import repository as repository_module
from renulus.services import Services
from renulus.storage import AppPaths, Database

STUDY = ContextScope(kind=Scope.STUDY)


def no_body_document(kind="picture"):
    document = DoclingDocument(name="Synthetic image without readable text")
    document.add_page(page_no=1, size=Size(width=16, height=16))
    if kind == "picture":
        document.add_picture(prov=ProvenanceItem(page_no=1,
            bbox=BoundingBox(l=0, t=0, r=16, b=16), charspan=(0, 0)))
    elif kind == "blank":
        document.add_text(label=DocItemLabel.PARAGRAPH, text="   ")
    return document


def image_bytes(suffix=".png"):
    output = BytesIO()
    format_name = "JPEG" if suffix.lower() in (".jpg", ".jpeg") else (
        "TIFF" if suffix.lower() in (".tif", ".tiff") else "PNG")
    Image.new("RGB", (16, 16), "white").save(output, format=format_name)
    return output.getvalue()


class SeamIndex:
    def __init__(self, path, dimensions=384):
        self.path = Path(path)
        self.rows, self.stages, self.searches = [], [], []
        self.fts_calls, self.closed = 0, False
        self.validated = None

    def stage(self, rows, *, create_fts=True):
        self.stages.append((len(rows), create_fts))
        self.rows.extend(dict(row) for row in rows)
        if create_fts:
            self.build_fts()

    def build_fts(self):
        self.fts_calls += 1

    def search(self, query, vector, revision_ids, limit):
        self.searches.append(list(revision_ids))
        return [dict(row) for row in self.rows if row["revision_id"] in revision_ids][:limit]

    def remove(self, revision_id):
        self.rows[:] = [row for row in self.rows if row["revision_id"] != revision_id]

    def validate_passages(self, identities):
        actual = {(r["passage_id"], r["revision_id"], r["document_id"]) for r in self.rows}
        assert actual == identities
        self.validated = set(identities)
        self.path.mkdir(parents=True, exist_ok=True)

    def close(self):
        self.closed = True


class SeamEmbedder:
    model_id, dimensions, max_tokens = "synthetic-384", 384, 512

    def __init__(self):
        self.calls = []
        self.on_query = None

    def embed(self, texts, *, query=False):
        self.calls.append((list(texts), query))
        if query and self.on_query:
            self.on_query()
        return [[1.0] + [0.0] * 383 for _ in texts]


@pytest.fixture
def engine(tmp_path, monkeypatch):
    tokenizer = os.environ.get("RENULUS_TEST_TOKENIZER")
    if not tokenizer or not Path(tokenizer).is_file():
        pytest.skip("Set RENULUS_TEST_TOKENIZER to the existing local tokenizer.json")
    from docling.datamodel.base_models import ConversionStatus

    class Assets:
        def validate(self, kind):
            return Path(tokenizer).parent if kind == "fastembed" else tmp_path

        def config(self, kind):
            return {}

    result = SimpleNamespace(status=ConversionStatus.SUCCESS, document=no_body_document())
    calls = []

    class Converter:
        def __init__(self, **kwargs):
            pass

        def convert(self, source, **kwargs):
            calls.append((source, kwargs))
            return result

    # Keep real data/status/options and image validation; replace the two imports
    # that could construct or import the native conversion pipeline.
    converter_module = ModuleType("docling.document_converter")
    converter_module.DocumentConverter = Converter
    converter_module.PdfFormatOption = lambda **kwargs: kwargs
    converter_module.ImageFormatOption = lambda **kwargs: kwargs
    pipeline_module = ModuleType("docling.pipeline.standard_pdf_pipeline")
    pipeline_module.StandardPdfPipeline = object
    monkeypatch.setitem(sys.modules, converter_module.__name__, converter_module)
    monkeypatch.setitem(sys.modules, pipeline_module.__name__, pipeline_module)
    extractor = DoclingExtractor(Assets())
    return SimpleNamespace(extractor=extractor, result=result, calls=calls,
                           statuses=ConversionStatus)


@pytest.fixture
def library(tmp_path, engine):
    paths = AppPaths.create(tmp_path / "p")
    db = Database(paths.database)
    schema = Path(__file__).parents[2] / "runtime/renulus/knowledge/schema.sql"
    db.apply_migration("knowledge-001", schema.read_text())
    for migration in sorted((schema.parent / "migrations").glob("*.sql")):
        db.apply_migration("knowledge-" + migration.stem, migration.read_text())
    return KnowledgeRepository(Services(paths, db), extractor=engine.extractor,
        embedder=SeamEmbedder(), index=SeamIndex(paths.indexes / "knowledge"))


def import_image(library, tmp_path, suffix=".png", **kwargs):
    selected = tmp_path / ("selected" + suffix)
    selected.write_bytes(image_bytes(suffix))
    return library.import_file(selected, rights=own_text_rights(), **kwargs)


@pytest.mark.parametrize("kind", ["empty", "picture", "blank"])
def test_real_chunker_preserves_no_body_export_only_when_explicitly_allowed(engine, kind):
    document = no_body_document(kind)
    exported = document.export_to_dict()
    with pytest.raises(ApiError) as caught:
        engine.extractor._chunk(document)
    assert caught.value.code == "empty_extraction"
    extracted = engine.extractor._chunk(document, allow_empty=True)
    assert extracted.passages == []
    assert extracted.document == exported == document.export_to_dict()
    assert extracted.ocr == {"used": None, "confidence": None}


@pytest.mark.parametrize("allow_empty", [False, True])
@pytest.mark.parametrize("label", [DocItemLabel.TITLE, DocItemLabel.SECTION_HEADER])
def test_real_heading_only_fallback_keeps_actual_text_and_export(engine, allow_empty, label):
    document = no_body_document("empty")
    document.add_text(label=label, text="Transplant rejection teaching")
    exported = document.export_to_dict()
    extracted = engine.extractor._chunk(document, allow_empty=allow_empty)
    assert [p["text"] for p in extracted.passages] == ["Transplant rejection teaching"]
    assert extracted.document == exported == document.export_to_dict()


@pytest.mark.parametrize("suffix", [".png", ".PNG", ".jpg", ".jpeg", ".tif", ".tiff"])
def test_durable_success_browses_original_and_empty_citation_then_deletes(library, engine, tmp_path, suffix):
    imported = import_image(library, tmp_path, suffix, idempotency_key="image")
    assert imported["status"] == "ready" and imported["job"]["error_code"] is None
    assert import_image(library, tmp_path, suffix, idempotency_key="image") == imported
    revision_id = imported["revision_id"]
    stored = library.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (revision_id,))
    assert json.loads(stored["extraction_json"]) == engine.result.document.export_to_dict()
    original, media_type = library.original(revision_id)
    assert media_type.startswith("image/")
    assert original.read_bytes() == (tmp_path / ("selected" + suffix)).read_bytes()
    document = library.get_document(imported["document_id"])
    assert document["active_revision"] == revision_id
    assert document["status"] == "ready" and document["revisions"][0]["passage_count"] == 0
    assert library.list_documents(status="ready")["documents"] == [document]
    citation = library.citation(revision_id)
    assert citation["locators"] == [] and citation["original_url"].endswith(revision_id + "/original")
    with pytest.raises(ApiError) as caught:
        library.citation(revision_id, page=1)
    assert caught.value.code == "page_missing"
    assert library.retrieve("image", scope=STUDY)["status"] == "no_eligible_documents"
    assert library.embedder.calls == []
    assert library.index.stages == library.index.searches == [] and library.index.fts_calls == 0
    assert library.recover() == [] and original.is_file()
    assert library.cancel_job(imported["job"]["id"])["state"] == "ready"
    assert original.is_file()  # Publication won before cancellation.
    restarted = KnowledgeRepository(library.services, extractor=engine.extractor,
        embedder=SeamEmbedder(), index=library.index)
    assert restarted.original(revision_id)[0] == original
    assert restarted.retrieve("image", scope=STUDY)["status"] == "no_eligible_documents"
    assert restarted.embedder.calls == []
    assert library.delete_document(imported["document_id"])["cleanup_pending"] is False
    assert not original.exists() and library.db.fetch_all("SELECT * FROM knowledge_passages") == []
    stored = library.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (revision_id,))
    assert stored["status"] == "deleted" and stored["extraction_json"] is None
    for operation in (library.original, library.citation):
        with pytest.raises(ApiError):
            operation(revision_id)
    library.run_job(imported["job"]["id"])
    assert library.get_document(imported["document_id"], include_deleted=True)["active_revision"] is None
    assert (tmp_path / ("selected" + suffix)).is_file()


@pytest.mark.parametrize("status", ["FAILURE", "PARTIAL_SUCCESS", "SKIPPED"])
def test_non_success_image_replacement_fails_and_preserves_previous_original(library, engine, tmp_path, status):
    initial = import_image(library, tmp_path)
    original = library.original(initial["revision_id"])[0]
    engine.result.status = getattr(engine.statuses, status)
    failed = import_image(library, tmp_path, document_id=initial["document_id"])
    assert failed["status"] == "failed" and failed["job"]["error_code"] == "extraction_failed"
    assert library.get_document(initial["document_id"])["active_revision"] == initial["revision_id"]
    assert original.is_file()
    failed_row = library.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (failed["revision_id"],))
    assert failed_row["original_path"] is None and failed_row["extraction_json"] is None
    assert library.embedder.calls == [] and library.index.fts_calls == 0


@pytest.mark.parametrize("data", [b"not an image", image_bytes()[:40]])
def test_malformed_image_cannot_reach_success_seam_or_keep_app_original(library, engine, tmp_path, data):
    selected = tmp_path / "bad.png"
    selected.write_bytes(data)
    imported = library.import_file(selected, rights=own_text_rights())
    assert imported["status"] == "failed" and imported["job"]["error_code"] == "extraction_failed"
    assert engine.calls == [] and library.embedder.calls == []
    assert not list(library.paths.library.rglob("original.*"))
    assert selected.read_bytes() == data


def test_image_without_exportable_docling_metadata_cannot_activate(library, tmp_path, monkeypatch):
    def rejected_export(self, *args, **kwargs):
        raise ValueError("Synthetic Docling export failure")

    monkeypatch.setattr(DoclingDocument, "export_to_dict", rejected_export)
    imported = import_image(library, tmp_path)
    assert imported["status"] == "failed" and imported["job"]["error_code"] == "extraction_failed"
    assert library.get_document(imported["document_id"])["active_revision"] is None
    assert not list(library.paths.library.rglob("original.*"))
    assert library.embedder.calls == [] and library.index.fts_calls == 0


@pytest.mark.parametrize("filename,data", [("empty.png", image_bytes()),
    ("empty.pdf", b"%PDF-1.7 synthetic conversion seam"), ("empty.txt", b"  "), ("empty.md", b"  ")])
def test_successful_temporary_bytes_still_require_readable_text(engine, filename, data):
    with pytest.raises(ApiError) as caught:
        engine.extractor.extract_bytes(data, filename, "Synthetic temporary input")
    assert caught.value.code == "empty_extraction"


@pytest.mark.parametrize("suffix", [".pdf", ".txt", ".md", ".pptx", ".docx", ".xlsx"])
def test_successful_empty_durable_non_image_stays_strict(library, engine, tmp_path, suffix):
    selected = tmp_path / ("empty" + suffix)
    if suffix in office.OFFICE_MEDIA:
        main, content_type = office.MAIN_PARTS[suffix]
        output = BytesIO()
        with ZipFile(output, "w") as package:
            package.writestr("[Content_Types].xml", f'<Types xmlns="{office.CONTENT_NS}"><Override PartName="/{main}" ContentType="{content_type}"/></Types>')
            package.writestr("_rels/.rels", f'<Relationships xmlns="{office.REL_NS}"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{main}"/></Relationships>')
            package.writestr(main, "<document/>")
        selected.write_bytes(output.getvalue())
        engine.extractor._office_converter = SimpleNamespace(convert=lambda *a, **k: engine.result)
    else:
        selected.write_bytes(b"%PDF-1.7 synthetic conversion seam" if suffix == ".pdf" else b"  ")
    imported = library.import_file(selected, rights=own_text_rights())
    assert imported["status"] == "failed" and imported["job"]["error_code"] == "empty_extraction"
    assert selected.is_file() and not list(library.paths.library.rglob("original.*"))
    assert library.embedder.calls == [] and library.index.fts_calls == 0


def test_text_image_remains_searchable_and_zero_passage_images_are_excluded(library, engine, tmp_path):
    empty = import_image(library, tmp_path)
    engine.result.document.add_text(label=DocItemLabel.PARAGRAPH, text="Dialysis access teaching")
    readable = import_image(library, tmp_path, ".jpg")
    assert readable["status"] == "ready"
    result = library.retrieve("access", scope=STUDY)
    assert [p["document_revision"] for p in result["passages"]] == [readable["revision_id"]]
    assert result["passages"][0]["text"] == "Dialysis access teaching"
    assert library.index.searches == [[readable["revision_id"]]]
    assert library.get_document(empty["document_id"])["revisions"][0]["passage_count"] == 0


def test_replacing_searchable_text_with_empty_image_keeps_history_and_prunes_search(library, tmp_path):
    note = library.import_text("Glomerular disease teaching")
    previous = library.original(note["revision_id"])[0]
    calls = list(library.embedder.calls)
    image = import_image(library, tmp_path, document_id=note["document_id"])
    assert image["status"] == "ready" and previous.is_file()
    assert library.get_document(note["document_id"])["active_revision"] == image["revision_id"]
    assert library.index.rows == [] and library.index.fts_calls == 1
    assert library.citation(note["revision_id"])["locators"]
    assert library.retrieve("glomerular", scope=STUDY)["status"] == "no_eligible_documents"
    assert library.embedder.calls == calls
    replacement = library.import_text("Electrolyte learning", document_id=note["document_id"])
    assert library.original(image["revision_id"])[0].is_file()
    assert library.citation(image["revision_id"])["locators"] == []
    assert library.retrieve("electrolyte", scope=STUDY)["passages"][0]["document_revision"] == replacement["revision_id"]


@pytest.mark.parametrize("operation", ["cancel", "delete", "replace"])
@pytest.mark.parametrize("phase", ["conversion", "publication"])
def test_empty_image_cannot_publish_after_cancel_delete_or_newer_revision(library, engine, tmp_path, monkeypatch, operation, phase):
    initial = import_image(library, tmp_path)
    previous = library.original(initial["revision_id"])[0]
    queued = import_image(library, tmp_path, document_id=initial["document_id"], process=False)
    entered, release = Event(), Event()
    def block():
        entered.set()
        assert release.wait(10), "Image seam was not released"

    if phase == "conversion":
        convert = engine.extractor._converter.convert

        def blocked(*args, **kwargs):
            block()
            return convert(*args, **kwargs)

        monkeypatch.setattr(engine.extractor._converter, "convert", blocked)
    else:
        original_dumps = repository_module.dumps

        def blocked_dump(value):
            if isinstance(value, dict) and value.get("schema_name") == "DoclingDocument":
                block()
            return original_dumps(value)

        monkeypatch.setattr(repository_module, "dumps", blocked_dump)

    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(library.run_job, queued["job"]["id"])
        try:
            assert entered.wait(10), "Image seam was not entered"
            if operation == "delete":
                library.delete_document(initial["document_id"])
            elif operation == "replace":
                newer = import_image(library, tmp_path, document_id=initial["document_id"], process=False)
            else:
                library.cancel_job(queued["job"]["id"])
        finally:
            release.set()
        assert running.result(timeout=10)["state"] == "cancelled"
    row = library.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (queued["revision_id"],))
    assert row["status"] == ("deleted" if operation == "delete" else "cancelled")
    assert row["original_path"] is None
    assert row["extraction_json"] is None and library.db.fetch_all("SELECT * FROM knowledge_passages") == []
    document = library.get_document(initial["document_id"], include_deleted=True)
    assert document["active_revision"] == (None if operation == "delete" else initial["revision_id"])
    assert previous.is_file() == (operation != "delete")
    if operation == "replace":
        assert library.run_job(newer["job"]["id"])["state"] == "ready"
        assert library.get_document(initial["document_id"])["active_revision"] == newer["revision_id"]
    assert library.embedder.calls == [] and library.index.fts_calls == 0


def test_retrieval_rechecks_after_last_searchable_revision_becomes_empty_image(library, tmp_path):
    note = library.import_text("Dialysis teaching")
    library.embedder.on_query = lambda: import_image(library, tmp_path, document_id=note["document_id"])
    assert library.retrieve("dialysis", scope=STUDY)["status"] == "no_eligible_documents"
    assert library.index.searches == []


@pytest.mark.parametrize("content", ["empty", "image", "mixed"])
def test_rebuild_retains_originals_and_only_indexes_canonical_passages(library, tmp_path, monkeypatch, content):
    image = import_image(library, tmp_path) if content != "empty" else None
    if content == "mixed":
        library.import_text("Transplant education")
    library.embedder.calls.clear()
    previous = library.index
    monkeypatch.setattr("renulus.knowledge.repository.LanceIndex", SeamIndex)
    rebuilt = library.rebuild_index()
    expected = 1 if content == "mixed" else 0
    assert rebuilt["status"] == "ready" and rebuilt["passages"] == expected
    assert library.index.fts_calls == expected and len(library.index.validated) == expected
    assert len(library.embedder.calls) == expected and previous.closed
    if image:
        assert library.original(image["revision_id"])[0].is_file()
        assert library.citation(image["revision_id"])["locators"] == []
    if not expected:
        assert library.retrieve("teaching", scope=STUDY)["status"] == "no_eligible_documents"
        assert library.embedder.calls == []


@pytest.mark.parametrize("create_fts", [False, True])
def test_empty_lance_stage_never_opens_index_or_builds_fts(tmp_path, monkeypatch, create_fts):
    index = LanceIndex(tmp_path / "unused-index")
    monkeypatch.setattr(index, "_open", lambda: pytest.fail("Empty stage opened LanceDB"))
    monkeypatch.setattr(index, "build_fts", lambda: pytest.fail("Empty stage built FTS"))
    index.stage([], create_fts=create_fts)
    assert not index.path.exists()
