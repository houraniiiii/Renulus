"""Generated practice inputs, deliberately separate from reviewed bank inputs."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .contracts import Command


class GenerateRequest(Command):
    prompt: str = Field(min_length=1, max_length=12000)
    count: int = Field(default=3, ge=1, le=5, strict=True)
    topic_id: str | None = Field(default=None, min_length=1, max_length=128)
    context: Literal["study", "temporary", "unclassified"] = "unclassified"
    case_handoff_id: str | None = Field(default=None, min_length=1, max_length=128)


class GeneratedOption(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=2000)
    rationale: str | None = Field(default=None, max_length=3000)


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    stem: str = Field(min_length=1, max_length=6000)
    options: list[GeneratedOption] = Field(min_length=2, max_length=6)
    correct_option_id: str = Field(min_length=1, max_length=32)
    explanation: str = Field(min_length=1, max_length=6000)
    hint: str | None = Field(default=None, max_length=1600)
    source_indices: list[int] = Field(default_factory=list, max_length=5)

    @field_validator("source_indices")
    @classmethod
    def unique_indices(cls, values):
        if len(set(values)) != len(values) or any(value < 0 or value > 4 for value in values):
            raise ValueError("Use unique supplied evidence indices")
        return values

    @model_validator(mode="after")
    def usable_key(self):
        ids = [option.id for option in self.options]
        if len(ids) != len(set(ids)) or self.correct_option_id not in ids:
            raise ValueError("A generated key must identify one unique supplied option")
        return self


class GeneratedBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[GeneratedQuestion] = Field(min_length=1, max_length=5)


class HandoffGuard(BaseModel):
    """Structural consumer of Cases HandoffCase; no raw text crosses the API."""
    revision: int
    target: Literal["generated-practice"] = "generated-practice"
    question: str = ""
