# SPDX-License-Identifier: MIT
"""Safe opt-in preferences and private scheduler metadata; no learner payloads."""
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from renulus.design_c_contracts import Identifier


class NightlyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


LocalTime = Annotated[str, Field(strict=True, pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")]
Revision = Annotated[int, Field(strict=True, ge=1)]
ErrorCode = Annotated[str, Field(strict=True, pattern=r"^[a-z][a-z0-9_]{0,79}$")]
Token = Annotated[str, Field(strict=True, pattern=r"^nightly_[a-f0-9]{32}$")]


class _Settings(NightlyModel):
    enabled: bool = Field(default=False, strict=True)
    local_time: LocalTime = "22:00"
    question_count: int = Field(default=5, strict=True)

    @field_validator("question_count")
    @classmethod
    def allowed_counts(cls, value):
        if value not in (5, 10, 20):
            raise ValueError("Choose five, ten or twenty questions")
        return value


class NightlyPreferences(_Settings):
    revision: Revision = 1


class PreferencesUpdate(_Settings):
    expected_revision: Revision


class NightlySchedule(NightlyModel):
    """Trusted generation metadata; not accepted from the renderer."""
    day: date
    timezone: Annotated[str, Field(strict=True, min_length=1, max_length=100)]
    preferences_revision: Revision
    home_settings_revision: Revision
    eligibility_token: Token


class NightlyState(NightlyModel):
    schema_version: Literal["nightly-state/1"] = "nightly-state/1"
    context_epoch: int = Field(strict=True, ge=0)
    preferences_revision: Revision
    eligibility_token: Token
    timezone: Annotated[str, Field(strict=True, min_length=1, max_length=100)]
    not_before: datetime
    last_claimed_day: date | None = None
    last_key: Annotated[str, Field(strict=True, pattern=r"^nightly:[0-9]{4}-[0-9]{2}-[0-9]{2}$")] | None = None
    latest_job_id: Identifier | None = None
    error_code: ErrorCode | None = None

    @field_validator("not_before")
    @classmethod
    def aware_boundary(cls, value):
        if value.utcoffset() is None:
            raise ValueError("Eligibility requires an aware local time")
        return value


class PreferenceReceipt(NightlyModel):
    key: Annotated[str, Field(strict=True, min_length=8, max_length=128)]
    request_hash: Annotated[str, Field(strict=True, pattern=r"^[a-f0-9]{64}$")]
    result: NightlyPreferences


class NightlyCommands(NightlyModel):
    receipts: tuple[PreferenceReceipt, ...] = Field(default=(), max_length=128)
