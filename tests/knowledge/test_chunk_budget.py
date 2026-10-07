from docling_core.types.doc import BoundingBox, DoclingDocument, ProvenanceItem, Size, TableCell, TableData
from tokenizers import Tokenizer

from test_offline_engines import live_repository


def test_real_hybrid_table_split_reserves_heading_overhead_and_preserves_cells(live_repository):
    document = DoclingDocument(name="Synthetic long table")
    document.add_page(page_no=1, size=Size(width=612, height=792))
    document.add_heading(text="Transplant donor eligibility " + "reviewed teaching context " * 35, level=1)
    cells = []
    for row in range(61):
        for column in range(3):
            text = ["Item", "Education observation", "Review context"][column] if row == 0 else (
                "ROW" + str(row) if column == 0 else "transplant dialysis glomerular teaching observation " * 8)
            cells.append(TableCell(start_row_offset_idx=row, end_row_offset_idx=row + 1,
                start_col_offset_idx=column, end_col_offset_idx=column + 1,
                text=text, column_header=row == 0))
    document.add_table(data=TableData(num_rows=61, num_cols=3, table_cells=cells),
        prov=ProvenanceItem(page_no=1, bbox=BoundingBox(l=40, t=40, r=560, b=750), charspan=(0, 0)))
    result = live_repository.extractor._chunk(document)
    tokenizer = Tokenizer.from_file(str(live_repository.paths.helpers / "fastembed/bge-small-en-v1.5/tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    assert len(result.passages) > 1
    assert all(len(tokenizer.encode(p["context_text"], add_special_tokens=False).ids) <= 480 for p in result.passages)
    text = "\n".join(p["text"] for p in result.passages)
    assert all("ROW" + str(row) in text for row in range(1, 61))
    assert all(p["headings"] and p["locators"][0]["page"] == 1 and p["locators"][0]["bbox"] for p in result.passages)
