"""Synthetic SDKs and real helper hash validation; no model/native workload."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys
from threading import Event, Lock
from types import ModuleType, SimpleNamespace

from pydantic import BaseModel
import pytest

from renulus.contracts import ApiError
from renulus.knowledge.engines import (
    DoclingExtractor, OfflineAssets, TEMP_MAX_BYTES, TEMP_MAX_PAGES,
)
from renulus.runtime.helpers import HelperAssets
from renulus.services import Services
from renulus.storage import AppPaths, Database


@pytest.fixture(autouse=True)
def no_native_workload():
    before = set(sys.modules)
    yield
    roots = ("docling", "docling_core", "fastembed", "lancedb", "onnxruntime", "torch")
    # SDK doubles are removed by monkeypatch before this fixture tears down.
    assert not any(name == root or name.startswith(root + ".")
                   for name in set(sys.modules) - before for root in roots)


@pytest.fixture
def sdk(monkeypatch):
    state = SimpleNamespace(tokenizer_loads=0, converters=[], entered=Event(), release=Event(),
        block=False, active=0, peak=0, lock=Lock(), fail_tokenizer=False,
        semantic=False, table=False, table_calls=[])

    def module(name, **members):
        value = ModuleType(name)
        value.__dict__.update(members)
        monkeypatch.setitem(sys.modules, name, value)

    class Document:
        pages = {}

        def export_to_dict(self):
            return {"synthetic": True}

    class Options(SimpleNamespace):
        def model_copy(self, **kwargs):
            return copy.deepcopy(self)

    class Converter:
        def __init__(self, **kwargs):
            self.options, self.calls = kwargs, []
            state.converters.append(self)

        def convert(self, source, **kwargs):
            with state.lock:
                state.active += 1
                state.peak = max(state.peak, state.active)
            try:
                self.calls.append(kwargs)
                if state.block:
                    state.entered.set()
                    assert state.release.wait(10), "Synthetic converter not released"
                return SimpleNamespace(status="success", document=Document())
            finally:
                with state.lock:
                    state.active -= 1

    class Tokenizer:
        def __init__(self):
            self.truncation_disabled = self.padding_disabled = False

        @classmethod
        def from_file(cls, path):
            state.tokenizer_loads += 1
            if state.fail_tokenizer:
                raise ValueError("Synthetic tokenizer failure")
            assert Path(path).is_file()
            return cls()

        def no_truncation(self):
            self.truncation_disabled = True

        def no_padding(self):
            self.padding_disabled = True

        def encode(self, text, **kwargs):
            assert self.truncation_disabled and self.padding_disabled
            return SimpleNamespace(ids=text.split())

    class Chunker:
        def __init__(self, **kwargs):
            self.tokenizer = kwargs["tokenizer"]
            self.repeat_table_header = kwargs.get("repeat_table_header", True)

        def model_copy(self, update):
            return type(self)(tokenizer=update["tokenizer"], repeat_table_header=self.repeat_table_header)

        def segment(self, chunk, available_length, serializer):
            if state.table:
                state.table_calls.append((available_length, self.tokenizer.get_max_tokens()))
                return ["Synthetic table header units and body"]
            import semchunk
            return semchunk.chunkerify(self.tokenizer.get_tokenizer(),
                chunk_size=available_length)(chunk.text)

        def chunk(self, **kwargs):
            items = [TableItem(self_ref="#/tables/0", prov=[])] if state.table else []
            meta = SimpleNamespace(doc_items=items, headings=[])
            chunk = SimpleNamespace(text="SYNTHETIC_TEMPORARY_SENTINEL renal teaching " * 60, meta=meta)
            if state.semantic or state.table:
                serializer = Serializer() if state.table else SimpleNamespace()
                for text in self.segment(chunk, 32, serializer):
                    yield SimpleNamespace(text=text, meta=meta)
            else:
                yield SimpleNamespace(text="Synthetic dialysis transplant glomerular teaching", meta=meta)

        def contextualize(self, chunk):
            return chunk.text

    class Serializer:
        pass

    class TableItem(SimpleNamespace):
        pass

    module("docling.datamodel.base_models", ConversionStatus=SimpleNamespace(SUCCESS="success"),
        InputFormat=SimpleNamespace(PDF="pdf", IMAGE="image"), DocumentStream=Options)
    module("docling.datamodel.pipeline_options", PdfPipelineOptions=Options, RapidOcrOptions=Options,
        OcrMode=SimpleNamespace(FULL_PAGE="full-page"))
    module("docling.datamodel.accelerator_options", AcceleratorDevice=SimpleNamespace(CPU="cpu"),
        AcceleratorOptions=Options)
    module("docling.document_converter", DocumentConverter=Converter, PdfFormatOption=Options,
        ImageFormatOption=Options)
    module("docling.pipeline.standard_pdf_pipeline", StandardPdfPipeline=object)
    module("docling_core.transforms.chunker.hybrid_chunker", HybridChunker=Chunker)
    module("docling_core.transforms.chunker.hierarchical_chunker", ChunkingDocSerializer=Serializer)
    module("docling_core.transforms.chunker.tokenizer.base", BaseTokenizer=BaseModel)
    module("docling_core.types.doc", TableItem=TableItem)
    module("tokenizers", Tokenizer=Tokenizer)
    return state


@pytest.fixture
def assets(tmp_path):
    paths = AppPaths.create(tmp_path / "synthetic")
    groups = {
        "embedding": ["fastembed/bge-small-en-v1.5/" + name for name in (
            "model_optimized.onnx", "tokenizer.json", "config.json",
            "tokenizer_config.json", "special_tokens_map.json")],
        "docling": ["docling/docling-project--docling-layout-heron/" + name
            for name in ("config.json", "model.safetensors", "preprocessor_config.json")] +
            ["docling/docling-project--docling-models/model_artifacts/tableformer/accurate/" + name
             for name in ("tableformer_accurate.safetensors", "tm_config.json")],
        "ocr": ["ocr/" + name for name in ("det.onnx", "rec.onnx", "cls.onnx")],
    }
    manifest = {"version": 1, "groups": {}}
    for group, files in groups.items():
        records = []
        for relative in files:
            payload = ("SYNTHETIC_HELPER " + relative).encode()
            file = paths.helpers / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(payload)
            records.append({"path": relative, "size": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest()})
        manifest["groups"][group] = {"source_url": "https://example.invalid/synthetic",
            "revision": "synthetic", "files": records}
    manifest["groups"]["embedding"]["model_id"] = "BAAI/bge-small-en-v1.5"
    (paths.helpers / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    class CountingHelpers(HelperAssets):
        def __init__(self):
            super().__init__(paths, expected_manifest=manifest)
            self.validations = Counter()

        def _validate(self, group):
            self.validations[group] += 1
            return super()._validate(group)

    services = Services(paths, Database(paths.database))
    helpers = CountingHelpers()
    services.registry["helpers"] = helpers
    source = paths.cache / "synthetic.pdf"
    source.write_bytes(b"%PDF-SYNTHETIC_ONLY")
    return OfflineAssets(services), helpers, source


def test_twenty_nine_jobs_reuse_validated_converter_and_tokenizer(assets, sdk, record_property):
    assets, helpers, source = assets
    extractor = DoclingExtractor(assets)
    for _ in range(29):
        result = extractor.extract_file(source, "Synthetic renal teaching")
        assert len(result.passages) == 1
    record_property("validation_calls", dict(helpers.validations))
    record_property("tokenizer_loads", sdk.tokenizer_loads)
    assert helpers.validations == {"docling": 3, "ocr": 3, "embedding": 1}
    assert sdk.tokenizer_loads == len(sdk.converters) == 1
    assert len(sdk.converters[0].calls) == 29
    pdf = sdk.converters[0].options["format_options"]["pdf"].pipeline_options
    image = sdk.converters[0].options["format_options"]["image"].pipeline_options
    assert pdf.queue_max_size == image.queue_max_size == 8
    assert pdf.do_ocr and pdf.do_table_structure and not pdf.enable_remote_services
    assert not pdf.generate_page_images and not pdf.generate_picture_images
    assert image.ocr_options.mode == "full-page"


def test_fresh_extractor_revalidates_and_rejects_same_size_tampering(assets, sdk):
    assets, helpers, source = assets
    DoclingExtractor(assets).extract_file(source, "Synthetic initial")
    artifact = assets.services.paths.helpers / "docling/docling-project--docling-layout-heron/model.safetensors"
    payload = artifact.read_bytes()
    artifact.write_bytes(b"X" * len(payload))
    fresh = DoclingExtractor(assets)
    with pytest.raises(ApiError, match="failed validation"):
        fresh.extract_file(source, "Synthetic fresh")
    assert fresh._converter is None and len(sdk.converters) == 1
    artifact.write_bytes(payload)
    assert fresh.extract_file(source, "Synthetic repaired").passages
    assert len(sdk.converters) == 2 and sdk.tokenizer_loads == 2


def test_failed_tokenizer_load_does_not_cache_an_unusable_tokenizer(assets, sdk):
    assets, helpers, source = assets
    extractor = DoclingExtractor(assets)
    sdk.fail_tokenizer = True
    with pytest.raises(ApiError):
        extractor.extract_file(source, "Synthetic failure")
    assert extractor._tokenizer is None
    sdk.fail_tokenizer = False
    assert extractor.extract_file(source, "Synthetic retry").passages
    assert sdk.tokenizer_loads == 2 and len(sdk.converters) == 1


def test_semantic_splitting_does_not_accumulate_global_text_caches(assets, sdk, record_property):
    import semchunk
    memoized = importlib.import_module("semchunk.semchunk")._memoized_token_counters
    original = set(memoized)
    foreign = lambda text: len(text.split())
    try:
        semchunk.chunkerify(foreign, chunk_size=8)("Synthetic unrelated split preserved")
        before = set(memoized)
        assets, helpers, source = assets
        extractor = DoclingExtractor(assets)
        sdk.semantic = True
        for _ in range(29):
            output = extractor.extract_file(source, "Synthetic semantic split")
            assert len(output.passages) > 1
            assert all(0 < len(item["context_text"].split()) <= 24 for item in output.passages)
            assert [word for item in output.passages for word in item["text"].split()] == (
                "SYNTHETIC_TEMPORARY_SENTINEL renal teaching " * 60).split()
        record_property("new_semchunk_global_counters", len(set(memoized) - before))
        assert set(memoized) == before
        assert foreign in memoized and memoized[foreign].cache_info().currsize > 0
        assert sdk.tokenizer_loads == 1
    finally:
        # Only this test process's newly created synthetic counters are removed.
        for counter in set(memoized) - original:
            memoized.pop(counter).cache_clear()


def test_table_segmentation_keeps_the_upstream_splitter_and_reserved_budget(assets, sdk):
    assets, helpers, source = assets
    sdk.table = True
    output = DoclingExtractor(assets).extract_file(source, "Synthetic table")
    assert sdk.table_calls == [(24, 24)]
    assert output.passages[0]["text"] == "Synthetic table header units and body"


def test_temporary_and_durable_conversion_remain_serial_with_the_same_limits(assets, sdk):
    assets, helpers, source = assets
    extractor = DoclingExtractor(assets)
    sdk.block = True
    with ThreadPoolExecutor(max_workers=2) as pool:
        durable = pool.submit(extractor.extract_file, source, "Synthetic durable")
        try:
            assert sdk.entered.wait(10)
            temporary = pool.submit(extractor.extract_bytes, b"%PDF-SYNTHETIC",
                "synthetic.pdf", "Synthetic temporary")
            sdk.release.set()
            assert durable.result(timeout=10).passages
            assert temporary.result(timeout=10).passages
        finally:
            sdk.release.set()
    assert sdk.peak == len(sdk.converters) == 1
    assert sdk.converters[0].calls[1]["max_num_pages"] == TEMP_MAX_PAGES
    assert sdk.converters[0].calls[1]["max_file_size"] == TEMP_MAX_BYTES
    assert helpers.validations == {"docling": 3, "ocr": 3, "embedding": 1}
