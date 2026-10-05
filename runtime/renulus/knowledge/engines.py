"""Selected engines only, with explicit CPU assets and no first-use downloads."""
from dataclasses import dataclass, field
from datetime import timedelta
import importlib.util
from importlib.metadata import PackageNotFoundError, version
import math
from io import BytesIO
from pathlib import Path
from threading import RLock
from typing import Any

from ..contracts import ApiError

MODEL_ID = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
MAX_TOKENS = 512
CHUNK_TOKENS = 480  # Reserve space for special tokens and query/document prefixes.
MAX_BYTES = 64 * 1024 * 1024
MAX_PAGES = 300
MAX_PASSAGES = 12000
TEMP_MAX_BYTES = 10 * 1024 * 1024
TEMP_MAX_PAGES = 20
TEMP_MAX_PIXELS = 12_000_000
TEMPORARY_EXTRACTION_PROVEN = True


@dataclass
class Extracted:
    passages: list[dict]
    document: dict
    ocr: dict = field(default_factory=lambda: {"used": None, "confidence": None})
    status: str = "extracted"


class OfflineAssets:
    """Consume the F0 helper object, which validates the central hash manifest."""

    def __init__(self, services):
        self.services = services

    def config(self, kind: str) -> dict:
        helpers = self.services.registry.get("helpers")
        method = "embedding_config" if kind == "fastembed" else "docling_config"
        if helpers is None or not hasattr(helpers, method):
            raise ApiError("helper_assets_missing", "Validated offline helpers are not available yet", 503, True)
        config = getattr(helpers, method)()
        if kind == "fastembed" and (config["model_id"] != MODEL_ID or config["dimensions"] != DIMENSIONS or config["max_tokens"] != MAX_TOKENS or config["local_files_only"] is not True):
            raise ApiError("incompatible_embedding", "The shared embedding configuration requires a coordinated rebuild", 503)
        return config

    def validate(self, kind: str) -> Path:
        config = self.config(kind)
        key = {"fastembed": "model_path", "docling": "artifacts_path", "ocr": "ocr_path"}[kind]
        root = Path(config[key]).resolve()
        if not root.is_relative_to(self.services.paths.helpers.resolve()):
            raise ApiError("unsafe_helper_path", "Helper files must be app owned", 503)
        return root

    def capabilities(self) -> dict:
        result = {"model_id": MODEL_ID, "dimensions": DIMENSIONS, "max_tokens": MAX_TOKENS,
                  "temporary_extraction": False, "downloads_in_doctor_flow": False}
        for kind in ("fastembed", "docling", "ocr"):
            try:
                self.validate(kind)
                result[kind] = {"ready": True}
            except ApiError as error:
                result[kind] = {"ready": False, "code": error.code, "message": error.message}
        result["packages"] = {name: importlib.util.find_spec(name) is not None
                              for name in ("docling", "docling_core", "fastembed", "lancedb", "pptx", "docx", "openpyxl")}
        result["text_import"] = result["fastembed"]["ready"] and all(
            result["packages"][x] for x in ("docling_core", "fastembed", "lancedb"))
        from .office import DOCLING_VERSION, DOCLING_CORE_VERSION
        try:
            office_versions = version("docling") == DOCLING_VERSION and version("docling-core") == DOCLING_CORE_VERSION
        except PackageNotFoundError:
            office_versions = False
        result["office_import"] = bool(result["text_import"] and office_versions and all(
            result["packages"][name] for name in ("docling", "pptx", "docx", "openpyxl")))
        result["pdf_image_import"] = result["text_import"] and result["docling"]["ready"] and result["ocr"]["ready"] and result["packages"]["docling"]
        helpers = self.services.registry.get("helpers")
        startup = getattr(helpers, "startup", None)
        prepared = startup.status() if startup is not None else {}
        result["temporary_extraction"] = bool(TEMPORARY_EXTRACTION_PROVEN and result["pdf_image_import"]
            and prepared.get("configured") and prepared.get("imports", {}).get("docling", {}).get("ready"))
        result["temporary_limits"] = {"max_bytes": TEMP_MAX_BYTES, "max_pages": TEMP_MAX_PAGES,
                                      "image_pixels": TEMP_MAX_PIXELS, "ocr_confidence": "unavailable"}
        return result


class FastEmbedEngine:
    model_id = MODEL_ID
    dimensions = DIMENSIONS
    max_tokens = MAX_TOKENS

    def __init__(self, assets: OfflineAssets):
        self.assets = assets
        self._model = None
        self._model_lock = RLock()

    def _load(self):
        if self._model is None:
            # The loaded model belongs to this profile/process. Validate pinned
            # artifacts on construction, not again for every bounded batch.
            root = self.assets.validate("fastembed")
            config = self.assets.config("fastembed")
            try:
                from fastembed import TextEmbedding
                self._model = TextEmbedding(model_name=MODEL_ID, specific_model_path=str(root),
                    cache_dir=str(config["cache_dir"]), local_files_only=True,
                    threads=config["cpu_threads"], providers=["CPUExecutionProvider"], cuda=False)
            except ImportError:
                raise ApiError("helper_package_unavailable", "FastEmbed is not installed in this runtime", 503, True) from None
        return self._model

    def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        # Query and ingestion share one lazy model. Serialize construction and
        # complete iterator consumption without holding the repository lock.
        with self._model_lock:
            model = self._load()
            values = model.query_embed(texts) if query else model.passage_embed(texts)
            vectors = [[float(x) for x in vector] for vector in values]
        if len(vectors) != len(texts) or any(len(v) != DIMENSIONS or not all(math.isfinite(x) for x in v) for v in vectors):
            raise ApiError("invalid_embedding", "The offline helper returned incompatible vectors", 503)
        return vectors


class DoclingExtractor:
    def __init__(self, assets: OfflineAssets):
        self.assets = assets
        self._converter = None
        self._office_converter = None
        self._conversion_lock = RLock()

    def _chunk(self, document, text_offsets=None, *, office_format=None, allow_empty=False) -> Extracted:
        try:
            from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
            from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer
            from pydantic import ConfigDict
            from tokenizers import Tokenizer
        except ImportError:
            raise ApiError("helper_package_unavailable", "Docling chunking helpers are not installed", 503, True) from None
        root = self.assets.validate("fastembed")
        tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
        # Chunking must count untruncated tokens, using exactly the embedder vocabulary.
        tokenizer.no_truncation()
        tokenizer.no_padding()

        class LocalTokenizer(BaseTokenizer):
            model_config = ConfigDict(arbitrary_types_allowed=True)
            backend: Any
            budget: int = CHUNK_TOKENS

            def count_tokens(self, text: str) -> int:
                return len(self.backend.encode(text, add_special_tokens=False).ids)

            def get_max_tokens(self) -> int:
                return self.budget

            def get_tokenizer(self):
                # semchunk accepts a token-count callable. Rust Tokenizer.encode
                # returns Encoding rather than the list expected by its generic
                # encode adapter, so supply the untruncated shared counter.
                return self.count_tokens

        local = LocalTokenizer(backend=tokenizer)
        class BudgetedHybridChunker(HybridChunker):
            def segment(self, doc_chunk, available_length, doc_serializer):
                # Docling-core 2.99's table splitter uses self.max_tokens rather
                # than available_length. Reserve heading/caption overhead in its
                # maintained LineBasedTokenChunker, preserving repeated headers
                # and the original table/page metadata. No embedding truncation.
                bounded = self.model_copy(update={"tokenizer": LocalTokenizer(
                    backend=tokenizer, budget=max(1, available_length - 8))})
                return HybridChunker.segment(bounded, doc_chunk, max(1, available_length - 8), doc_serializer)

        chunker = BudgetedHybridChunker(tokenizer=local, merge_peers=True, repeat_table_header=True)
        passages = []
        for chunk in chunker.chunk(dl_doc=document):
            context = chunker.contextualize(chunk=chunk)
            if local.count_tokens(context) > CHUNK_TOKENS:
                raise ApiError("chunk_budget_exceeded", "A structured chunk exceeds the shared embedding budget", 422)
            locators = []
            for item in chunk.meta.doc_items:
                if office_format:
                    from .office import item_locators
                    locators.extend(item_locators(item, document, office_format))
                    continue
                ref = item.self_ref
                if text_offsets and ref in text_offsets:
                    locators.append({"item_ref": ref, "page": None, "char_span": text_offsets[ref]})
                for prov in item.prov:
                    page = document.pages.get(prov.page_no)
                    locators.append({"item_ref": ref, "page": prov.page_no,
                        "bbox": prov.bbox.model_dump(mode="json"),
                        "char_span": list(prov.charspan),
                        "page_size": page.size.model_dump(mode="json") if page else None})
            if chunk.text.strip():
                passages.append({"text": chunk.text, "context_text": context,
                                 "locators": locators, "headings": chunk.meta.headings or []})
            if len(passages) > MAX_PASSAGES:
                raise ApiError("document_limit", "The document contains too many passages", 413)
        if not passages:
            from docling_core.types.doc import DocItemLabel, TextItem
            # A short scanned slide can consist entirely of a title/header.
            # HybridChunker uses headings as context and emits no body chunk
            # for it. Reclassify only the chunking copy, retaining the actual
            # Docling extraction and all OCR provenance in canonical storage.
            body = document.model_copy(deep=True)
            changed = False
            for position, item in enumerate(body.texts):
                if item.text.strip() and item.label in (DocItemLabel.TITLE, DocItemLabel.SECTION_HEADER):
                    payload = {key: value for key, value in item.model_dump().items() if key in TextItem.model_fields}
                    payload["label"] = DocItemLabel.PARAGRAPH
                    body.texts[position] = TextItem.model_validate(payload)
                    changed = True
            if changed:
                fallback = self._chunk(body, text_offsets, office_format=office_format, allow_empty=allow_empty)
                return Extracted(fallback.passages, document.export_to_dict())
            if not allow_empty:
                raise ApiError("empty_extraction", "No readable document text was extracted", 422)
        return Extracted(passages, document.export_to_dict())

    def extract_text(self, text: str, title: str) -> Extracted:
        from docling_core.types.doc import DoclingDocument, DocItemLabel
        document = DoclingDocument(name=title)
        offsets = {}
        # Text enters the structured representation directly. These are original
        # character spans, never invented PDF pages/regions.
        position = 0
        for paragraph in text.split("\n\n"):
            if paragraph.strip():
                item = document.add_text(label=DocItemLabel.PARAGRAPH, text=paragraph)
                offsets[item.self_ref] = [position, position + len(paragraph)]
            position += len(paragraph) + 2
        return self._chunk(document, offsets)

    def extract_file(self, path: Path, title: str) -> Extracted:
        from .office import OFFICE_MEDIA
        if path.suffix.lower() in OFFICE_MEDIA:
            with self._conversion_lock:
                return self._extract_office(path)
        if path.suffix.lower() in (".txt", ".md"):
            try:
                return self.extract_text(path.read_text(encoding="utf-8-sig"), title)
            except UnicodeError:
                raise ApiError("invalid_text_encoding", "Use a UTF-8 text file", 422) from None
        with self._conversion_lock:
            return self._extract_document(path, path.suffix.lower(), title)

    def _extract_office(self, path: Path) -> Extracted:
        from .office import office_converter, validate_office
        try:
            with path.open("rb") as source:
                validate_office(source.read(MAX_BYTES + 1), path.suffix.lower(),
                    max_bytes=MAX_BYTES, max_pages=MAX_PAGES)
            from docling.datamodel.base_models import ConversionStatus
            if self._office_converter is None:
                self._office_converter = office_converter()
            result = self._office_converter.convert(path, max_file_size=MAX_BYTES,
                max_num_pages=MAX_PAGES, raises_on_error=False)
            if result.status != ConversionStatus.SUCCESS:
                raise ApiError("extraction_failed", "Docling could not completely extract this Office document", 422)
            extracted = self._chunk(result.document, office_format=path.suffix.lower())
            extracted.ocr["used"] = False
            return extracted
        except ImportError:
            raise ApiError("helper_package_unavailable", "Docling Office extraction is not installed", 503, True) from None
        except ApiError:
            raise
        except Exception:
            raise ApiError("extraction_failed", "Docling could not extract this Office document", 422) from None

    def extract_bytes(self, data: bytes, filename: str, title: str) -> Extracted:
        """Docling input remains a BytesIO stream; this method never creates a file."""
        suffix = Path(filename).suffix.lower()
        if len(data) > TEMP_MAX_BYTES:
            raise ApiError("document_limit", "Temporary input is limited to 10 MiB", 413)
        if suffix not in (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt", ".md"):
            raise ApiError("unsupported_file", "Choose a PDF, image or UTF-8 text input", 415)
        if suffix in (".txt", ".md"):
            try:
                result = self.extract_text(data.decode("utf-8-sig"), title)
                result.ocr["used"] = False
                return result
            except UnicodeError:
                raise ApiError("invalid_text_encoding", "Use UTF-8 text", 422) from None
        if suffix == ".pdf" and not data.lstrip().startswith(b"%PDF-"):
            raise ApiError("malformed_pdf", "The input has no PDF signature", 422)
        from docling.datamodel.base_models import DocumentStream
        source = DocumentStream(name="temporary" + suffix, stream=BytesIO(data))
        with self._conversion_lock:
            result = self._extract_document(source, suffix, title, temporary=True)
        result.ocr["used"] = True if suffix != ".pdf" else None
        return result

    def _extract_document(self, source, suffix, title, temporary=False) -> Extracted:
        artifacts = self.assets.validate("docling")
        ocr_root = self.assets.validate("ocr")
        helper_config = self.assets.config("docling")
        try:
            if suffix != ".pdf":
                from PIL import Image
                with Image.open(source.stream if temporary else source) as image:
                    frames = getattr(image, "n_frames", 1)
                    if frames > (TEMP_MAX_PAGES if temporary else MAX_PAGES):
                        raise ApiError("document_limit", "The image contains too many pages", 413)
                    pixels = 0
                    for frame in range(frames):
                        image.seek(frame)
                        pixels += image.width * image.height
                    limit = TEMP_MAX_PIXELS if temporary else 40_000_000
                    if pixels > limit:
                        raise ApiError("document_limit", "The image exceeds the extraction pixel limit", 413)
                    if frames == 1:
                        image.verify()
                if temporary:
                    source.stream.seek(0)
            from docling.datamodel.base_models import ConversionStatus, InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, OcrMode
            from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption, ImageFormatOption
            from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline
            rapidocr_params = {**helper_config.get("rapidocr_params", {}),
                "Global.model_root_dir": str(ocr_root), "Global.log_level": "error",
                "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                "EngineConfig.onnxruntime.inter_op_num_threads": 1,
                "EngineConfig.onnxruntime.use_cuda": False,
                "EngineConfig.onnxruntime.use_dml": False}
            options = PdfPipelineOptions(artifacts_path=artifacts, do_ocr=True,
                do_table_structure=True, do_picture_classification=False,
                do_picture_description=False, do_code_enrichment=False, do_formula_enrichment=False,
                generate_page_images=False, generate_picture_images=False,
                accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=2),
                enable_remote_services=False,
                ocr_options=RapidOcrOptions(backend="onnxruntime", lang=["en"],
                    det_model_path=str(ocr_root / "det.onnx"),
                    rec_model_path=str(ocr_root / "rec.onnx"),
                    cls_model_path=str(ocr_root / "cls.onnx"),
                    rapidocr_params=rapidocr_params))
            image_options = options.model_copy(deep=True)
            image_options.ocr_options.mode = OcrMode.FULL_PAGE
            if self._converter is None:
                self._converter = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
                    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options),
                        InputFormat.IMAGE: ImageFormatOption(pipeline_cls=StandardPdfPipeline, pipeline_options=image_options)})
            result = self._converter.convert(source, max_num_pages=TEMP_MAX_PAGES if temporary else MAX_PAGES,
                max_file_size=TEMP_MAX_BYTES if temporary else MAX_BYTES, raises_on_error=False)
            if result.status != ConversionStatus.SUCCESS:
                raise ApiError("extraction_failed", "Docling could not completely extract this document; it may be malformed, encrypted or over the page limit", 422)
            # A successful durable image remains a useful original even without
            # OCR text. Keep the actual Docling export; other input paths still
            # require readable passages, including temporary image bytes.
            return self._chunk(result.document, allow_empty=not temporary and
                suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff"))
        except ImportError:
            raise ApiError("helper_package_unavailable", "Docling CPU extraction is not installed", 503, True) from None
        except ApiError:
            raise
        except Exception:
            # Engine exception strings can contain source contents and local paths.
            raise ApiError("extraction_failed", "Docling could not extract this file; check its format, encryption and offline helpers", 422) from None


class LanceIndex:
    """Native embedded FTS/vector fusion. Canonical revision filters come from SQLite."""

    def __init__(self, path: Path, dimensions: int = DIMENSIONS):
        self.path = Path(path).resolve()
        self.dimensions = dimensions
        self._table = None
        self._connection = None

    def _open(self):
        if self._table is None:
            try:
                import lancedb
                import pyarrow as pa
            except ImportError:
                raise ApiError("helper_package_unavailable", "LanceDB is not installed", 503, True) from None
            connection = lancedb.connect(str(self.path))
            self._connection = connection
            schema = pa.schema([pa.field("passage_id", pa.string()),
                pa.field("revision_id", pa.string()), pa.field("document_id", pa.string()),
                pa.field("text", pa.string()), pa.field("vector", pa.list_(pa.float32(), self.dimensions))])
            self._table = connection.create_table("passages", schema=schema, exist_ok=True)
            if self._table.schema.field("vector").type.list_size != self.dimensions:
                raise ApiError("incompatible_index", "The library index requires a coordinated rebuild", 503)
        return self._table

    def stage(self, rows: list[dict], *, create_fts=True):
        if not rows:
            return
        table = self._open()
        table.add(rows)
        if create_fts:
            self.build_fts()

    def build_fts(self):
        from lancedb.index import FTS
        table = self._open()
        table.create_index("text", config=FTS(with_position=True), replace=True)

    def validate_passages(self, identities: set[tuple[str, str, str]]):
        table = self._open()
        if table.count_rows() != len(identities):
            raise ApiError("index_validation_failed", "The rebuilt library index has an unexpected passage count", 503, True)
        rows = table.search().select(["passage_id", "revision_id", "document_id"]).limit(len(identities) + 1).to_list()
        actual = {(row["passage_id"], row["revision_id"], row["document_id"]) for row in rows}
        if actual != identities:
            raise ApiError("index_validation_failed", "The rebuilt library index does not match its canonical passages", 503, True)

    def close(self):
        # The pinned synchronous SDK wraps the public AsyncTable/Connection
        # lifecycle. Their close methods are synchronous and release Rust handles.
        table, connection = self._table, self._connection
        self._table = self._connection = None
        try:
            if table is not None:
                table._table.close()
        finally:
            if connection is not None:
                connection._conn.close()

    def search(self, query: str, vector: list[float], revision_ids: list[str], limit: int) -> list[dict]:
        if not revision_ids:
            return []
        from lancedb.rerankers import RRFReranker
        # IDs are canonical app IDs; quoting still covers imported/restored profiles.
        allowed = ",".join("'" + x.replace("'", "''") + "'" for x in revision_ids)
        table = self._open()
        return (table.search(query_type="hybrid").vector(vector).text(query)
                .where(f"revision_id IN ({allowed})", prefilter=True)
                .rerank(RRFReranker()).limit(limit).to_list())

    def remove(self, revision_id: str):
        if self._table is None and not self.path.exists():
            return
        table = self._open()
        table.delete("revision_id = '" + revision_id.replace("'", "''") + "'")
        # All access is serialised by the repository; no other process may own
        # this isolated profile. Delete old data/FTS versions, not only live rows.
        table.optimize(cleanup_older_than=timedelta(seconds=0), delete_unverified=True)
