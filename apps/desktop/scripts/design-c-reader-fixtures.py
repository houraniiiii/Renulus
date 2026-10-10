# SPDX-License-Identifier: MIT
"""Deterministic synthetic originals for the installed reader driver, never profiles.

No clinical claims, downloads, source data or application database access. Office
packages and PDF are declarative bytes; Pillow is the shipped image encoder.
Importing this module has no filesystem effects. The caller owns a fresh output
directory and verifies this script against the exact installed source revision.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo


MARKER = "DC21_SYNTHETIC_SCRIPT_EXECUTED"
EXTERNAL = "https://design-c-reader.invalid/never-fetch"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE = "http://schemas.openxmlformats.org/package/2006/relationships"
WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SHEET = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def package(entries):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for name, value in sorted(entries.items()):
            entry = ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_STORED
            entry.create_system = 0
            entry.external_attr = 0o600 << 16
            archive.writestr(entry, value.encode("utf-8") if isinstance(value, str) else value)
    return output.getvalue()


def types(overrides, image=False):
    return ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            + ('<Default Extension="png" ContentType="image/png"/>' if image else "")
            + "".join(f'<Override PartName="/{part}" ContentType="{media}"/>' for part, media in overrides)
            + "</Types>")


def relationships(items):
    return f'<Relationships xmlns="{PACKAGE}">' + "".join(
        f'<Relationship Id="{key}" Type="{OFFICE}/{kind}" Target="{target}"/>'
        for key, kind, target in items) + "</Relationships>"


def pdf():
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>"]
    for index, text in enumerate(("Synthetic CKD reading page one.", "Synthetic dialysis reading page two.")):
        stream = f"BT /F1 18 Tf 32 180 Td ({text}) Tj ET\n".encode("ascii")
        objects.extend([f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 360 240] /Resources << /Font << /F1 7 0 R >> >> /Contents {4 + index * 2} 0 R >>".encode(),
                        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"])
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    result, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), [0]
    for number, data in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode() + data + b"\nendobj\n")
    start = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    result.extend("".join(f"{offset:010} 00000 n \n" for offset in offsets[1:]).encode())
    result.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(result)


def images():
    from PIL import Image, __version__
    first, second = Image.new("RGB", (48, 32), (20, 100, 120)), Image.new("RGB", (48, 32), (180, 90, 30))
    outputs = {}
    for suffix, fmt, options in (("png", "PNG", {"compress_level": 9}),
                                 ("jpg", "JPEG", {"quality": 90, "subsampling": 0, "optimize": False, "progressive": False}),
                                 ("tiff", "TIFF", {"compression": "raw", "save_all": True, "append_images": [second]})):
        stream = BytesIO()
        first.save(stream, format=fmt, **options)
        outputs[suffix] = stream.getvalue()
    first.close()
    second.close()
    return outputs, __version__


def docx(png):
    def paragraph(text):
        return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
    rows = "".join("<w:tr>" + ("<w:trPr><w:tblHeader/></w:trPr>" if index == 0 else "")
                   + "".join("<w:tc>" + paragraph(cell) + "</w:tc>" for cell in row) + "</w:tr>"
                   for index, row in enumerate((("Topic", "Source"), ("Transplantation", "Synthetic row"))))
    body = (paragraph("Synthetic transplantation reading paragraph.")
            + '<w:tbl><w:tblPr/><w:tblGrid><w:gridCol w:w="3000"/><w:gridCol w:w="3000"/></w:tblGrid>' + rows + "</w:tbl>"
            + '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="457200" cy="304800"/><wp:docPr id="1" name="Synthetic rectangle"/>'
              '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
              '<pic:nvPicPr><pic:cNvPr id="1" name="Synthetic rectangle"/><pic:cNvPicPr/></pic:nvPicPr>'
              '<pic:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
              '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="457200" cy="304800"/></a:xfrm>'
              '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic>'
              '</wp:inline></w:drawing></w:r></w:p><w:sectPr/>')
    return package({
        "[Content_Types].xml": types([("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")], image=True),
        "_rels/.rels": relationships([("rId1", "officeDocument", "word/document.xml")]),
        "word/document.xml": f'<w:document xmlns:w="{WORD}" xmlns:r="{OFFICE}" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><w:body>{body}</w:body></w:document>',
        "word/_rels/document.xml.rels": relationships([("rId1", "image", "media/synthetic.png")]),
        "word/media/synthetic.png": png,
    })


def xlsx():
    def sheet(label, cells):
        return f'<worksheet xmlns="{SHEET}"><dimension ref="A1:B2"/><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>{label}</t></is></c></row><row r="2">{cells}</row></sheetData></worksheet>'
    entries = {
        "[Content_Types].xml": types([
            ("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
            ("xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
            *[(f"xl/worksheets/sheet{i}.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml") for i in (1, 2)]]),
        "_rels/.rels": relationships([("rId1", "officeDocument", "xl/workbook.xml")]),
        "xl/workbook.xml": f'<workbook xmlns="{SHEET}" xmlns:r="{OFFICE}"><sheets><sheet name="CKD" sheetId="1" r:id="rId1"/><sheet name="Dialysis" sheetId="2" r:id="rId2"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": relationships([("rId1", "worksheet", "worksheets/sheet1.xml"), ("rId2", "worksheet", "worksheets/sheet2.xml"), ("rId3", "styles", "styles.xml")]),
        "xl/styles.xml": f'<styleSheet xmlns="{SHEET}"><fonts count="1"><font><name val="Calibri"/><sz val="11"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0"/><xf numFmtId="10" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        "xl/worksheets/sheet1.xml": sheet("Synthetic CKD sheet", '<c r="A2"><v>12</v></c><c r="B2"><f>A2*2</f><v>24</v></c>'),
        "xl/worksheets/sheet2.xml": sheet("Synthetic dialysis sheet", '<c r="A2" s="1"><v>0.25</v></c><c r="B2"><f>A2*2</f></c>'),
    }
    return package(entries)


def fixture_set():
    pictures, pillow_version = images()
    records = []

    def add(name, gate, media, data, **expect):
        if isinstance(data, str):
            data = data.encode("utf-8")
        records.append(({"filename": name, "gate": "reader-" + gate, "media_type": media,
                         "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "expect": expect}, data))

    add("synthetic-reading.pdf", "pdf", "application/pdf", pdf(), kind="pdf", pages=2, text="Synthetic dialysis reading page two.")
    add("synthetic-reading.docx", "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx(pictures["png"]), kind="text", text="Synthetic transplantation reading paragraph.", table_cell="Synthetic row", embedded_image=True)
    add("synthetic-reading.csv", "csv", "text/csv", "Topic,Label\n" + "".join(f'Electrolytes,"Synthetic row {number:03}, quoted"\n' for number in range(1, 106)), kind="table", rows=106, first_row=101, text="Synthetic row 100, quoted")
    add("synthetic-reading.xlsx", "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", xlsx(), kind="table", sheets=["CKD", "Dialysis"], text="25.00%")
    add("synthetic-reading.md", "markdown", "text/markdown", "# Synthetic glomerular reading\n\nSynthetic glomerular reading paragraph.\n\n| Topic | Source |\n| --- | --- |\n| Glomerular | Synthetic row |\n", kind="text", text="Synthetic glomerular reading paragraph.", table_cell="Synthetic row")
    add("synthetic-reading.html", "html", "text/html", f'<!doctype html><html><head><link rel="stylesheet" href="{EXTERNAL}.css"><script>window.{MARKER}=true;fetch("{EXTERNAL}")</script></head><body onload="window.{MARKER}=true"><h1>Synthetic electrolyte reading</h1><p>Synthetic electrolyte reading paragraph.</p><img src="{EXTERNAL}.png" onerror="window.{MARKER}=true"><iframe src="{EXTERNAL}">HIDDEN_REMOTE_FALLBACK</iframe><form>HIDDEN_FORM</form><table><tr><th>Topic</th><th>Source</th></tr><tr><td>Electrolytes</td><td>Synthetic row</td></tr></table></body></html>', kind="text", text="Synthetic electrolyte reading paragraph.", table_cell="Synthetic row", inert=True)
    add("synthetic-reading.xml", "xml", "application/xml", f'<?xml version="1.0"?><?xml-stylesheet type="text/xsl" href="{EXTERNAL}.xsl"?><reading><topic>Glomerular</topic><text>Synthetic XML reading paragraph.</text><script>window.{MARKER}=true</script><external href="{EXTERNAL}"/></reading>', kind="text", text="Synthetic XML reading paragraph.", inert=True)
    add("synthetic-denied-entity.xml", "xml", "application/xml", f'<?xml version="1.0"?><!DOCTYPE reading [<!ENTITY external SYSTEM "{EXTERNAL}">]><reading>&external;</reading>', error="reader_xml_invalid", inert=True)
    for suffix, media in (("png", "image/png"), ("jpg", "image/jpeg"), ("tiff", "image/tiff")):
        add("synthetic-reading." + suffix, "images", media, pictures[suffix], kind="image", pages=2 if suffix == "tiff" else 1, width=48, height=32)
    return {"schema": "design-c-reader-fixtures/1", "synthetic": True, "pillow_version": pillow_version,
            "execution_marker": MARKER, "external_origin": "https://design-c-reader.invalid", "files": [item for item, _ in records]}, records


def write_fixtures(output):
    if not output.is_absolute():
        raise ValueError("Use an absolute fresh output directory")
    # Caller guards the evidence root; also refuse all filesystem indirections.
    for ancestor in (output, *output.parents):
        if ancestor.is_symlink() or getattr(ancestor, "is_junction", lambda: False)():
            raise ValueError("Fixture paths may not traverse filesystem links")
    manifest, records = fixture_set()
    output.mkdir(exist_ok=False)
    for record, data in records:
        with (output / record["filename"]).open("xb") as target:
            target.write(data)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = write_fixtures(args.output)
    print(json.dumps({"schema": manifest["schema"], "files": len(manifest["files"]), "pillow_version": manifest["pillow_version"]}))
