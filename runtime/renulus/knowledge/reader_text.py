# SPDX-License-Identifier: MIT
"""Bounded markup/table adapters; markup never reaches a browser parser."""
import csv
from html.parser import HTMLParser
from io import StringIO

from ..contracts import ApiError
from .reader_models import ReaderBlock, ReaderCell, ReaderDiagnostic, ReaderPayload, ReaderTable

MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_CHARACTERS = 2_000_000
MAX_CELLS = 100000
MAX_COLUMNS = 200


def decode_text(data):
    if len(data) > MAX_TEXT_BYTES:
        raise ApiError("reader_text_limit", "Choose text or a table up to 4 MiB", 413)
    encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        text = data.decode(encoding)
    except UnicodeError:
        raise ApiError("reader_encoding", "Use UTF-8 or BOM-marked UTF-16 text", 422) from None
    if "\x00" in text or len(text) > MAX_CHARACTERS:
        raise ApiError("reader_text_limit", "The text exceeds the reader's character limit", 413)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def block(kind, text, number, *, level=None, section=None):
    ref = f"reader-v1:item:{number}"
    return ReaderBlock(kind=kind, text=text, item_ref=ref, level=level,
        locator={"kind": "text", "item_ref": ref, "section": section,
                 "start": 0, "end": len(text)} if text else None)


class InertHTML(HTMLParser):
    # Discard active/non-document subtrees, including their fallback text.
    hidden = {"script", "style", "iframe", "object", "embed", "svg", "math",
              "template", "form", "head", "noscript"}
    breaks = {"p", "div", "section", "article", "li", "pre", "tr", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = []
        self.parts, self.blocks = [], []
        self.kind, self.level = "paragraph", None
        self.events = 0

    def tick(self):
        self.events += 1
        if self.events > 100000:
            raise ApiError("reader_markup_limit", "The markup contains too many elements", 413)

    def flush(self):
        text = "".join(self.parts).strip()
        if text:
            if len(self.blocks) >= 4000 or len(text) > 200000:
                raise ApiError("reader_markup_limit", "The document contains too much text", 413)
            self.blocks.append(block(self.kind, text, len(self.blocks), level=self.level))
        self.parts = []

    def handle_starttag(self, tag, attrs):
        self.tick()
        if self.skip:
            if tag in self.hidden and tag not in {"embed"}:
                self.skip.append(tag)
            return
        if tag in self.hidden:
            if tag != "embed":
                self.skip.append(tag)
            return
        if tag in self.breaks or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.flush()
            self.kind = "heading" if tag.startswith("h") else "list_item" if tag == "li" else "code" if tag == "pre" else "paragraph"
            self.level = int(tag[1]) if self.kind == "heading" else None
        elif tag in {"td", "th"} and self.parts:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        self.tick()
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
            return
        if tag in self.breaks or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.flush()
            self.kind, self.level = "paragraph", None

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_payload(text):
    parser = InertHTML()
    parser.feed(text)
    parser.close()
    parser.flush()
    return ReaderPayload(kind="text", blocks=tuple(parser.blocks), diagnostics=(ReaderDiagnostic(
        code="inert_markup", message="Scripts, forms, embedded content and external resources are omitted."),))


def markdown_payload(text):
    from markdown_it import MarkdownIt
    parser = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")
    tokens = parser.parse(text)
    if len(tokens) > 16000:
        raise ApiError("reader_markup_limit", "The Markdown contains too many blocks", 413)
    blocks = []
    kind, level = "paragraph", None
    list_depth = 0
    for token in tokens:
        if token.type in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1
        elif token.type in ("bullet_list_close", "ordered_list_close"):
            list_depth -= 1
        elif token.type == "heading_open":
            kind, level = "heading", int(token.tag[1])
        elif token.type == "paragraph_open":
            kind, level = ("list_item" if list_depth else "paragraph"), None
        elif token.type in ("fence", "code_block"):
            blocks.append(block("code", token.content.rstrip("\n"), len(blocks)))
        elif token.type == "inline":
            # Ignore href/src attributes: inline text/code only, never HTML/URLs.
            content = "".join("\n" if child.type in ("softbreak", "hardbreak") else child.content
                              for child in token.children or []
                              if child.type not in ("html_inline", "image"))
            if content:
                blocks.append(block(kind, content, len(blocks), level=level))
        if len(blocks) > 4000:
            raise ApiError("reader_markup_limit", "The Markdown contains too many blocks", 413)
    return ReaderPayload(kind="text", blocks=tuple(blocks), diagnostics=(ReaderDiagnostic(
        code="inert_markdown", message="Embedded HTML is escaped; remote images and active links are omitted."),))


def xml_payload(data):
    from defusedxml.ElementTree import fromstring
    from defusedxml.common import DefusedXmlException
    import xml.etree.ElementTree as ET
    if len(data) > MAX_TEXT_BYTES:
        raise ApiError("reader_text_limit", "Choose XML up to 4 MiB", 413)
    try:
        root = fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (DefusedXmlException, ET.ParseError):
        raise ApiError("reader_xml_invalid", "XML must be complete and contain no DTD or entity declarations", 422) from None
    count = 0
    stack = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > 10000 or depth > 80:
            raise ApiError("reader_markup_limit", "The XML tree exceeds its element or depth limit", 413)
        stack.extend((child, depth + 1) for child in node)
    ET.indent(root, space="  ")
    text = ET.tostring(root, encoding="unicode")
    if len(text) > 200000:
        raise ApiError("reader_text_limit", "The formatted XML exceeds 200,000 characters", 413)
    return ReaderPayload(kind="text", blocks=(block("code", text, 0),))


def csv_rows(text):
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(StringIO(text), dialect, strict=True)
    total, columns = 0, 0
    try:
        for number, row in enumerate(reader, 1):
            total += len(row)
            columns = max(columns, len(row))
            if total > MAX_CELLS or columns > MAX_COLUMNS or number > 100000:
                raise ApiError("reader_table_limit", "The table exceeds 100,000 cells or 200 columns", 413)
            if any(len(cell) > 20000 for cell in row):
                raise ApiError("reader_table_limit", "A table cell exceeds 20,000 characters", 413)
            yield number, row
    except csv.Error:
        raise ApiError("reader_csv_invalid", "The CSV quoting or cell size is invalid", 422) from None


def csv_payload(text, request):
    rows, columns, count = [], 0, 0
    for number, row in csv_rows(text):
        count = number
        columns = max(columns, len(row))
        if request.first_row <= number < request.first_row + request.row_limit:
            rows.append(tuple(ReaderCell(display=value, value=value) for value in row))
    return ReaderPayload(kind="table", table=ReaderTable(format="csv", first_row=request.first_row,
        total_rows=count, total_columns=columns, rows=tuple(rows)))


def text_payload(data, suffix, request):
    if suffix == ".xml":
        return xml_payload(data)
    text = decode_text(data)
    if suffix in (".html", ".htm"):
        return html_payload(text)
    if suffix == ".md":
        return markdown_payload(text)
    if suffix == ".csv":
        return csv_payload(text, request)
    if len(text) > 200000:
        raise ApiError("reader_text_limit", "The text exceeds 200,000 characters", 413)
    return ReaderPayload(kind="text", blocks=(block("paragraph", text, 0),))
