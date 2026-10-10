# SPDX-License-Identifier: MIT
"""New chat intent never supplies retention or runtime context scope."""
from typing import Literal

from pydantic import Field, model_validator

from renulus.design_c_contracts import (Contract, CreateConversation, Identifier,
    Revision, ContentReference)


class NewConversation(CreateConversation):
    topic_id: Identifier | None = None
    teaching_style: Literal["direct", "guided"] = "direct"
    text: str = Field(default="", max_length=50000)
    teaching_case_id: Identifier | None = None

    @model_validator(mode="after")
    def correct_owner(self):
        if self.kind == "learning" and (self.text or self.teaching_case_id):
            raise ValueError("Case material belongs to the Case owner")
        if self.teaching_case_id and self.text:
            raise ValueError("Teaching material is pinned from its installed content ID")
        return self


class Mutation(Contract):
    expected_revision: Revision


class Rename(Mutation):
    title: str = Field(min_length=1, max_length=120)


class ProjectMove(Mutation):
    project_id: Identifier | None = None


class Send(Mutation):
    text: str = Field(min_length=1, max_length=16000)
    request_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    teaching_style: Literal["direct", "guided"] = "direct"
    topic_id: Identifier | None = None
    model: str | None = Field(default=None, max_length=128)
    freshness: bool | None = None
    content_refs: tuple[ContentReference, ...] = Field(default=(), max_length=20)
