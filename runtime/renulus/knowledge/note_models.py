# SPDX-License-Identifier: MIT
"""User-authored note commands; source authority never comes from the renderer."""
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_NOTE_BYTES = 4 * 1024 * 1024
NoteIdentifier = Annotated[str, Field(min_length=1, max_length=128, strict=True,
    pattern=r"^[A-Za-z0-9_-]+$")]
CommandKey = Annotated[str, Field(min_length=1, max_length=200, strict=True)]


class NoteText(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    title: str = Field(min_length=1, max_length=500, strict=True)
    text: str = Field(min_length=1, max_length=MAX_NOTE_BYTES, strict=True)
    idempotency_key: CommandKey

    @field_validator("title", "idempotency_key")
    @classmethod
    def not_blank(cls, value):
        if not value.strip() or "\0" in value:
            raise ValueError("Use nonempty text without NUL characters")
        return value

    @field_validator("text")
    @classmethod
    def bounded_original(cls, value):
        if not value.strip() or "\0" in value or len(value.encode("utf-8")) > MAX_NOTE_BYTES:
            raise ValueError("Add note text up to 4 MiB without NUL characters")
        return value


class CreateNote(NoteText):
    project_id: NoteIdentifier | None = None


class EditNote(NoteText):
    expected_revision_id: NoteIdentifier


class DeleteNote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_revision_id: NoteIdentifier
    idempotency_key: CommandKey

    @field_validator("idempotency_key")
    @classmethod
    def not_blank(cls, value):
        return NoteText.not_blank(value)
