# SPDX-License-Identifier: MIT
"""Strict Home preferences and all-or-nothing daily suggestion output."""
from datetime import date
from typing import Annotated
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class HomeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def plain_text(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError("Use plain text without control characters")
    return value


DoctorName = Annotated[str, Field(strict=True, max_length=80)]
Prompt = Annotated[str, Field(strict=True, min_length=1, max_length=400)]


class _Named(HomeModel):
    doctor_name: DoctorName | None = None

    @field_validator("doctor_name")
    @classmethod
    def name(cls, value):
        if value is None:
            return None
        return plain_text(value) or None


class HomePreferences(_Named):
    revision: int = Field(default=1, strict=True, ge=1)


class NameUpdate(_Named):
    expected_revision: int = Field(strict=True, ge=1)


FivePrompts = Annotated[tuple[Prompt, ...], Field(min_length=5, max_length=5)]


class SuggestionBundle(HomeModel):
    explain: FivePrompts
    case: FivePrompts
    practice: FivePrompts

    @field_validator("explain", "case", "practice")
    @classmethod
    def clean_prompts(cls, values):
        cleaned = tuple(plain_text(value) for value in values)
        if any(not value for value in cleaned):
            raise ValueError("Suggestions cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def distinct_prompts(self):
        values = self.explain + self.case + self.practice
        if len({" ".join(unicodedata.normalize("NFKC", value).casefold().split())
                for value in values}) != 15:
            raise ValueError("The whole daily bundle must contain fifteen distinct prompts")
        return self


class DailyCache(HomeModel):
    day: date
    timezone: Annotated[str, Field(strict=True, min_length=1, max_length=100)]
    bundle: SuggestionBundle
    job_id: Annotated[str, Field(strict=True, min_length=1, max_length=128)]
    context_epoch: int = Field(strict=True, ge=0)
    settings_revision: int = Field(strict=True, ge=1)
    policy_revision: int = Field(strict=True, ge=1)
    inputs: tuple[dict, ...] = Field(default=(), max_length=100)
