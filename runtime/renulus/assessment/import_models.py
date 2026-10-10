# SPDX-License-Identifier: MIT
"""Private import intent and editable candidates; review is never model-owned."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from renulus.design_c_contracts import Identifier, Option, Revision
from .contracts import Command


class ImportModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TextSpan(ImportModel):
    start: Annotated[int, Field(ge=0, strict=True)]
    end: Annotated[int, Field(gt=0, strict=True)]

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Use a nonempty original text span")
        return self


class PastedOriginal(ImportModel):
    kind: Literal["paste"]
    text: Annotated[str, Field(min_length=1, max_length=96000)]
    terms: Annotated[str, Field(min_length=1, max_length=2000)]
    permission_confirmed: Literal[True]

    @field_validator("text", "terms")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Supply nonempty original text and retained terms")
        return value


class LibraryOriginal(ImportModel):
    kind: Literal["library_revision"]
    revision_id: Identifier


class CreateImportRequest(Command):
    # Exact private originals must survive even leading/trailing whitespace.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    title: Annotated[str, Field(min_length=1, max_length=120)] = "Imported practice"
    original: Annotated[PastedOriginal | LibraryOriginal, Field(discriminator="kind")]

    @field_validator("title")
    @classmethod
    def meaningful_title(cls, value):
        if not value.strip():
            raise ValueError("Name this private import")
        return value.strip()


class ImportRevisionCommand(Command):
    expected_revision: Revision


class EditImportCandidateRequest(ImportRevisionCommand):
    stem: Annotated[str, Field(min_length=1, max_length=6000)]
    options: tuple[Option, ...] = Field(min_length=2, max_length=20)
    explanation: Annotated[str, Field(max_length=6000)] = ""
    topic_id: Identifier = "personal-import"


class ResolveImportCandidateRequest(ImportRevisionCommand):
    correct_option_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)
    review_confirmed: Literal[True]


class CandidateVisibilityRequest(ImportRevisionCommand):
    removed: bool


class LocatedOption(ImportModel):
    id: Identifier
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    span: TextSpan


class NormalizedCandidate(ImportModel):
    """Output can propose formatting, never keys, reviewed quality or permissions."""
    span: TextSpan
    stem_span: TextSpan
    stem: Annotated[str, Field(min_length=1, max_length=6000)]
    options: tuple[LocatedOption, ...] = Field(min_length=2, max_length=20)
    explanation: Annotated[str, Field(max_length=6000)] = ""
    explanation_span: TextSpan | None = None


class NormalizedImport(ImportModel):
    candidates: tuple[NormalizedCandidate, ...] = Field(min_length=1, max_length=50)
