"""Narrow adapters to the selected engines; no Services/Database construction.

Only immutable launch paths reach HelperAssets. Its existing manifest validator
anchors the assets to packaging/runtime/helper-assets.json before loading. The
existing OfflineAssets adapter accepts this minimal registry/paths container.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import importlib
from importlib.metadata import version
import os
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from threading import RLock

from renulus.worker_contracts import HelperPaths


@dataclass(frozen=True)
class Paths:
    helpers: Path
    cache: Path
    source_root: Path


class SelectedEngines:
    def __init__(self, config: HelperPaths | None):
        self.config = config
        self._embedding = None
        self._extractor = None
        self._assets = None
        self._load_lock = RLock()

    def _load(self):
        with self._load_lock:
            self._load_locked()

    def _load_locked(self):
        if self._assets is not None:
            return
        from renulus.contracts import ApiError
        if self.config is None:
            raise ApiError("helper_assets_missing", "Offline helper configuration is absent", 503)
        paths = Paths(Path(self.config.helpers_root), Path(self.config.cache_root),
                      Path(self.config.source_root))
        # Some selected dependencies evaluate Path.home() at import even with
        # explicit model paths. The dedicated worker has an owned empty native
        # home/cache; it never falls back to the doctor's global profile.
        native = paths.cache / "native-home"
        for directory in (native, native / "roaming", native / "local", native / "cache"):
            directory.mkdir(parents=True, exist_ok=True)
        os.environ.update(USERPROFILE=str(native), APPDATA=str(native / "roaming"),
                          LOCALAPPDATA=str(native / "local"), XDG_CACHE_HOME=str(native / "cache"))
        from renulus.runtime.helpers import HelperAssets
        from renulus.knowledge.engines import OfflineAssets, DoclingExtractor, FastEmbedEngine
        # No profile, repositories, canonical DB, network clients or service registry.
        helper = HelperAssets(paths)
        helper.startup.configure()  # Owned import/cache roots before third-party imports.
        assets = OfflineAssets(SimpleNamespace(paths=paths,
                            registry=MappingProxyType({"helpers": helper})))
        self._embedding = FastEmbedEngine(assets)
        self._extractor = DoclingExtractor(assets)
        self._assets = assets

    def prepare(self):
        """Cold native imports on the owning main thread, before input arrives.

        In the pinned Windows CPython 3.14 runtime, first importing numpy from
        a task while the main thread blocks reading the inherited pipe can
        stall native initialisation. Warm the existing startup import lists
        here; this creates no model/converter and sees no document payload.
        """
        if self.config is None:
            return
        self._load()
        from renulus.runtime.startup import EMBEDDING_IMPORTS, DOCUMENT_IMPORTS
        for name in (*EMBEDDING_IMPORTS, *DOCUMENT_IMPORTS):
            importlib.import_module(name)
        # Lance/PyArrow and Mem0/Qdrant also import native modules. Warm their
        # selected local implementations before the main pipe reader blocks.
        importlib.import_module("lancedb")
        from renulus.memory.engine import bootstrap
        bootstrap(SimpleNamespace(paths=SimpleNamespace(owned=lambda relative:
            Path(self.config.cache_root) / "memory-bootstrap")))
        importlib.import_module("renulus.memory.providers")

    def embed(self, texts, *, query):
        self._load()
        self._versions({"fastembed":"0.8.1"})
        return {"tag": "embeddings", "model_id": self._embedding.model_id,
                "dimensions": self._embedding.dimensions,
                "vectors": self._embedding.embed(texts, query=query)}

    def extract(self, body, *, format, title, retention):
        self._load()
        self._versions({"docling":"2.133.0", "docling-core":"2.99.0"})
        from renulus.knowledge.engines import MAX_BYTES, TEMP_MAX_BYTES
        if len(body) > (TEMP_MAX_BYTES if retention == "temporary" else MAX_BYTES):
            from renulus.contracts import ApiError
            raise ApiError("document_limit", "Input exceeds extraction bounds", 413)
        if format in ("txt", "md"):
            extracted = self._extractor.extract_text(body.decode("utf-8-sig"), title)
        elif format in ("csv", "html", "xml"):
            from renulus.knowledge.reader_extraction import extract_markup
            extracted = extract_markup(self._extractor, body, '.' + format, title)
        elif format in ("docx", "xlsx", "pptx"):
            from io import BytesIO
            from renulus.knowledge.office import office_converter, validate_office
            from docling.datamodel.base_models import DocumentStream, ConversionStatus
            validate_office(body, '.' + format, max_bytes=MAX_BYTES, max_pages=300)
            with self._extractor._conversion_lock:
                if self._extractor._office_converter is None:
                    self._extractor._office_converter = office_converter()
                converted = self._extractor._office_converter.convert(
                    DocumentStream(name='input.' + format, stream=BytesIO(body)),
                    max_file_size=MAX_BYTES, max_num_pages=300, raises_on_error=False)
                if converted.status != ConversionStatus.SUCCESS:
                    raise ValueError('incomplete Office extraction')
                extracted = self._extractor._chunk(converted.document, office_format='.' + format)
                extracted.ocr['used'] = False
        elif retention == "temporary":
            extracted = self._extractor.extract_bytes(body, "input." + format, title)
        else:
            # Reuse the saved Docling converter/limits with a RAM DocumentStream;
            # the engine's public byte helper deliberately uses temporary limits.
            from io import BytesIO
            from docling.datamodel.base_models import DocumentStream
            if format == "pdf" and not body.lstrip().startswith(b"%PDF-"):
                raise ValueError("invalid PDF")
            # _extract_document's saved image path requires a native path. Keep
            # images on the existing fully volatile byte path and its limits.
            if format != "pdf":
                extracted = self._extractor.extract_bytes(body, "input." + format, title)
            else:
                source = DocumentStream(name="input.pdf", stream=BytesIO(body))
                with self._extractor._conversion_lock:
                    extracted = self._extractor._extract_document(source, ".pdf", title)
        return {"tag": "document", **asdict(extracted)}

    def chunk(self, body):
        self._load()
        self._versions({"docling-core":"2.99.0"})
        from docling_core.types.doc import DoclingDocument
        value = json.loads(body)
        if not isinstance(value, dict) or value.get("tag") != "document":
            raise ValueError("not a staged document")
        document = DoclingDocument.model_validate(value["document"])
        offsets = {loc["item_ref"]: loc["char_span"] for p in value.get("passages", [])
                   for loc in p.get("locators", [])
                   if loc.get("page") is None and loc.get("char_span") and loc.get("item_ref")}
        return {"tag": "document", **asdict(self._extractor._chunk(document, offsets))}

    @staticmethod
    def _versions(expected):
        from renulus.contracts import ApiError
        if any(version(name) != pinned for name, pinned in expected.items()):
            raise ApiError("helper_package_incompatible", "Selected helper version is unavailable", 503)
