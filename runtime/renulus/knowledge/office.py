"""Bounded, inert OOXML admission and Docling's model-free Office pipeline."""
from io import BytesIO
from pathlib import PurePosixPath
import re
import stat
import struct
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from ..contracts import ApiError

DOCLING_VERSION = "2.133.0"
DOCLING_CORE_VERSION = "2.99.0"
OFFICE_MEDIA = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
MAIN_PARTS = {
    ".pptx": ("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
    ".docx": ("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
    ".xlsx": ("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
}
MAX_ENTRIES = 4096
MAX_ENTRY_BYTES = 32 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_EXPANSION_RATIO = 200
MAX_SHEET_AREA = 1_000_000
CONTENT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _malformed():
    return ApiError("malformed_office", "The selected file is not a complete, valid OOXML document", 422)


def _limit():
    return ApiError("office_container_limit", "The Office container exceeds its entry, expansion or worksheet limits", 413)


def _xml(data):
    # Also detect declarations in UTF-16/32 before the parser can expand entities.
    declarations = data.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in declarations or b"<!ENTITY" in declarations:
        raise ApiError("unsafe_office", "Office XML entity declarations are not supported", 422)
    return ET.fromstring(data)


def _sheet_area(root):
    # A tiny sparse sheet can otherwise request a huge dense rectangle in Docling.
    max_row = max_col = 0
    def coordinate(value):
        match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", value)
        if not match:
            raise _malformed()
        col = 0
        for letter in match[1]:
            col = col * 26 + ord(letter) - ord("A") + 1
        return col, int(match[2])
    for cell in root.iter():
        tag = cell.tag.rsplit("}", 1)[-1]
        if tag == "c":
            positions = [cell.get("r", "")]
        elif tag in ("mergeCell", "dimension"):
            # openpyxl materializes merged cells during load, before Docling.
            positions = cell.get("ref", "").split(":")
        else:
            continue
        for position in positions:
            col, row = coordinate(position)
            max_col, max_row = max(max_col, col), max(max_row, row)
    if max_col * max_row > MAX_SHEET_AREA:
        raise _limit()


def validate_office(data: bytes, suffix: str, *, max_bytes: int, max_pages: int):
    """Validate before storage/conversion; never extract a ZIP entry to disk."""
    if len(data) > max_bytes:
        raise ApiError("document_limit", "The maximum file size is 64 MiB", 413)
    if data.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise ApiError("office_encrypted", "Encrypted or legacy Office containers are unsupported; save an unencrypted OOXML file", 422)
    # Bound the central directory before ZipFile allocates one object per member.
    end = data.rfind(b"PK\x05\x06", max(0, len(data) - 65557))
    if end < 0 or len(data) - end < 22 or not data.startswith(b"PK\x03\x04"):
        raise _malformed()
    _, disk, directory_disk, disk_count, count, size, offset, comment = struct.unpack_from("<4s4H2LH", data, end)
    if count > MAX_ENTRIES or count == 65535 or size == 0xffffffff or offset == 0xffffffff:
        raise _limit()  # ZIP64 is deliberately outside this bounded scope.
    if disk or directory_disk or disk_count != count or offset + size != end or end + 22 + comment != len(data):
        raise _malformed()
    position, observed = offset, 0
    while position < end:
        # Do not trust EOCD's count: ZipFile scans until the directory ends.
        if position + 46 > end or data[position:position + 4] != b"PK\x01\x02":
            raise _malformed()
        observed += 1
        if observed > count or observed > MAX_ENTRIES:
            raise _malformed()
        name_size, extra_size, comment_size = struct.unpack_from("<3H", data, position + 28)
        position += 46 + name_size + extra_size + comment_size
    if position != end or observed != count:
        raise _malformed()
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) != count or not entries:
                raise _malformed()
            names, canonical_names, total = set(), set(), 0
            for entry in entries:
                name = entry.filename
                path = PurePosixPath(name)
                if (entry.orig_filename != name or name.casefold() in canonical_names or not name or
                        name.startswith("/") or "\\" in name or ":" in name or
                        any(part in (".", "..", "") for part in name.rstrip("/").split("/")) or
                        stat.S_ISLNK(entry.external_attr >> 16)):
                    raise _malformed()
                names.add(name)
                canonical_names.add(name.casefold())
                if entry.flag_bits & (1 | 64):
                    raise ApiError("office_encrypted", "Encrypted Office ZIP entries are not supported", 422)
                if entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED):
                    raise _malformed()
                if entry.extract_version >= 45:
                    raise _limit()
                total += entry.file_size
                if (entry.file_size > MAX_ENTRY_BYTES or total > MAX_EXPANDED_BYTES or
                        entry.file_size > max(1, entry.compress_size) * MAX_EXPANSION_RATIO):
                    raise _limit()
                lower = name.lower()
                if ("vbaproject" in lower or "/activex/" in lower or
                        "/embeddings/" in lower or path.suffix.lower() in (".emf", ".wmf")):
                    raise ApiError("unsafe_office", "Macros, active objects, embedded packages and vector image rendering are unsupported", 422)
            main, content_type = MAIN_PARTS[suffix]
            if not {"[Content_Types].xml", "_rels/.rels", main}.issubset(names):
                raise _malformed()
            content_types = main_xml = root_relationships = None
            for entry in entries:
                # Consume all members in bounded blocks, checking real expansion and CRC.
                parts, actual = [], 0
                is_xml = entry.filename.lower().endswith((".xml", ".rels"))
                with archive.open(entry) as stream:
                    while block := stream.read(64 * 1024):
                        actual += len(block)
                        if actual > MAX_ENTRY_BYTES or actual > entry.file_size:
                            raise _limit()
                        if is_xml:
                            parts.append(block)
                if actual != entry.file_size:
                    raise _malformed()
                if not is_xml:
                    continue
                root = _xml(b"".join(parts))
                if entry.filename == "[Content_Types].xml":
                    content_types = root
                if entry.filename == main:
                    main_xml = root
                if entry.filename.endswith(".rels"):
                    if root.tag != f"{{{REL_NS}}}Relationships":
                        raise _malformed()
                    for rel in root:
                        kind = rel.get("Type", "").lower()
                        if any(active in kind for active in ("vbaproject", "oleobject", "activex")):
                            raise ApiError("unsafe_office", "Active Office relationships are not supported", 422)
                        if rel.get("TargetMode", "").lower() == "external" and not kind.endswith("/hyperlink"):
                            raise ApiError("unsafe_office", "Linked external Office resources are not supported; embed the content instead", 422)
                    if entry.filename == "_rels/.rels":
                        root_relationships = root
                if suffix == ".xlsx" and entry.filename.startswith("xl/worksheets/"):
                    _sheet_area(root)
            if content_types.tag != f"{{{CONTENT_NS}}}Types":
                raise _malformed()
            if not any(item.get("PartName") == "/" + main and item.get("ContentType") == content_type for item in content_types):
                raise _malformed()
            if any(any(active in item.get("ContentType", "").lower() for active in
                       ("macroenabled", "vba", "activex", "oleobject")) for item in content_types):
                raise ApiError("unsafe_office", "Macro-enabled Office content is not supported", 422)
            if not any(rel.get("Type", "").endswith("/officeDocument") and rel.get("Target", "").lstrip("/") == main for rel in root_relationships):
                raise _malformed()
            unit = {".pptx": "sldId", ".xlsx": "sheet"}.get(suffix)
            if unit and sum(item.tag.rsplit("}", 1)[-1] == unit for item in main_xml.iter()) > max_pages:
                raise ApiError("document_limit", "The Office document exceeds the 300-slide/sheet limit", 413)
    except ApiError:
        raise
    except Exception:
        # Parser/ZIP exception strings may contain content or private paths.
        raise _malformed() from None


def office_converter():
    from docling.backend.msword_backend import MsWordDocumentBackend
    from docling.backend.mspowerpoint_backend import MsPowerpointDocumentBackend
    from docling.backend.msexcel_backend import MsExcelDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.backend_options import MsExcelBackendOptions, MsPowerpointBackendOptions, MsWordBackendOptions
    from docling.datamodel.pipeline_options import ConvertPipelineOptions
    from docling.document_converter import DocumentConverter, ExcelFormatOption, PowerpointFormatOption, WordFormatOption
    from docling.pipeline.simple_pipeline import SimplePipeline

    # The pinned backends also have legacy-picture/shape render fallbacks that
    # are independent of render_chart_images. Reuse their parsers, disabling
    # only external converter discovery. No Office executable may be invoked.
    class LocalWordBackend(MsWordDocumentBackend):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.docx_to_pdf_converter = None
            self.docx_to_pdf_converter_init = True

    class LocalPowerpointBackend(MsPowerpointDocumentBackend):
        def _get_libreoffice_converter(self):
            return None

    class LocalExcelBackend(MsExcelDocumentBackend):
        def _get_libreoffice_converter(self):
            return None

    options = ConvertPipelineOptions(enable_remote_services=False, allow_external_plugins=False,
        do_picture_classification=False, do_picture_description=False, do_chart_extraction=False)
    def format_option(option, backend_options, backend):
        return option(pipeline_cls=SimplePipeline, pipeline_options=options, backend=backend,
            backend_options=backend_options(enable_remote_fetch=False, enable_local_fetch=False, render_chart_images=False))
    return DocumentConverter(allowed_formats=[InputFormat.PPTX, InputFormat.DOCX, InputFormat.XLSX],
        format_options={InputFormat.PPTX: format_option(PowerpointFormatOption, MsPowerpointBackendOptions, LocalPowerpointBackend),
            InputFormat.DOCX: format_option(WordFormatOption, MsWordBackendOptions, LocalWordBackend),
            InputFormat.XLSX: format_option(ExcelFormatOption, MsExcelBackendOptions, LocalExcelBackend)})


def item_locators(item, document, suffix):
    """Preserve Docling references/geometry; Office ordinals are never PDF pages."""
    base = {"item_ref": item.self_ref, "page": None, "format": suffix[1:]}
    if item.self_ref.startswith("#/tables/"):
        base["table_ref"] = item.self_ref
    sheet_name = None
    parent = item.parent
    seen = set()
    while parent and parent.cref not in seen:
        seen.add(parent.cref)
        group = parent.resolve(document)
        if getattr(group, "label", None) == "sheet":
            sheet_name = group.name
            break
        parent = group.parent
    result = []
    for prov in item.prov:
        locator = {**base, "char_span": list(prov.charspan)}
        if suffix == ".pptx":
            locator.update(slide=prov.page_no, bbox=prov.bbox.model_dump(mode="json"))
            page = document.pages.get(prov.page_no)
            if page:
                locator["slide_size"] = page.size.model_dump(mode="json")
        elif suffix == ".xlsx":
            locator.update(sheet=prov.page_no, sheet_name=sheet_name, cell_bbox=prov.bbox.model_dump(mode="json"))
        result.append(locator)
    return result or [base]
