# SPDX-License-Identifier: MIT
"""Whole-attempt requests. Legacy quiz/answer models keep their old meanings."""
from typing import Annotated, Literal

from pydantic import Field, model_validator

from renulus.design_c_contracts import Contract, DraftAnswer, Identifier, TestVersionIdentity

Revision = Annotated[int, Field(ge=0, strict=True)]


class SetupTiming(Contract):
    kind: Literal["untimed", "timed"] = "untimed"
    duration_seconds: Annotated[int, Field(ge=1, le=86400, strict=True)] | None = None

    @model_validator(mode="after")
    def duration_matches_kind(self):
        if (self.kind == "timed") != (self.duration_seconds is not None):
            raise ValueError("Only timed setup has a duration")
        return self


class StartAttempt(Contract):
    version: TestVersionIdentity
    mode: Literal["study", "test"] = "study"
    timing: SetupTiming = Field(default_factory=SetupTiming)


class DraftState(Contract):
    position: Annotated[int, Field(ge=0, le=49, strict=True)]
    answers: tuple[DraftAnswer, ...] = Field(max_length=50)

    @model_validator(mode="after")
    def unique_items(self):
        if len({answer.item_id for answer in self.answers}) != len(self.answers):
            raise ValueError("Draft items must be unique")
        return self


class SaveDraft(DraftState):
    expected_revision: Revision


class ItemRequest(Contract):
    expected_revision: Revision
    item_id: Identifier


class CommitAnswer(ItemRequest):
    option_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_options(self):
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError("Choices must be unique")
        return self


class HelpRequest(ItemRequest):
    kind: Literal["hint", "sources", "notes", "chat"]
    expected_policy_revision: Revision


class SubmitAttempt(Contract):
    expected_draft_revision: Revision
    latest_draft: DraftState | None = None


class Transition(Contract):
    expected_revision: Revision


class QuestionReport(Contract):
    item_id: Identifier
    report_text: Annotated[str, Field(min_length=1, max_length=2000)]
