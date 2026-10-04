"""Public request contracts. Scope and scoring policy are application-owned."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    idempotency_key: str = Field(min_length=8, max_length=128)


class Selector(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    domain_ids: list[str] = Field(default_factory=list, max_length=40)
    topic_ids: list[str] = Field(default_factory=list, max_length=100)
    track: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("domain_ids", "topic_ids")
    @classmethod
    def clean_ids(cls, values):
        if any(not value or len(value) > 128 for value in values):
            raise ValueError("Use nonempty content identifiers")
        return sorted(set(values))


class StartRequest(Command):
    mode: Literal["reviewed", "generated"] = "reviewed"
    count: int = Field(default=10, ge=1, le=50, strict=True)
    selector: Selector = Field(default_factory=Selector)


class AnswerRequest(Command):
    item_id: str = Field(min_length=1, max_length=128)
    option_ids: list[str] = Field(min_length=1, max_length=20)

    @field_validator("option_ids")
    @classmethod
    def unique_options(cls, values):
        if len(set(values)) != len(values) or any(not value or len(value) > 128 for value in values):
            raise ValueError("Submit each selected option once")
        return sorted(values)


class HelpRequest(Command):
    item_id: str = Field(min_length=1, max_length=128)
    kind: Literal["hint", "sources"] = "hint"
