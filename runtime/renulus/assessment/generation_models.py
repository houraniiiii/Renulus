# SPDX-License-Identifier: MIT
"""Saved-input generation intent; renderer text cannot attest retention or review."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from renulus.design_c_contracts import ContentReference, EligibleInput, Identifier
from .contracts import Command


class CreateGenerationRequest(Command):
    title: Annotated[str, Field(min_length=1, max_length=120)] = "Generated practice"
    count: Literal[5, 10, 20] = 5
    topic_id: Identifier | None = None
    inputs: tuple[EligibleInput, ...] = Field(default=(), max_length=20)
    source_refs: tuple[ContentReference, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def saved_references(self):
        if len({entry.dependency.target.key for entry in self.inputs}) != len(self.inputs):
            raise ValueError("Select each saved learning input once")
        if any(entry.target.type != "library_revision" or entry.locator is not None for entry in self.source_refs):
            raise ValueError("Generation sources must be saved Library revisions")
        if len({entry.target.key for entry in self.source_refs}) != len(self.source_refs):
            raise ValueError("Select each source revision once")
        return self


class GenerationAction(Command):
    pass


class AcceptShorterRequest(Command):
    accepted_count: Annotated[int, Field(strict=True, ge=1, le=20)]

