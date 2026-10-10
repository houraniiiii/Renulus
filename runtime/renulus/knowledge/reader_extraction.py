# SPDX-License-Identifier: MIT
"""Missing format adapters feed the existing Docling HybridChunker, once."""
from .reader_models import ReaderRequest
from .reader_text import csv_rows, decode_text, text_payload
from ..contracts import ApiError


def extract_markup(extractor, data, suffix, title):
    from docling_core.types.doc import DoclingDocument, DocItemLabel
    document = DoclingDocument(name=title)
    offsets, source_locations = {}, {}

    def add(text, location):
        if not text.strip():
            return
        if len(source_locations) >= 12000:
            raise ApiError("document_limit", "The extraction contains too many source items", 413)
        item = document.add_text(label=DocItemLabel.PARAGRAPH, text=text)
        offsets[item.self_ref] = [0, len(text)]
        source_locations[item.self_ref] = location

    if suffix == ".csv":
        for number, cells in csv_rows(decode_text(data)):
            if cells:
                add("\t".join(cells), {"kind": "table", "format": "csv", "first_row": number,
                    "last_row": number, "first_column": 1, "last_column": len(cells)})
    else:
        request = ReaderRequest(reference={"target": {"type": "library_revision", "id": "extraction_input"}})
        payload = text_payload(data, suffix, request)
        for item in payload.blocks:
            if item.locator:
                add(item.text, item.locator.model_dump(mode="json"))
    result = extractor._chunk(document, offsets)
    for passage in result.passages:
        for locator in passage["locators"]:
            source = source_locations.get(locator["item_ref"])
            if source:
                locator["content_locator"] = source
                if source["kind"] == "text":
                    locator["item_ref"] = source["item_ref"]
    result.ocr["used"] = False
    return result
