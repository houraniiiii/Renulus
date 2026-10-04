# SPDX-License-Identifier: MIT
"""Public case inputs. Retention and context scope are never caller inputs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class StartCase(Input):
    kind: Literal["daily", "teaching"] = "daily"
    title: str = Field(default="Daily case", min_length=1, max_length=120)
    text: str = Field(default="", max_length=50000)
    teaching_case_id: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def appropriate_input(self):
        if self.kind == "daily" and (not self.text or self.teaching_case_id):
            raise ValueError("Daily cases require text and cannot select teaching material")
        if self.kind == "teaching" and (not self.teaching_case_id or self.text):
            raise ValueError("Teaching cases require an installed content ID")
        return self


class RevisionInput(Input):
    revision: int = Field(ge=1)


class EditCase(RevisionInput):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    text: str | None = Field(default=None, min_length=1, max_length=50000)

    @model_validator(mode="after")
    def has_change(self):
        if self.title is None and self.text is None:
            raise ValueError("Supply the title or case text")
        return self


class DiscussCase(RevisionInput):
    message: str = Field(min_length=1, max_length=12000)
    request_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")


class HandoffCase(RevisionInput):
    target: Literal["explain", "generated-practice"]
    question: str = Field(default="", max_length=12000)


class AttachmentInput(RevisionInput):
    # Deliberately no path, URI, base64 or byte input until volatile processing is proved.
    kind: Literal["image", "pdf"]
