"""Container refusals use generated packages only, before any durable write."""
from io import BytesIO
import struct
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

import pytest

from renulus.contracts import ApiError
from renulus.knowledge import office
from renulus.knowledge.engines import MAX_BYTES, MAX_PAGES
from renulus.knowledge.models import own_text_rights
from test_repository import repository


def package(suffix=".docx", extra=None, main_xml=None):
    main, content_type = office.MAIN_PARTS[suffix]
    entries = {
        "[Content_Types].xml": f'<Types xmlns="{office.CONTENT_NS}"><Override PartName="/{main}" ContentType="{content_type}"/></Types>',
        "_rels/.rels": f'<Relationships xmlns="{office.REL_NS}"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="{main}"/></Relationships>',
        main: main_xml or '<document/>',
        **(extra or {}),
    }
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return output.getvalue()


def validate(data, suffix=".docx"):
    office.validate_office(data, suffix, max_bytes=MAX_BYTES, max_pages=MAX_PAGES)


@pytest.mark.parametrize("suffix", office.OFFICE_MEDIA)
def test_recognises_only_matching_ooxml_container(suffix):
    validate(package(suffix), suffix)
    other = ".xlsx" if suffix != ".xlsx" else ".docx"
    with pytest.raises(ApiError) as error:
        validate(package(suffix), other)
    assert error.value.code == "malformed_office"


@pytest.mark.parametrize("data", [b"not a ZIP", b"PK\x03\x04", package()[:-8],
    package(extra={"../escape.xml": "<bad/>"}),
    package(extra={"word/broken.xml": "<broken>"}),
    package(extra={"word/document.xml": "<!DOCTYPE document [<!ENTITY a 'boom'>]><document>&a;</document>"})])
def test_malformed_or_entity_packages_are_refused(data):
    with pytest.raises(ApiError) as error:
        validate(data)
    assert error.value.code in ("malformed_office", "unsafe_office")


def test_declared_member_count_is_bounded_before_zipfile_allocates(monkeypatch):
    data = bytearray(package())
    end = data.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", data, end + 8, office.MAX_ENTRIES + 1, office.MAX_ENTRIES + 1)
    monkeypatch.setattr(office, "ZipFile", lambda *a, **k: pytest.fail("Allocated unbounded ZIP metadata"))
    with pytest.raises(ApiError) as error:
        validate(bytes(data))
    assert error.value.code == "office_container_limit"


def test_forged_small_member_count_cannot_hide_unbounded_metadata(monkeypatch):
    data = bytearray(package())
    end = data.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", data, end + 8, 1, 1)
    monkeypatch.setattr(office, "ZipFile", lambda *a, **k: pytest.fail("Allocated hidden ZIP entries"))
    with pytest.raises(ApiError) as error:
        validate(bytes(data))
    assert error.value.code == "malformed_office"


@pytest.mark.parametrize("kind", ["ratio", "member", "total"])
def test_expansion_limits_before_docling(kind, monkeypatch):
    if kind == "ratio":
        data = package(extra={"word/padding.bin": b"A" * 100000})
    else:
        data = package()
        monkeypatch.setattr(office, "MAX_ENTRY_BYTES" if kind == "member" else "MAX_EXPANDED_BYTES", 32)
    with pytest.raises(ApiError) as error:
        validate(data)
    assert error.value.code == "office_container_limit"


@pytest.mark.parametrize("suffix, unit", [(".pptx", "sldId"), (".xlsx", "sheet")])
def test_slide_and_sheet_limit(suffix, unit):
    data = package(suffix, main_xml="<root>" + ("<" + unit + "/>") * (MAX_PAGES + 1) + "</root>")
    with pytest.raises(ApiError) as error:
        validate(data, suffix)
    assert error.value.code == "document_limit"


@pytest.mark.parametrize("element", ['<c r="XFD1048576"/>',
    '<mergeCell ref="A1:XFD1048576"/>', '<dimension ref="A1:XFD1048576"/>'])
def test_sparse_spreadsheet_cannot_expand_to_a_huge_dense_rectangle(element):
    data = package(".xlsx", extra={"xl/worksheets/sheet1.xml": '<worksheet>' + element + '</worksheet>'})
    with pytest.raises(ApiError) as error:
        validate(data, ".xlsx")
    assert error.value.code == "office_container_limit"


def test_existing_compressed_byte_limit_is_kept():
    with pytest.raises(ApiError) as error:
        office.validate_office(package(), ".docx", max_bytes=1, max_pages=MAX_PAGES)
    assert error.value.code == "document_limit"


@pytest.mark.parametrize("payload", ["word/vbaProject.bin", "word/activeX/activeX1.bin",
    "ppt/embeddings/embedded.xlsx", "word/media/image1.emf"])
def test_active_packages_and_external_renderers_are_refused(payload):
    with pytest.raises(ApiError) as error:
        validate(package(extra={payload: b"synthetic"}))
    assert error.value.code == "unsafe_office"


def test_external_hyperlinks_are_inert_but_linked_content_is_refused():
    def relationships(kind):
        return f'<Relationships xmlns="{office.REL_NS}"><Relationship Id="rId7" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{kind}" Target="https://example.invalid/never-fetch" TargetMode="External"/></Relationships>'
    validate(package(extra={"word/_rels/document.xml.rels": relationships("hyperlink")}))
    with pytest.raises(ApiError) as error:
        validate(package(extra={"word/_rels/document.xml.rels": relationships("image")}))
    assert error.value.code == "unsafe_office"


def test_encrypted_entry_and_compound_office_are_explicitly_refused():
    data = bytearray(package())
    struct.pack_into("<H", data, 6, 1)
    central = data.find(b"PK\x01\x02")
    struct.pack_into("<H", data, central + 8, 1)
    for encrypted in (bytes(data), bytes.fromhex("d0cf11e0a1b11ae1") + b"synthetic"):
        with pytest.raises(ApiError) as error:
            validate(encrypted)
        assert error.value.code == "office_encrypted"


def test_crc_corruption_duplicate_names_and_symlink_are_refused():
    original = package()
    central = original.find(b"PK\x01\x02")
    corrupted = bytearray(original)
    struct.pack_into("<L", corrupted, central + 16, 1)
    duplicate, symlink = BytesIO(), BytesIO()
    with ZipFile(duplicate, "w", ZIP_STORED) as archive:
        archive.writestr("same", b"one")
        with pytest.warns(UserWarning):
            archive.writestr("same", b"two")
    with ZipFile(symlink, "w", ZIP_STORED) as archive:
        entry = ZipInfo("symlink")
        entry.create_system, entry.external_attr = 3, 0o120777 << 16
        archive.writestr(entry, "target")
    for data in (bytes(corrupted), duplicate.getvalue(), symlink.getvalue()):
        with pytest.raises(ApiError) as error:
            validate(data)
        assert error.value.code == "malformed_office"


def test_case_ambiguous_parts_and_local_zip64_are_refused():
    with pytest.raises(ApiError) as error:
        validate(package(extra={"WORD/DOCUMENT.XML": "<document/>"}))
    assert error.value.code == "malformed_office"
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        with archive.open("word/document.xml", "w", force_zip64=True) as entry:
            entry.write(b"<document/>")
    with pytest.raises(ApiError) as error:
        validate(output.getvalue())
    assert error.value.code == "office_container_limit"


def test_bad_container_and_unchanged_rights_cannot_create_library_records(repository, tmp_path):
    path = tmp_path / "selected.docx"
    path.write_bytes(package(extra={"word/padding.bin": b"A" * 100000}))
    with pytest.raises(ApiError) as error:
        repository.import_file(path, rights=own_text_rights(), process=False)
    assert error.value.code == "office_container_limit"
    assert repository.db.fetch_all("SELECT * FROM knowledge_documents") == []
    assert not list(repository.paths.library.rglob("original.*"))
    path.write_bytes(package())
    with pytest.raises(ApiError) as error:
        repository.import_file(path, process=False)
    assert error.value.code == "source_permission_required"
