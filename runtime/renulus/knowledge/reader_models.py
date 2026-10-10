# SPDX-License-Identifier: MIT
"""Inert, bounded reader transport. No paths, HTML, URLs or executable markup."""
from typing import Literal

from pydantic import Field, model_validator

from ..design_c_contracts import (Contract, ContentReference, ConversationIdentity,
                                 Locator)


class ReaderRequest(Contract):
    reference: ContentReference
    conversation: ConversationIdentity | None = None
    page: int = Field(default=1, ge=1, le=300)
    sheet: str | None = Field(default=None, max_length=120)
    first_row: int = Field(default=1, ge=1, le=100000)
    row_limit: int = Field(default=100, ge=1, le=200)
    expected_policy_revision: int | None = Field(default=None, ge=0)
    expected_context_epoch: int | None = Field(default=None, ge=0)


class ReaderAssetRequest(ReaderRequest):
    asset_id: str = Field(min_length=1, max_length=160)
    original_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReaderSelectionRequest(ReaderRequest):
    locator: Locator
    original_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ReaderGrid(Contract):
    rows: tuple[tuple[str, ...], ...] = Field(min_length=1, max_length=200)
    header_rows: int = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def bounded_cells(self):
        if any(not 1 <= len(row) <= 200 or any(len(cell) > 20000 for cell in row) for row in self.rows):
            raise ValueError("Document tables require 1–200 columns and bounded plain text cells")
        return self


class ReaderBlock(Contract):
    kind: Literal["paragraph", "heading", "list_item", "code", "image", "table"]
    item_ref: str = Field(min_length=1, max_length=256)
    text: str = Field(default="", max_length=200000)
    level: int | None = Field(default=None, ge=1, le=6)
    locator: Locator | None = None
    asset_id: str | None = Field(default=None, max_length=160)
    grid: ReaderGrid | None = None


class ReaderDiagnostic(Contract):
    code: str = Field(max_length=80)
    message: str = Field(max_length=400)


class ReaderCell(Contract):
    display: str = Field(max_length=20000)
    value: str | int | float | bool | None = None
    number_format: str | None = Field(default=None, max_length=240)
    formula: str | None = Field(default=None, max_length=20000)
    cached: bool = True


class ReaderTable(Contract):
    format: Literal["csv", "xlsx"]
    sheet_name: str | None = None
    sheets: tuple[str, ...] = Field(default=(), max_length=300)
    first_row: int
    total_rows: int
    total_columns: int
    rows: tuple[tuple[ReaderCell, ...], ...] = Field(max_length=200)


class ReaderPayload(Contract):
    schema_version: Literal["reader/1"] = "reader/1"
    kind: Literal["text", "table", "pdf", "image"]
    blocks: tuple[ReaderBlock, ...] = Field(default=(), max_length=4000)
    table: ReaderTable | None = None
    page: int | None = None
    pages: int | None = None
    asset_id: str | None = None
    diagnostics: tuple[ReaderDiagnostic, ...] = Field(default=(), max_length=32)
