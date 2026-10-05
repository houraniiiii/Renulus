from types import SimpleNamespace

import pytest

from renulus.contracts import ApiError
from renulus.knowledge import engines
from renulus.knowledge.office import DOCLING_CORE_VERSION, DOCLING_VERSION


def capabilities(monkeypatch, *, absent=None, versions=None, tokenizer_ready=True):
    class Assets(engines.OfflineAssets):
        def validate(self, kind):
            if kind == "fastembed" and tokenizer_ready:
                return None
            raise ApiError("helper_assets_missing", "No PDF/OCR assets in this synthetic capability check", 503)
    monkeypatch.setattr(engines.importlib.util, "find_spec", lambda name: None if name == absent else object())
    selected = {"docling": DOCLING_VERSION, "docling-core": DOCLING_CORE_VERSION, **(versions or {})}
    monkeypatch.setattr(engines, "version", lambda name: selected[name])
    return Assets(SimpleNamespace(registry={})).capabilities()


def test_office_capability_does_not_need_pdf_ocr_assets_or_startup(monkeypatch):
    result = capabilities(monkeypatch)
    assert result["text_import"] is True and result["office_import"] is True
    assert result["pdf_image_import"] is False and result["temporary_extraction"] is False
    assert result["docling"]["ready"] is False and result["ocr"]["ready"] is False


@pytest.mark.parametrize("absent", ["docling", "docling_core", "fastembed", "lancedb", "pptx", "docx", "openpyxl"])
def test_office_capability_requires_its_import_packages(monkeypatch, absent):
    assert capabilities(monkeypatch, absent=absent)["office_import"] is False


@pytest.mark.parametrize("package", ["docling", "docling-core"])
def test_office_capability_requires_the_verified_pins(monkeypatch, package):
    assert capabilities(monkeypatch, versions={package: "0.0.0"})["office_import"] is False


def test_office_capability_requires_shared_embedding_tokenizer_assets(monkeypatch):
    assert capabilities(monkeypatch, tokenizer_ready=False)["office_import"] is False


def test_missing_pinned_distribution_metadata_is_not_readiness(monkeypatch):
    result = capabilities(monkeypatch)
    assert result["office_import"] is True
    def missing(name):
        raise engines.PackageNotFoundError(name)
    monkeypatch.setattr(engines, "version", missing)
    assert engines.OfflineAssets(SimpleNamespace(registry={})).capabilities()["office_import"] is False
